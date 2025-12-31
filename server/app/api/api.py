from fastapi import APIRouter
from app.api.endpoints import health, llm, persona, chat

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(persona.router, prefix="/personas", tags=["personas"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])