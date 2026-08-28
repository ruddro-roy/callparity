from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Connection

from app.config import get_settings
from app.models.orm import Base

INITIAL_REVISION = "f270a9f3aa8f"


def _config(database_url: str) -> Config:
    config = Config(Path(__file__).resolve().parents[1] / "alembic.ini")
    config.attributes["database_url"] = database_url
    return config


def _matches_current_metadata(connection: Connection) -> bool:
    context = MigrationContext.configure(connection)
    return not compare_metadata(context, Base.metadata)


def upgrade_database(database_url: str | None = None) -> None:
    url = database_url or get_settings().database_url
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            tables = frozenset(inspect(connection).get_table_names())
            application_tables = frozenset(Base.metadata.tables)
            has_unversioned_schema = (
                "alembic_version" not in tables and bool(tables & application_tables)
            )
            if has_unversioned_schema and not _matches_current_metadata(connection):
                raise RuntimeError(
                    "The unversioned database schema does not match the initial migration"
                )

        config = _config(url)
        if has_unversioned_schema:
            command.stamp(config, INITIAL_REVISION)
        command.upgrade(config, "head")
    finally:
        engine.dispose()


if __name__ == "__main__":
    upgrade_database()
