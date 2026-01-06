import logging
import sys

# 1. 基础日志配置 - 尽量使用 stdout 避免 PowerShell 把日志当成错误流
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True
)

import asyncio
import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# 现在安全地导入业务模块
from app.core.config import settings
from app.api.api import api_router
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.chat_service import check_and_archive_expired_sessions

logger = logging.getLogger(__name__)

# 定义应用实例
app = FastAPI(title=settings.PROJECT_NAME)

# --- 强力日志配置 (必须在 API 加载后，解决 Uvicorn 覆盖问题) ---
def apply_force_logging():
    # 强制修改 Root 级别
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    
    # 强制确保 app 命名空间有 Handler 且不依赖 root 的 propagate (如果 root 还是有问题的话)
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    
    # 清理旧的（可能损坏或错误的）Handlers
    for h in app_logger.handlers[:]:
        app_logger.removeHandler(h)
        
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    app_logger.addHandler(handler)
    app_logger.propagate = False # 独立处理，不依赖 Root
    
    # 同样处理 memobase_server
    memo_logger = logging.getLogger("memobase_server")
    memo_logger.setLevel(logging.INFO)
    memo_logger.disabled = False

    # 关键修复：遍历所有 app.* logger 并解除 disabled 状态
    # Uvicorn log_config 可能会 disable_existing_loggers
    logger_manager = logging.Logger.manager
    for name, logger_obj in logger_manager.loggerDict.items():
        if isinstance(logger_obj, logging.Logger) and (name.startswith("app.") or name == "app"):
            logger_obj.disabled = False
            # 确保它们没有残留的 invalid handlers? 暂时不动 handlers, 依赖 propagate 到 app


apply_force_logging()
# -----------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 再次确保初始化没改掉级别
    apply_force_logging()
    
    # Initialize database
    init_db()
    
    # Initialize Memobase SDK
    from app.services.memo import initialize_memo_sdk
    memo_worker_task = await initialize_memo_sdk()
    
    # 再次确保初始化没改掉级别
    apply_force_logging()
    
    logger.info("Application startup complete. Logging is now set to INFO.")
    
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


# 关联 lifespan
app.router.lifespan_context = lifespan

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
