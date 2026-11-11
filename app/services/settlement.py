import csv
import io
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import Conflict, InvalidInput, NotFound
from ..models import APPROVED, SettlementBatch, Transaction
from ..schemas import AmountMismatch, ReconciliationReport

FILE_COLUMNS = [
    "rrn",
    "stan",
    "terminal_id",
    "merchant_id",
    "pan_masked",
    "type",
    "amount",
    "currency",
    "auth_code",
    "host_id",
]


def close_batch(session: Session, business_date: date, now: datetime) -> SettlementBatch:
    """Settle every approved, unsettled transaction for the day. Reversed ones are excluded."""
    txns = list(
        session.scalars(
            select(Transaction).where(
                Transaction.status == APPROVED,
                Transaction.batch_id.is_(None),
                Transaction.business_date == business_date,
            )
        )
    )
    if not txns:
        raise Conflict(f"Nothing to settle for {business_date}")

    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"purchase": 0, "refund": 0})
    for t in txns:
        totals[t.currency][t.type] += t.amount
    for t in totals.values():
        t["net"] = t["purchase"] - t["refund"]

    batch = SettlementBatch(
        id=str(uuid.uuid4()),
        business_date=business_date,
        closed_at=now,
        transaction_count=len(txns),
        totals=dict(totals),
    )
    session.add(batch)
    session.flush()
    for t in txns:
        t.batch_id = batch.id
    session.commit()
    return batch


def get_batch(session: Session, batch_id: str) -> SettlementBatch:
    batch = session.get(SettlementBatch, batch_id)
    if batch is None:
        raise NotFound(f"Batch {batch_id} not found")
    return batch


def _batch_transactions(session: Session, batch_id: str) -> list[Transaction]:
    get_batch(session, batch_id)
    return list(
        session.scalars(
            select(Transaction).where(Transaction.batch_id == batch_id).order_by(Transaction.rrn)
        )
    )


def settlement_file(session: Session, batch_id: str) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(FILE_COLUMNS)
    for t in _batch_transactions(session, batch_id):
        writer.writerow([getattr(t, c) or "" for c in FILE_COLUMNS])
    return out.getvalue()


def reconcile(session: Session, batch_id: str, host_csv: str) -> ReconciliationReport:
    """Compare the switch's batch with a host settlement file containing rrn and amount columns."""
    reader = csv.DictReader(io.StringIO(host_csv))
    if not reader.fieldnames or not {"rrn", "amount"} <= set(reader.fieldnames):
        raise InvalidInput("Host file must have a header with rrn and amount columns")

    host_rows: dict[str, int] = {}
    counts: Counter[str] = Counter()
    for line_no, row in enumerate(reader, start=2):
        rrn = (row["rrn"] or "").strip()
        try:
            amount = int(row["amount"])
        except (TypeError, ValueError):
            raise InvalidInput(f"Line {line_no}: amount must be an integer") from None
        counts[rrn] += 1
        host_rows.setdefault(rrn, amount)

    switch_rows = {t.rrn: t.amount for t in _batch_transactions(session, batch_id)}
    matched, mismatched = [], []
    for rrn, amount in switch_rows.items():
        if rrn in host_rows:
            if host_rows[rrn] == amount:
                matched.append(rrn)
            else:
                mismatched.append(
                    AmountMismatch(rrn=rrn, switch_amount=amount, host_amount=host_rows[rrn])
                )

    missing_in_host = sorted(set(switch_rows) - set(host_rows))
    missing_in_switch = sorted(set(host_rows) - set(switch_rows))
    duplicates = sorted(rrn for rrn, n in counts.items() if n > 1)
    return ReconciliationReport(
        batch_id=batch_id,
        balanced=not (mismatched or missing_in_host or missing_in_switch or duplicates),
        matched=sorted(matched),
        amount_mismatch=mismatched,
        missing_in_host=missing_in_host,
        missing_in_switch=missing_in_switch,
        duplicates_in_host=duplicates,
    )
