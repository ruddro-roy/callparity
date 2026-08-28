from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.orm import Base

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
    """Create ORM tables in place. SQLite/local and pytest use this path."""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def prepare_schema() -> None:
    """Postgres: Alembic upgrade (or stamp a complete pre-migration schema).

    SQLite and any other URL keep create_all so offline tests and the local
    seed path stay fast and do not require a migration runner.
    """
    from app.migrate import apply_migrations, uses_alembic

    if uses_alembic(get_settings().database_url):
        apply_migrations()
        return
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
