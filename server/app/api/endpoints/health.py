from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api import deps
from app.services.llm_service import llm_service
from app.services.embedding_service import embedding_service

router = APIRouter()

@router.get("/health")
def health_check(db: Session = Depends(deps.get_db)):
    llm_config = llm_service.get_active_config(db)
    embedding_config = embedding_service.get_active_setting(db)
    
    return {
        "status": "ok",
        "llm_configured": llm_config is not None,
        "embedding_configured": embedding_config is not None
    }
