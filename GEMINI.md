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

*   **Root Directory:** `e:\workspace\code\DouDouChat`

---

### 🎨 Frontend (`front/`)
Vue 3 frontend implemented with a focus on WeChat's aesthetic.

#### 📁 `src/` (Core Source)
*   **`components/`**: UI logic and views.
    *   `ai-elements/`: AI-native components (Reasoning, Tool, Canvas, etc.) from `ai-elements-vue`.
    *   `ui/`: Base UI primitives (via shadcn-vue, e.g., HoverCard, Dialog, Button).
    *   `ChatArea.vue`: Main message terminal (supports SSE events & reasoning).
    *   `Sidebar.vue`: Session list and search.
    *   `IconSidebar.vue`: Vertical icon menu (WeChat style).
    *   `SettingsDialog.vue`: Management of LLM, Memory, and System settings.
*   **`stores/`**: Pinia state management.
    *   `session.ts`: Chat session buffers, SSE event parsing, and message history.
    *   `friend.ts`: Persona/Friend metadata and state.
    *   `llm.ts` & `embedding.ts`: Global config synchronization with backend.
    *   `settings.ts`: System-wide settings (e.g., memory expiration).
*   **`api/`**: Strongly typed REST & SSE clients.
    *   `chat.ts`, `friend.ts`, `llm.ts`, `embedding.ts`, `settings.ts`.
*   **`composables/`**: Reusable Vue Composition API logic (e.g., `useChat.ts`).
*   **`lib/`**: Utility functions (e.g., `utils.ts` for Tailwind/CSS classes).

#### 📁 Configuration
*   `vite.config.js`, `tailwind.config.js`, `components.json` (shadcn config).

---

### ⚙️ Backend (`server/`)
FastAPI backend with a modular service-oriented architecture.

#### 📁 `app/` (Application Logic)
*   **`api/endpoints/`**: FastAPI routers.
    *   `chat.py`: Real-time SSE streaming.
    *   `profile.py` & `friend.py`: User profile and AI persona management.
    *   `settings.py`: System configuration API.
    *   `llm.py` & `embedding.py`: AI model provider management.
*   **`services/`**: Business logic layer.
    *   `chat_service.py`: LLM orchestration, message persistence, and memory RAG.
    *   `memo/`: Memory system bridge.
        *   `bridge.py`: Interface to the embedded Memobase SDK.
    *   `settings_service.py`: Config defaults and DB persistence.
*   **`models/`**: SQLAlchemy ORM definitions (SQLite target).
    *   `chat.py`, `friend.py`, `system_setting.py`, `llm.py`, `embedding.py`.
*   **`schemas/`**: Pydantic data validation and serialization.
*   **`db/`**: Database initialization (`init_db.py`) and session management.
*   **`utils/`**: Generic backend utilities (e.g., logging, async helpers).
*   **`vendor/`**: Third-party modules embedded as SDKs.
    *   **`memobase_server/`**: The core Memory Engine (Event Extraction, RAG).

#### 📁 Infrastructure
*   **`alembic/`**: Production-ready database migrations.
*   **`data/`**: Storage for `.db` files.
    *   `doudou.db`: Primary application data.
    *   `memobase.db`: Memory/Vector storage.
*   **`logs/`**: Backend log files.
    *   `app.log`: Application runtime logs (rotated daily).
*   **`tests/`**: Pytest suite (e.g., `test_memo_bridge.py`, `test_chat.py`).

---

### 📄 Documentation & Planning (`dev-docs/`)
*   **`userStroy/`**: Business logic and feature requirements (e.g., `passive_session_memory.md`).
*   **`coding/`**: Granular implementation plans (Divided by Epics).
*   **`swagger-api/`**: API definitions (Legacy/Reference).

---

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
    *   **Database Operations:** 使用 `sqlite3` 命令（已配置全局环境变量）直接操作数据库文件（如 `sqlite3 server/data/doudou.db`）。
    *   **Database Migrations (Alembic):**
        *   **Automatic Update:** The server automatically applies the latest migrations on startup (`init_db.py` calls `alembic upgrade head`).
        *   **Generate Migration:** Run `gen_migration.bat` in the project root to generate a new migration script after modifying SQLAlchemy models.
        *   **Manual Operations:** See `server/ALEMBIC_SETUP.md` for detailed Alembic commands.
    *   **UI Design:** **所有的 UI 界面必须高度参考微信 (WeChat) 的视觉风格和交互体验。** 这包括但不限于：
    *   配色方案（如微信绿、浅灰色渐变背景等）。
    *   布局（侧边栏、对话列表、聊天窗口的排布）。
    *   交互细节（点击反馈、对话气泡样式等）。
*   **Unit Testing:** Run tests using `server\venv\Scripts\python -m pytest server/tests`.
*   **Logging:** Backend logs are output to the console and saved to `server/logs/app.log`, with daily rotation and 30-day retention.

---

# Memobase SDK (Memory System)

"双轨长期记忆系统" (Dual-Track Long-Term Memory System) 现在作为嵌入式 SDK 集成在主后端服务中，为 LLM 应用提供持久化、上下文感知的记忆能力。

-   **Integration:** Embedded SDK (`server/app/vendor/memobase_server`)
-   **Runtime:** 主 FastAPI 进程内运行 (Managed by `server/app/main.py` lifespan)
-   **Database:** `server/data/memobase.db` (SQLite + sqlite-vec)
-   **Configuration:** 统一通过主项目 `server/app/core/config.py` 管理

### Configuration (Environment Variables)

需要在 `.env` 或环境变量中配置记忆系统专用的 Key：

*   `MEMOBASE_LLM_API_KEY`: 用于提取记忆的 LLM API Key
*   `MEMOBASE_LLM_BASE_URL`: (可选) LLM Base URL
*   `MEMOBASE_ENABLE_EVENT_EMBEDDING`: 是否启用向量检索 (Default: `True`)
*   `MEMOBASE_EMBEDDING_API_KEY`: 用于向量化的 Embedding API Key
*   `MEMOBASE_EMBEDDING_BASE_URL`: (可选) Embedding Base URL

### Architecture
此模块不再作为独立服务 (`mem-system`) 运行。
*   **Bridge Layer**: `server/app/services/memo/bridge.py` 负责将主配置注入 SDK 并封装调用。
*   **Background Worker**:  主服务启动时自动挂载后台任务，用于异步处理记忆提取和归档。

