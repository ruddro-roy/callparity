from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine

from app.models.orm import Base

ALEMBIC_CONFIG = Path(__file__).resolve().parents[1] / "alembic.ini"
VERSION_TABLE = "alembic_version"


class LegacySchemaMismatchError(RuntimeError):
    """An unversioned database has drifted from the initial migration."""


def _include_managed_schema_object(
    _schema_object: object,
    _name: str | None,
    object_type: str,
    reflected: bool,
    compare_to: object | None,
) -> bool:
    return not (object_type == "table" and reflected and compare_to is None)


def _matches_current_metadata(connection: Connection) -> bool:
    migration_context = MigrationContext.configure(
        connection,
        opts={
            "compare_server_default": True,
            "compare_type": True,
            "include_object": _include_managed_schema_object,
        },
    )
    return not compare_metadata(migration_context, Base.metadata)


def _config_for(connection: Connection) -> Config:
    config = Config(str(ALEMBIC_CONFIG))
    config.attributes["connection"] = connection
    return config


def upgrade_schema(engine: Engine) -> None:
    """Upgrade to head, safely adopting the schema created before Alembic."""
    with engine.begin() as connection:
        config = _config_for(connection)
        table_names = set(inspect(connection).get_table_names())
        managed_tables = set(Base.metadata.tables)

        if VERSION_TABLE not in table_names and table_names & managed_tables:
            if not _matches_current_metadata(connection):
                raise LegacySchemaMismatchError(
                    "Unversioned database schema does not match the Alembic baseline"
                )
            command.stamp(config, "head")

        command.upgrade(config, "head")


def main() -> None:
    from app.db import get_engine

    upgrade_schema(get_engine())


if __name__ == "__main__":
    main()
