from app.cards import is_expired, luhn_valid, mask_pan


def test_health_and_docs(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/openapi.json").json()["info"]["title"] == "Payment Switch Simulator"


def test_dashboard_served(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Switch Console" in res.text
    assert res.headers["cache-control"] == "no-store"


def test_hosts(client, set_host):
    hosts = client.get("/v1/hosts").json()
    assert [h["id"] for h in hosts] == ["host-a", "host-b", "host-c", "host-d"]
    set_host("host-b", "timeout")
    assert client.get("/v1/hosts").json()[1]["status"] == "timeout"
    assert client.patch("/v1/hosts/host-a", json={"status": "broken"}).status_code == 422
    assert client.patch("/v1/hosts/nope", json={"status": "up"}).status_code == 404


def test_admin_reset(client, send, set_host):
    send()
    set_host("host-a", "down")
    assert client.post("/v1/admin/reset").status_code == 204
    assert client.get("/v1/transactions").json() == []
    assert client.get("/v1/hosts").json()[0]["status"] == "up"


def test_card_helpers():
    assert luhn_valid("4111111111111111")
    assert luhn_valid("5555555555554444")
    assert not luhn_valid("4111111111111112")
    assert mask_pan("5061000000000000007") == "506100*********0007"
    from datetime import date

    assert is_expired("2610", date(2026, 11, 1))
    assert not is_expired("2611", date(2026, 11, 30))
