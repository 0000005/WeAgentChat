# 后端开发文档 - Story 01-02: 会话管理功能

## 1. 需求理解与澄清

### 1.1 核心需求
用户希望在后端实现完整的会话（Session）管理能力。
主要功能点包括：
1.  **新建会话**：创建一个新的会话记录，关联特定的角色（Persona）。
2.  **会话列表**：获取当前所有的会话列表（支持分页）。
3.  **会话详情/消息记录**：获取特定会话内的消息历史（只读）。
4.  **删除会话**：软删除特定会话。
5.  **更新会话**：修改会话标题等信息。

### 1.2 关键功能点
-   **Session CRUD**: 创建、读取列表、修改（标题）、软删除。
-   **Message Read**: 读取会话下的消息列表。
-   **注**：本阶段暂不实现“发送消息”接口，消息的产生和存储可能由后续 Story 或前端逻辑触发后同步。

### 1.3 澄清与假设
-   **关于 LocalStorage**: Story 中提到的 LocalStorage 持久化属于前端实现细节。本后端文档专注于提供对应的服务器端能力。
-   **发送消息**: 暂不实现后端发送消息接口。

## 2. 现状分析

### 2.1 现有代码结构
-   **Models**: `server/app/models/` 下已有 `persona.py`。缺少 `chat.py` 或 `session.py`。
-   **Schemas**: `server/app/schemas/` 下已有 `persona.py`。缺少对应的 Chat 相关 schemas。
-   **API**: `server/app/api/endpoints/` 下已有 `persona.py`。
-   **Database**: SQLite 数据库中已存在 `chat_sessions` 和 `messages` 表。

### 2.2 技术栈
-   **Framework**: FastAPI
-   **ORM**: SQLAlchemy
-   **Validation**: Pydantic v2

## 3. 架构设计

### 3.1 模块划分
我们将创建一个新的业务领域模块 `chat`，包含会话和消息的处理。

-   **Models**: `app/models/chat.py` (包含 `ChatSession` 和 `Message` 类)
-   **Schemas**: `app/schemas/chat.py` (包含 Pydantic 模型)
-   **Service**: `app/services/chat_service.py` (业务逻辑)
-   **API**: `app/api/endpoints/chat.py` (路由处理)

### 3.2 数据流向
1.  **API Layer**: 接收 HTTP 请求 (POST /sessions, GET /sessions, PATCH /sessions, etc.)。
2.  **Service Layer**: 处理业务逻辑。
3.  **ORM Layer**: 操作 `chat_sessions` 和 `messages` 表。
4.  **Database**: 持久化数据。

### 3.3 关键逻辑
-   **创建会话**: 接收 `persona_id`，创建一条 `ChatSession` 记录，`title` 默认为 "新对话"。
-   **更新会话**: 允许更新 `title`。

## 4. 核心技术方案

### 4.1 数据模型 (Models)
在 `app/models/chat.py` 中定义：
-   `ChatSession`: 映射 `chat_sessions` 表。
    -   Relationship: `messages` (one-to-many).
-   `Message`: 映射 `messages` 表。
    -   Relationship: `session` (many-to-one).

### 4.2 数据验证 (Schemas)
在 `app/schemas/chat.py` 中定义：
-   `ChatSessionCreate`: `persona_id` (required), `title` (optional).
-   `ChatSessionUpdate`: `title` (optional).
-   `ChatSessionRead`: 返回完整字段。
-   `MessageRead`: 返回完整字段。

### 4.3 接口设计 (API)
-   `POST /api/chat/sessions`: 创建会话
-   `GET /api/chat/sessions`: 获取会话列表 (支持分页)
-   `PATCH /api/chat/sessions/{session_id}`: 更新会话 (如标题)
-   `DELETE /api/chat/sessions/{session_id}`: 删除会话
-   `GET /api/chat/sessions/{session_id}/messages`: 获取消息历史。

## 5. 变更规划

### 5.1 新增文件
-   `server/app/models/chat.py`
-   `server/app/schemas/chat.py`
-   `server/app/services/chat_service.py`
-   `server/app/api/endpoints/chat.py`

### 5.2 修改文件
-   `server/app/api/api.py`: 注册 `chat` router。

## 6. 开发实施指南

### 6.1 Step 1: 定义 ORM 模型
在 `server/app/models/chat.py` 中实现 `ChatSession` and `Message` 类。

### 6.2 Step 2: 定义 Schemas
在 `server/app/schemas/chat.py` 中创建 Request/Response 模型。增加 `ChatSessionUpdate`。

### 6.3 Step 3: 实现 Service
在 `server/app/services/chat_service.py` 中实现 CRUD 方法。
-   `create_session`
-   `update_session`
-   `get_sessions`
-   `delete_session`
-   `get_messages`: 获取某会话的消息

### 6.4 Step 4: 实现 API
在 `server/app/api/endpoints/chat.py` 中暴露接口，调用 Service。

### 6.5 Step 5: 注册路由
在 `server/app/api/api.py` 中添加 `api_router.include_router(chat.router, prefix="/chat", tags=["chat"])`。
