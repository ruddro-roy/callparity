from dataclasses import dataclass

import pytest
from app.migrations import INITIAL_REVISION, upgrade_database
from app.models.orm import Base, TicketRow
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

APPLICATION_TABLES = {
    "action_cards",
    "claims",
    "graph_edges",
    "import_audit",
    "jobs",
    "tickets",
    "transcript_pointers",
}


@dataclass(frozen=True)
class ColumnShape:
    name: str
    type: str
    nullable: bool
    default: str | None
    primary_key: int


@dataclass(frozen=True)
class IndexShape:
    name: str
    columns: tuple[str, ...]
    unique: bool


@dataclass(frozen=True)
class TableShape:
    columns: tuple[ColumnShape, ...]
    primary_key: tuple[str, ...]
    indexes: tuple[IndexShape, ...]
    unique_constraints: tuple[tuple[str, tuple[str, ...]], ...]
    foreign_keys: tuple[tuple[tuple[str, ...], str, tuple[str, ...]], ...]
    checks: tuple[tuple[str, str], ...]


def _schema(engine: Engine) -> dict[str, TableShape]:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names()) - {"alembic_version"}
    return {
        table: TableShape(
            columns=tuple(
                ColumnShape(
                    name=column["name"],
                    type=str(column["type"]),
                    nullable=column["nullable"],
                    default=column["default"],
                    primary_key=column["primary_key"],
                )
                for column in inspector.get_columns(table)
            ),
            primary_key=tuple(inspector.get_pk_constraint(table)["constrained_columns"]),
            indexes=tuple(
                sorted(
                    (
                        IndexShape(
                            name=index["name"],
                            columns=tuple(index["column_names"]),
                            unique=index["unique"],
                        )
                        for index in inspector.get_indexes(table)
                    ),
                    key=lambda index: index.name,
                )
            ),
            unique_constraints=tuple(
                sorted(
                    (constraint["name"] or "", tuple(constraint["column_names"]))
                    for constraint in inspector.get_unique_constraints(table)
                )
            ),
            foreign_keys=tuple(
                sorted(
                    (
                        tuple(foreign_key["constrained_columns"]),
                        foreign_key["referred_table"],
                        tuple(foreign_key["referred_columns"]),
                    )
                    for foreign_key in inspector.get_foreign_keys(table)
                )
            ),
            checks=tuple(
                sorted(
                    (check["name"] or "", check["sqltext"])
                    for check in inspector.get_check_constraints(table)
                )
            ),
        )
        for table in sorted(tables)
    }


def _revision(engine: Engine) -> str:
    with engine.connect() as connection:
        return connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()


def test_initial_migration_matches_create_all_schema(tmp_path):
    metadata_engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'metadata.db'}")
    migrated_engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'migrated.db'}")
    try:
        Base.metadata.create_all(metadata_engine)
        upgrade_database(str(migrated_engine.url))
        upgrade_database(str(migrated_engine.url))

        migrated_schema = _schema(migrated_engine)
        assert set(migrated_schema) == APPLICATION_TABLES
        assert migrated_schema == _schema(metadata_engine)
        assert _revision(migrated_engine) == INITIAL_REVISION
    finally:
        metadata_engine.dispose()
        migrated_engine.dispose()


def test_migration_adopts_matching_unversioned_schema_without_data_loss(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'legacy.db'}")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                TicketRow(
                    id="legacy-ticket",
                    domain="freight",
                    fact="A retained migration row",
                    entities={},
                    parties=[],
                    sla_usd_per_hour=1,
                )
            )
            session.commit()

        upgrade_database(str(engine.url))

        with Session(engine) as session:
            assert session.get(TicketRow, "legacy-ticket") is not None
        assert _revision(engine) == INITIAL_REVISION
    finally:
        engine.dispose()


def test_migration_rejects_partial_unversioned_schema(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'partial.db'}")
    try:
        TicketRow.__table__.create(engine)

        with pytest.raises(RuntimeError, match="does not match the initial migration"):
            upgrade_database(str(engine.url))

        assert "alembic_version" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()
