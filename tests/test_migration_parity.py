from pathlib import Path
from typing import NamedTuple

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from app.migrations import SchemaDriftError, run_migrations
from app.models.orm import Base
from sqlalchemy import Column, MetaData, String, Table, create_engine, inspect, text
from sqlalchemy.engine import Engine

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"


class ColumnShape(NamedTuple):
    name: str
    type: str
    nullable: bool
    default: str | None


class IndexShape(NamedTuple):
    name: str
    columns: tuple[str, ...]
    unique: bool


class ConstraintShape(NamedTuple):
    name: str | None
    columns: tuple[str, ...]


class CheckShape(NamedTuple):
    name: str | None
    expression: str


class ForeignKeyShape(NamedTuple):
    name: str | None
    columns: tuple[str, ...]
    referred_table: str
    referred_columns: tuple[str, ...]


class TableShape(NamedTuple):
    columns: tuple[ColumnShape, ...]
    primary_key: ConstraintShape
    indexes: tuple[IndexShape, ...]
    unique_constraints: tuple[ConstraintShape, ...]
    checks: tuple[CheckShape, ...]
    foreign_keys: tuple[ForeignKeyShape, ...]


def _constraint_shape(constraint: dict) -> ConstraintShape:
    return ConstraintShape(
        name=constraint.get("name"),
        columns=tuple(constraint.get("column_names") or constraint.get("constrained_columns") or ()),
    )


def _table_shape(engine: Engine, table_name: str) -> TableShape:
    inspector = inspect(engine)
    columns = tuple(
        ColumnShape(
            name=column["name"],
            type=str(column["type"].compile(dialect=engine.dialect)),
            nullable=column["nullable"],
            default=None if column["default"] is None else str(column["default"]),
        )
        for column in inspector.get_columns(table_name)
    )
    indexes = tuple(
        sorted(
            IndexShape(
                name=index["name"],
                columns=tuple(index["column_names"]),
                unique=bool(index["unique"]),
            )
            for index in inspector.get_indexes(table_name)
        )
    )
    unique_constraints = tuple(
        sorted(
            (_constraint_shape(constraint) for constraint in inspector.get_unique_constraints(table_name)),
            key=lambda constraint: (constraint.name or "", constraint.columns),
        )
    )
    checks = tuple(
        sorted(
            (
                CheckShape(name=check.get("name"), expression=str(check["sqltext"]))
                for check in inspector.get_check_constraints(table_name)
            ),
            key=lambda check: (check.name or "", check.expression),
        )
    )
    foreign_keys = tuple(
        sorted(
            (
                ForeignKeyShape(
                    name=foreign_key.get("name"),
                    columns=tuple(foreign_key["constrained_columns"]),
                    referred_table=foreign_key["referred_table"],
                    referred_columns=tuple(foreign_key["referred_columns"]),
                )
                for foreign_key in inspector.get_foreign_keys(table_name)
            ),
            key=repr,
        )
    )
    return TableShape(
        columns=columns,
        primary_key=_constraint_shape(inspector.get_pk_constraint(table_name)),
        indexes=indexes,
        unique_constraints=unique_constraints,
        checks=checks,
        foreign_keys=foreign_keys,
    )


def _schema_shape(engine: Engine) -> dict[str, TableShape]:
    return {table: _table_shape(engine, table) for table in sorted(Base.metadata.tables)}


def _sqlite_engine(path: Path) -> Engine:
    return create_engine(f"sqlite+pysqlite:///{path}")


def test_initial_migration_matches_create_all_schema(tmp_path):
    create_all_engine = _sqlite_engine(tmp_path / "create_all.db")
    migrated_engine = _sqlite_engine(tmp_path / "migrated.db")

    Base.metadata.create_all(create_all_engine)
    run_migrations(migrated_engine)
    run_migrations(migrated_engine)

    expected_tables = set(Base.metadata.tables)
    assert set(inspect(create_all_engine).get_table_names()) == expected_tables
    assert set(inspect(migrated_engine).get_table_names()) == expected_tables | {
        "alembic_version"
    }
    assert _schema_shape(migrated_engine) == _schema_shape(create_all_engine)

    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={"compare_server_default": True, "compare_type": True},
        )
        assert compare_metadata(context, Base.metadata) == []

    config = Config(str(API_ROOT / "alembic.ini"))
    assert ScriptDirectory.from_config(config).get_heads() == ["0001_initial_schema"]


def test_migrations_adopt_an_exact_legacy_schema(tmp_path):
    engine = _sqlite_engine(tmp_path / "legacy.db")
    Base.metadata.create_all(engine)

    run_migrations(engine)

    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert revision == "0001_initial_schema"


def test_migrations_reject_a_drifted_legacy_schema(tmp_path):
    engine = _sqlite_engine(tmp_path / "drifted.db")
    metadata = MetaData()
    Table("tickets", metadata, Column("id", String(64), primary_key=True))
    metadata.create_all(engine)

    with pytest.raises(SchemaDriftError, match="differs from the initial migration"):
        run_migrations(engine)

    assert "alembic_version" not in inspect(engine).get_table_names()
