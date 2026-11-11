from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Transaction
from ..schemas import AuthorizationRequest, RetryResult, TransactionOut
from ..services import authorization
from .deps import get_clock, get_session

router = APIRouter(prefix="/v1", tags=["transactions"])
SessionDep = Annotated[Session, Depends(get_session)]
ClockDep = Annotated[Callable[[], datetime], Depends(get_clock)]


@router.post("/transactions", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    req: AuthorizationRequest, response: Response, session: SessionDep, clock: ClockDep
):
    """Authorize a purchase or refund. A repeated terminal and STAN on the same day returns
    the original result with duplicate=true instead of charging twice."""
    txn, duplicate = authorization.authorize(session, req, clock())
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return TransactionOut.model_validate(txn).model_copy(update={"duplicate": duplicate})


@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    session: SessionDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
):
    query = select(Transaction).order_by(Transaction.created_at.desc()).limit(limit)
    if status_filter:
        query = query.where(Transaction.status == status_filter.upper())
    return session.scalars(query).all()


@router.get("/transactions/{txn_id}", response_model=TransactionOut)
def get_transaction(txn_id: str, session: SessionDep):
    return authorization.get(session, txn_id)


@router.post("/transactions/{txn_id}/reversal", response_model=TransactionOut)
def reverse_transaction(txn_id: str, session: SessionDep, clock: ClockDep):
    return authorization.reverse(session, txn_id, clock())


@router.post("/reversals/retry", response_model=RetryResult)
def retry_reversals(session: SessionDep):
    delivered, pending = authorization.retry_pending_reversals(session)
    return RetryResult(delivered=delivered, still_pending=pending)
