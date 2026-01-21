import asyncio
import traceback
import logging
import json
from pathlib import Path
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from agents import add_trace_processor, set_trace_processors
from agents.tracing import Trace, Span, TracingProcessor

# 1. 初始日志设置 (尽可能早地配置)
from app.core.logging import setup_logging, refresh_app_logging
setup_logging()

# 安全地导入业务模块
from app.core.config import settings
from app.api.api import api_router
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.chat_service import check_and_archive_expired_sessions

logger = logging.getLogger(__name__)
trace_logger = logging.getLogger("openai.agents.tracing")

def _serialize_span_data(span_data: object):
    if span_data is None:
        return None
    if hasattr(span_data, "export"):
        try:
            return span_data.export()
        except Exception:
            return None
    if hasattr(span_data, "model_dump"):
        try:
            return span_data.model_dump()
        except Exception:
            return None
    if hasattr(span_data, "__dict__"):
        try:
            return dict(span_data.__dict__)
        except Exception:
            return None
    return str(span_data)

def _export_span(span: Span):
    if hasattr(span, "export"):
        try:
            return span.export()
        except Exception:
            return None
    return None

class LocalTraceProcessor(TracingProcessor):
    def on_trace_start(self, trace: Trace) -> None:
        trace_logger.info(json.dumps({
            "event": "trace_start",
            "trace_id": getattr(trace, "trace_id", None),
            "workflow_name": getattr(trace, "workflow_name", None),
        }, ensure_ascii=False, default=str))

    def on_trace_end(self, trace: Trace) -> None:
        trace_logger.info(json.dumps({
            "event": "trace_end",
            "trace_id": getattr(trace, "trace_id", None),
            "workflow_name": getattr(trace, "workflow_name", None),
            "duration_ms": getattr(trace, "duration_ms", None),
        }, ensure_ascii=False, default=str))

    def on_span_start(self, span: Span) -> None:
        trace_logger.info(json.dumps({
            "event": "span_start",
            "trace_id": getattr(span, "trace_id", None),
            "span_id": getattr(span, "span_id", None),
            "parent_id": getattr(span, "parent_id", None),
            "span": _export_span(span),
        }, ensure_ascii=False, default=str))

    def on_span_end(self, span: Span) -> None:
        trace_logger.info(json.dumps({
            "event": "span_end",
            "trace_id": getattr(span, "trace_id", None),
            "span_id": getattr(span, "span_id", None),
            "parent_id": getattr(span, "parent_id", None),
            "duration_ms": getattr(span, "duration_ms", None),
            "span": _export_span(span),
        }, ensure_ascii=False, default=str))

    def shutdown(self) -> None:
        return

    def force_flush(self) -> None:
        return

# Replace default processors to avoid OpenAI cloud export while keeping local traces.
set_trace_processors([])
add_trace_processor(LocalTraceProcessor())

# 定义应用实例
app = FastAPI(title=settings.PROJECT_NAME)

# 添加 CORS 中间件 - 允许任意跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)

# 挂载静态文件目录
uploads_dir = os.path.join(settings.DATA_DIR, "uploads")
os.makedirs(uploads_dir, exist_ok=True)
base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
static_dir = base_dir / "static"
(static_dir / "avatars" / "presets").mkdir(parents=True, exist_ok=True)

app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# 在 API 定义后刷新一次，确保 Logger 被激活
refresh_app_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 在 lifespan 启动时刷新，对抗 Uvicorn 的配置覆盖
    refresh_app_logging()
    
    # Initialize database (SQLAlchemy models and Alembic migrations)
    init_db()
    
    # Initialize Memobase SDK
    from app.services.memo import initialize_memo_sdk
    memo_worker_task = await initialize_memo_sdk()
    
    # 在第三方库初始化完成后再次确保日志配置生效
    refresh_app_logging()
    
    logger.info("Application startup complete. Logging system is active.")
    
    # Start Session Archiver Task (Every 30 seconds)
    async def run_session_archiver():
        logger.info("Starting session archiver background task...")
        # 初始延迟，等待系统完全就绪
        await asyncio.sleep(5)
        
        while True:
            try:
                with SessionLocal() as db:
                     # 1. 检查过期会话并标记（加入队列）
                     count = check_and_archive_expired_sessions(db)
                     if count > 0:
                         logger.info(f"Session archiver: archived {count} expired sessions.")
                     
                     # 2. 消费队列中的记忆生成任务
                     from app.services.chat_service import process_memory_queue
                     await process_memory_queue(db)
                     
                await asyncio.sleep(30)  # 每 30 秒运行一次，提高灵敏度
            except asyncio.CancelledError:
                logger.debug("Session archiver task cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in session archiver task: {e}")
                await asyncio.sleep(30)

    archiver_task = asyncio.create_task(run_session_archiver())
    
    yield
    
    # Clean up tasks
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
    return {"message": "Welcome to WeAgentChat API"}
