import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects import sqlite
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import hosts
from ..cards import hash_pan, luhn_valid, mask_pan
from ..config import settings
from ..errors import Conflict, NotFound
from ..models import (
    APPROVED,
    DECLINED,
    REVERSAL_PENDING,
    REVERSED,
    RRN_SEQUENCE,
    Host,
    RrnCounter,
    Transaction,
)
from ..schemas import AuthorizationRequest
from .routing import resolve


def _next_sequence(session: Session) -> int:
    if session.get_bind().dialect.name == "postgresql":  # pragma: no cover (Docker and load tests)
        # No row lock, so concurrent authorizations never wait on each other.
        return session.execute(RRN_SEQUENCE.next_value()).scalar_one()
    return session.execute(
        sqlite.insert(RrnCounter)
        .values(name="rrn", value=1)
        .on_conflict_do_update(index_elements=["name"], set_={"value": RrnCounter.value + 1})
        .returning(RrnCounter.value)
    ).scalar_one()


def _next_rrn(session: Session, now: datetime) -> str:
    """YDDDHH plus the last 6 digits of a sequence, unique while an hour has under a million
    transactions. Random digits collided after a few thousand transactions an hour."""
    return f"{now:%y}"[-1] + f"{now:%j%H}" + f"{_next_sequence(session) % 1_000_000:06d}"


def _find_duplicate(session: Session, req: AuthorizationRequest, now: datetime):
    return session.scalar(
        select(Transaction).where(
            Transaction.terminal_id == req.terminal_id,
            Transaction.stan == req.stan,
            Transaction.business_date == now.date(),
        )
    )


def _send_to_hosts(session: Session, req: AuthorizationRequest, now: datetime):
    """Try the primary host then the fallback. Returns (code, auth_code, host_id, attempts)."""
    if not luhn_valid(req.pan):
        return "14", None, None, []
    route = resolve(session, req.pan)
    if route is None:
        return "92", None, None, []

    attempts = []
    for host_id in filter(None, (route.primary_host_id, route.fallback_host_id)):
        host = session.get(Host, host_id)
        try:
            code, auth = hosts.authorize(
                host,
                txn_type=req.type,
                pan=req.pan,
                expiry=req.expiry,
                amount=req.amount,
                stan=req.stan,
                today=now.date(),
            )
        except hosts.HostUnavailable:
            attempts.append({"host": host_id, "result": "unavailable"})
            continue
        except hosts.HostTimeout:
            # A late approval may still arrive at the issuer, so reverse before failing over.
            attempts.append({"host": host_id, "result": "timeout", "reversal_sent": True})
            continue
        attempts.append({"host": host_id, "result": code})
        return code, auth, host_id, attempts
    return "91", None, None, attempts


def authorize(
    session: Session, req: AuthorizationRequest, now: datetime
) -> tuple[Transaction, bool]:
    """Returns the transaction and whether it was a duplicate of an earlier request."""
    if existing := _find_duplicate(session, req, now):
        return existing, True

    code, auth, host_id, attempts = _send_to_hosts(session, req, now)
    txn = Transaction(
        id=str(uuid.uuid4()),
        created_at=now,
        business_date=now.date(),
        type=req.type,
        stan=req.stan,
        rrn=_next_rrn(session, now),
        terminal_id=req.terminal_id,
        merchant_id=req.merchant_id,
        pan_masked=mask_pan(req.pan),
        pan_hash=hash_pan(req.pan, settings.pan_hash_key),
        amount=req.amount,
        currency=req.currency,
        host_id=host_id,
        response_code=code,
        auth_code=auth,
        status=APPROVED if code == "00" else DECLINED,
        attempts=attempts,
    )
    session.add(txn)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # Lost a race with an identical request. Any other conflict is a real error.
        if existing := _find_duplicate(session, req, now):
            return existing, True
        raise
    return txn, False


def get(session: Session, txn_id: str) -> Transaction:
    txn = session.get(Transaction, txn_id)
    if txn is None:
        raise NotFound(f"Transaction {txn_id} not found")
    return txn


def reverse(session: Session, txn_id: str, now: datetime) -> Transaction:
    """Reverse an approved transaction. Repeating the call is safe."""
    txn = get(session, txn_id)
    if txn.status in (REVERSED, REVERSAL_PENDING):
        return txn
    if txn.status != APPROVED:
        raise Conflict(f"Only approved transactions can be reversed, status is {txn.status}")
    if txn.batch_id:
        raise Conflict("Transaction is already settled; raise a refund instead")

    txn.reversed_at = now
    delivered = hosts.deliver_reversal(session.get(Host, txn.host_id))
    txn.status = REVERSED if delivered else REVERSAL_PENDING
    session.commit()
    return txn


def retry_pending_reversals(session: Session) -> tuple[list[str], list[str]]:
    """Store and forward: resend queued reversals to hosts that are back up."""
    delivered, pending = [], []
    for txn in session.scalars(select(Transaction).where(Transaction.status == REVERSAL_PENDING)):
        if hosts.deliver_reversal(session.get(Host, txn.host_id)):
            txn.status = REVERSED
            delivered.append(txn.id)
        else:
            pending.append(txn.id)
    session.commit()
    return delivered, pending
