"""Simulated issuer hosts. Behaviour is driven by host status and test amounts."""

import hashlib
from datetime import date

from .cards import is_expired
from .models import Host

# Purchases whose minor units end in these values are declined with that code.
DECLINE_BY_MINOR_UNITS = {5: "05", 51: "51", 61: "61", 91: "91"}

HOST_STATUSES = ("up", "down", "timeout")


class HostUnavailable(Exception):
    pass


class HostTimeout(Exception):
    pass


def authorize(
    host: Host, *, txn_type: str, pan: str, expiry: str, amount: int, stan: str, today: date
) -> tuple[str, str | None]:
    if host.status == "down":
        raise HostUnavailable(host.id)
    if host.status == "timeout":
        raise HostTimeout(host.id)
    if is_expired(expiry, today):
        return "54", None
    if txn_type == "purchase" and (code := DECLINE_BY_MINOR_UNITS.get(amount % 100)):
        return code, None
    digest = hashlib.sha256(f"{host.id}{pan}{stan}{amount}".encode()).hexdigest()
    return "00", digest[:6].upper()


def deliver_reversal(host: Host) -> bool:
    """True if the host accepted the reversal. Unreachable hosts keep it queued."""
    return host.status == "up"
