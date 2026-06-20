import asyncio
import logging
from app.core.state_machine import DebateState, validate_transition, InvalidStateTransitionError
from app.core.llm_client import llm_client
from app.core.mock_engine import MockEngine
from app.core.telemetry import compute_telemetry
from app.models.schemas import DebateTurnChunk, DebateTurnComplete, ErrorPayload
from app.services.session_manager import session_manager
from app.agents import CEOAgent, CFOAgent, CMOAgent
from app.config import MAX_TURNS

logger = logging.getLogger(__name__)
AGENT_MAP = {DebateState.CEO_AGENDA: ("CEO", CEOAgent()), DebateState.CFO_ANALYSIS: ("CFO", CFOAgent()), DebateState.CMO_COUNTER: ("CMO", CMOAgent()), DebateState.CEO_SYNTHESIS: ("CEO", CEOAgent())}

async def run_debate_orchestration(session_id):
    session = session_manager.get_session(session_id)
    if not session:
        yield {"event_type": "error", "data": ErrorPayload(error_type="session_missing", message="Not found", recoverable=False).model_dump()}
        return
    session.max_turns = MAX_TURNS
    session.current_turn_index = 0

    while session.current_turn_index < MAX_TURNS:
        if session.state == DebateState.INTERJECTED:
            if session.current_turn_index == 0: session.state = DebateState.CEO_AGENDA
            elif session.current_turn_index == 1: session.state = DebateState.CFO_ANALYSIS
            elif session.current_turn_index == 2: session.state = DebateState.CMO_COUNTER
            elif session.current_turn_index == 3: session.state = DebateState.CEO_SYNTHESIS
            else: session.state = DebateState.CONVERGED
            session.interjection_directive = None
            session_manager.update_session(session)

        if session.state in [DebateState.CONVERGED, DebateState.BRIEFING_READY, DebateState.ERRORED]: break

        agent_id, agent_instance = AGENT_MAP.get(session.state, (None, None))
        if not agent_id:
            session.state = DebateState.ERRORED
            yield {"event_type": "error", "data": ErrorPayload(error_type="orchestration", message="Unknown state", recoverable=False).model_dump()}
            break

        transcript = [turn.public_message for turn in session.transcript]
        interjection = session.interjection_directive if session.state != DebateState.INTERJECTED else None
        full_message = ""

        try:
            from app.config import DEMO_MODE
            if DEMO_MODE or session.interjection_directive:
                stream_gen = MockEngine.generate_stream(agent_id, session.concept_text, session.current_turn_index, transcript, interjection)
            else:
                stream_gen = llm_client.generate_stream(agent_id, agent_instance.system_prompt(), agent_instance.user_prompt(session.concept_text, transcript, interjection))

            async for chunk in stream_gen:
                if chunk:
                    yield {"event_type": "chunk", "data": DebateTurnChunk(session_id=session_id, turn_index=session.current_turn_index, agent_id=agent_id, chunk_text=chunk, is_final_chunk=False).model_dump()}
                    full_message += chunk
                    await asyncio.sleep(0.01)

            if full_message:
                new_scores = compute_telemetry(session.final_scores, agent_id, session.current_turn_index, transcript + [full_message], session.concept_text)
                complete = DebateTurnComplete(session_id=session_id, turn_index=session.current_turn_index, agent_id=agent_id, public_message=full_message, internal_thought_log=full_message, telemetry_scores=new_scores.model_dump(), state=session.state)
                session.transcript.append(complete)
                session.final_scores = new_scores
                session.telemetry_history.append(new_scores)

                next_state = [DebateState.CFO_ANALYSIS, DebateState.CMO_COUNTER, DebateState.CEO_SYNTHESIS, DebateState.CONVERGED][session.current_turn_index] if session.current_turn_index < 4 else DebateState.CONVERGED
                if session.current_turn_index + 1 >= MAX_TURNS: next_state = DebateState.CONVERGED

                try:
                    validate_transition(session.state, next_state)
                    session.state = next_state
                except:
                    session.state = DebateState.ERRORED
                    yield {"event_type": "error", "data": ErrorPayload(error_type="state", message="Invalid transition", recoverable=False).model_dump()}
                    session_manager.update_session(session)
                    break

                yield {"event_type": "complete", "data": complete.model_dump()}
                session.current_turn_index += 1
                session_manager.update_session(session)

                if session.state == DebateState.CONVERGED:
                    from app.services.briefing_generator import generate_briefing
                    briefing = generate_briefing(session)
                    session.briefing_ready = True
                    session_manager.update_session(session)
                    yield {"event_type": "briefing_ready", "data": briefing.model_dump(mode='json')}
                    break
            else:
                session.state = DebateState.ERRORED
                yield {"event_type": "error", "data": ErrorPayload(error_type="empty_response", message="Agent returned empty", recoverable=False).model_dump()}
                break

        except Exception as e:
            logger.error(f"Orchestration error: {e}")
            session.state = DebateState.ERRORED
            session_manager.update_session(session)
            yield {"event_type": "error", "data": ErrorPayload(error_type="orchestration", message=str(e), recoverable=False).model_dump()}
            break

    if session.state not in [DebateState.CONVERGED, DebateState.BRIEFING_READY, DebateState.ERRORED]:
        session.state = DebateState.CONVERGED
        session_manager.update_session(session)
        if not session.briefing_ready:
            from app.services.briefing_generator import generate_briefing
            briefing = generate_briefing(session)
            session.briefing_ready = True
            session_manager.update_session(session)
            yield {"event_type": "briefing_ready", "data": briefing.model_dump()}
