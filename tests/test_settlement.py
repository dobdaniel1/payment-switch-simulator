import csv
import io
from datetime import timedelta


def _rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_close_batch_totals(client, send):
    send(amount=10000)
    send(amount=2500)
    send(type="refund", amount=1500)
    send(amount=10051)  # declined, excluded
    reversed_txn = send(amount=7000).json()
    client.post(f"/v1/transactions/{reversed_txn['id']}/reversal")

    res = client.post("/v1/settlement/batches", json={})
    assert res.status_code == 201
    batch = res.json()
    assert batch["transaction_count"] == 3
    assert batch["totals"] == {"566": {"purchase": 12500, "refund": 1500, "net": 11000}}
    assert client.get(f"/v1/settlement/batches/{batch['id']}").json() == batch


def test_totals_per_currency(client, send):
    send(amount=1000)
    send(amount=300, currency="840")
    totals = client.post("/v1/settlement/batches").json()["totals"]
    assert totals["566"]["net"] == 1000
    assert totals["840"]["net"] == 300


def test_nothing_to_settle(client, send):
    assert client.post("/v1/settlement/batches", json={}).status_code == 409
    send()
    client.post("/v1/settlement/batches", json={})
    assert client.post("/v1/settlement/batches", json={}).status_code == 409


def test_batch_by_business_date(client, send, clock):
    send()
    clock.now += timedelta(days=1)
    res = client.post("/v1/settlement/batches", json={"business_date": "2026-11-11"})
    assert res.status_code == 201
    assert res.json()["business_date"] == "2026-11-11"


def test_settlement_file(client, send):
    t = send().json()
    batch = client.post("/v1/settlement/batches", json={}).json()
    res = client.get(f"/v1/settlement/batches/{batch['id']}/file")
    assert res.headers["content-type"].startswith("text/csv")
    (row,) = _rows(res.text)
    assert row["rrn"] == t["rrn"]
    assert row["amount"] == "10000"
    assert row["pan_masked"] == "411111******1111"


def test_unknown_batch(client):
    assert client.get("/v1/settlement/batches/nope").status_code == 404
    assert client.get("/v1/settlement/batches/nope/file").status_code == 404


def _reconcile(client, batch_id, body):
    return client.post(
        f"/v1/settlement/batches/{batch_id}/reconcile",
        content=body,
        headers={"Content-Type": "text/csv"},
    )


def _batch_with(client, send, n):
    txns = [send(amount=1000 * (i + 1)).json() for i in range(n)]
    return client.post("/v1/settlement/batches", json={}).json()["id"], txns


def test_reconcile_balanced(client, send):
    batch_id, _ = _batch_with(client, send, 3)
    host_file = client.get(f"/v1/settlement/batches/{batch_id}/file").text
    report = _reconcile(client, batch_id, host_file).json()
    assert report["balanced"] is True
    assert len(report["matched"]) == 3


def test_reconcile_exceptions(client, send):
    batch_id, txns = _batch_with(client, send, 4)
    a, b, c, d = (t["rrn"] for t in txns)
    host_file = "rrn,amount\n" + "\n".join(
        [f"{a},1000", f"{b},2001", f"{d},4000", f"{d},4000", "999999999999,500"]
    )
    report = _reconcile(client, batch_id, host_file).json()
    assert report["balanced"] is False
    assert report["matched"] == sorted([a, d])
    assert report["amount_mismatch"] == [{"rrn": b, "switch_amount": 2000, "host_amount": 2001}]
    assert report["missing_in_host"] == [c]
    assert report["missing_in_switch"] == ["999999999999"]
    assert report["duplicates_in_host"] == [d]


def test_reconcile_bad_file(client, send):
    batch_id, _ = _batch_with(client, send, 1)
    assert _reconcile(client, batch_id, "id,value\n1,2").status_code == 422
    assert _reconcile(client, batch_id, "rrn,amount\n123,abc").status_code == 422
    assert _reconcile(client, "nope", "rrn,amount\n").status_code == 404
