import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()
if settings.database_url.startswith("sqlite"):
    database_path = settings.database_url.removeprefix("sqlite:///")
    Path(database_path).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(
    settings.database_url,
    future=True,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    migrations = root / "migrations"
    config = Config()
    config.set_main_option("script_location", str(migrations))
    config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
    command.upgrade(config, "head")
    _migrate_legacy_simulations()


def _migrate_legacy_simulations() -> None:
    from app.models import (
        Person,
        SimulationLog,
        SimulationMessage,
        SimulationSession,
    )

    with SessionLocal() as db:
        legacy_logs = db.query(SimulationLog).all()
        for legacy in legacy_logs:
            exists = db.query(SimulationSession.id).filter(
                SimulationSession.legacy_log_id == legacy.id
            ).first()
            if exists:
                continue
            person = db.get(Person, legacy.person_id)
            if not person:
                continue
            session = SimulationSession(
                user_id=person.user_id,
                person_id=person.id,
                title=legacy.question[:80] or "Legacy simulation",
                original_question=legacy.question,
                status="archived",
                legacy_log_id=legacy.id,
                created_at=legacy.created_at,
                updated_at=legacy.created_at,
            )
            db.add(session)
            db.flush()
            db.add(
                SimulationMessage(
                    session_id=session.id,
                    role="user",
                    kind="question",
                    content=legacy.question,
                    created_at=legacy.created_at,
                )
            )
            db.add(
                SimulationMessage(
                    session_id=session.id,
                    role="assistant",
                    kind="legacy_result",
                    content="Imported from the legacy simulation history.",
                    payload_json=legacy.response_json,
                    created_at=legacy.created_at,
                )
            )
        db.commit()
