from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from .api import network, settlement, transactions
from .api.deps import get_session
from .config import settings
from .db import Base, Database
from .errors import Conflict, InvalidInput, NotFound
from .seed import reset, seed

STATIC = Path(__file__).parent / "static"


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(
        title="Payment Switch Simulator",
        version="0.1.0",
        description="Routes card transactions to simulated issuer hosts, with failover, "
        "reversals, settlement and reconciliation.",
    )
    db = Database(database_url or settings.database_url)
    Base.metadata.create_all(db.engine)
    with db.sessions() as session:
        seed(session)
    app.state.db = db

    for exc_type, code in ((NotFound, 404), (Conflict, 409), (InvalidInput, 422)):
        app.add_exception_handler(
            exc_type,
            lambda _req, exc, code=code: JSONResponse({"detail": str(exc)}, status_code=code),
        )

    app.include_router(transactions.router)
    app.include_router(network.router)
    app.include_router(settlement.router)

    @app.get("/health", tags=["ops"])
    def health():
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(STATIC / "dashboard.html")

    if settings.enable_admin:

        @app.post("/v1/admin/reset", tags=["ops"], status_code=204)
        def reset_data(session: Annotated[Session, Depends(get_session)]):
            """Clear all data and restore default hosts and routes. For test environments."""
            reset(session)

    @app.middleware("http")
    async def no_cache(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    return app
