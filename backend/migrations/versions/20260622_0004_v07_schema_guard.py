"""Guard the v0.7 schema indexes and uniqueness invariants.

Revision ID: 20260622_0004
Revises: 20260609_0003
"""

from alembic import op
import json
import sqlalchemy as sa


revision = "20260622_0004"
down_revision = "20260609_0003"
branch_labels = None
depends_on = None


# (name, table, columns, unique).  These are deliberately limited to indexes
# represented by the v0.7 ORM.  No table rewrite or destructive cleanup occurs.
INDEXES = (
    ("ix_users_email", "users", ("email",), True),
    ("ix_persons_user_id", "persons", ("user_id",), False),
    ("ix_persons_name", "persons", ("name",), False),
    ("ix_import_tasks_user_id", "import_tasks", ("user_id",), False),
    ("ix_import_tasks_file_hash", "import_tasks", ("file_hash",), False),
    ("ix_import_tasks_status", "import_tasks", ("status",), False),
    ("ix_messages_user_id", "messages", ("user_id",), False),
    ("ix_messages_person_id", "messages", ("person_id",), False),
    ("ix_messages_sender_name", "messages", ("sender_name",), False),
    ("ix_messages_fingerprint", "messages", ("fingerprint",), False),
    ("ix_messages_import_task_id", "messages", ("import_task_id",), False),
    ("uq_message_fingerprint", "messages", ("user_id", "person_id", "fingerprint"), True),
    ("ix_person_memories_person_id", "person_memories", ("person_id",), False),
    ("ix_relationships_user_id", "relationships", ("user_id",), False),
    ("ix_relationships_person_id", "relationships", ("person_id",), False),
    ("ix_message_vectors_message_id", "message_vectors", ("message_id",), False),
    ("ix_message_vectors_person_id", "message_vectors", ("person_id",), False),
    ("ix_simulation_logs_person_id", "simulation_logs", ("person_id",), False),
    ("ix_simulation_sessions_user_id", "simulation_sessions", ("user_id",), False),
    ("ix_simulation_sessions_person_id", "simulation_sessions", ("person_id",), False),
    ("ix_simulation_sessions_status", "simulation_sessions", ("status",), False),
    ("uq_simulation_sessions_legacy_log_id", "simulation_sessions", ("legacy_log_id",), True),
    ("ix_simulation_messages_session_id", "simulation_messages", ("session_id",), False),
    ("ix_simulation_evidence_simulation_message_id", "simulation_evidence", ("simulation_message_id",), False),
    ("ix_simulation_evidence_person_id", "simulation_evidence", ("person_id",), False),
    ("ix_simulation_evidence_source_id", "simulation_evidence", ("source_id",), False),
    ("uq_simulation_evidence_source", "simulation_evidence", ("simulation_message_id", "source_type", "source_id"), True),
    ("ix_relationship_events_user_id", "relationship_events", ("user_id",), False),
    ("ix_relationship_events_person_id", "relationship_events", ("person_id",), False),
    ("ix_relationship_events_event_type", "relationship_events", ("event_type",), False),
    ("ix_relationship_events_source_fingerprint", "relationship_events", ("source_fingerprint",), False),
    ("uq_relationship_event_source", "relationship_events", ("person_id", "event_type", "source_fingerprint"), True),
    ("ix_relationship_event_evidence_event_id", "relationship_event_evidence", ("event_id",), False),
    ("ix_relationship_event_evidence_message_id", "relationship_event_evidence", ("message_id",), False),
    ("uq_event_message", "relationship_event_evidence", ("event_id", "message_id"), True),
    ("ix_communication_scenarios_session_id", "communication_scenarios", ("session_id",), False),
    ("ix_strategy_reports_user_id", "strategy_reports", ("user_id",), False),
    ("ix_strategy_reports_session_id", "strategy_reports", ("session_id",), False),
    ("ix_group_simulations_user_id", "group_simulations", ("user_id",), False),
    ("ix_group_simulations_primary_person_id", "group_simulations", ("primary_person_id",), False),
    ("ix_group_simulation_rounds_simulation_id", "group_simulation_rounds", ("simulation_id",), False),
    ("uq_group_round", "group_simulation_rounds", ("simulation_id", "round_number"), True),
    ("ix_persona_worlds_user_id", "persona_worlds", ("user_id",), False),
    ("ix_world_personas_world_id", "world_personas", ("world_id",), False),
    ("ix_world_personas_name", "world_personas", ("name",), False),
    ("ix_world_personas_faction", "world_personas", ("faction",), False),
    ("uq_world_persona_source", "world_personas", ("world_id", "source_type", "source_ref"), True),
    ("ix_world_relationships_world_id", "world_relationships", ("world_id",), False),
    ("ix_world_relationships_source_persona_id", "world_relationships", ("source_persona_id",), False),
    ("ix_world_relationships_target_persona_id", "world_relationships", ("target_persona_id",), False),
    ("uq_world_relationship", "world_relationships", ("world_id", "source_persona_id", "target_persona_id", "relationship_type"), True),
    ("ix_world_sources_world_id", "world_sources", ("world_id",), False),
    ("ix_world_sources_persona_id", "world_sources", ("persona_id",), False),
    ("ix_world_sources_relationship_id", "world_sources", ("relationship_id",), False),
    ("ix_world_sources_external_id", "world_sources", ("external_id",), False),
    ("ix_world_import_tasks_user_id", "world_import_tasks", ("user_id",), False),
    ("ix_world_import_tasks_world_id", "world_import_tasks", ("world_id",), False),
    ("ix_world_simulations_world_id", "world_simulations", ("world_id",), False),
    ("ix_world_simulations_user_id", "world_simulations", ("user_id",), False),
    ("ix_world_simulation_rounds_simulation_id", "world_simulation_rounds", ("simulation_id",), False),
    ("uq_world_simulation_round", "world_simulation_rounds", ("simulation_id", "round_number"), True),
    ("ix_world_events_world_id", "world_events", ("world_id",), False),
    ("ix_world_events_source_simulation_id", "world_events", ("source_simulation_id",), False),
)


