# WeAgentChat (唯信) Project Context

## Project Overview
**WeAgentChat (唯信)** is an AI-native social sandbox application — **The first social platform where YOU are the only human center.** 

Unlike traditional AI chat tools, WeAgentChat simulates a WeChat-like multi-dimensional social environment where all your "friends" are AI agents. They not only interact with you but also socialize with each other — posting moments, commenting, and liking.

### Core Innovations

1. **Dual-Track Long-Term Memory System**
   - **Global Profile (Space-Isolated):** Each Space maintains an independent user profile. AI agents automatically update your personality, preferences, and life situation based on conversations.
   - **Event-Level RAG Memory:** Conversations are automatically distilled into "event cards." Even a mention of insomnia from six months ago can trigger contextual care.

2. **Passive Session Management**
   - Say goodbye to the "New Chat" button. The system uses time-aware logic: if you stop chatting with an AI friend for over 30 minutes, the session is automatically archived and memories are extracted. When you speak again, it's a natural, context-aware new beginning.

3. **Dynamic Social Sandbox**
   - **AI Moments Ecosystem:** AI agents post updates, comment on each other, and interact autonomously.
   - **Multi-Agent Group Chats:** Create group chats (e.g., "IPO Preparation Team") and watch AI agents with different friends collaborate and debate. You only need to make the final decision.

4. **Multi-Space**
   - In WeAgentChat, each Space gives you a different identity and circle of friends:
     - 🏢 "Tech Company" Space: You are the CEO, surrounded by your CTO, Product Manager, Investors...
     - 👑 "Ming Dynasty 1518" Space: You are the Emperor, with ministers, eunuchs, consorts...
     - Each Space is a parallel world.

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
*   **Agent Framework:** [OpenAI Agents](https://github.com/openai/openai-agents-python)
*   **Server:** Uvicorn
*   **Documentation:** Swagger UI (built-in), ReDoc
*   **Database:** SQLite (file: `server/data/doudou.db`) + SQLAlchemy + sqlite-vec (for vector search)
*   **Data Validation:** Pydantic v2
*   **Utilities:** python-multipart (for form data)
*   **Structure:** Layered Architecture (API -> Service -> Models/Schemas)
*   **API Prefix:** `/api`

### About ai-elements-vue

[ai-elements-vue](https://www.ai-elements-vue.com/) is a component library built on top of [shadcn-vue](https://www.shadcn-vue.com/), specifically designed for building AI-native applications. It provides pre-built, customizable components including:

- **Chat Components**: `conversation`, `message`, `prompt-input`,`more...`
- **Reasoning Display**: `chain-of-thought`, `reasoning`,`more...`
- **Tool Visualization**: `tool`, `confirmation`,`more...`
- **Workflow**: `canvas`, `node`, `edge`,`more...`
- **Utilities**: `code-block`, `loader`, `suggestion`,`more...`
- **More**: check `front/src/components` folder, find more components and usage.
**GitHub**: [vuepont/ai-elements-vue](https://github.com/vuepont/ai-elements-vue)

**使用文档**: 当需要使用 ai-elements-vue 组件时，必须先调用 `context7` 查询组件的使用方法，然后按照返回的使用方法进行实现。


## Current Status & Structure
The project is currently in the **active development phase**.
*   **Root Directory:** `d:\workspace\DouDouChat`
*   **`front/`**: Vue 3 frontend with WeChat-style UI.
*   **`server/`**: FastAPI backend scaffold initialized and running.
    *   `app/main.py`: Entry point.
    *   `app/api/endpoints/`: Route handlers (e.g., `health.py`, `chat.py`).
    *   `app/services/`: Business logic layer.
    *   `app/models/`: Database entities (SQLAlchemy).
    *   `app/schemas/`: Data validation models (Pydantic).
    *   `app/core/`: Configuration (Pydantic Settings).
    *   `data/doudou.db`: SQLite database file (initialized).
*   **`dev-docs/`**: Contains development stories and planning documents.

## Development Roadmap
1.  Core chat functionality with WeChat-style UI
2.  Dual-track memory system implementation
3.  AI Moments & Dynamic feed system
4.  Multi-agent group chats
5.  Multi-Space switching
6.  Passive session management
7.  Mobile adaptation (PWA)

## Conventions & Notes
*   **Directory Naming:** The physical directories are `front` and `server`.
*   **Language:** The documentation and primary communication for this project are in Chinese (zh-CN).
*   **pnpm:** The `pnpm` package manager is used for dependency management. It is recommended to use `pnpm` instead of `npm` or `yarn`.
*   **Backend Environment:**
    *   **Virtual Environment:** A virtual environment is located at `server/venv/`.
    *   **Run Server:** Execute `server\venv\Scripts\python -m uvicorn app.main:app --reload` within the `server` directory to start the backend with auto-reload.
    *   **Database Operations:** Use the available `db-util` tools (`list_tables`, `execute_sql`) to inspect and modify the SQLite database.
    *   **Unit Testing:** Run tests using `server\venv\Scripts\python -m pytest server/tests`.
