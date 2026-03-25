from pydantic import BaseModel, ConfigDict, Field

# ── Constants ────────────────────────────────────────────────────────────────
_MAX_MESSAGE_LENGTH = 10_000  # characters (~2500 tokens)
_MAX_SESSION_ID_LENGTH = 128

# Inbound request payload for the /v1/chat endpoint
class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_SESSION_ID_LENGTH,
        pattern=r"^[a-zA-Z0-9_\-\.]+$",
        description="Alphanumeric session identifier (no special characters).",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=_MAX_MESSAGE_LENGTH,
        description="User prompt text.",
    )

# Metadata returned alongside response
class ChatMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    routed_to: str
    pii_entities_masked: int
    latency_ms: int

# Outbound response payload from the /v1/chat endpoint
class ChatResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    reply: str
    metadata: ChatMetadata
