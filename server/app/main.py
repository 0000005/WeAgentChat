from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.api.api import api_router
from app.db.init_db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    init_db()
    yield

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.include_router(api_router, prefix=settings.API_STR)

@app.get("/")
def root():
    return {"message": "Welcome to DouDouChat API"}