# The v0.6 application normally created these constraints through ORM metadata,
# but databases originating from older standalone builds may lack some of them.
# Repair the key (rather than deleting the entity) before adding a missing unique
# index.  Pure duplicate association rows cannot be given a different valid
# foreign key; those are archived in full before the redundant row is removed.
TEXT_REPAIR_COLUMNS = {
    "ix_users_email": "email",
    "uq_message_fingerprint": "fingerprint",
    "uq_simulation_evidence_source": "source_id",
    "uq_relationship_event_source": "source_fingerprint",
    "uq_world_persona_source": "source_ref",
    "uq_world_relationship": "relationship_type",
}
NULL_REPAIR_COLUMNS = {
    "uq_simulation_sessions_legacy_log_id": "legacy_log_id",
}
ROUND_REPAIR_COLUMNS = {
    "uq_group_round": "round_number",
    "uq_world_simulation_round": "round_number",
}
ARCHIVE_AND_DELETE = {
    "uq_event_message",
}
ARCHIVE_TABLE = "v07_migration_duplicate_archive"


def _signature(columns: tuple[str, ...], unique: bool) -> tuple[tuple[str, ...], bool]:
    return columns, unique


def _quoted(bind: sa.Connection, identifier: str) -> str:
    return bind.dialect.identifier_preparer.quote(identifier)


def _duplicate_groups(
    bind: sa.Connection, table: str, columns: tuple[str, ...]
) -> list[tuple[object, ...]]:
    quoted_table = _quoted(bind, table)
    quoted_columns = ", ".join(_quoted(bind, column) for column in columns)
    not_null = " AND ".join(
        f"{_quoted(bind, column)} IS NOT NULL" for column in columns
    )
    statement = sa.text(
        f"SELECT {quoted_columns} FROM {quoted_table} "
        f"WHERE {not_null} GROUP BY {quoted_columns} HAVING COUNT(*) > 1"
    )
    return [tuple(row) for row in bind.execute(statement)]


def _matching_rows(
    bind: sa.Connection,
    table: str,
    columns: tuple[str, ...],
    values: tuple[object, ...],
) -> list[dict[str, object]]:
    predicates = " AND ".join(
        f"{_quoted(bind, column)} = :value_{position}"
        for position, column in enumerate(columns)
    )
    parameters = {f"value_{position}": value for position, value in enumerate(values)}
    result = bind.execute(
        sa.text(
            f"SELECT * FROM {_quoted(bind, table)} WHERE {predicates} "
            f"ORDER BY {_quoted(bind, 'id')}"
        ),
        parameters,
    )
    return [dict(row._mapping) for row in result]


def _ensure_archive_table(bind: sa.Connection) -> None:
    op.execute(sa.text(
        f'CREATE TABLE IF NOT EXISTS "{ARCHIVE_TABLE}" ('
        '"id" VARCHAR(255) PRIMARY KEY, '
        '"index_name" VARCHAR(128) NOT NULL, '
        '"table_name" VARCHAR(128) NOT NULL, '
        '"row_id" VARCHAR(255) NOT NULL, '
        '"row_json" TEXT NOT NULL)'
    ))


def _archive_row(
    bind: sa.Connection, index_name: str, table: str, row: dict[str, object]
) -> None:
    _ensure_archive_table(bind)
    row_id = str(row["id"])
    archive_id = f"{index_name}:{row_id}"
    bind.execute(
        sa.text(
            f'INSERT INTO "{ARCHIVE_TABLE}" '
            '("id", "index_name", "table_name", "row_id", "row_json") '
            'VALUES (:id, :index_name, :table_name, :row_id, :row_json)'
        ),
        {
            "id": archive_id,
            "index_name": index_name,
            "table_name": table,
            "row_id": row_id,
            "row_json": json.dumps(row, ensure_ascii=False, default=str, sort_keys=True),
        },
    )


