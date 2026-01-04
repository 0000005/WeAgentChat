# Memobase Server Context

## Project Overview
**Memobase Server** is the backend system for the "Dual-Track Long-Term Memory System" (likely for DouDouChat). It is a FastAPI-based service designed to provide persistent, context-aware memory for LLM applications. It manages user profiles, chat history (blobs), and significant events, using vector embeddings for retrieval.

## Key Features
- **User Memory Management:** persistent storage of user profiles and attributes.
- **Dual-Track Memory:**
    - **Global Profile:** Long-term personality and preference tracking.
    - **Event-Level Memory:** RAG-based retrieval of specific past events ("Event Cards").
- **Blob Storage:** Handles various data types (Chat, Document, Image) as "Blobs".
- **Buffer System:** Temporary storage for incoming data before asynchronous processing and summarization.
- **LLM Integration:** Built-in support for OpenAI and Volcengine for memory processing and summarization.

## Architecture
- **Framework:** FastAPI (Python 3.12+)
- **Database:** PostgreSQL with `pgvector` (via SQLAlchemy).
- **Caching/Queue:** Redis.
- **Package Manager:** `uv` (implied by `uv.lock`) or `pip`.

### Directory Structure
- `api.py`: Application entry point and route definitions.
- `memobase_server/`: Main source code.
    - `api_layer/`: API route handlers (User, Blob, Profile, Project).
    - `controllers/`: Core business logic and orchestration.
    - `models/`: Database models (SQLAlchemy) and Pydantic schemas.
    - `llms/`: LLM provider integrations (OpenAI, Doubao/Volcengine) and Embedding services.
    - `prompts/`: System prompts for memory extraction and summarization.
    - `connectors.py`: Database and Redis connection management.
- `config.yaml.example`: Template for system configuration.
- `alembic.ini`: Database migration configuration.

## Setup & Running

### Prerequisites
- Python 3.12+
- PostgreSQL (with `pgvector` extension)
- Redis

### Installation
1.  **Install Dependencies:**
    ```bash
    uv sync
    # OR
    pip install -e .
    ```
2.  **Configuration:**
    - Copy `config.yaml.example` to `config.yaml` and configure LLM settings.
    - Create a `.env` file (see `.env.example` if available, otherwise check `memobase_server/env.py` for required variables like `DATABASE_URL`, `REDIS_URL`, `OPENAI_API_KEY`).

### Running the Server
```bash
# Development mode
python -m uvicorn api:app --reload --port 8019
```

## Development Conventions
- **Async/Await:** All I/O operations (DB, Redis, LLM) must be asynchronous.
- **Type Hints:** Strict usage of Python type hints and Pydantic models.
- **Error Handling:** Use the custom Promise pattern and `memobase_server.errors`.
- **Instrumentation:** OpenTelemetry is integrated for tracing.

## Key API Endpoints (Prefix: `/api/v1`)
- **Health:** `GET /healthcheck`
- **User:** `POST /users`, `GET /users/{id}`
- **Memory (Blob):** `POST /blobs/insert/{user_id}`
- **Profile:** `GET /users/profile/{user_id}`
- **Context:** `GET /users/context/{user_id}` (Retrieves relevant context for chat)
