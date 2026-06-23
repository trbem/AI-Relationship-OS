from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


class ImportChatResponse(BaseModel):
    status: str = "queued"
    task_id: str
    import_id: str


class ImportTaskResponse(BaseModel):
    task_id: str
    status: str
    stage: str
    progress: int
    filename: str
    file_hash: str
    encoding: str | None
    contact_name: str | None
    person_id: str | None
    parsed_count: int
    imported_count: int
    duplicate_count: int
    attempts: int
    error: str | None


class ChatPreviewMessage(BaseModel):
    sender_name: str
    content: str
    sent_at: str | None


class ChatPreviewResponse(BaseModel):
    filename: str
    format: str
    encoding: str
    input_type: str = "text"
    extraction_method: str = "decode"
    recognized_text: str = ""
    import_candidates: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message_count: int
    sender_names: list[str]
    sample: list[ChatPreviewMessage]


class MessageResponse(BaseModel):
    id: str
    person_id: str | None
    sender_name: str
    direction: str
    content: str
    sent_at: str | None


class SettingsUpdateRequest(BaseModel):
    llm_api_key: str | None = Field(default=None, max_length=512)
    llm_base_url: str | None = Field(default=None, max_length=2048)
    llm_provider: str | None = Field(default=None, max_length=64)
    llm_model: str | None = Field(default=None, max_length=255)
    completion_model: str | None = Field(default=None, max_length=255)
    llm_timeout_seconds: float | None = Field(default=None, ge=5, le=600)
    llm_temperature: float | None = Field(default=None, ge=0, le=2)
    llm_fallback_enabled: bool | None = None
    ollama_base_url: str | None = Field(default=None, max_length=2048)
    ollama_timeout_seconds: float | None = Field(default=None, ge=5, le=600)
    ollama_model: str | None = Field(default=None, max_length=255)
    web_search_api_key: str | None = Field(default=None, max_length=512)
    web_search_base_url: str | None = Field(default=None, max_length=2048)
    web_search_model: str | None = Field(default=None, max_length=255)
    web_search_timeout_seconds: float | None = Field(default=None, ge=10, le=600)
    world_import_search_provider: str | None = Field(default=None, max_length=64)
    data_directory: str | None = Field(default=None, max_length=2048)

    @field_validator("llm_provider")
    @classmethod
    def validate_provider(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"openai_compatible", "ollama"}:
            raise ValueError("llm_provider must be openai_compatible or ollama")
        return normalized

    @field_validator("world_import_search_provider")
    @classmethod
    def validate_world_import_search_provider(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"free_web", "openai_web_search"}:
            raise ValueError(
                "world_import_search_provider must be free_web or openai_web_search"
            )
        return normalized

    @field_validator("llm_base_url", "ollama_base_url", "web_search_base_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return value
        normalized = value.strip()
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("base URL must start with http:// or https://")
        return normalized.rstrip("/")

    @field_validator("llm_model", "completion_model", "ollama_model", "web_search_model")
    @classmethod
    def validate_model(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("model name cannot be empty")
        return normalized


class ConnectionTestRequest(BaseModel):
    llm_api_key: str | None = Field(default=None, max_length=512)
    llm_base_url: str | None = Field(default=None, max_length=2048)
    llm_provider: str | None = Field(default=None, max_length=64)
    llm_model: str | None = Field(default=None, max_length=255)
    llm_timeout_seconds: float | None = Field(default=None, ge=5, le=600)
    llm_temperature: float | None = Field(default=None, ge=0, le=2)
    ollama_base_url: str | None = Field(default=None, max_length=2048)
    ollama_timeout_seconds: float | None = Field(default=None, ge=5, le=600)
    ollama_model: str | None = Field(default=None, max_length=255)
    web_search_api_key: str | None = Field(default=None, max_length=512)
    web_search_base_url: str | None = Field(default=None, max_length=2048)
    web_search_model: str | None = Field(default=None, max_length=255)
    web_search_timeout_seconds: float | None = Field(default=None, ge=10, le=600)

    @field_validator("llm_provider")
    @classmethod
    def validate_provider(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in {"openai_compatible", "ollama"}:
            raise ValueError("llm_provider must be openai_compatible or ollama")
        return normalized

    @field_validator("llm_base_url", "ollama_base_url", "web_search_base_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return value
        normalized = value.strip()
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("base URL must start with http:// or https://")
        return normalized.rstrip("/")

    @field_validator("llm_model", "ollama_model", "web_search_model")
    @classmethod
    def validate_model(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("model name cannot be empty")
        return normalized


class PersonMergeRequest(BaseModel):
    source_person_id: str
    target_person_id: str


class GeneratePersonRequest(BaseModel):
    contact_id: str


class PersonaResponse(BaseModel):
    name: str
    traits: list[str]
    communication: list[str]
    interests: list[str]
    emotion_patterns: list[str]
    keywords: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_note: str


class PersonSummaryResponse(BaseModel):
    id: str
    user_id: str
    name: str
    profile_summary: str | None
    confidence: float | None
    message_count: int
    memory_count: int


class MemoryItemResponse(BaseModel):
    id: str
    event: str
    emotion: str
    importance: float
    source_message_ids: str | None
    timestamp: str | None


class PersonDetailResponse(BaseModel):
    id: str
    user_id: str
    name: str
    profile_summary: str | None
    confidence: float | None
    messages: list[str]
    memories: list[MemoryItemResponse]
    vector_refs: list[str]


class GraphNodeResponse(BaseModel):
    id: str
    name: str
    type: str
    group: str
    weight: float
    emotion: str = "neutral"
    intimacy: float = Field(default=0.0, ge=0.0, le=1.0)
    interaction: int = 0
    trust: float = Field(default=0.0, ge=0.0, le=1.0)
    recent_active: bool = False
    active_score: float = Field(default=0.0, ge=0.0, le=1.0)
    relationship_score: float = 0.0
    hint: str | None = None
    score_components: dict[str, float] = Field(default_factory=dict)
    change_reasons: list[str] = Field(default_factory=list)


class GraphLinkResponse(BaseModel):
    source: str
    target: str
    strength: float = Field(ge=0.0, le=1.0)
    interaction: int = 0
    emotion: str = "neutral"
    width: float = 1.0


class GraphInsightsResponse(BaseModel):
    top_changes: list[str]
    active_count: int
    strongest_tie: str | None
    stress_count: int


class RelationshipGraphResponse(BaseModel):
    nodes: list[GraphNodeResponse]
    links: list[GraphLinkResponse]
    insights: GraphInsightsResponse


class SimulationRequest(BaseModel):
    person_id: str
    question: str


class PredictionOption(BaseModel):
    text: str
    probability: float = Field(ge=0.0, le=1.0)


class SimulationResponse(BaseModel):
    prediction: list[PredictionOption]
    reason: list[str]
    disclaimer: str
