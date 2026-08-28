"""Apply Alembic migrations. Used for Postgres at process start.

SQLite/local and pytest keep Base.metadata.create_all via init_db. An existing
complete create_all schema (no alembic_version) is stamped at head so a compose
volume created before this change keeps its data.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.config import get_settings
from app.models.orm import Base

log = logging.getLogger("callparity.migrate")

_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
_SCRIPTS = Path(__file__).resolve().parents[1] / "alembic"

# Tables the current ORM owns. alembic_version is Alembic's, not ours.
ORM_TABLES = frozenset(Base.metadata.tables)


def alembic_config(url: str | None = None) -> Config:
    if not _INI.is_file():
        raise RuntimeError(f"alembic.ini missing at {_INI}")
    cfg = Config(str(_INI))
    cfg.set_main_option("script_location", str(_SCRIPTS))
    resolved = url if url is not None else get_settings().database_url
    # ConfigParser interpolation treats % as escape.
    cfg.set_main_option("sqlalchemy.url", resolved.replace("%", "%%"))
    return cfg


def _inspect_engine(url: str):
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args, future=True)
    return engine


def apply_migrations() -> str:
    """Bring the configured database to Alembic head.

    Returns the action taken: "upgrade", "stamp", or "upgrade" after a no-op.
    Raises RuntimeError if some but not all ORM tables exist (partial schema).
    Idempotent: a second call on a current database is a no-op upgrade.
    """
    url = get_settings().database_url
    engine = _inspect_engine(url)
    try:
        present = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    cfg = alembic_config(url)
    ours = present & ORM_TABLES
    versioned = "alembic_version" in present

    if versioned:
        command.upgrade(cfg, "head")
        log.info("schema.migrate action=upgrade")
        return "upgrade"

    if ours == ORM_TABLES:
        command.stamp(cfg, "head")
        log.info("schema.migrate action=stamp")
        return "stamp"

    if ours:
        missing = sorted(ORM_TABLES - ours)
        raise RuntimeError(
            "partial schema; refuse to guess. missing tables: "
            + ", ".join(missing)
            + ". wipe the volume or restore a complete create_all schema"
        )

    command.upgrade(cfg, "head")
    log.info("schema.migrate action=upgrade")
    return "upgrade"


def uses_alembic(url: str) -> bool:
    """Postgres (any driver) is migrated. Everything else uses create_all."""
    return url.split(":", 1)[0].startswith("postgres")
