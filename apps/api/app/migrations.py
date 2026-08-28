from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine

from app.models.orm import Base

_SCRIPT_LOCATION = Path(__file__).resolve().parent.parent / "alembic"
_MANAGED_TABLES = frozenset(Base.metadata.tables)
_LOCK_NAME = "callparity-schema-migrations"


class SchemaDriftError(RuntimeError):
    """The unversioned database is not the schema represented by the initial revision."""


def _alembic_config(connection: Connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(_SCRIPT_LOCATION))
    config.attributes["connection"] = connection
    return config


def _matches_metadata(connection: Connection) -> bool:
    context = MigrationContext.configure(
        connection,
        opts={"compare_server_default": True, "compare_type": True},
    )
    return not compare_metadata(context, Base.metadata)


def _upgrade_or_adopt_legacy_schema(connection: Connection) -> None:
    tables = set(inspect(connection).get_table_names())
    config = _alembic_config(connection)

    if "alembic_version" not in tables and tables.intersection(_MANAGED_TABLES):
        if not _matches_metadata(connection):
            raise SchemaDriftError(
                "unversioned database schema differs from the initial migration"
            )
        command.stamp(config, "head")
        return

    command.upgrade(config, "head")


def run_migrations(engine: Engine) -> None:
    """Upgrade a database to the sole Alembic head in one transaction."""
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_name))"),
                {"lock_name": _LOCK_NAME},
            ).scalar_one()
        _upgrade_or_adopt_legacy_schema(connection)


def main() -> None:
    from app.db import get_engine

    engine = get_engine()
    try:
        run_migrations(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
