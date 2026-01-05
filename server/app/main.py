import asyncio
import logging
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.api import api_router
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.chat_service import check_and_archive_expired_sessions

# 配置日志 - 确保异常能输出到控制台
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database
    init_db()
    
    # Initialize Memobase SDK
    from app.services.memo import initialize_memo_sdk
    memo_worker_task = await initialize_memo_sdk()
    
    # Start Session Archiver Task (Every 1 minute)
    async def run_session_archiver():
        logger.info("Starting session archiver background task...")
        while True:
            try:
                with SessionLocal() as db:
                     count = check_and_archive_expired_sessions(db)
                     if count > 0:
                         logger.info(f"Session archiver: archived {count} expired sessions.")
                await asyncio.sleep(60)  # 1 minute
            except asyncio.CancelledError:
                logger.info("Session archiver task cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in session archiver task: {e}")
                await asyncio.sleep(60)

    archiver_task = asyncio.create_task(run_session_archiver())
    
    yield
    
    # Clean up
    if memo_worker_task:
        memo_worker_task.cancel()
        try:
            await memo_worker_task
        except asyncio.CancelledError:
            pass

    if archiver_task:
        archiver_task.cancel()
        try:
            await archiver_task
        except asyncio.CancelledError:
            pass

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# 全局异常处理器 - 记录完整堆栈
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未处理的异常，打印完整堆栈跟踪"""
    error_trace = traceback.format_exc()
    logger.error(f"Unhandled exception for {request.method} {request.url}:\n{error_trace}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)}
    )

app.include_router(api_router, prefix=settings.API_STR)

@app.get("/")
def root():
    return {"message": "Welcome to DouDouChat API"}
