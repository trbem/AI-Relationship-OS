from __future__ import annotations

from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
import sqlalchemy as sa

from app.db import Base
from app.models import entities  # noqa: F401


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = BACKEND_ROOT / "migrations"
HEAD = "20260622_0004"


def _config(url: str, *, output_buffer: StringIO | None = None) -> Config:
    config = Config(output_buffer=output_buffer)
    config.set_main_option("script_location", str(MIGRATIONS))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _revision(engine: sa.Engine) -> str:
    with engine.connect() as connection:
        return connection.scalar(sa.text("SELECT version_num FROM alembic_version"))


def _index_signatures(inspector: sa.Inspector, table: str) -> set[tuple[tuple[str, ...], bool]]:
    signatures = {
        (tuple(index["column_names"]), bool(index.get("unique")))
        for index in inspector.get_indexes(table)
        if index.get("column_names")
    }
    signatures.update(
        (tuple(constraint["column_names"]), True)
        for constraint in inspector.get_unique_constraints(table)
        if constraint.get("column_names")
    )
    return signatures


def _metadata_index_signatures(table: sa.Table) -> set[tuple[tuple[str, ...], bool]]:
    signatures = {
        (tuple(column.name for column in index.columns), bool(index.unique))
        for index in table.indexes
    }
    signatures.update(
        (tuple(column.name for column in constraint.columns), True)
        for constraint in table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    )
    return signatures


def test_empty_sqlite_upgrades_to_head_and_matches_orm(tmp_path: Path) -> None:
    url = _sqlite_url(tmp_path / "empty.db")
    command.upgrade(_config(url), "head")
    engine = sa.create_engine(url)
    try:
        inspector = sa.inspect(engine)
        assert _revision(engine) == HEAD
        assert set(inspector.get_table_names()) - {"alembic_version"} == set(Base.metadata.tables)

        for name, model_table in Base.metadata.tables.items():
            database_columns = {column["name"] for column in inspector.get_columns(name)}
            assert database_columns == {column.name for column in model_table.columns}, name
            assert _index_signatures(inspector, name) == _metadata_index_signatures(model_table), name
    finally:
        engine.dispose()


def test_existing_0003_upgrade_is_additive_and_repeatable(tmp_path: Path) -> None:
    url = _sqlite_url(tmp_path / "existing.db")
    config = _config(url)
    command.upgrade(config, "20260609_0003")
    engine = sa.create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(sa.text(
                "INSERT INTO users (id, email, password_hash, created_at) "
                "VALUES ('sentinel', 'sentinel@example.test', 'hash', '2026-06-22 00:00:00')"
            ))
            connection.execute(sa.text("DROP INDEX ix_persons_name"))
            connection.execute(sa.text("DROP INDEX ix_world_events_world_id"))

        command.upgrade(config, "head")
        command.upgrade(config, "head")

        inspector = sa.inspect(engine)
        assert _revision(engine) == HEAD
        assert {index["name"] for index in inspector.get_indexes("persons")} >= {"ix_persons_name"}
        assert {index["name"] for index in inspector.get_indexes("world_events")} >= {"ix_world_events_world_id"}
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT email FROM users WHERE id='sentinel'")) == "sentinel@example.test"
    finally:
        engine.dispose()


def _create_legacy_v06_fixture(engine: sa.Engine) -> None:
    """Create a frozen v0.6-style SQLite fixture without importing migrations/ORM."""
    legacy_ddl = """
    PRAGMA foreign_keys=OFF;
    CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY);
    INSERT INTO alembic_version VALUES ('20260609_0003');
    CREATE TABLE users (
        id VARCHAR(36) PRIMARY KEY, email VARCHAR(255) NOT NULL,
        password_hash VARCHAR(255) NOT NULL, created_at DATETIME NOT NULL
    );
    CREATE TABLE persons (
        id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36) NOT NULL,
        name VARCHAR(255) NOT NULL, profile_summary TEXT, confidence FLOAT,
        created_at DATETIME NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE messages (
        id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36) NOT NULL,
        person_id VARCHAR(36), sender_name VARCHAR(255) NOT NULL,
        direction VARCHAR(32) NOT NULL, content TEXT NOT NULL,
        fingerprint VARCHAR(64), import_task_id VARCHAR(36), sent_at DATETIME,
        created_at DATETIME NOT NULL
    );
    CREATE TABLE group_simulations (
        id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36) NOT NULL,
        primary_person_id VARCHAR(36) NOT NULL, title VARCHAR(255) NOT NULL,
        goal TEXT NOT NULL, participant_ids_json TEXT NOT NULL,
        status VARCHAR(32) NOT NULL, round_count INTEGER NOT NULL,
        created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL
    );
    CREATE TABLE group_simulation_rounds (
        id VARCHAR(36) PRIMARY KEY, simulation_id VARCHAR(36) NOT NULL,
        round_number INTEGER NOT NULL, state_json TEXT NOT NULL,
        created_at DATETIME NOT NULL
    );
    CREATE TABLE relationship_event_evidence (
        id VARCHAR(36) PRIMARY KEY, event_id VARCHAR(36) NOT NULL,
        message_id VARCHAR(36) NOT NULL, created_at DATETIME NOT NULL
    );
    INSERT INTO users VALUES
        ('user-a', 'duplicate@example.test', 'hash-a', '2026-06-01'),
        ('user-b', 'duplicate@example.test', 'hash-b', '2026-06-02');
    INSERT INTO persons VALUES
        ('person-a', 'user-a', 'Alice', NULL, 0.8, '2026-06-01');
    INSERT INTO messages VALUES
        ('message-a', 'user-a', 'person-a', 'Alice', 'in', 'first', 'same-fp', NULL, NULL, '2026-06-01'),
        ('message-b', 'user-a', 'person-a', 'Alice', 'in', 'second', 'same-fp', NULL, NULL, '2026-06-02');
    INSERT INTO group_simulations VALUES
        ('simulation-a', 'user-a', 'person-a', 'legacy', 'goal', '[]', 'done', 2, '2026-06-01', '2026-06-01');
    INSERT INTO group_simulation_rounds VALUES
        ('round-a', 'simulation-a', 1, '{"turn":"first"}', '2026-06-01'),
        ('round-b', 'simulation-a', 1, '{"turn":"second"}', '2026-06-02');
    INSERT INTO relationship_event_evidence VALUES
        ('evidence-a', 'event-a', 'message-a', '2026-06-01'),
        ('evidence-b', 'event-a', 'message-a', '2026-06-02');
    """
    raw = engine.raw_connection()
    try:
        raw.executescript(legacy_ddl)
        raw.commit()
    finally:
        raw.close()


