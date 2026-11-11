from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Route


def resolve(session: Session, pan: str) -> Route | None:
    """Longest matching BIN prefix wins."""
    matches = [r for r in session.scalars(select(Route)) if pan.startswith(r.prefix)]
    return max(matches, key=lambda r: len(r.prefix), default=None)
