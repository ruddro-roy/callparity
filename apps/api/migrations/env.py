from typing import cast

from alembic import context
from app.config import get_settings
from app.models.orm import Base
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

config = context.config
target_metadata = Base.metadata

# ConfigParser treats percent signs as interpolation markers. Doubling them
# preserves URL-encoded credentials while Alembic reads the setting.
database_url = get_settings().database_url.replace("%", "%%")
config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """Render migrations without opening a database connection."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_with_connection(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations using a supplied connection or a short-lived engine."""
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        _run_with_connection(cast(Connection, supplied_connection))
        return

    engine = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with engine.connect() as connection:
        _run_with_connection(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