def test_real_legacy_sqlite_fixture_upgrades_with_duplicates_and_keeps_data(
    tmp_path: Path,
) -> None:
    url = _sqlite_url(tmp_path / "legacy-v06.db")
    engine = sa.create_engine(url)
    try:
        _create_legacy_v06_fixture(engine)
        long_fingerprint = "f" * 64
        with engine.begin() as connection:
            connection.execute(
                sa.text("UPDATE messages SET fingerprint=:fingerprint"),
                {"fingerprint": long_fingerprint},
            )
        command.upgrade(_config(url), "head")

        assert _revision(engine) == HEAD
        inspector = sa.inspect(engine)
        assert (("email",), True) in _index_signatures(inspector, "users")
        assert (
            ("user_id", "person_id", "fingerprint"), True
        ) in _index_signatures(inspector, "messages")
        assert (
            ("simulation_id", "round_number"), True
        ) in _index_signatures(inspector, "group_simulation_rounds")

        with engine.connect() as connection:
            users = connection.execute(
                sa.text("SELECT id, email, password_hash FROM users ORDER BY id")
            ).all()
            assert users == [
                ("user-a", "duplicate@example.test", "hash-a"),
                ("user-b", "duplicate+legacy-user-b@example.test", "hash-b"),
            ]
            messages = connection.execute(
                sa.text("SELECT id, content, fingerprint FROM messages ORDER BY id")
            ).all()
            assert messages == [
                ("message-a", "first", long_fingerprint),
                (
                    "message-b",
                    "second",
                    f"{'f' * (64 - len('~legacy-message-b'))}~legacy-message-b",
                ),
            ]
            assert all(len(row.fingerprint) <= 64 for row in messages)
            rounds = connection.execute(
                sa.text(
                    "SELECT id, round_number, state_json "
                    "FROM group_simulation_rounds ORDER BY id"
                )
            ).all()
            assert rounds == [
                ("round-a", 1, '{"turn":"first"}'),
                ("round-b", 2, '{"turn":"second"}'),
            ]
            assert connection.scalar(
                sa.text("SELECT COUNT(*) FROM relationship_event_evidence")
            ) == 1
            archived = connection.execute(
                sa.text(
                    "SELECT row_id, row_json FROM v07_migration_duplicate_archive "
                    "WHERE index_name='uq_event_message'"
                )
            ).one()
            assert archived[0] == "evidence-b"
            assert '"created_at": "2026-06-02"' in archived[1]

        # A second upgrade is a no-op and proves the repair is restart-safe.
        command.upgrade(_config(url), "head")
    finally:
        engine.dispose()


def test_postgresql_offline_upgrade_emits_complete_ddl() -> None:
    output = StringIO()
    command.upgrade(
        _config("postgresql+psycopg://offline:offline@localhost/offline", output_buffer=output),
        "head",
        sql=True,
    )
    ddl = output.getvalue()
    assert 'CREATE TABLE users' in ddl
    assert 'CREATE TABLE world_events' in ddl
    assert 'VECTOR(1536)' in ddl.upper()
    assert 'CREATE UNIQUE INDEX IF NOT EXISTS "uq_message_fingerprint"' in ddl
    assert f"UPDATE alembic_version SET version_num='{HEAD}'" in ddl


def test_frozen_revisions_do_not_reference_live_metadata() -> None:
    for filename in (
        "20260609_0001_standalone_schema.py",
        "20260609_0002_intelligence_workbench.py",
        "20260609_0003_persona_worlds.py",
        "20260622_0004_v07_schema_guard.py",
    ):
        source = (MIGRATIONS / "versions" / filename).read_text(encoding="utf-8")
        assert "Base" not in source
        assert "app.models" not in source
        assert "create_all" not in source
