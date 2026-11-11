from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, computed_field

from .response_codes import message_for


def _as_utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes; everything is stored in UTC.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


class AuthorizationRequest(BaseModel):
    type: Literal["purchase", "refund"] = "purchase"
    pan: str = Field(pattern=r"^\d{12,19}$", examples=["4111111111111111"])
    expiry: str = Field(pattern=r"^\d{2}(0[1-9]|1[0-2])$", description="YYMM", examples=["2812"])
    amount: int = Field(gt=0, le=9_999_999_999, description="Minor units", examples=[10000])
    currency: str = Field("566", pattern=r"^\d{3}$", description="ISO 4217 numeric")
    stan: str = Field(pattern=r"^\d{6}$", examples=["000123"])
    terminal_id: str = Field(pattern=r"^[A-Za-z0-9]{8}$", examples=["TERM0001"])
    merchant_id: str = Field(pattern=r"^[A-Za-z0-9]{15}$", examples=["MERCHANT0000001"])


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: UtcDatetime
    business_date: date
    type: str
    stan: str
    rrn: str
    terminal_id: str
    merchant_id: str
    pan_masked: str
    amount: int
    currency: str
    host_id: str | None
    response_code: str
    auth_code: str | None
    status: str
    attempts: list[dict]
    reversed_at: UtcDatetime | None
    batch_id: str | None
    duplicate: bool = False

    @computed_field
    @property
    def response_message(self) -> str:
        return message_for(self.response_code)


class HostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: str


class HostUpdate(BaseModel):
    status: Literal["up", "down", "timeout"]


class RouteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prefix: str
    primary_host_id: str
    fallback_host_id: str | None


class BatchRequest(BaseModel):
    business_date: date | None = None


class BatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_date: date
    closed_at: UtcDatetime
    transaction_count: int
    totals: dict[str, dict[str, int]]


class AmountMismatch(BaseModel):
    rrn: str
    switch_amount: int
    host_amount: int


class ReconciliationReport(BaseModel):
    batch_id: str
    balanced: bool
    matched: list[str]
    amount_mismatch: list[AmountMismatch]
    missing_in_host: list[str]
    missing_in_switch: list[str]
    duplicates_in_host: list[str]


class RetryResult(BaseModel):
    delivered: list[str]
    still_pending: list[str]
