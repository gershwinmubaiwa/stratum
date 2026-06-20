from fastapi import APIRouter, HTTPException
from app.services.session_manager import session_manager
router = APIRouter()
@router.get("/")
async def list_registry(): return session_manager.list_registry()
@router.get("/{session_id}")
async def get_session_detail(session_id: str):
    session = session_manager.get_session(session_id)
    if not session: raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()
