"""Create and upgrade the standalone schema.

Revision ID: 20260609_0001
Revises:
"""
from alembic import op
from sqlalchemy import inspect, text

from app.db import Base
from app.models import entities  # noqa: F401


revision = "20260609_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    additions = {
        "messages": {
            "fingerprint": "VARCHAR(64)",
            "import_task_id": "VARCHAR(36)",
        },
    }
    for table, columns in additions.items():
        if table not in tables:
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        for column, sql_type in columns.items():
            if column not in existing:
                bind.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
    if "messages" in tables:
        bind.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_message_fingerprint_idx "
                "ON messages(user_id, person_id, fingerprint)"
            )
        )


def downgrade() -> None:
    # User data is intentionally preserved when an application version is rolled back.
    pass
