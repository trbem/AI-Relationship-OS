"""Add intelligence workbench tables.

Revision ID: 20260609_0002
Revises: 20260609_0001
"""

from alembic import op
import sqlalchemy as sa


revision = "20260609_0002"
down_revision = "20260609_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "simulation_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("original_question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("legacy_log_id", sa.String(36), sa.ForeignKey("simulation_logs.id"), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_simulation_sessions_user_id", "simulation_sessions", ["user_id"])
    op.create_index("ix_simulation_sessions_person_id", "simulation_sessions", ["person_id"])
    op.create_index("ix_simulation_sessions_status", "simulation_sessions", ["status"])

    op.create_table(
        "simulation_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("simulation_sessions.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_simulation_messages_session_id", "simulation_messages", ["session_id"])

    op.create_table(
        "simulation_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("simulation_message_id", sa.String(36), sa.ForeignKey("simulation_messages.id"), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("relevance", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("simulation_message_id", "source_type", "source_id", name="uq_simulation_evidence_source"),
    )
    op.create_index("ix_simulation_evidence_simulation_message_id", "simulation_evidence", ["simulation_message_id"])
    op.create_index("ix_simulation_evidence_person_id", "simulation_evidence", ["person_id"])
    op.create_index("ix_simulation_evidence_source_id", "simulation_evidence", ["source_id"])

    op.create_table(
        "relationship_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("emotion", sa.String(64), nullable=False),
        sa.Column("impact_direction", sa.String(16), nullable=False),
        sa.Column("impact_strength", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("extraction_version", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("person_id", "event_type", "source_fingerprint", name="uq_relationship_event_source"),
    )
    op.create_index("ix_relationship_events_user_id", "relationship_events", ["user_id"])
    op.create_index("ix_relationship_events_person_id", "relationship_events", ["person_id"])
    op.create_index("ix_relationship_events_event_type", "relationship_events", ["event_type"])
    op.create_index("ix_relationship_events_source_fingerprint", "relationship_events", ["source_fingerprint"])

    op.create_table(
        "relationship_event_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("relationship_events.id"), nullable=False),
        sa.Column("message_id", sa.String(36), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("event_id", "message_id", name="uq_event_message"),
    )
    op.create_index("ix_relationship_event_evidence_event_id", "relationship_event_evidence", ["event_id"])
    op.create_index("ix_relationship_event_evidence_message_id", "relationship_event_evidence", ["message_id"])

    op.create_table(
        "communication_scenarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("simulation_sessions.id"), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("wording", sa.Text(), nullable=False),
        sa.Column("timing", sa.String(255), nullable=True),
        sa.Column("channel", sa.String(64), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_communication_scenarios_session_id", "communication_scenarios", ["session_id"])

    op.create_table(
        "strategy_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("simulation_sessions.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("evidence_snapshot_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_strategy_reports_user_id", "strategy_reports", ["user_id"])
    op.create_index("ix_strategy_reports_session_id", "strategy_reports", ["session_id"])

    op.create_table(
        "group_simulations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("primary_person_id", sa.String(36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("participant_ids_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("round_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_group_simulations_user_id", "group_simulations", ["user_id"])
    op.create_index("ix_group_simulations_primary_person_id", "group_simulations", ["primary_person_id"])

    op.create_table(
        "group_simulation_rounds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("simulation_id", sa.String(36), sa.ForeignKey("group_simulations.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("simulation_id", "round_number", name="uq_group_round"),
    )
    op.create_index("ix_group_simulation_rounds_simulation_id", "group_simulation_rounds", ["simulation_id"])


def downgrade() -> None:
    # Relationship data is intentionally preserved on application rollback.
    pass
