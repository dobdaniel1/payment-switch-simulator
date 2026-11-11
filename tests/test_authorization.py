import pytest
from conftest import MASTERCARD


def test_approved_purchase(send):
    res = send()
    assert res.status_code == 201
    t = res.json()
    assert t["status"] == "APPROVED"
    assert t["response_code"] == "00"
    assert t["response_message"] == "Approved"
    assert t["host_id"] == "host-a"
    assert len(t["auth_code"]) == 6
    assert len(t["rrn"]) == 12 and t["rrn"].isdigit()
    assert t["pan_masked"] == "411111******1111"
    assert t["attempts"] == [{"host": "host-a", "result": "00"}]


def test_pan_is_never_returned_or_stored_in_clear(client, send):
    send()
    text = client.get("/v1/transactions").text
    assert "4111111111111111" not in text


@pytest.mark.parametrize(
    "pan,host",
    [
        ("4111111111111111", "host-a"),
        (MASTERCARD, "host-b"),
        ("2223000048400011", "host-b"),
        ("5061000000000000007", "host-d"),
    ],
)
def test_bin_routing(send, pan, host):
    assert send(pan=pan).json()["host_id"] == host


def test_longest_prefix_wins(client):
    routes = {r["prefix"]: r for r in client.get("/v1/routes").json()}
    assert routes["5061"]["primary_host_id"] == "host-d"
    assert routes["4"]["fallback_host_id"] == "host-c"


@pytest.mark.parametrize(
    "amount,code",
    [(10005, "05"), (10051, "51"), (10061, "61"), (10091, "91"), (10050, "00")],
)
def test_issuer_decline_by_test_amount(send, amount, code):
    t = send(amount=amount).json()
    assert t["response_code"] == code
    assert t["status"] == ("APPROVED" if code == "00" else "DECLINED")


def test_refund_ignores_decline_amounts(send):
    assert send(type="refund", amount=10051).json()["response_code"] == "00"


def test_expired_card(send):
    assert send(expiry="2610").json()["response_code"] == "54"


def test_card_valid_through_expiry_month(send):
    assert send(expiry="2611").json()["response_code"] == "00"


def test_luhn_failure_declined_without_host(send):
    t = send(pan="4111111111111112").json()
    assert t["response_code"] == "14"
    assert t["host_id"] is None and t["attempts"] == []


def test_no_route(send):
    t = send(pan="6011000990139424").json()
    assert t["response_code"] == "92"
    assert t["response_message"] == "No route to issuer"


def test_failover_when_primary_down(send, set_host):
    set_host("host-a", "down")
    t = send().json()
    assert t["status"] == "APPROVED"
    assert t["host_id"] == "host-c"
    assert t["attempts"][0] == {"host": "host-a", "result": "unavailable"}


def test_timeout_sends_reversal_then_fails_over(send, set_host):
    set_host("host-a", "timeout")
    t = send().json()
    assert t["host_id"] == "host-c"
    assert t["attempts"][0] == {"host": "host-a", "result": "timeout", "reversal_sent": True}


def test_all_hosts_unavailable(send, set_host):
    set_host("host-a", "down")
    set_host("host-c", "timeout")
    t = send().json()
    assert t["response_code"] == "91"
    assert t["status"] == "DECLINED"
    assert [a["result"] for a in t["attempts"]] == ["unavailable", "timeout"]


def test_route_without_fallback(send, set_host):
    set_host("host-d", "down")
    t = send(pan="5061000000000000007").json()
    assert t["response_code"] == "91"
    assert len(t["attempts"]) == 1


def test_duplicate_returns_original(send):
    first = send(stan="000777")
    second = send(stan="000777", amount=99999)
    assert first.status_code == 201 and second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["amount"] == 10000


def test_same_stan_next_day_is_new(send, clock):
    first = send(stan="000777").json()
    clock.now = clock.now.replace(day=12)
    second = send(stan="000777")
    assert second.status_code == 201
    assert second.json()["id"] != first["id"]


def test_same_stan_other_terminal_is_new(send):
    send(stan="000777")
    assert send(stan="000777", terminal_id="TERM0002").status_code == 201


@pytest.mark.parametrize(
    "field,value",
    [
        ("pan", "41111"),
        ("pan", "4111x11111111111"),
        ("expiry", "2813"),
        ("amount", 0),
        ("amount", -5),
        ("stan", "12345"),
        ("terminal_id", "TERM01"),
        ("merchant_id", "SHORT"),
        ("currency", "NGN"),
        ("type", "cashback"),
    ],
)
def test_validation(send, field, value):
    assert send(**{field: value}).status_code == 422


def test_get_and_list(client, send):
    t = send().json()
    send(amount=10051)
    assert client.get(f"/v1/transactions/{t['id']}").json()["rrn"] == t["rrn"]
    assert len(client.get("/v1/transactions").json()) == 2
    declined = client.get("/v1/transactions", params={"status": "declined"}).json()
    assert [d["response_code"] for d in declined] == ["51"]
    assert client.get("/v1/transactions/nope").status_code == 404
