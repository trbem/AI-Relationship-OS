from datetime import datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    persons: Mapped[list["Person"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    profile_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="persons")
    messages: Mapped[list["Message"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    memories: Mapped[list["PersonMemory"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    vectors: Mapped[list["MessageVector"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    simulations: Mapped[list["SimulationLog"]] = relationship(back_populates="person", cascade="all, delete-orphan")
    relationships: Mapped[list["Relationship"]] = relationship(back_populates="person", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("user_id", "person_id", "fingerprint", name="uq_message_fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    person_id: Mapped[str | None] = mapped_column(ForeignKey("persons.id"), index=True, nullable=True)
    sender_name: Mapped[str] = mapped_column(String(255), index=True)
    direction: Mapped[str] = mapped_column(String(32), default="unknown")
    content: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    import_task_id: Mapped[str | None] = mapped_column(
        ForeignKey("import_tasks.id"), nullable=True, index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="messages")
    person: Mapped["Person | None"] = relationship(back_populates="messages")
    vectors: Mapped[list["MessageVector"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class PersonMemory(Base):
    __tablename__ = "person_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), index=True)
    event: Mapped[str] = mapped_column(Text)
    emotion: Mapped[str] = mapped_column(String(64))
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    source_message_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    person: Mapped["Person"] = relationship(back_populates="memories")


class Relationship(Base):
    __tablename__ = "relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    trust: Mapped[float] = mapped_column(Float, default=0.0)
    frequency: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    person: Mapped["Person"] = relationship(back_populates="relationships")


class MessageVector(Base):
    __tablename__ = "message_vectors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), index=True)
    embedding = mapped_column(Vector(1536).with_variant(JSON(), "sqlite"), nullable=True)
    embedding_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    message: Mapped["Message"] = relationship(back_populates="vectors")
    person: Mapped["Person"] = relationship(back_populates="vectors")


class SimulationLog(Base):
    __tablename__ = "simulation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    response_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    person: Mapped["Person"] = relationship(back_populates="simulations")


class SimulationSession(Base):
    __tablename__ = "simulation_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    original_question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    legacy_log_id: Mapped[str | None] = mapped_column(
        ForeignKey("simulation_logs.id"), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    messages: Mapped[list["SimulationMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    scenarios: Mapped[list["CommunicationScenario"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class SimulationMessage(Base):
    __tablename__ = "simulation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("simulation_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(32), default="text")
    content: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["SimulationSession"] = relationship(back_populates="messages")
    evidence_links: Mapped[list["SimulationEvidence"]] = relationship(
        back_populates="simulation_message", cascade="all, delete-orphan"
    )


class SimulationEvidence(Base):
    __tablename__ = "simulation_evidence"
    __table_args__ = (
        UniqueConstraint(
            "simulation_message_id", "source_type", "source_id",
            name="uq_simulation_evidence_source",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    simulation_message_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_messages.id"), index=True
    )
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(36), index=True)
    excerpt: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    simulation_message: Mapped["SimulationMessage"] = relationship(
        back_populates="evidence_links"
    )


class RelationshipEvent(Base):
    __tablename__ = "relationship_events"
    __table_args__ = (
        UniqueConstraint(
            "person_id", "event_type", "source_fingerprint",
            name="uq_relationship_event_source",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    emotion: Mapped[str] = mapped_column(String(64), default="neutral")
    impact_direction: Mapped[str] = mapped_column(String(16), default="neutral")
    impact_strength: Mapped[float] = mapped_column(Float, default=0.5)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    extraction_version: Mapped[str] = mapped_column(String(32), default="rules-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    evidence_links: Mapped[list["RelationshipEventEvidence"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class RelationshipEventEvidence(Base):
    __tablename__ = "relationship_event_evidence"
    __table_args__ = (
        UniqueConstraint("event_id", "message_id", name="uq_event_message"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    event_id: Mapped[str] = mapped_column(ForeignKey("relationship_events.id"), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    event: Mapped["RelationshipEvent"] = relationship(back_populates="evidence_links")


class CommunicationScenario(Base):
    __tablename__ = "communication_scenarios"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(ForeignKey("simulation_sessions.id"), index=True)
    label: Mapped[str] = mapped_column(String(255))
    wording: Mapped[str] = mapped_column(Text)
    timing: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(64), nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["SimulationSession"] = relationship(back_populates="scenarios")


class StrategyReport(Base):
    __tablename__ = "strategy_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("simulation_sessions.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="completed")
    content_markdown: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text)
    evidence_snapshot_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GroupSimulation(Base):
    __tablename__ = "group_simulations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    primary_person_id: Mapped[str] = mapped_column(ForeignKey("persons.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    goal: Mapped[str] = mapped_column(Text)
    participant_ids_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="created")
    round_count: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    rounds: Mapped[list["GroupSimulationRound"]] = relationship(
        back_populates="simulation", cascade="all, delete-orphan"
    )


class GroupSimulationRound(Base):
    __tablename__ = "group_simulation_rounds"
    __table_args__ = (
        UniqueConstraint("simulation_id", "round_number", name="uq_group_round"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    simulation_id: Mapped[str] = mapped_column(ForeignKey("group_simulations.id"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    state_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    simulation: Mapped["GroupSimulation"] = relationship(back_populates="rounds")


class PersonaWorld(Base):
    __tablename__ = "persona_worlds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    theme: Mapped[str | None] = mapped_column(String(255), nullable=True)
    world_type: Mapped[str] = mapped_column(String(32), default="custom")
    source_type: Mapped[str] = mapped_column(String(32), default="manual")
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    world_background: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    personas: Mapped[list["WorldPersona"]] = relationship(
        back_populates="world", cascade="all, delete-orphan"
    )
    relationships: Mapped[list["WorldRelationship"]] = relationship(
        back_populates="world", cascade="all, delete-orphan"
    )
    sources: Mapped[list["WorldSource"]] = relationship(
        back_populates="world", cascade="all, delete-orphan"
    )
    simulations: Mapped[list["WorldSimulation"]] = relationship(
        back_populates="world", cascade="all, delete-orphan"
    )
    events: Mapped[list["WorldEvent"]] = relationship(
        back_populates="world", cascade="all, delete-orphan"
    )


class WorldPersona(Base):
    __tablename__ = "world_personas"
    __table_args__ = (
        UniqueConstraint("world_id", "source_type", "source_ref", name="uq_world_persona_source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    world_id: Mapped[str] = mapped_column(ForeignKey("persona_worlds.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    aliases_json: Mapped[str] = mapped_column(Text, default="[]")
    summary: Mapped[str] = mapped_column(Text)
    traits_json: Mapped[str] = mapped_column(Text, default="[]")
    motivations_json: Mapped[str] = mapped_column(Text, default="[]")
    values_json: Mapped[str] = mapped_column(Text, default="[]")
    abilities_json: Mapped[str] = mapped_column(Text, default="[]")
    communication_json: Mapped[str] = mapped_column(Text, default="[]")
    faction: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    background: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), default="manual")
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    setting_completeness: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    world: Mapped["PersonaWorld"] = relationship(back_populates="personas")


class WorldRelationship(Base):
    __tablename__ = "world_relationships"
    __table_args__ = (
        UniqueConstraint(
            "world_id", "source_persona_id", "target_persona_id", "relationship_type",
            name="uq_world_relationship",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    world_id: Mapped[str] = mapped_column(ForeignKey("persona_worlds.id"), index=True)
    source_persona_id: Mapped[str] = mapped_column(ForeignKey("world_personas.id"), index=True)
    target_persona_id: Mapped[str] = mapped_column(ForeignKey("world_personas.id"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(64))
    directed: Mapped[bool] = mapped_column(Boolean, default=True)
    strength: Mapped[float] = mapped_column(Float, default=0.5)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source_type: Mapped[str] = mapped_column(String(32), default="manual")
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    world: Mapped["PersonaWorld"] = relationship(back_populates="relationships")


class WorldSource(Base):
    __tablename__ = "world_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    world_id: Mapped[str] = mapped_column(ForeignKey("persona_worlds.id"), index=True)
    persona_id: Mapped[str | None] = mapped_column(
        ForeignKey("world_personas.id"), nullable=True, index=True
    )
    relationship_id: Mapped[str | None] = mapped_column(
        ForeignKey("world_relationships.id"), nullable=True, index=True
    )
    source_type: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    accessed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    world: Mapped["PersonaWorld"] = relationship(back_populates="sources")


class WorldImportTask(Base):
    __tablename__ = "world_import_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    world_id: Mapped[str | None] = mapped_column(
        ForeignKey("persona_worlds.id"), nullable=True, index=True
    )
    query: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    stage: Mapped[str] = mapped_column(String(64), default="search")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    requested_limit: Mapped[int] = mapped_column(Integer, default=20)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class WorldSimulation(Base):
    __tablename__ = "world_simulations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    world_id: Mapped[str] = mapped_column(ForeignKey("persona_worlds.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    scenario: Mapped[str] = mapped_column(Text)
    participant_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    round_count: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    setting_completeness: Mapped[float] = mapped_column(Float, default=0.0)
    source_coverage: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    world: Mapped["PersonaWorld"] = relationship(back_populates="simulations")
    rounds: Mapped[list["WorldSimulationRound"]] = relationship(
        back_populates="simulation", cascade="all, delete-orphan"
    )


class WorldSimulationRound(Base):
    __tablename__ = "world_simulation_rounds"
    __table_args__ = (
        UniqueConstraint("simulation_id", "round_number", name="uq_world_simulation_round"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    simulation_id: Mapped[str] = mapped_column(ForeignKey("world_simulations.id"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    state_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    simulation: Mapped["WorldSimulation"] = relationship(back_populates="rounds")


class WorldEvent(Base):
    __tablename__ = "world_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    world_id: Mapped[str] = mapped_column(ForeignKey("persona_worlds.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(String(64), default="derived")
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    source_simulation_id: Mapped[str | None] = mapped_column(
        ForeignKey("world_simulations.id"), nullable=True, index=True
    )
    source_round_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    world: Mapped["PersonaWorld"] = relationship(back_populates="events")


class ImportTask(Base):
    __tablename__ = "import_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(Text)
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    self_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encoding: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(32), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    person_id: Mapped[str | None] = mapped_column(ForeignKey("persons.id"), nullable=True)
    parsed_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
