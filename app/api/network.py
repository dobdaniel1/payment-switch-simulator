from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..errors import NotFound
from ..models import Host, Route
from ..schemas import HostOut, HostUpdate, RouteOut
from .deps import get_session

router = APIRouter(prefix="/v1", tags=["network"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/hosts", response_model=list[HostOut])
def list_hosts(session: SessionDep):
    return session.scalars(select(Host).order_by(Host.id)).all()


@router.patch("/hosts/{host_id}", response_model=HostOut)
def update_host(host_id: str, update: HostUpdate, session: SessionDep):
    """Set a host up, down or timeout to exercise failover and reversal paths."""
    host = session.get(Host, host_id)
    if host is None:
        raise NotFound(f"Host {host_id} not found")
    host.status = update.status
    session.commit()
    return host


@router.get("/routes", response_model=list[RouteOut])
def list_routes(session: SessionDep):
    return session.scalars(select(Route).order_by(Route.prefix)).all()
