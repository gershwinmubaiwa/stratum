import os
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
MODE = LLM_PROVIDER