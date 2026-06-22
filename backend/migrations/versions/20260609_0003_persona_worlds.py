"""Add persona worlds and role sandbox.

Revision ID: 20260609_0003
Revises: 20260609_0002
Create Date: 2026-06-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260609_0003"
down_revision = "20260609_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persona_worlds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("theme", sa.String(255), nullable=True),
        sa.Column("world_type", sa.String(32), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("version", sa.String(64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("world_background", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_persona_worlds_user_id", "persona_worlds", ["user_id"])

    op.create_table(
        "world_personas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("world_id", sa.String(36), sa.ForeignKey("persona_worlds.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("aliases_json", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("traits_json", sa.Text(), nullable=False),
        sa.Column("motivations_json", sa.Text(), nullable=False),
        sa.Column("values_json", sa.Text(), nullable=False),
        sa.Column("abilities_json", sa.Text(), nullable=False),
        sa.Column("communication_json", sa.Text(), nullable=False),
        sa.Column("faction", sa.String(128), nullable=True),
        sa.Column("background", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("setting_completeness", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("world_id", "source_type", "source_ref", name="uq_world_persona_source"),
    )
    op.create_index("ix_world_personas_world_id", "world_personas", ["world_id"])
    op.create_index("ix_world_personas_name", "world_personas", ["name"])
    op.create_index("ix_world_personas_faction", "world_personas", ["faction"])

    op.create_table(
        "world_relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("world_id", sa.String(36), sa.ForeignKey("persona_worlds.id"), nullable=False),
        sa.Column("source_persona_id", sa.String(36), sa.ForeignKey("world_personas.id"), nullable=False),
        sa.Column("target_persona_id", sa.String(36), sa.ForeignKey("world_personas.id"), nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=False),
        sa.Column("directed", sa.Boolean(), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "world_id", "source_persona_id", "target_persona_id", "relationship_type",
            name="uq_world_relationship",
        ),
    )
    op.create_index("ix_world_relationships_world_id", "world_relationships", ["world_id"])
    op.create_index("ix_world_relationships_source_persona_id", "world_relationships", ["source_persona_id"])
    op.create_index("ix_world_relationships_target_persona_id", "world_relationships", ["target_persona_id"])

    op.create_table(
        "world_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("world_id", sa.String(36), sa.ForeignKey("persona_worlds.id"), nullable=False),
        sa.Column("persona_id", sa.String(36), sa.ForeignKey("world_personas.id"), nullable=True),
        sa.Column("relationship_id", sa.String(36), sa.ForeignKey("world_relationships.id"), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("version", sa.String(64), nullable=True),
        sa.Column("accessed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_world_sources_world_id", "world_sources", ["world_id"])
    op.create_index("ix_world_sources_persona_id", "world_sources", ["persona_id"])
    op.create_index("ix_world_sources_relationship_id", "world_sources", ["relationship_id"])
    op.create_index("ix_world_sources_external_id", "world_sources", ["external_id"])

    op.create_table(
        "world_import_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("world_id", sa.String(36), sa.ForeignKey("persona_worlds.id"), nullable=True),
        sa.Column("query", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("requested_limit", sa.Integer(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_world_import_tasks_user_id", "world_import_tasks", ["user_id"])
    op.create_index("ix_world_import_tasks_world_id", "world_import_tasks", ["world_id"])

    op.create_table(
        "world_simulations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("world_id", sa.String(36), sa.ForeignKey("persona_worlds.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("scenario", sa.Text(), nullable=False),
        sa.Column("participant_ids_json", sa.Text(), nullable=False),
        sa.Column("round_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("setting_completeness", sa.Float(), nullable=False),
        sa.Column("source_coverage", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_world_simulations_world_id", "world_simulations", ["world_id"])
    op.create_index("ix_world_simulations_user_id", "world_simulations", ["user_id"])

    op.create_table(
        "world_simulation_rounds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("simulation_id", sa.String(36), sa.ForeignKey("world_simulations.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("simulation_id", "round_number", name="uq_world_simulation_round"),
    )
    op.create_index("ix_world_simulation_rounds_simulation_id", "world_simulation_rounds", ["simulation_id"])

    op.create_table(
        "world_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("world_id", sa.String(36), sa.ForeignKey("persona_worlds.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), nullable=False),
        sa.Column("source_simulation_id", sa.String(36), sa.ForeignKey("world_simulations.id"), nullable=True),
        sa.Column("source_round_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_world_events_world_id", "world_events", ["world_id"])
    op.create_index("ix_world_events_source_simulation_id", "world_events", ["source_simulation_id"])


def downgrade() -> None:
    # World data is intentionally preserved on application rollback.
    pass
