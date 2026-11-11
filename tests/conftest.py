from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_clock
from app.main import create_app

NOW = datetime(2026, 11, 11, 9, 30, tzinfo=UTC)

VISA = "4111111111111111"
MASTERCARD = "5555555555554444"


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def client(clock):
    app = create_app("sqlite://")
    app.dependency_overrides[get_clock] = lambda: clock
    with TestClient(app) as c:
        yield c
    app.state.db.engine.dispose()


@pytest.fixture
def send(client):
    counter = iter(range(1, 1_000_000))

    def _send(**overrides):
        body = {
            "type": "purchase",
            "pan": VISA,
            "expiry": "2812",
            "amount": 10000,
            "currency": "566",
            "stan": f"{next(counter):06d}",
            "terminal_id": "TERM0001",
            "merchant_id": "MERCHANT0000001",
        } | overrides
        return client.post("/v1/transactions", json=body)

    return _send


@pytest.fixture
def set_host(client):
    def _set(host_id, status):
        assert client.patch(f"/v1/hosts/{host_id}", json={"status": status}).status_code == 200

    return _set
