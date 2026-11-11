def test_reverse_approved(client, send):
    t = send().json()
    r = client.post(f"/v1/transactions/{t['id']}/reversal")
    assert r.status_code == 200
    assert r.json()["status"] == "REVERSED"
    assert r.json()["reversed_at"] is not None


def test_reversal_is_idempotent(client, send):
    t = send().json()
    first = client.post(f"/v1/transactions/{t['id']}/reversal").json()
    second = client.post(f"/v1/transactions/{t['id']}/reversal").json()
    assert first == second


def test_cannot_reverse_declined(client, send):
    t = send(amount=10051).json()
    r = client.post(f"/v1/transactions/{t['id']}/reversal")
    assert r.status_code == 409
    assert "approved" in r.json()["detail"]


def test_cannot_reverse_settled(client, send):
    t = send().json()
    client.post("/v1/settlement/batches", json={})
    assert client.post(f"/v1/transactions/{t['id']}/reversal").status_code == 409


def test_reverse_unknown(client):
    assert client.post("/v1/transactions/nope/reversal").status_code == 404


def test_store_and_forward_when_host_down(client, send, set_host):
    t = send().json()
    set_host("host-a", "down")
    assert (
        client.post(f"/v1/transactions/{t['id']}/reversal").json()["status"] == "REVERSAL_PENDING"
    )

    retry = client.post("/v1/reversals/retry").json()
    assert retry == {"delivered": [], "still_pending": [t["id"]]}

    set_host("host-a", "up")
    retry = client.post("/v1/reversals/retry").json()
    assert retry == {"delivered": [t["id"]], "still_pending": []}
    assert client.get(f"/v1/transactions/{t['id']}").json()["status"] == "REVERSED"
