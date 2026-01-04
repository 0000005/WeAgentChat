import sqlite3
import os
import logging
from alembic import command
from alembic.config import Config
from app.core.config import settings

# Configure logging
logger = logging.getLogger(__name__)

def init_db():
    db_path = os.path.join(settings.DATA_DIR, "doudou.db")
    sql_path = os.path.join(os.path.dirname(__file__), "init.sql")
    
    # 1. Initialize with SQL script if DB is missing (Pre-Alembic State + Seed Data)
    needs_init = not os.path.exists(db_path) or os.path.getsize(db_path) == 0
    
    if needs_init:
        print(f"Initializing database at {db_path}...")
        # Ensure directory exists
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        
        try:
            conn = sqlite3.connect(db_path)
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            conn.executescript(sql_script)
            conn.commit()
            conn.close()
            print("Database initialized successfully with init.sql.")
        except Exception as e:
            print(f"Error initializing database: {e}")
            # If init.sql fails, we probably shouldn't continue to migrations
            return
    else:
        print("Database already exists. Skipping SQL initialization.")

    # 2. Run Alembic Migrations (Upgrade to Head)
    # This applies any schema changes (including the initial diff) and future migrations.
    print("Running Alembic migrations...")
    try:
        # Resolve alembic.ini path relative to project root
        # init_db.py is in app/db/, so project root (server/) is ../../
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        alembic_cfg_path = os.path.join(base_dir, "alembic.ini")
        
        if not os.path.exists(alembic_cfg_path):
            print(f"Warning: alembic.ini not found at {alembic_cfg_path}. Skipping migrations.")
            return

        alembic_cfg = Config(alembic_cfg_path)
        
        # In case we are running from a different directory, we might need to be careful.
        # But generally assuming CWD is server root or close enough for relative paths in ini.
        # If necessary, we can set absolute path for script_location:
        # alembic_cfg.set_main_option("script_location", os.path.join(base_dir, "alembic"))
        
        command.upgrade(alembic_cfg, "head")
        print("Alembic migrations applied successfully.")
        
    except Exception as e:
        print(f"Error running Alembic migrations: {e}")