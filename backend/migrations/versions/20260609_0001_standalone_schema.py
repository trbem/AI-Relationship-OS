"""Create the standalone core schema.

Revision ID: 20260609_0001
Revises:
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision = "20260609_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "persons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("profile_summary", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_persons_user_id", "persons", ["user_id"])
    op.create_index("ix_persons_name", "persons", ["name"])

    op.create_table(
        "import_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("stored_path", sa.Text(), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("self_name", sa.String(255), nullable=True),
        sa.Column("encoding", sa.String(32), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id"), nullable=True),
        sa.Column("parsed_count", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_import_tasks_user_id", "import_tasks", ["user_id"])
    op.create_index("ix_import_tasks_file_hash", "import_tasks", ["file_hash"])
    op.create_index("ix_import_tasks_status", "import_tasks", ["status"])

    op.create_table(
        "messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id"), nullable=True),
        sa.Column("sender_name", sa.String(255), nullable=False),
        sa.Column("direction", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=True),
        sa.Column("import_task_id", sa.String(36), sa.ForeignKey("import_tasks.id"), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "person_id", "fingerprint", name="uq_message_fingerprint"),
    )
    op.create_index("ix_messages_user_id", "messages", ["user_id"])
    op.create_index("ix_messages_person_id", "messages", ["person_id"])
    op.create_index("ix_messages_sender_name", "messages", ["sender_name"])
    op.create_index("ix_messages_fingerprint", "messages", ["fingerprint"])
    op.create_index("ix_messages_import_task_id", "messages", ["import_task_id"])

    op.create_table(
        "person_memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("event", sa.Text(), nullable=False),
        sa.Column("emotion", sa.String(64), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("source_message_ids", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_person_memories_person_id", "person_memories", ["person_id"])

    op.create_table(
        "relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("trust", sa.Float(), nullable=False),
        sa.Column("frequency", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_relationships_user_id", "relationships", ["user_id"])
    op.create_index("ix_relationships_person_id", "relationships", ["person_id"])

    op.create_table(
        "message_vectors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("message_id", sa.String(36), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("embedding", Vector(1536).with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("embedding_ref", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_message_vectors_message_id", "message_vectors", ["message_id"])
    op.create_index("ix_message_vectors_person_id", "message_vectors", ["person_id"])

    op.create_table(
        "simulation_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("response_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_simulation_logs_person_id", "simulation_logs", ["person_id"])


def downgrade() -> None:
    # User data is intentionally preserved when an application version is rolled back.
    pass
