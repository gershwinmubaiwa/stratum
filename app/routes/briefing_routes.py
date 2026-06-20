from fastapi import APIRouter, HTTPException, Response
from app.services.session_manager import session_manager
from app.services.briefing_generator import generate_briefing
router = APIRouter()
@router.get("/{session_id}")
async def get_briefing(session_id: str):
    session = session_manager.get_session(session_id)
    if not session: raise HTTPException(status_code=404, detail="Session not found")
    briefing = generate_briefing(session); session.briefing_ready = True; session_manager.update_session(session)
    return briefing.model_dump()
@router.get("/{session_id}/download")
async def download_briefing(session_id: str):
    session = session_manager.get_session(session_id)
    if not session: raise HTTPException(status_code=404, detail="Session not found")
    briefing = generate_briefing(session)
    return Response(content=briefing.markdown_content, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="briefing_{session_id}.md"'})
