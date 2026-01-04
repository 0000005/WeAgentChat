import os
import asyncio
import sqlite3
import sqlite_vec
from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from .env import LOG
from .models.database import REG, Project, UserEvent, UserEventGist
from .memory_store import LocalMemoryCache

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/memobase.db")
PROJECT_ID = os.getenv("PROJECT_ID")
ADMIN_URL = os.getenv("ADMIN_URL")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

if PROJECT_ID is None:
    LOG.warning(f"PROJECT_ID is not set")
    PROJECT_ID = "default"
LOG.info(f"Project ID: {PROJECT_ID}")

# Ensure database directory exists if using sqlite file
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if db_path and db_path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        LOG.info(f"Ensured database directory exists for: {db_path}")

LOG.info(f"Database URL: {DATABASE_URL}")

# Create an engine
# Note: SQLite connection pooling is different. For simple file-based usage, 
# standard pool is fine.
DB_ENGINE = create_engine(
    DATABASE_URL,
    pool_recycle=300,
    pool_pre_ping=True,
    echo_pool=False,
)

# Load sqlite-vec extension
@event.listens_for(DB_ENGINE, "connect")
def load_extensions(dbapi_connection, connection_record):
    # Ensure we are dealing with a sqlite3 connection
    if isinstance(dbapi_connection, sqlite3.Connection):
        try:
            dbapi_connection.enable_load_extension(True)
            sqlite_vec.load(dbapi_connection)
            dbapi_connection.enable_load_extension(False)
            # LOG.info("sqlite-vec extension loaded successfully") # Verbose logging
        except Exception as e:
            LOG.error(f"Failed to load sqlite-vec extension: {e}")

Session = sessionmaker(bind=DB_ENGINE)


def create_tables():
    REG.metadata.create_all(DB_ENGINE)
    with Session() as session:
        Project.initialize_root_project(session)
        # These checks are now no-ops or logs in the model file, but kept for flow consistency
        UserEvent.check_legal_embedding_dim(session)
        UserEventGist.check_legal_embedding_dim(session)
    LOG.info("Database tables created successfully")


create_tables()


def db_health_check() -> bool:
    try:
        conn = DB_ENGINE.connect()
    except OperationalError as e:
        LOG.error(f"Database connection failed: {e}")
        return False
    else:
        conn.close()
        return True


async def redis_health_check() -> bool:
    # Always true for in-memory
    return True


async def close_connection():
    DB_ENGINE.dispose()
    LOG.info("Connections closed")


def get_redis_client() -> LocalMemoryCache:
    return LocalMemoryCache()


def get_pool_status() -> dict:
    """Get current connection pool status for monitoring."""
    pool = DB_ENGINE.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "total_capacity": pool.size() + pool.overflow(),
        "utilization_percent": (
            round((pool.checkedout() / (pool.size() + pool.overflow())) * 100, 2)
            if (pool.size() + pool.overflow()) > 0
            else 0
        ),
    }


def log_pool_status(operation: str = "unknown"):
    """Log current pool status for debugging."""
    status = get_pool_status()
    if status["utilization_percent"] > 80:  # Log warning if utilization is high
        LOG.warning(
            f"High DB pool utilization after {operation}: "
            f"{status['checked_out']}/{status['total_capacity']} "
            f"({status['utilization_percent']}%) - "
            f"Available: {status['checked_in']}, Overflow: {status['overflow']}"
        )
    # LOG.info(f"[DB pool status] {operation}: {status}")


if __name__ == "__main__":

    async def main():
        try:
            result = await redis_health_check()
            print(result)
        finally:
            await close_connection()

    asyncio.run(main())