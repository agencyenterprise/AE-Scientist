"""
Main API router for the AE Scientist

This module aggregates all API routes from individual modules.
"""

from dotenv import load_dotenv
from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.chat_stream import router as chat_stream_router
from app.api.conversations import router as conversations_router
from app.api.files import router as files_router
from app.api.ideas import router as ideas_router
from app.api.llm_defaults import router as llm_defaults_router
from app.api.llm_prompts import router as llm_prompts_router
from app.api.research_pipeline_events import router as rp_events_router
from app.api.research_pipeline_runs import router as rp_runs_router

# Load environment variables first
load_dotenv()

router = APIRouter(prefix="/api")

# Include sub-routers
router.include_router(auth_router)
router.include_router(chat_router)
router.include_router(chat_stream_router)
router.include_router(conversations_router)
router.include_router(files_router)
router.include_router(ideas_router)
router.include_router(llm_defaults_router)
router.include_router(llm_prompts_router)
router.include_router(rp_events_router)
router.include_router(rp_runs_router)
