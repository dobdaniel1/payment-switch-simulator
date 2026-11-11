from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ..schemas import BatchOut, BatchRequest, ReconciliationReport
from ..services import settlement
from .deps import get_clock, get_session

router = APIRouter(prefix="/v1/settlement", tags=["settlement"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.post("/batches", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
def close_batch(
    session: SessionDep,
    clock: Annotated[Callable[[], datetime], Depends(get_clock)],
    req: BatchRequest | None = None,
):
    now = clock()
    business_date = (req and req.business_date) or now.date()
    return settlement.close_batch(session, business_date, now)


@router.get("/batches/{batch_id}", response_model=BatchOut)
def get_batch(batch_id: str, session: SessionDep):
    return settlement.get_batch(session, batch_id)


@router.get("/batches/{batch_id}/file", response_class=PlainTextResponse)
def batch_file(batch_id: str, session: SessionDep):
    return PlainTextResponse(settlement.settlement_file(session, batch_id), media_type="text/csv")


@router.post("/batches/{batch_id}/reconcile", response_model=ReconciliationReport)
def reconcile(
    batch_id: str, session: SessionDep, host_file: Annotated[str, Body(media_type="text/csv")]
):
    """Upload the host's settlement CSV (needs rrn and amount columns)."""
    return settlement.reconcile(session, batch_id, host_file)
