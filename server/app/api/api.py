from fastapi import APIRouter
from app.api.endpoints import health, llm, friend, chat, friend_template, upload

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(friend.router, prefix="/friends", tags=["friends"])   
api_router.include_router(friend_template.router, prefix="/friend-templates", tags=["friend-templates"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(upload.router, prefix="/upload", tags=["upload"])

from app.api.endpoints import embedding, settings, profile
api_router.include_router(embedding.router, prefix="/embedding-settings", tags=["embedding-settings"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(profile.router, prefix="/memory", tags=["memory"])
