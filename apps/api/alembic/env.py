"""Alembic env. Schema source of truth is app.models.orm.Base.metadata."""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

# apps/api (repo) or /app (compose). Required before importing app.*.
_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.config import get_settings
from app.models.orm import Base

target_metadata = Base.metadata


def _database_url() -> str:
    return get_settings().database_url


def _connect_args(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def run_migrations_offline() -> None:
    url = _database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_with_connection(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # app.migrate shares one connection (and its transaction, holding the
    # Postgres advisory lock) so inspection and DDL cannot interleave across
    # processes. Standalone `alembic upgrade` still builds its own engine.
    shared = context.config.attributes.get("connection")
    if shared is not None:
        _run_with_connection(shared)
        return

    url = _database_url()
    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=_connect_args(url),
        future=True,
    )
    with connectable.connect() as connection:
        _run_with_connection(connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
