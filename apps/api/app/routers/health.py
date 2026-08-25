from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings
from app.db import session_factory
from app.deps import get_calle
from app.models.schemas import Healthz
from app.services.redis_client import ping_redis

router = APIRouter()


@router.get("/healthz", response_model=Healthz)
def healthz() -> Healthz:
    pg = "down"
    try:
        SessionLocal = session_factory()
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        pg = "up"
    except Exception:
        pg = "down"
    rd = "up" if ping_redis() else "down"
    calle = "up" if get_calle().ping() else "down"
    status = "ok" if pg == "up" and rd == "up" and calle == "up" else "degraded"
    mode = "fixture" if get_settings().use_fixtures else "live"
    return Healthz(status=status, postgres=pg, redis=rd, calle=calle, mode=mode)