def _unique_text_value(
    bind: sa.Connection, table: str, column: str, original: object, row_id: object
) -> str:
    base = str(original)
    marker = f"legacy-{row_id}"
    reflected = next(
        item for item in sa.inspect(bind).get_columns(table) if item["name"] == column
    )
    max_length = getattr(reflected["type"], "length", None)

    def candidate_for(suffix: str) -> str:
        if column == "email" and "@" in base:
            local, domain = base.rsplit("@", 1)
            affix = f"+{marker}{suffix}"
            if max_length:
                local = local[: max(0, max_length - len(domain) - len(affix) - 1)]
            return f"{local}{affix}@{domain}"
        affix = f"~{marker}{suffix}"
        prefix = base[: max(0, max_length - len(affix))] if max_length else base
        return f"{prefix}{affix}"

    candidate = candidate_for("")
    suffix = 1
    while bind.scalar(
        sa.text(
            f"SELECT 1 FROM {_quoted(bind, table)} "
            f"WHERE {_quoted(bind, column)} = :candidate LIMIT 1"
        ),
        {"candidate": candidate},
    ):
        suffix += 1
        candidate = candidate_for(f"-{suffix}")
    return candidate


def _repair_unique_conflicts(
    bind: sa.Connection, index_name: str, table: str, columns: tuple[str, ...]
) -> None:
    for values in _duplicate_groups(bind, table, columns):
        rows = _matching_rows(bind, table, columns, values)
        # The lexicographically smallest primary key remains canonical.
        for row in rows[1:]:
            _archive_row(bind, index_name, table, row)
            row_id = row["id"]
            if index_name in ARCHIVE_AND_DELETE:
                bind.execute(
                    sa.text(
                        f"DELETE FROM {_quoted(bind, table)} "
                        f"WHERE {_quoted(bind, 'id')} = :row_id"
                    ),
                    {"row_id": row_id},
                )
                continue
            if index_name in NULL_REPAIR_COLUMNS:
                repair_column = NULL_REPAIR_COLUMNS[index_name]
                new_value: object = None
            elif index_name in ROUND_REPAIR_COLUMNS:
                repair_column = ROUND_REPAIR_COLUMNS[index_name]
                scope_columns = tuple(column for column in columns if column != repair_column)
                scope_values = tuple(row[column] for column in scope_columns)
                predicates = " AND ".join(
                    f"{_quoted(bind, column)} = :scope_{position}"
                    for position, column in enumerate(scope_columns)
                )
                parameters = {
                    f"scope_{position}": value
                    for position, value in enumerate(scope_values)
                }
                new_value = bind.scalar(
                    sa.text(
                        f"SELECT COALESCE(MAX({_quoted(bind, repair_column)}), 0) + 1 "
                        f"FROM {_quoted(bind, table)} WHERE {predicates}"
                    ),
                    parameters,
                )
            else:
                repair_column = TEXT_REPAIR_COLUMNS[index_name]
                new_value = _unique_text_value(
                    bind, table, repair_column, row[repair_column], row_id
                )
            bind.execute(
                sa.text(
                    f"UPDATE {_quoted(bind, table)} "
                    f"SET {_quoted(bind, repair_column)} = :new_value "
                    f"WHERE {_quoted(bind, 'id')} = :row_id"
                ),
                {"new_value": new_value, "row_id": row_id},
            )


def upgrade() -> None:
    context = op.get_context()
    if context.as_sql:
        for name, table, columns, unique in INDEXES:
            qualifier = "UNIQUE " if unique else ""
            quoted_columns = ", ".join(f'"{column}"' for column in columns)
            op.execute(sa.text(
                f'CREATE {qualifier}INDEX IF NOT EXISTS "{name}" '
                f'ON "{table}" ({quoted_columns})'
            ))
        return

    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    signatures: dict[str, set[tuple[tuple[str, ...], bool]]] = {}
    for table in tables:
        found = {
            _signature(tuple(index["column_names"]), bool(index.get("unique")))
            for index in inspector.get_indexes(table)
            if index.get("column_names")
        }
        found.update(
            _signature(tuple(constraint["column_names"]), True)
            for constraint in inspector.get_unique_constraints(table)
            if constraint.get("column_names")
        )
        signatures[table] = found

    for name, table, columns, unique in INDEXES:
        if table not in tables or _signature(columns, unique) in signatures[table]:
            continue
        if unique:
            _repair_unique_conflicts(op.get_bind(), name, table, columns)
        op.create_index(name, table, list(columns), unique=unique, if_not_exists=True)
        signatures[table].add(_signature(columns, unique))


def downgrade() -> None:
    # Guards are additive and intentionally remain in place on rollback.
    pass
