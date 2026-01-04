# Alembic Setup

The server has been configured to use **Alembic** for database migrations.

## Changes Made
1.  **Dependencies**: Added `alembic` to `server/requirements.txt` and installed it.
2.  **Configuration**:
    *   Created `server/alembic.ini` and `server/alembic/` directory.
    *   Configured `server/alembic/env.py` to:
        *   Load database URL from `app.core.config.settings`.
        *   Import `app.models.*` to register models with Alembic.
        *   Enable `render_as_batch=True` to support SQLite schema changes (e.g. `ALTER COLUMN`).
    *   **Naming Conventions**: Updated `server/app/db/base.py` to enforce strict naming conventions for constraints (indexes, foreign keys, etc.). This ensures deterministic schema generation and compatibility with SQLite batch migrations.
3.  **Initial Migration**: Generated migration `2cab6e171efe_initial_migration.py`.
    *   This migration aligns the existing SQLite database schema (created by `init.sql`) with the strict SQLAlchemy models (adds correct indexes, fixes column types).
4.  **Auto-Migration**: Updated `server/app/db/init_db.py`.
    *   It now runs `alembic upgrade head` automatically on startup.
    *   It preserves the existing logic to run `init.sql` for fresh installs (to populate seed data).

## How to use
- **Create new migration**:
  ```bash
  cd server
  venv\Scripts\alembic revision --autogenerate -m "description"
  ```
- **Run migrations manually**:
  ```bash
  cd server
  venv\Scripts\alembic upgrade head
  ```
