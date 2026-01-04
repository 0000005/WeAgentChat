# Switch to SQLite + sqlite-vec

This document outlines the plan to replace the PostgreSQL and pgvector dependency with SQLite and `sqlite-vec`. This change simplifies the local setup and deployment by removing the need for a separate heavy database server.

## Rationale

The current dependency on PostgreSQL is primarily for:
1.  **Vector Search:** Using `pgvector` for embedding similarity.
2.  **JSON Operations:** Using `JSONB` for flexible data storage and querying.
3.  **Data Consistency:** Standard relational database features.

By switching to SQLite with the `sqlite-vec` extension, we can achieve:
*   **Zero-dependency setup:** No external DB process required.
*   **Portability:** The database is a single file.
*   **Performance:** `sqlite-vec` is highly optimized for vector search.

## Implementation Plan

### 1. Update Dependencies (`pyproject.toml`)

*   **Remove:** `psycopg2-binary`, `pgvector`.
*   **Add:** `sqlite-vec`.
*   **Ensure:** `sqlalchemy` and `alembic` remain.

### 2. Update Data Models (`memobase_server/models/database.py`)

SQLite has a more limited set of types compared to PostgreSQL. We need to adjust the SQLAlchemy models:

*   **UUID:** SQLite doesn't have a native UUID type. Use `sqlalchemy.types.String(36)` or `sqlalchemy.types.Uuid` (which stores as binary or string).
*   **JSONB:** Replace `dialects.postgresql.JSONB` with `sqlalchemy.types.JSON`.
*   **Vector:** Replace `pgvector.sqlalchemy.Vector` with a custom implementation or standard `Float` arrays that serialize to the binary format `sqlite-vec` expects (Little Endian Float32 array).
    *   *Note:* `sqlite-vec` usually operates on raw BLOB columns or virtual tables. For a simple integration with SQLAlchemy, we might store embeddings as `BLOB` or `JSON` and use `vec_distance` functions in queries.

### 3. Database Connection & Extension Loading (`memobase_server/connectors.py`)

The connection logic needs to be updated to:
1.  Use the `sqlite:///` driver.
2.  Load the `sqlite-vec` extension immediately after connection.

```python
# Conceptual change in memobase_server/connectors.py
import sqlite3
import sqlite_vec
from sqlalchemy import event

# ... inside get_db_engine or similar setup ...
engine = create_engine("sqlite:///data/memobase.db")

@event.listens_for(engine, "connect")
def load_extensions(dbapi_connection, connection_record):
    dbapi_connection.enable_load_extension(True)
    sqlite_vec.load(dbapi_connection)
    dbapi_connection.enable_load_extension(False)
```

### 4. Vector Search Logic (`memobase_server/controllers/`)

Update `event.py` and `event_gist.py`:

*   **Distance Function:** Replace `UserEvent.embedding.cosine_distance(vec)` with `func.vec_distance_cosine(UserEvent.embedding, serialize_float32(vec))`.
*   **Serialization:** Implement a helper to convert python lists of floats to the binary format `sqlite-vec` requires.

### 5. JSON Filtering Logic

PostgreSQL's `@>` operator (JSON containment) is not available in SQLite.
*   **Replacement:** Use `json_each` in raw SQL fragments or filter in Python if the dataset is small enough (though SQL filtering is preferred).
*   **Alternative:** Flatten critical JSON fields into separate columns if possible.

### 6. Migrations

*   Update `alembic.ini` to point to the SQLite file.
*   Since this is a database switch, existing migrations might be incompatible. It is recommended to clear `migrations/versions` and strictly recreate the initial migration for SQLite.

## Action Items

1.  [ ] Modify `pyproject.toml` and lock files.
2.  [ ] Refactor `memobase_server/models/database.py`.
3.  [ ] Update `memobase_server/connectors.py` to use SQLite and load extension.
4.  [ ] Rewrite search queries in `memobase_server/controllers/event.py`.
5.  [ ] Verify and update `alembic` configuration.
