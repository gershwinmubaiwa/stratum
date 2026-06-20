import logging
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
