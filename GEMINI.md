# DouDouChat Project Context

## Project Overview
**DouDouChat (豆豆)** is an open-source AI role-playing chat application designed to be a lightweight alternative to "DouBao". It focuses on providing a deep companionship experience through **long-term memory** and **multi-modal interaction** (TTS/STT).

## Quick Start

### Frontend
1.  Navigate to `front/`: `cd front`
2.  Install dependencies: `pnpm install`
3.  Run dev server: `pnpm dev`
4.  Access: `http://localhost:5173`

### Backend
1.  Navigate to `server/`: `cd server`
2.  Run server: `venv\Scripts\python -m uvicorn app.main:app --reload`
3.  Access docs: `http://localhost:8000/docs`

## Tech Stack
### Frontend (`front/`)
*   **Framework:** Vue 3.5+ (Composition API)
*   **Build Tool:** Vite 6
*   **Language:** TypeScript 5
*   **Styling:** Tailwind CSS 3.4
*   **UI Components:**
    *   shadcn-vue (Radix Vue based)
    *   ai-elements-vue (AI-native components)
    *   Lucide Vue Next (Icons)
*   **State Management:** Pinia
*   **Routing:** Vue Router
*   **AI Integration:** Vercel AI SDK (`ai` package)
*   **Markdown & Highlighting:** streamdown-vue, shiki
*   **Animations:** motion-v
*   **Diagrams:** @vue-flow

### Backend (`server/`)
*   **Language:** Python 3.11+
*   **Framework:** FastAPI
*   **Agent Framework:** [OpenAI Swarm](https://github.com/openai/openai-agents-python)
*   **Server:** Uvicorn
*   **Database:** SQLite (file: `server/data/doudou.db`) + SQLAlchemy + sqlite-vec (for vector search)
*   **Data Validation:** Pydantic v2
*   **Structure:** Layered Architecture (API -> Service -> Models/Schemas)
*   **API Prefix:** `/api`

### About ai-elements-vue

[ai-elements-vue](https://www.ai-elements-vue.com/) is a component library built on top of [shadcn-vue](https://www.shadcn-vue.com/), specifically designed for building AI-native applications. It provides pre-built, customizable components including:

- **Chat Components**: `conversation`, `message`, `prompt-input`,`more...`
- **Reasoning Display**: `chain-of-thought`, `reasoning`,`more...`
- **Tool Visualization**: `tool`, `confirmation`,`more...`
- **Workflow**: `canvas`, `node`, `edge`,`more...`
- **Utilities**: `code-block`, `loader`, `suggestion`,`more...`
- **More**: check `front/src/components` folder, find more components and uasage.
**GitHub**: [vuepont/ai-elements-vue](https://github.com/vuepont/ai-elements-vue)

**使用文档**: 当需要使用 ai-elements-vue 组件时，必须先调用 `context7` 查询组件的使用方法，然后按照返回的使用方法进行实现。


## Current Status & Structure
The project is currently in the **initialization phase**.
*   **Root Directory:** `E:\workspace\code\DouDouChat`
*   **`front/`**: Empty directory. Intended for the Vue 3 frontend.
*   **`server/`**: FastAPI backend scaffold initialized and running.
    *   `app/main.py`: Entry point.
    *   `app/api/endpoints/`: Route handlers (e.g., `health.py`).
    *   `app/services/`: Business logic layer.
    *   `app/models/`: Database entities (SQLAlchemy).
    *   `app/schemas/`: Data validation models (Pydantic).
    *   `app/core/`: Configuration (Pydantic Settings).
    *   `data/doudou.db`: SQLite database file (initialized).
*   **`dev-docs/`**: Contains development stories and planning documents.
    *   `story01/init-story.md`: Outlines the initial goal: **Frontend only** first, basic chat UI, responsive PC design.

## Development Goals (Story 01)
1.  **Platform:** PC Web (Responsive).
2.  **Scope:** Frontend only (mock data initially, no backend connection yet).
3.  **Features:**
    *   Chat Interface
    *   Session/Conversation Management
    *   Persona Settings (Basic)
    *   LLM Configuration

## Conventions & Notes
*   **Directory Naming:** The physical directories are `front` and `server`, though the `README.md` currently references `frontend` and `backend`. We will likely use `front` and `server` to match the file system or rename them to match the documentation.
*   **Language:** The documentation and primary communication for this project seem to be in Chinese (zh-CN).
*   **pnpm:** The `pnpm` package manager is used for dependency management. It is recommended to use `pnpm` instead of `npm` or `yarn`.
*   **Backend Environment:**
    *   **Virtual Environment:** A virtual environment is located at `server/venv/`.
    *   **Run Server:** Execute `server\venv\Scripts\python -m uvicorn app.main:app --reload` within the `server` directory to start the backend with auto-reload.
    *   **Database Operations:** Use the available `db-util` tools (`list_tables`, `execute_sql`) to inspect and modify the SQLite database.
    *   **Unit Testing:** Run tests using `server\venv\Scripts\python -m pytest server/tests`.

## Getting Started (Current Tasks)
The project scaffold for both frontend and backend is ready.
1.  **Backend Development**:
    *   Define database entities in `server/app/models/`.
    *   Implement chat services and LLM integration.
2.  **Frontend-Backend Integration**:
    *   Connect Vue frontend to FastAPI backend.
    *   Replace mock data with real API calls.
3.  **Advanced Features**:
    *   Implement WebSocket for streaming chat.
    *   Add vector storage for long-term memory.
