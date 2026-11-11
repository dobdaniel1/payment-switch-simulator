from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

APPROVED = "APPROVED"
DECLINED = "DECLINED"
REVERSED = "REVERSED"
REVERSAL_PENDING = "REVERSAL_PENDING"


class Host(Base):
    __tablename__ = "hosts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="up")


class Route(Base):
    __tablename__ = "routes"

    prefix: Mapped[str] = mapped_column(String(11), primary_key=True)
    primary_host_id: Mapped[str] = mapped_column(ForeignKey("hosts.id"))
    fallback_host_id: Mapped[str | None] = mapped_column(ForeignKey("hosts.id"), nullable=True)


class SettlementBatch(Base):
    __tablename__ = "settlement_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    business_date: Mapped[date] = mapped_column(Date)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    transaction_count: Mapped[int]
    totals: Mapped[dict] = mapped_column(JSON)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (UniqueConstraint("terminal_id", "stan", "business_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    business_date: Mapped[date] = mapped_column(Date, index=True)
    type: Mapped[str] = mapped_column(String(16))
    stan: Mapped[str] = mapped_column(String(6))
    rrn: Mapped[str] = mapped_column(String(12), unique=True)
    terminal_id: Mapped[str] = mapped_column(String(8))
    merchant_id: Mapped[str] = mapped_column(String(15))
    pan_masked: Mapped[str] = mapped_column(String(19))
    pan_hash: Mapped[str] = mapped_column(String(64), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    host_id: Mapped[str | None] = mapped_column(ForeignKey("hosts.id"), nullable=True)
    response_code: Mapped[str] = mapped_column(String(2))
    auth_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    attempts: Mapped[list] = mapped_column(JSON, default=list)
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("settlement_batches.id"), nullable=True, index=True
    )
