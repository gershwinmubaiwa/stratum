from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.models.schemas import TelemetryScores, DebateTurnComplete
from app.core.state_machine import DebateState

class SessionData(BaseModel):
    session_id: str
    concept_text: str
    created_at: datetime
    state: DebateState
    transcript: List[DebateTurnComplete] = []
    telemetry_history: List[dict] = []
    final_scores: Optional[dict] = None
    interjection_directive: Optional[str] = None
    current_turn_index: int = 0
    max_turns: int = 5
    briefing_ready: bool = False
    error: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True