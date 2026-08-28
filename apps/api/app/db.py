from collections.abc import Generator
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models.orm import Base

_ALEMBIC_CONFIG_PATH = Path(__file__).resolve().parents[1] / "alembic.ini"

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
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
    if engine.dialect.name != "sqlite":
        raise RuntimeError("init_db() only supports SQLite; use Alembic for managed databases")
    Base.metadata.create_all(bind=engine)


def _include_managed_tables(_, name: str | None, type_: str, reflected: bool, __) -> bool:
    return type_ != "table" or not reflected or name in Base.metadata.tables


def _stamp_legacy_schema_if_compatible(connection: Connection, config: Config) -> bool:
    migration_context = MigrationContext.configure(connection)
    if migration_context.get_current_revision() is not None:
        return False

    managed_tables = set(inspect(connection).get_table_names()) & set(Base.metadata.tables)
    if not managed_tables:
        return False

    comparison_context = MigrationContext.configure(
        connection,
        opts={
            "compare_type": True,
            "include_object": _include_managed_tables,
        },
    )
    if compare_metadata(comparison_context, Base.metadata):
        raise RuntimeError(
            "database has an unversioned schema that does not match the application metadata"
        )

    command.stamp(config, "head")
    return True


def migrate_db() -> None:
    alembic_config = Config(str(_ALEMBIC_CONFIG_PATH))
    alembic_config.attributes["configure_logger"] = False
    with get_engine().begin() as connection:
        alembic_config.attributes["connection"] = connection
        if not _stamp_legacy_schema_if_compatible(connection, alembic_config):
            command.upgrade(alembic_config, "head")


def initialize_database() -> None:
    dialect = get_engine().dialect.name
    if dialect == "sqlite":
        init_db()
        return
    if dialect == "postgresql":
        migrate_db()
        return
    raise RuntimeError(f"unsupported database dialect: {dialect}")


def reset_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
    get_settings.cache_clear()


def session_factory() -> sessionmaker[Session]:
    get_engine()
    if _SessionLocal is None:
        raise RuntimeError("database session factory was not initialized")
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
