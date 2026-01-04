import sqlite3
import os
import logging
from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.vendor.memobase_server.connectors import init_db as init_memo_db, Session as MemoSession
from app.vendor.memobase_server.models.database import Project as MemoProject

# Configure logging
logger = logging.getLogger(__name__)

def run_migrations(alembic_cfg_path: str, db_url: str = None, tag: str = "main"):
    """Generic function to run alembic migrations."""
    logger.info(f"Running Alembic migrations for [{tag}]...")
    try:
        if not os.path.exists(alembic_cfg_path):
            logger.warning(f"alembic.ini not found at {alembic_cfg_path}. Skipping migrations for {tag}.")
            return

        alembic_cfg = Config(alembic_cfg_path)
        if db_url:
            alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        
        command.upgrade(alembic_cfg, "head")
        logger.info(f"Alembic migrations for [{tag}] applied successfully.")
    except Exception as e:
        logger.error(f"Error running Alembic migrations for [{tag}]: {e}")

def init_db():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.makedirs(settings.DATA_DIR, exist_ok=True)

    # --- 1. Main Database initialization ---
    db_path = os.path.join(settings.DATA_DIR, "doudou.db")
    sql_path = os.path.join(os.path.dirname(__file__), "init.sql")
    
    needs_init = not os.path.exists(db_path) or os.path.getsize(db_path) == 0
    if needs_init:
        logger.info(f"Initializing main database at {db_path}...")
        try:
            conn = sqlite3.connect(db_path)
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            conn.executescript(sql_script)
            conn.commit()
            conn.close()
            logger.info("Main database initialized successfully with init.sql.")
        except Exception as e:
            logger.error(f"Error initializing main database: {e}")
            # If main init fails, we probably shouldn't continue
            return
    else:
        logger.debug("Main database already exists. Skipping SQL initialization.")

    # --- 2. Run Main Alembic Migrations ---
    main_alembic_cfg = os.path.join(base_dir, "alembic.ini")
    run_migrations(main_alembic_cfg, settings.SQLALCHEMY_DATABASE_URI, tag="main")

    # --- 3. Run Memobase SDK migrations ---
    memo_alembic_cfg = os.path.join(base_dir, "app", "vendor", "memobase_server", "alembic.ini")
    run_migrations(memo_alembic_cfg, settings.MEMOBASE_DB_URL, tag="memobase")

    # --- 4. Initialize Memobase Static Data ---
    logger.info("Initializing Memobase static data...")
    try:
        init_memo_db(settings.MEMOBASE_DB_URL)
        with MemoSession() as session:
            MemoProject.initialize_root_project(session)
        logger.info("Memobase static data initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing Memobase static data: {e}")
        # Memobase is critical for memory features, raise to halt startup
        raise