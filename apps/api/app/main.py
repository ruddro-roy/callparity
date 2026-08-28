import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import PlainTextResponse

from app.config import get_settings
from app.db import prepare_schema, session_factory
from app.logging_conf import configure_logging
from app.models.orm import TicketRow
from app.request_id import HEADER, RequestIdMiddleware, resolve_request_id
from app.routers import health, jobs, tickets
from app.services.jobs import reconcile_interrupted_jobs


def _maybe_seed() -> None:
    settings = get_settings()
    if not settings.seed_on_startup:
        return
    SessionLocal = session_factory()
    with SessionLocal() as session:
        empty = session.query(TicketRow).count() == 0
    if not empty:
        return
    candidates = [Path("/app/scripts")] + [
        parent / "scripts" for parent in Path(__file__).resolve().parents
    ]
    for scripts in candidates:
        if (scripts / "seed_demo_data.py").exists():
            sys.path.insert(0, str(scripts))
            break
    from seed_demo_data import seed  # type: ignore

    seed(SessionLocal())


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    prepare_schema()
    _maybe_seed()
    with session_factory()() as session:
        reconcile_interrupted_jobs(session)
    yield


app = FastAPI(title="CallParity API", version="0.2.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def _unhandled_error(request: Request, _exc: Exception) -> PlainTextResponse:
    request_id = resolve_request_id(getattr(request.state, "request_id", None))
    return PlainTextResponse(
        "Internal Server Error",
        status_code=500,
        headers={HEADER: request_id},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
# Last added runs first: request id wraps CORS so every response, including
# preflight, carries X-Request-ID and one access line.
app.add_middleware(RequestIdMiddleware)
app.include_router(health.router)
app.include_router(tickets.router)
app.include_router(jobs.router)


@app.get("/")
def root() -> dict:
    return {"service": "callparity-api", "use_fixtures": get_settings().use_fixtures}
