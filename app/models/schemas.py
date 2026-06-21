from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
from app.core.state_machine import DebateState

AgentID = Literal["CEO", "CFO", "CMO"]

class TelemetryScores(BaseModel):
    market_validation: float = Field(ge=0, le=100)
    capital_efficiency: float = Field(ge=0, le=100)
    execution_risk: float = Field(ge=0, le=100)

    class Config:
        arbitrary_types_allowed = True

class DebateTurnChunk(BaseModel):
    session_id: str
    turn_index: int
    agent_id: AgentID
    chunk_text: str
    is_final_chunk: bool

    class Config:
        arbitrary_types_allowed = True

class DebateTurnComplete(BaseModel):
    session_id: str
    turn_index: int
    agent_id: AgentID
    public_message: str
    internal_thought_log: str
    telemetry_scores: dict  # Changed to dict for v1 compatibility
    state: DebateState

    class Config:
        arbitrary_types_allowed = True

class InterjectionRequest(BaseModel):
    session_id: str
    directive_text: str = Field(min_length=5, max_length=500)

    class Config:
        arbitrary_types_allowed = True

class DebateStartRequest(BaseModel):
    concept_text: str = Field(min_length=10, max_length=2000)

    class Config:
        arbitrary_types_allowed = True

class DebateStartResponse(BaseModel):
    session_id: str
    initial_state: DebateState

    class Config:
        arbitrary_types_allowed = True

class ErrorPayload(BaseModel):
    error_type: str
    message: str
    recoverable: bool

    class Config:
        arbitrary_types_allowed = True

class RegistryEntry(BaseModel):
    session_id: str
    concept_summary: str
    created_at: datetime
    status: DebateState
    final_scores: Optional[dict] = None

    class Config:
        arbitrary_types_allowed = True

class BriefingDocument(BaseModel):
    session_id: str
    markdown_content: str
    generated_at: datetime

    class Config:
        arbitrary_types_allowed = True