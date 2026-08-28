from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.config import get_settings
from app.db import session_factory
from app.deps import get_calle
from app.models.schemas import Healthz
from app.services.redis_client import ping_redis

router = APIRouter()


def _db_up() -> bool:
    try:
        SessionLocal = session_factory()
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/healthz", response_model=Healthz)
def healthz() -> Healthz:
    pg = "up" if _db_up() else "down"
    rd = "up" if ping_redis() else "down"
    calle = "up" if get_calle().ping() else "down"
    status = "ok" if pg == "up" and rd == "up" and calle == "up" else "degraded"
    return Healthz(status=status, postgres=pg, redis=rd, calle=calle, mode=get_settings().calle_mode)


@router.get("/readyz")
def readyz() -> dict:
    """Kubernetes-style readiness: 200 only when the database answers, else 503."""
    if not _db_up():
        raise HTTPException(status_code=503, detail="database unavailable")
    return {"status": "ready"}
