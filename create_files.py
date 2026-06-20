import os

# List of (file_path, file_content) tuples - much safer than a dictionary
files = [
    ("app/main.py", """import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import MODE, DEMO_MODE
from app.routes import debate_routes, registry_routes, briefing_routes
from app.services.session_manager import session_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if DEMO_MODE:
        logger.warning("[WARN] No live API keys detected -- Stratum running in DEMO MODE")
    else:
        logger.info(f"[OK] Stratum running in LIVE mode (provider={MODE})")
    yield
    session_manager.cleanup_all()
    logger.info("Shutdown complete")

app = FastAPI(title="Stratum", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(debate_routes.router, prefix="/api/debate", tags=["debate"])
app.include_router(registry_routes.router, prefix="/api/registry", tags=["registry"])
app.include_router(briefing_routes.router, prefix="/api/briefing", tags=["briefing"])

app.mount("/", StaticFiles(directory="public", html=True), name="public")

@app.get("/")
async def root():
    return {"message": "Stratum API is running. Serve frontend from /public."}
"""),

    ("app/config.py", """import os
from dotenv import load_dotenv

load_dotenv()

CEO_API_KEY = os.getenv("CEO_API_KEY", "")
CFO_API_KEY = os.getenv("CFO_API_KEY", "")
CMO_API_KEY = os.getenv("CMO_API_KEY", "")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

_REQUIRED_KEYS = [CEO_API_KEY, CFO_API_KEY, CMO_API_KEY]
DEMO_MODE = any(not key.strip() for key in _REQUIRED_KEYS)

if DEMO_MODE:
    LLM_PROVIDER = "mock"
    LLM_MODEL = "mock"

MAX_TURNS = 5
BRIEFING_TIMEOUT_SECONDS = 10
MOCK_CHUNK_DELAY_MS = 40
MOCK_CHUNK_SIZE = 4
TELEMETRY_HISTORY_LENGTH = 5
RETRY_TOTAL_ATTEMPTS = 3
RETRY_BACKOFF_BASE = 0.5
"""),

    ("app/core/__init__.py", "# Core package\n"),
    ("app/core/state_machine.py", """from enum import Enum
from typing import List, Dict

class DebateState(str, Enum):
    AWAITING_INPUT = "AWAITING_INPUT"
    CEO_AGENDA = "CEO_AGENDA"
    CFO_ANALYSIS = "CFO_ANALYSIS"
    CMO_COUNTER = "CMO_COUNTER"
    CEO_SYNTHESIS = "CEO_SYNTHESIS"
    CONVERGED = "CONVERGED"
    BRIEFING_READY = "BRIEFING_READY"
    INTERJECTED = "INTERJECTED"
    ERRORED = "ERRORED"

TRANSITIONS: Dict[DebateState, List[DebateState]] = {
    DebateState.AWAITING_INPUT: [DebateState.CEO_AGENDA],
    DebateState.CEO_AGENDA: [DebateState.CFO_ANALYSIS, DebateState.INTERJECTED, DebateState.ERRORED],
    DebateState.CFO_ANALYSIS: [DebateState.CMO_COUNTER, DebateState.INTERJECTED, DebateState.ERRORED],
    DebateState.CMO_COUNTER: [DebateState.CEO_SYNTHESIS, DebateState.INTERJECTED, DebateState.ERRORED],
    DebateState.CEO_SYNTHESIS: [DebateState.CONVERGED, DebateState.INTERJECTED, DebateState.ERRORED],
    DebateState.CONVERGED: [DebateState.BRIEFING_READY, DebateState.ERRORED],
    DebateState.BRIEFING_READY: [DebateState.ERRORED],
    DebateState.INTERJECTED: [DebateState.CEO_AGENDA, DebateState.CFO_ANALYSIS, DebateState.CMO_COUNTER, DebateState.CEO_SYNTHESIS, DebateState.ERRORED],
    DebateState.ERRORED: [],
}

class InvalidStateTransitionError(Exception):
    def __init__(self, from_state: DebateState, to_state: DebateState):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Invalid transition from {from_state} to {to_state}")

def validate_transition(from_state: DebateState, to_state: DebateState) -> bool:
    if to_state not in TRANSITIONS.get(from_state, []):
        raise InvalidStateTransitionError(from_state, to_state)
    return True
"""),

    ("app/core/llm_client.py", """import asyncio
import json
import logging
from typing import AsyncGenerator
import httpx
from app.config import CEO_API_KEY, CFO_API_KEY, CMO_API_KEY, LLM_PROVIDER, LLM_MODEL, RETRY_TOTAL_ATTEMPTS, RETRY_BACKOFF_BASE, DEMO_MODE

logger = logging.getLogger(__name__)
_AGENT_KEY_MAP = {"CEO": CEO_API_KEY, "CFO": CFO_API_KEY, "CMO": CMO_API_KEY}

class LLMClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60.0)

    async def generate_stream(self, agent_id: str, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 800):
        if DEMO_MODE:
            raise RuntimeError("LLMClient called in DEMO_MODE")
        api_key = _AGENT_KEY_MAP.get(agent_id)
        if not api_key:
            raise ValueError(f"No API key configured for agent {agent_id}")

        if LLM_PROVIDER == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            data = {"model": LLM_MODEL, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": temperature, "max_tokens": max_tokens, "stream": True}
        else:
            raise ValueError(f"Unsupported provider: {LLM_PROVIDER}")

        attempt = 0
        while attempt < RETRY_TOTAL_ATTEMPTS:
            try:
                async with self.client.stream("POST", url, headers=headers, json=data) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            payload = line[6:]
                            if payload == "[DONE]": break
                            try:
                                chunk = json.loads(payload)
                                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
                                if delta: yield delta
                            except: continue
                    return
            except Exception as e:
                attempt += 1
                if attempt < RETRY_TOTAL_ATTEMPTS:
                    await asyncio.sleep(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
                else: raise e

    async def close(self): await self.client.aclose()

llm_client = LLMClient()
"""),

    ("app/core/mock_engine.py", """import asyncio
from typing import AsyncGenerator, Tuple
from app.config import MOCK_CHUNK_DELAY_MS, MOCK_CHUNK_SIZE

SAAS_SCRIPT = [
    "CEO: We're launching a vertical SaaS for independent pharmacies. Our initial focus will be inventory management and patient engagement. We'll target 500 pharmacies in year one, with a subscription model at $199/month.",
    "CFO: The financials show a $1.2M burn rate to reach 500 customers. At $199/month, breakeven requires 650 subscribers. We should consider a tiered pricing.",
    "CMO: The market is crowded, but our differentiator is AI-driven predictive restocking. We should highlight that in our messaging.",
    "CEO: Synthesizing: we adopt a two-tier pricing: Basic ($99) and Pro ($199). We'll focus initial sales on 100 beta pharmacies.",
    "CMO: Final convergence: Our AI predictive restocking is the killer feature. We'll partner with a major pharmacy association."
]
SAAS_INTERJECTIONS = {
    "europe": ["CEO: Great insight on Europe. We'll adapt our pricing to EUR99/EUR199 and address GDPR.", "CFO: Budget an extra $200k for legal and localization.", "CMO: We'll run a targeted LinkedIn campaign in the DACH region."],
    "default": ["CEO: Acknowledging. We'll pivot to focus on the core AI engine.", "CFO: This reduces development costs by 30%.", "CMO: We'll re-target our messaging to emphasize speed."]
}
RETAIL_SCRIPT = [
    "CEO: We're launching a direct-to-consumer sustainable fashion brand. We aim for $500k revenue in year one.",
    "CFO: Initial inventory investment is $150k, plus $50k for marketing. We project break-even at $400k revenue.",
    "CMO: The eco-conscious consumer segment is growing 25% annually. We'll use Instagram and TikTok.",
    "CEO: We'll adopt a pre-order model to reduce inventory risk.",
    "CMO: Final convergence: We'll launch with a limited drop to build hype, then expand."
]
RETAIL_INTERJECTIONS = {
    "online": ["CEO: We'll double down on online sales, investing in better UX.", "CFO: This increases marketing spend by $20k but expands reach.", "CMO: We'll run targeted ads on Pinterest."],
    "default": ["CEO: We'll shift our strategy to focus on a niche demographic.", "CFO: This reduces marketing waste.", "CMO: We'll create a dedicated content hub."]
}
FOOD_SCRIPT = [
    "CEO: We're launching a ghost kitchen concept for healthy meal delivery. We target $1M revenue in year two.",
    "CFO: Startup costs: $200k for kitchen equipment, $50k for marketing. We project a 20% net margin.",
    "CMO: The meal delivery market is saturated, but our differentiator is real-time nutrition tracking.",
    "CEO: We'll start with a limited menu to perfect operations.",
    "CFO: Final convergence: With a subscription model, we improve revenue predictability."
]
FOOD_INTERJECTIONS = {
    "delivery": ["CEO: We'll optimize delivery routes using AI.", "CFO: This could increase margins by 5%.", "CMO: We'll market our delivery efficiency."],
    "default": ["CEO: We'll pivot to a more premium positioning.", "CFO: This raises COGS but allows higher price points.", "CMO: We'll build a brand around farm-to-table."]
}
DEFAULT_SCRIPT = SAAS_SCRIPT
DEFAULT_INTERJECTIONS = SAAS_INTERJECTIONS
SCRIPT_MAP = [(["saas","software","cloud","app"], (SAAS_SCRIPT, SAAS_INTERJECTIONS)), (["retail","product","store"], (RETAIL_SCRIPT, RETAIL_INTERJECTIONS)), (["food","restaurant","meal"], (FOOD_SCRIPT, FOOD_INTERJECTIONS))]

def _select_script(concept_text):
    for keywords, script_tuple in SCRIPT_MAP:
        if any(kw in concept_text.lower() for kw in keywords): return script_tuple
    return (DEFAULT_SCRIPT, DEFAULT_INTERJECTIONS)

def _get_pivot_branch(text, interjection_map):
    for keyword, branch in interjection_map.items():
        if keyword in text.lower(): return branch
    return interjection_map["default"]

class MockEngine:
    @staticmethod
    async def generate_stream(agent_id, concept_text, turn_index, prior_transcript, interjection_directive=None, current_state=None):
        script, interjection_map = _select_script(concept_text)
        if interjection_directive:
            branch = _get_pivot_branch(interjection_directive, interjection_map)
            agent_index = {"CEO":0,"CFO":1,"CMO":2}.get(agent_id,0)
            full_text = branch[agent_index] if agent_index < len(branch) else f"{agent_id}: Acknowledging the interjection."
        else:
            full_text = script[turn_index] if turn_index < len(script) else f"{agent_id}: Final convergence."
        for i in range(0, len(full_text), MOCK_CHUNK_SIZE):
            yield full_text[i:i+MOCK_CHUNK_SIZE]
            await asyncio.sleep(MOCK_CHUNK_DELAY_MS / 1000.0)

    @staticmethod
    def get_mock_complete_turn(agent_id, turn_index, concept_text, interjection_directive=None, current_state=None):
        script, interjection_map = _select_script(concept_text)
        if interjection_directive:
            branch = _get_pivot_branch(interjection_directive, interjection_map)
            agent_index = {"CEO":0,"CFO":1,"CMO":2}.get(agent_id,0)
            return branch[agent_index] if agent_index < len(branch) else f"{agent_id}: Acknowledging.", {}
        return script[turn_index] if turn_index < len(script) else f"{agent_id}: Final.", {}
"""),

    ("app/core/telemetry.py", """from pydantic import BaseModel, Field
from typing import List

class TelemetryScores(BaseModel):
    market_validation: float = Field(ge=0, le=100)
    capital_efficiency: float = Field(ge=0, le=100)
    execution_risk: float = Field(ge=0, le=100)

def compute_telemetry(prior_scores, agent_id, turn_index, transcript, concept_text):
    if prior_scores is None:
        return TelemetryScores(market_validation=50.0, capital_efficiency=50.0, execution_risk=50.0)
    base = prior_scores.dict()
    if agent_id == "CEO":
        base["capital_efficiency"] = min(100, base["capital_efficiency"] + 5)
        base["execution_risk"] = min(100, base["execution_risk"] + 3)
    elif agent_id == "CFO":
        base["capital_efficiency"] = min(100, base["capital_efficiency"] + 8)
        base["market_validation"] = max(0, base["market_validation"] - 5)
    elif agent_id == "CMO":
        base["market_validation"] = min(100, base["market_validation"] + 10)
        base["execution_risk"] = max(0, base["execution_risk"] - 5)
    if turn_index > 3:
        base["market_validation"] = (base["market_validation"] + 60) / 2
        base["capital_efficiency"] = (base["capital_efficiency"] + 60) / 2
        base["execution_risk"] = (base["execution_risk"] + 40) / 2
    for key in ["market_validation", "capital_efficiency", "execution_risk"]:
        base[key] = max(0, min(100, base[key]))
    return TelemetryScores(**base)
"""),

    ("app/core/orchestrator.py", """import asyncio
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
                complete = DebateTurnComplete(session_id=session_id, turn_index=session.current_turn_index, agent_id=agent_id, public_message=full_message, internal_thought_log=full_message, telemetry_scores=new_scores, state=session.state)
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
                    yield {"event_type": "briefing_ready", "data": briefing.model_dump()}
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
"""),

    ("app/agents/__init__.py", "from .base_agent import BaseAgent\nfrom .ceo_agent import CEOAgent\nfrom .cfo_agent import CFOAgent\nfrom .cmo_agent import CMOAgent\n"),
    ("app/agents/base_agent.py", "from abc import ABC, abstractmethod\n\nclass BaseAgent(ABC):\n    @abstractmethod\n    def system_prompt(self): pass\n    @abstractmethod\n    def user_prompt(self, concept, transcript, interjection=None): pass\n"),
    ("app/agents/ceo_agent.py", """from .base_agent import BaseAgent\nclass CEOAgent(BaseAgent):\n    def system_prompt(self): return "You are the CEO... decisive, data-driven."\n    def user_prompt(self, concept, transcript, interjection=None):\n        base = f"Concept: {concept}\\n\\nPrior debate transcript:\\n" + "\\n".join(transcript[-5:])\n        if interjection: base += f"\\n\\nInterjection: {interjection}."\n        return base\n"""),
    ("app/agents/cfo_agent.py", """from .base_agent import BaseAgent\nclass CFOAgent(BaseAgent):\n    def system_prompt(self): return "You are the CFO... quantitative, critical."\n    def user_prompt(self, concept, transcript, interjection=None):\n        base = f"Concept: {concept}\\n\\nPrior debate transcript:\\n" + "\\n".join(transcript[-5:])\n        if interjection: base += f"\\n\\nInterjection: {interjection}."\n        return base\n"""),
    ("app/agents/cmo_agent.py", """from .base_agent import BaseAgent\nclass CMOAgent(BaseAgent):\n    def system_prompt(self): return "You are the CMO... market-savvy, persuasive."\n    def user_prompt(self, concept, transcript, interjection=None):\n        base = f"Concept: {concept}\\n\\nPrior debate transcript:\\n" + "\\n".join(transcript[-5:])\n        if interjection: base += f"\\n\\nInterjection: {interjection}."\n        return base\n"""),

    ("app/models/__init__.py", "from .schemas import *\nfrom .session import *\n"),
    ("app/models/schemas.py", """from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, Optional
from datetime import datetime
from app.core.state_machine import DebateState
AgentID = Literal["CEO","CFO","CMO"]
class TelemetryScores(BaseModel): market_validation: float = Field(ge=0,le=100); capital_efficiency: float = Field(ge=0,le=100); execution_risk: float = Field(ge=0,le=100)
class DebateTurnChunk(BaseModel): session_id: str; turn_index: int; agent_id: AgentID; chunk_text: str; is_final_chunk: bool
class DebateTurnComplete(BaseModel): session_id: str; turn_index: int; agent_id: AgentID; public_message: str; internal_thought_log: str; telemetry_scores: TelemetryScores; state: DebateState
class InterjectionRequest(BaseModel): session_id: str; directive_text: str = Field(min_length=5, max_length=500); model_config = ConfigDict(strict=True)
class DebateStartRequest(BaseModel): concept_text: str = Field(min_length=10, max_length=2000); model_config = ConfigDict(strict=True)
class DebateStartResponse(BaseModel): session_id: str; initial_state: DebateState
class ErrorPayload(BaseModel): error_type: str; message: str; recoverable: bool
class RegistryEntry(BaseModel): session_id: str; concept_summary: str; created_at: datetime; status: DebateState; final_scores: Optional[TelemetryScores] = None
class BriefingDocument(BaseModel): session_id: str; markdown_content: str; generated_at: datetime
"""),
    ("app/models/session.py", """from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from app.models.schemas import TelemetryScores, DebateTurnComplete
from app.core.state_machine import DebateState
class SessionData(BaseModel): session_id: str; concept_text: str; created_at: datetime; state: DebateState; transcript: List[DebateTurnComplete] = []; telemetry_history: List[TelemetryScores] = []; final_scores: Optional[TelemetryScores] = None; interjection_directive: Optional[str] = None; current_turn_index: int = 0; max_turns: int = 5; briefing_ready: bool = False; error: Optional[str] = None
"""),

    ("app/services/__init__.py", "from .session_manager import session_manager\nfrom .briefing_generator import generate_briefing\n"),
    ("app/services/session_manager.py", """import uuid
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
"""),
    ("app/services/briefing_generator.py", """from datetime import datetime
from app.models.schemas import BriefingDocument
def generate_briefing(session):
    lines = [f"# Executive Briefing: {session.concept_text[:60]}...", f"**Generated:** {datetime.utcnow().isoformat()}", ""]
    lines.append("## Debate Transcript")
    for turn in session.transcript:
        lines.append(f"**{turn.agent_id} (Turn {turn.turn_index+1}):**"); lines.append(turn.public_message); lines.append("")
    if session.final_scores:
        lines.append("## Final Telemetry Scores"); lines.append(f"- Market Validation: {session.final_scores.market_validation:.1f}/100"); lines.append(f"- Capital Efficiency: {session.final_scores.capital_efficiency:.1f}/100"); lines.append(f"- Execution Risk: {session.final_scores.execution_risk:.1f}/100")
    lines.append("\\n---\\n*This briefing was generated automatically by Stratum.*")
    return BriefingDocument(session_id=session.session_id, markdown_content="\\n".join(lines), generated_at=datetime.utcnow())
"""),

    ("app/routes/__init__.py", ""),
    ("app/routes/debate_routes.py", """import asyncio, json, logging
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
                if payload: yield f"event: {event_type}\\ndata: {json.dumps(payload)}\\n\\n"; await asyncio.sleep(0.05)
        except asyncio.CancelledError: logger.info(f"Cancelled {session_id}")
        except Exception as e: logger.error(f"Error {session_id}: {e}"); yield f"event: error\\ndata: {json.dumps(ErrorPayload(error_type='orchestration_error', message=str(e), recoverable=False).model_dump())}\\n\\n"
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
"""),
    ("app/routes/registry_routes.py", """from fastapi import APIRouter, HTTPException
from app.services.session_manager import session_manager
router = APIRouter()
@router.get("/")
async def list_registry(): return session_manager.list_registry()
@router.get("/{session_id}")
async def get_session_detail(session_id: str):
    session = session_manager.get_session(session_id)
    if not session: raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()
"""),
    ("app/routes/briefing_routes.py", """from fastapi import APIRouter, HTTPException, Response
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
"""),

    ("public/index.html", """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Stratum -- AI Boardroom</title><link rel="stylesheet" href="styles.css"></head>
<body>
<div id="app">
  <header><h1>STRATUM</h1><div id="mode-indicator" class="indicator">LIVE</div></header>
  <div class="grid-container">
    <aside id="registry-panel"><h2>Portfolio</h2><div id="registry-list"></div><button id="new-debate-btn">+ New Strategy</button></aside>
    <main id="warroom"><div id="chat-feed"></div>
      <div id="input-area"><textarea id="concept-input" placeholder="Enter your business concept..." rows="3"></textarea><button id="start-debate-btn">Launch Debate</button><button id="interject-btn" style="display:none;">Interject</button></div>
      <div id="briefing-actions" style="display:none;"><button id="copy-briefing-btn">Copy Briefing</button><button id="download-briefing-btn">Download Briefing</button></div>
    </main>
    <aside id="telemetry-panel"><h2>Telemetry</h2>
      <div class="meter"><label>Market Validation</label><div class="meter-bar"><div id="market-bar" style="width:0%;"></div></div><span id="market-value">0</span></div>
      <div class="meter"><label>Capital Efficiency</label><div class="meter-bar"><div id="capital-bar" style="width:0%;"></div></div><span id="capital-value">0</span></div>
      <div class="meter"><label>Execution Risk</label><div class="meter-bar"><div id="risk-bar" style="width:0%;"></div></div><span id="risk-value">0</span></div>
      <div id="session-status">Standing by</div>
    </aside>
  </div>
  <div id="interject-modal" class="modal" style="display:none;"><div class="modal-content"><span class="close-btn">&times;</span><h2>Course Correction</h2><textarea id="interject-input" placeholder="Type your directive..."></textarea><button id="submit-interject">Submit</button></div></div>
</div>
<script type="module" src="app.js"></script>
</body></html>"""),

    ("public/styles.css", """* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0A0A0C; color:#E0E0E0; font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; height:100vh; overflow:hidden; }
header { background:#16161A; padding:12px 24px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #2A2A30; }
header h1 { font-weight:500; letter-spacing:2px; color:#FFF; font-size:1.4rem; }
.indicator { background:#1FBF75; color:#0A0A0C; padding:4px 12px; border-radius:12px; font-size:0.7rem; font-weight:600; text-transform:uppercase; }
.grid-container { display:grid; grid-template-columns:240px 1fr 300px; height:calc(100vh - 60px); background:#0A0A0C; }
aside { background:#16161A; padding:16px; overflow-y:auto; border-right:1px solid #2A2A30; }
#telemetry-panel { border-right:none; border-left:1px solid #2A2A30; }
main { background:#0A0A0C; padding:16px; display:flex; flex-direction:column; overflow:hidden; }
#registry-list { margin-top:12px; }
.registry-item { background:#1D1D22; padding:10px; margin-bottom:8px; border-radius:6px; cursor:pointer; border-left:3px solid #2D5BFF; font-size:0.85rem; }
.registry-item .summary { font-weight:500; }
.registry-item .status { font-size:0.7rem; color:#888; }
#chat-feed { flex:1; overflow-y:auto; margin-bottom:16px; padding-right:8px; }
.agent-bubble { margin-bottom:12px; padding:12px 16px; border-radius:8px; background:#1D1D22; border-left:4px solid #2D5BFF; animation:glow-pulse 2s infinite; }
.agent-bubble .agent-label { font-weight:600; font-size:0.8rem; margin-bottom:4px; text-transform:uppercase; }
.agent-bubble .agent-text { white-space:pre-wrap; word-break:break-word; }
.agent-bubble.ceo { border-color:#2D5BFF; box-shadow:0 0 12px rgba(45,91,255,0.3); }
.agent-bubble.cfo { border-color:#1FBF75; box-shadow:0 0 12px rgba(31,191,117,0.3); }
.agent-bubble.cmo { border-color:#A855F7; box-shadow:0 0 12px rgba(168,85,247,0.3); }
.agent-bubble.system { border-color:#FBBF24; background:#2A2A22; box-shadow:0 0 12px rgba(251,191,36,0.2); }
@keyframes glow-pulse { 0% { box-shadow:0 0 8px rgba(45,91,255,0.2); } 50% { box-shadow:0 0 20px rgba(45,91,255,0.6); } 100% { box-shadow:0 0 8px rgba(45,91,255,0.2); } }
#input-area { display:flex; gap:8px; flex-wrap:wrap; }
#concept-input { flex:1; background:#1D1D22; border:1px solid #2A2A30; color:#E0E0E0; padding:10px; border-radius:6px; resize:vertical; font-family:inherit; font-size:0.9rem; min-height:60px; }
#concept-input:focus { outline:none; border-color:#2D5BFF; }
button { background:#2D5BFF; border:none; color:white; padding:8px 20px; border-radius:6px; font-weight:600; cursor:pointer; transition:background 0.2s; }
button:hover { background:#1A4ADB; }
#interject-btn { background:#FBBF24; color:#0A0A0C; }
#interject-btn:hover { background:#E5A800; }
#briefing-actions { margin-top:8px; display:flex; gap:8px; }
#briefing-actions button { background:#1FBF75; }
#briefing-actions button:hover { background:#17A35B; }
.meter { margin-bottom:20px; }
.meter label { display:block; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.5px; color:#888; margin-bottom:4px; }
.meter-bar { background:#2A2A30; height:6px; border-radius:4px; overflow:hidden; margin-bottom:4px; }
.meter-bar div { height:100%; width:0%; background:linear-gradient(90deg, #2D5BFF, #A855F7); transition:width 600ms cubic-bezier(0.4,0,0.2,1); border-radius:4px; }
.meter span { font-variant-numeric:tabular-nums; font-size:0.9rem; font-weight:500; }
#session-status { margin-top:20px; font-size:0.8rem; color:#888; border-top:1px solid #2A2A30; padding-top:12px; }
.modal { position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; }
.modal-content { background:#1D1D22; padding:30px; border-radius:12px; width:500px; max-width:90%; position:relative; }
.close-btn { position:absolute; top:12px; right:20px; font-size:1.5rem; cursor:pointer; color:#888; }
.close-btn:hover { color:#fff; }
.modal textarea { width:100%; background:#0A0A0C; border:1px solid #2A2A30; color:#E0E0E0; padding:10px; border-radius:6px; margin:12px 0; resize:vertical; min-height:80px; }
.modal button { background:#FBBF24; color:#0A0A0C; width:100%; }
.modal button:hover { background:#E5A800; }
@media (max-width: 960px) { .grid-container { grid-template-columns:1fr; } #registry-panel { display:none; } #telemetry-panel { display:none; } }
"""),

    ("public/app.js", """import { Registry } from './components/registry.js';
import { WarRoom } from './components/warroom.js';
import { Telemetry } from './components/telemetry.js';

class App {
  constructor() {
    this.registry = new Registry();
    this.warroom = new WarRoom();
    this.telemetry = new Telemetry();
    this.currentSessionId = null;
    this.eventSource = null;
    this.isDebateActive = false;
    window.app = this;

    document.getElementById('start-debate-btn').addEventListener('click', () => this.startDebate());
    document.getElementById('interject-btn').addEventListener('click', () => this.showInterjectModal());
    document.querySelector('.close-btn').addEventListener('click', () => this.hideInterjectModal());
    document.getElementById('submit-interject').addEventListener('click', () => this.submitInterject());
    document.getElementById('copy-briefing-btn').addEventListener('click', () => this.copyBriefing());
    document.getElementById('download-briefing-btn').addEventListener('click', () => this.downloadBriefing());
    document.getElementById('new-debate-btn').addEventListener('click', () => {
      document.getElementById('concept-input').value = '';
      document.getElementById('chat-feed').innerHTML = '';
      this.telemetry.reset();
      this.currentSessionId = null;
      this.closeStream();
    });
    this.registry.poll();
  }

  async startDebate() {
    const concept = document.getElementById('concept-input').value.trim();
    if (!concept) { alert('Please enter a concept.'); return; }
    try {
      const res = await fetch('/api/debate/start', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({concept_text:concept}) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed');
      this.currentSessionId = data.session_id;
      this.isDebateActive = true;
      document.getElementById('interject-btn').style.display = 'inline-block';
      document.getElementById('start-debate-btn').disabled = true;
      this.warroom.clear();
      this.telemetry.reset();
      this.connectStream(data.session_id);
    } catch(e) { alert('Error: '+e.message); }
  }

  connectStream(id) {
    this.closeStream();
    const url = `/api/debate/stream/${id}`;
    this.eventSource = new EventSource(url);
    this.eventSource.addEventListener('chunk', (e) => {
      const payload = JSON.parse(e.data);
      this.warroom.appendChunk(payload);
    });
    this.eventSource.addEventListener('complete', (e) => {
      const payload = JSON.parse(e.data);
      this.warroom.completeTurn(payload);
      this.telemetry.update(payload.telemetry_scores);
    });
    this.eventSource.addEventListener('briefing_ready', (e) => {
      const payload = JSON.parse(e.data);
      this.warroom.showBriefingActions(true);
      this.isDebateActive = false;
      document.getElementById('start-debate-btn').disabled = false;
      document.getElementById('interject-btn').style.display = 'none';
      window._briefingContent = payload.markdown_content;
    });
    this.eventSource.addEventListener('error', (e) => {
      try { const err = JSON.parse(e.data); this.warroom.showSystemMessage('Error: '+err.message); } catch {}
    });
    this.eventSource.onerror = () => { console.warn('SSE error, reconnecting...'); };
  }

  closeStream() { if(this.eventSource) { this.eventSource.close(); this.eventSource = null; } }
  showInterjectModal() { document.getElementById('interject-modal').style.display = 'flex'; }
  hideInterjectModal() { document.getElementById('interject-modal').style.display = 'none'; }
  async submitInterject() {
    const directive = document.getElementById('interject-input').value.trim();
    if(!directive) { alert('Enter directive.'); return; }
    if(!this.currentSessionId) return;
    try {
      const res = await fetch(`/api/debate/interject/${this.currentSessionId}`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({session_id:this.currentSessionId, directive_text:directive}) });
      if(!res.ok) throw new Error('Interjection failed');
      this.warroom.showSystemMessage(`[INTERJECT] Course Correction Injected: "${directive}"`);
      this.hideInterjectModal();
      document.getElementById('interject-input').value = '';
    } catch(e) { alert('Interject error: '+e.message); }
  }
  async copyBriefing() { if(window._briefingContent) { try { await navigator.clipboard.writeText(window._briefingContent); alert('Copied!'); } catch {} } }
  downloadBriefing() { if(this.currentSessionId) window.open(`/api/briefing/${this.currentSessionId}/download`, '_blank'); }
}
const app = new App();
"""),

    ("public/components/registry.js", """export class Registry {
  constructor() { this.pollInterval = null; }
  poll() { this.pollInterval = setInterval(() => this.fetchRegistry(), 5000); this.fetchRegistry(); }
  async fetchRegistry() { try { const res = await fetch('/api/registry'); const data = await res.json(); this.render(data); } catch {} }
  render(entries) {
    const container = document.getElementById('registry-list'); container.innerHTML = '';
    entries.forEach(entry => {
      const div = document.createElement('div'); div.className = 'registry-item';
      div.innerHTML = `<div class="summary">${entry.concept_summary}</div><div class="status">${entry.status} · ${new Date(entry.created_at).toLocaleTimeString()}</div>`;
      div.addEventListener('click', () => this.loadSession(entry.session_id));
      container.appendChild(div);
    });
  }
  async loadSession(id) { try { const res = await fetch(`/api/registry/${id}`); const data = await res.json(); if(window.app) { window.app.warroom.loadTranscript(data.transcript || []); if(data.final_scores) window.app.telemetry.update(data.final_scores); } } catch {} }
}
"""),

    ("public/components/warroom.js", """export class WarRoom {
  constructor() { this.feed = document.getElementById('chat-feed'); this.currentBubble = null; this.currentAgent = null; this.currentTurn = null; this.briefingActions = document.getElementById('briefing-actions'); }
  clear() { this.feed.innerHTML = ''; this.currentBubble = null; this.briefingActions.style.display = 'none'; }
  appendChunk(payload) {
    const { agent_id, chunk_text, turn_index } = payload;
    if(!this.currentBubble || this.currentAgent !== agent_id || this.currentTurn !== turn_index) {
      const bubble = document.createElement('div'); bubble.className = `agent-bubble ${agent_id.toLowerCase()}`;
      bubble.innerHTML = `<div class="agent-label">${agent_id}</div><div class="agent-text"></div>`;
      this.feed.appendChild(bubble); this.currentBubble = bubble; this.currentAgent = agent_id; this.currentTurn = turn_index;
    }
    const textDiv = this.currentBubble.querySelector('.agent-text'); textDiv.textContent += chunk_text; this.feed.scrollTop = this.feed.scrollHeight;
  }
  completeTurn(payload) {}
  showSystemMessage(msg) { const div = document.createElement('div'); div.className = 'agent-bubble system'; div.innerHTML = `<div class="agent-text">${msg}</div>`; this.feed.appendChild(div); this.feed.scrollTop = this.feed.scrollHeight; }
  showBriefingActions(show) { this.briefingActions.style.display = show ? 'flex' : 'none'; }
  loadTranscript(transcript) { this.clear(); transcript.forEach(turn => { const bubble = document.createElement('div'); bubble.className = `agent-bubble ${turn.agent_id.toLowerCase()}`; bubble.innerHTML = `<div class="agent-label">${turn.agent_id}</div><div class="agent-text">${turn.public_message}</div>`; this.feed.appendChild(bubble); }); this.feed.scrollTop = this.feed.scrollHeight; }
}
"""),

    ("public/components/telemetry.js", """export class Telemetry {
  constructor() {
    this.bars = { market: document.getElementById('market-bar'), capital: document.getElementById('capital-bar'), risk: document.getElementById('risk-bar') };
    this.values = { market: document.getElementById('market-value'), capital: document.getElementById('capital-value'), risk: document.getElementById('risk-value') };
    this.status = document.getElementById('session-status');
  }
  reset() { this.update({ market_validation:0, capital_efficiency:0, execution_risk:0 }); this.status.textContent = 'Standing by'; }
  update(scores) {
    const { market_validation, capital_efficiency, execution_risk } = scores;
    this.setBar('market', market_validation); this.setBar('capital', capital_efficiency); this.setBar('risk', execution_risk);
    this.status.textContent = `Live · MV:${Math.round(market_validation)} CE:${Math.round(capital_efficiency)} ER:${Math.round(execution_risk)}`;
  }
  setBar(type, value) { const bar = this.bars[type]; const valSpan = this.values[type]; if(bar) bar.style.width = value + '%'; if(valSpan) valSpan.textContent = Math.round(value); }
}
"""),

    (".env.example", "CEO_API_KEY=sk-xxx\nCFO_API_KEY=sk-xxx\nCMO_API_KEY=sk-xxx\nLLM_PROVIDER=openai\nLLM_MODEL=gpt-3.5-turbo\n"),
    ("requirements.txt", "fastapi==0.111.0\nuvicorn==0.30.0\npython-dotenv==1.0.1\npydantic==2.7.1\nhttpx==0.27.0\n"),
    ("README.md", "# Stratum\nAI Boardroom Engine.\n## Setup\n1. `pip install -r requirements.txt`\n2. Copy `.env.example` to `.env` (optional, skip for demo).\n3. `uvicorn app.main:app --reload --port 8000`\n4. Open `http://localhost:8000`\n"),
    ("run.sh", "#!/bin/bash\nuvicorn app.main:app --reload --port 8000\n"),
]

def create_files():
    for filepath, content in files:
        # Create the directory if it doesn't exist
        dirname = os.path.dirname(filepath)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        # Write the file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created: {filepath}")

if __name__ == "__main__":
    create_files()
    print("\n[SUCCESS] All files created successfully!")
    print("\nNext steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Run the app: uvicorn app.main:app --reload --port 8000")
    print("3. Open your browser and go to: http://localhost:8000")