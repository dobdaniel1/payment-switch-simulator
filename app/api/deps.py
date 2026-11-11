from collections.abc import Callable, Iterator
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    yield from request.app.state.db.session()


def get_clock() -> Callable[[], datetime]:
    return lambda: datetime.now(UTC)
