import uuid
from datetime import datetime
from typing import List, Optional
from app.models.session import SessionData
from app.models.schemas import RegistryEntry
from app.core.state_machine import DebateState
class SessionManager:
    def __init__(self): self._sessions = {}
    def create_session(self, concept_text): session_id = str(uuid.uuid4())[:8]; self._sessions[session_id] = SessionData(session_id=session_id, concept_text=concept_text, created_at=datetime.utcnow(), state=DebateState.AWAITING_INPUT); return session_id
    def get_session(self, session_id): return self._sessions.get(session_id)
    def update_session(self, data): self._sessions[data.session_id] = data
    def list_registry(self): entries=[]; [entries.append(RegistryEntry(session_id=sid, concept_summary=data.concept_text[:50]+("..." if len(data.concept_text)>50 else ""), created_at=data.created_at, status=data.state, final_scores=data.final_scores)) for sid,data in self._sessions.items()]; return sorted(entries, key=lambda x: x.created_at, reverse=True)
    def cleanup_all(self): self._sessions.clear()
session_manager = SessionManager()
