# Memobase Server Context

## Project Overview
**Memobase Server** is the backend system for the "Dual-Track Long-Term Memory System" (used in WeAgentChat). It is a FastAPI-based service designed to provide persistent, context-aware memory for LLM applications. It manages user profiles, chat history (blobs), and significant events, using vector embeddings for retrieval.

## Key Features
- **User Memory Management:** Persistent storage of user profiles and attributes.
- **Dual-Track Memory:**
    - **Global Profile:** Long-term personality and preference tracking.
    - **Event-Level Memory:** RAG-based retrieval of specific past events ("Event Cards").
- **Blob Storage:** Handles various data types (Chat, Document, Image) as "Blobs".
- **Buffer System:** Temporary storage for incoming data before asynchronous processing and summarization.
- **LLM Integration:** Built-in support for OpenAI and Volcengine for memory processing and summarization.
- **Vector Search:** High-performance vector similarity search powered by `sqlite-vec`.

## Architecture
- **Framework:** FastAPI (Python 3.12+)
- **Database:** SQLite with `sqlite-vec` extension (via SQLAlchemy).
    - Stores embeddings as binary BLOBs.
    - Uses `vec_distance_cosine` for similarity search.
- **Caching/Queue:** Local process memory storage (Redis dependency removed). Suitable for single-instance deployment.

### Directory Structure
- `api.py`: Application entry point and route definitions.
- `memobase_server/`: Main source code.
    - `api_layer/`: API route handlers (User, Blob, Profile, Project).
    - `controllers/`: Core business logic and orchestration.
    - `models/`: Database models (SQLAlchemy) and Pydantic schemas.
    - `llms/`: LLM provider integrations (OpenAI, Doubao/Volcengine) and Embedding services.
    - `prompts/`: System prompts for memory extraction and summarization.
    - `connectors.py`: Database connection and extension loading.
    - `memory_store.py`: In-memory implementation of cache, queue, and locking.
- `config.yaml`: System configuration (including Embedding API settings).
- `alembic.ini`: Database migration configuration (updated for SQLite).

## Setup & Running

### Prerequisites
- Python 3.12+
- `sqlite-vec` python package (and its C extension)

### Installation
1.  **Install Dependencies:**
    ```bash
    uv sync
    ```
2.  **Configuration:**
    - Copy `config.yaml.example` to `config.yaml` and configure LLM settings.
    - SiliconFlow Embedding is supported (Provider: `openai`, Base URL: `https://api.siliconflow.cn/v1/`).
    - Database path defaults to `sqlite:///data/memobase.db`.

### Running the Server
```bash
# Development mode
python -m uvicorn api:app --reload --port 8019
```

## Development Conventions
- **Async/Await:** All I/O operations (DB, LLM) must be asynchronous.
- **Type Hints:** Strict usage of Python type hints and Pydantic models.
- **UUID Handling:** In SQLite mode, `user_id` and `profile_id` must be explicitly converted to `uuid.UUID` objects before DB queries (use `to_uuid` helper from `utils.py`).
- **Error Handling:** Use the custom Promise pattern and `memobase_server.errors`.
- **Instrumentation:** OpenTelemetry is integrated for tracing.

## Key API Endpoints (Prefix: `/api/v1`)
- **Health:** `GET /healthcheck`
- **User:** `POST /users`, `GET /users/{id}`
- **Memory (Blob):** `POST /blobs/insert/{user_id}`
- **Profile:** `GET /users/profile/{user_id}`
- **Context:** `GET /users/context/{user_id}` (Retrieves relevant context for chat)
- **Event Search:** `GET /users/event/search/{user_id}` (Vector search via `sqlite-vec`)