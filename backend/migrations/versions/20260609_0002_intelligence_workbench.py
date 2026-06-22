"""Add intelligence workbench tables.

Revision ID: 20260609_0002
Revises: 20260609_0001
"""
from alembic import op

from app.db import Base
from app.models import entities  # noqa: F401


revision = "20260609_0002"
down_revision = "20260609_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # Relationship data is intentionally preserved on application rollback.
    pass
