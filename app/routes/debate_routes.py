import asyncio, json, logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import DebateStartRequest, DebateStartResponse, InterjectionRequest, ErrorPayload
from app.services.session_manager import session_manager
from app.core.orchestrator import run_debate_orchestration
from app.core.state_machine import DebateState, validate_transition, InvalidStateTransitionError
logger = logging.getLogger(__name__); router = APIRouter()
@router.post("/start")
async def start_debate(request: DebateStartRequest):
    session_id = session_manager.create_session(request.concept_text); session = session_manager.get_session(session_id)
    try: validate_transition(session.state, DebateState.CEO_AGENDA); session.state = DebateState.CEO_AGENDA; session_manager.update_session(session)
    except InvalidStateTransitionError as e: raise HTTPException(status_code=400, detail=str(e))
    return DebateStartResponse(session_id=session_id, initial_state=session.state)
@router.get("/stream/{session_id}")
async def debate_stream(session_id: str):
    session = session_manager.get_session(session_id)
    if not session: raise HTTPException(status_code=404, detail="Session not found")
    async def event_generator():
        try:
            async for event_data in run_debate_orchestration(session_id):
                event_type = event_data.get("event_type"); payload = event_data.get("data")
                if payload: yield f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"; await asyncio.sleep(0.05)
        except asyncio.CancelledError: logger.info(f"Cancelled {session_id}")
        except Exception as e: logger.error(f"Error {session_id}: {e}"); yield f"event: error\ndata: {json.dumps(ErrorPayload(error_type='orchestration_error', message=str(e), recoverable=False).model_dump())}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
@router.post("/interject/{session_id}")
async def interject_debate(session_id: str, request: InterjectionRequest):
    session = session_manager.get_session(session_id)
    if not session: raise HTTPException(status_code=404, detail="Session not found")
    if session.state in [DebateState.CONVERGED, DebateState.BRIEFING_READY, DebateState.ERRORED]: raise HTTPException(status_code=400, detail="Cannot interject")
    session.interjection_directive = request.directive_text
    try: validate_transition(session.state, DebateState.INTERJECTED); session.state = DebateState.INTERJECTED; session_manager.update_session(session)
    except InvalidStateTransitionError as e: raise HTTPException(status_code=400, detail=str(e))
    return {"status": "accepted"}
