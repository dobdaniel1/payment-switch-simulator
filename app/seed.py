from sqlalchemy import delete
from sqlalchemy.orm import Session

from .models import Host, Route, SettlementBatch, Transaction

HOSTS = [
    ("host-a", "Issuer host A"),
    ("host-b", "Issuer host B"),
    ("host-c", "Backup processor"),
    ("host-d", "Domestic scheme host"),
]

# prefix, primary, fallback. Longest prefix wins.
ROUTES = [
    ("4", "host-a", "host-c"),
    ("51", "host-b", "host-c"),
    ("52", "host-b", "host-c"),
    ("53", "host-b", "host-c"),
    ("54", "host-b", "host-c"),
    ("55", "host-b", "host-c"),
    ("2", "host-b", "host-c"),
    ("5061", "host-d", None),
]


def seed(session: Session) -> None:
    if session.get(Host, "host-a"):
        return
    session.add_all(Host(id=i, name=n, status="up") for i, n in HOSTS)
    session.flush()
    session.add_all(Route(prefix=p, primary_host_id=a, fallback_host_id=b) for p, a, b in ROUTES)
    session.commit()


def reset(session: Session) -> None:
    for model in (Transaction, SettlementBatch, Route, Host):
        session.execute(delete(model))
    session.commit()
    seed(session)
