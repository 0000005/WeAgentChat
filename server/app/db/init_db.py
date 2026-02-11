import sqlite3
import os
import logging
from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.vendor.memobase_server.connectors import init_db as init_memo_db, Session as MemoSession
from app.vendor.memobase_server.models.database import Project as MemoProject
from app.services.memo.constants import DEFAULT_SPACE_ID
from app.services.memo.default_profile_config import get_default_profile_config_yaml

# Configure logging
logger = logging.getLogger(__name__)

def run_migrations(
    alembic_cfg_path: str,
    db_url: str = None,
    tag: str = "main",
    base_dir: str | None = None,
):
    """Generic function to run alembic migrations."""
    logger.info(f"Running Alembic migrations for [{tag}]...")
    try:
        if not os.path.exists(alembic_cfg_path):
            logger.warning(f"alembic.ini not found at {alembic_cfg_path}. Skipping migrations for {tag}.")
            return

        alembic_cfg = Config(alembic_cfg_path)
        script_location = alembic_cfg.get_main_option("script_location")
        if script_location and not os.path.isabs(script_location):
            candidates = []
            cfg_dir = os.path.dirname(alembic_cfg_path)
            candidates.append(os.path.abspath(os.path.join(cfg_dir, script_location)))
            if base_dir:
                candidates.append(os.path.abspath(os.path.join(base_dir, script_location)))

            absolute_script_location = next((path for path in candidates if os.path.exists(path)), None)
            if absolute_script_location:
                alembic_cfg.set_main_option("script_location", absolute_script_location)
            else:
                logger.warning(
                    f"script_location '{script_location}' not found for [{tag}]. Tried: {candidates}"
                )
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
            
            # 1.1 Load core schema
            with open(sql_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            conn.executescript(sql_script)
            
            # 1.2 Load persona templates if the file exists
            persona_sql_path = os.path.join(os.path.dirname(__file__), "init_persona_templates.sql")
            if os.path.exists(persona_sql_path):
                logger.info(f"Loading persona templates from {persona_sql_path}...")
                with open(persona_sql_path, 'r', encoding='utf-8') as f:
                    persona_sql = f.read()
                conn.executescript(persona_sql)
                logger.info("Persona templates loaded successfully.")
            else:
                logger.warning(f"Persona templates SQL file not found at {persona_sql_path}. Skipping.")
                
            conn.commit()
            conn.close()
            logger.info("Main database initialized successfully.")
        except Exception as e:
            logger.error(f"Error initializing main database: {e}")
            # If main init fails, we probably shouldn't continue
            return
    else:
        logger.debug("Main database already exists. Skipping SQL initialization.")

    # --- 2. Run Main Alembic Migrations ---
    main_alembic_cfg = os.path.join(base_dir, "alembic.ini")
    run_migrations(
        main_alembic_cfg,
        settings.SQLALCHEMY_DATABASE_URI,
        tag="main",
        base_dir=base_dir,
    )

    # --- 3. Run Memobase SDK migrations ---
    memo_alembic_cfg = os.path.join(base_dir, "app", "vendor", "memobase_server", "alembic.ini")
    run_migrations(
        memo_alembic_cfg,
        settings.MEMOBASE_DB_URL,
        tag="memobase",
        base_dir=base_dir,
    )

    # --- 4. Initialize Memobase Static Data ---
    logger.info("Initializing Memobase static data...")
    try:
        init_memo_db(settings.MEMOBASE_DB_URL)
        with MemoSession() as session:
            MemoProject.initialize_root_project(session)
            root_project = (
                session.query(MemoProject)
                .filter(MemoProject.project_id == DEFAULT_SPACE_ID)
                .one_or_none()
            )
            if root_project and not (root_project.profile_config or "").strip():
                root_project.profile_config = get_default_profile_config_yaml()
                session.commit()
        logger.info("Memobase static data initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing Memobase static data: {e}")
        # Memobase is critical for memory features, raise to halt startup
        raise

    # --- 5. Initialize System Settings ---
    logger.info("Initializing system settings...")
    try:
        from app.services.settings_service import SettingsService
        SettingsService.initialize_defaults()
        logger.info("System settings initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing system settings: {e}")

    # --- 6. Initialize Voice Timbres ---
    logger.info("Initializing voice timbres...")
    try:
        from app.services.voice_service import VoiceService
        VoiceService.initialize_voices()
        logger.info("Voice timbres initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing voice timbres: {e}")
