from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.orm import Base

# Revision id of apps/api/alembic/versions/0001_initial_schema.py, the
# migration equivalent of the pre-Alembic create_all() schema.
INITIAL_REVISION = "0001"

# Arbitrary but fixed application-wide id for the Postgres advisory lock that
# serializes schema migrations. Replicas booting together queue on it instead
# of racing stamp/upgrade DDL against the same database.
MIGRATION_LOCK_KEY = 7_214_180_042_001

_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        url = settings.database_url
        connect_args = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, connect_args=connect_args, future=True)
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, future=True)
    return _engine


def init_db() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def _alembic_config() -> Config:
    api_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(api_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(api_root / "alembic"))
    return cfg


def run_migrations() -> None:
    """Bring the schema to the Alembic head, converging from any start state.

    Handles three cases: an empty database (full upgrade), a database built by
    create_all() before migrations existed (stamped as the initial revision,
    then upgraded), and a database already under Alembic (plain upgrade).
    Re-running after a crash or retry is a no-op once head is reached.

    The whole decision plus the DDL runs on one connection inside one
    transaction, under a Postgres advisory lock, so replicas booting at the
    same moment serialize: the first one migrates, the rest see head and
    no-op. The transactional lock releases itself on commit or crash.
    """
    engine = get_engine()
    cfg = _alembic_config()
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
        cfg.attributes["connection"] = conn
        inspector = inspect(conn)
        if inspector.has_table("tickets") and not inspector.has_table("alembic_version"):
            command.stamp(cfg, INITIAL_REVISION)
        command.upgrade(cfg, "head")


def prepare_database() -> None:
    """Ready the schema at startup: Alembic on Postgres, create_all elsewhere.

    SQLite stays on create_all so the offline test and local paths keep their
    speed and zero moving parts; the schemas are identical either way, which
    tests/test_migrations.py proves.
    """
    engine = get_engine()
    if engine.dialect.name == "postgresql":
        run_migrations()
    else:
        init_db()


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
    get_settings.cache_clear()


def session_factory():
    get_engine()
    return _SessionLocal


def get_session() -> Generator[Session, None, None]:
    SessionLocal = session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
