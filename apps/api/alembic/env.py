"""Alembic environment for the CallParity API.

The target schema is app.models.orm.Base. The database URL is resolved in this
order: a connectable handed over programmatically (app startup shares its
engine via config.attributes["connection"]), then sqlalchemy.url from the ini,
then the application settings (DATABASE_URL / .env).
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import Connection, create_engine, pool

# Make the API package importable when Alembic runs from the CLI, where the
# working directory is not apps/api (mirrors scripts/seed_demo_data.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.models.orm import Base

config = context.config
# Apply the ini logging config only for standalone CLI runs. When the app
# shares its engine (config.attributes["connection"]), it has already
# configured logging and fileConfig would disable those loggers.
if config.config_file_name is not None and config.attributes.get("connection") is None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    configured = config.get_main_option("sqlalchemy.url")
    if configured:
        return configured
    return get_settings().database_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a database connection (--sql mode)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_with_connection(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection", None)
    if connectable is None:
        connectable = create_engine(_database_url(), poolclass=pool.NullPool)
        with connectable.connect() as connection:
            _run_with_connection(connection)
        connectable.dispose()
    elif isinstance(connectable, Connection):
        _run_with_connection(connectable)
    else:
        with connectable.connect() as connection:
            _run_with_connection(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
