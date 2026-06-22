"""add persona worlds and role sandbox

Revision ID: 20260609_0003
Revises: 20260609_0002
Create Date: 2026-06-09
"""

from alembic import op

from app.db import Base


revision = "20260609_0003"
down_revision = "20260609_0002"
branch_labels = None
depends_on = None


TABLES = (
    "persona_worlds",
    "world_personas",
    "world_relationships",
    "world_sources",
    "world_import_tasks",
    "world_simulations",
    "world_simulation_rounds",
    "world_events",
)


def upgrade() -> None:
    bind = op.get_bind()
    for table_name in TABLES:
        Base.metadata.tables[table_name].create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in reversed(TABLES):
        Base.metadata.tables[table_name].drop(bind, checkfirst=True)
