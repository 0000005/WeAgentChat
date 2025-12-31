# 后端开发文档 - Epic 01 - Story 01-01: 聊天界面核心功能

## 1. 需求理解与澄清

### 核心需求
本 Story 旨在为前端聊天界面提供后端支持，核心是实现消息的发送与接收流程。虽然当前阶段不涉及真实的 LLM 调用，但后端需要建立完整的消息处理链路，包括：
1.  **发送消息**：接收用户输入的消息并持久化存储。
2.  **模拟回复**：后端在接收消息后，生成一条模拟的 AI 回复并存储，以支撑前端的对话体验。
3.  **历史记录**：提供获取会话消息历史的接口。

### 关键功能点
- **消息持久化**：所有用户发送的消息和 AI 回复的消息都必须存入数据库。
- **Mock AI 服务**：在 Service 层实现一个简单的 Mock 逻辑，模拟 AI 回复（例如回显用户发送的内容或固定话术）。
- **API 设计**：提供标准的 RESTful API 供前端调用。

### 澄清事项
- **Mock 策略**：Mock 逻辑将直接在后端 Service 层实现，作为占位符，未来将被真实的 LLM Service 替换。
- **打字效果**：后端仅负责返回完整消息内容（或支持未来的流式扩展），前端 Story 中提到的"打字效果"当前阶段可由前端根据返回的完整文本进行视觉模拟，后端暂不需要实现 SSE (Server-Sent Events) 或 WebSocket。
- **会话上下文**：发送消息时需指定 `session_id`。

## 2. Codebase 现状分析

### 现有架构
- **框架**：FastAPI + SQLAlchemy + Pydantic。
- **模型**：
    - `ChatSession` (models/chat.py): 已存在，包含 `persona_id`, `title` 等字段。
    - `Message` (models/chat.py): 已存在，包含 `role`, `content`, `session_id` 等字段。
- **API**：
    - `endpoints/chat.py` 目前仅包含会话 (Session) 的 CRUD 和消息列表的获取 (`GET /sessions/{id}/messages`)。
    - **缺少**：发送消息的接口 (`POST`).
- **Service**：
    - `services/chat_service.py` 包含会话管理和获取消息列表的逻辑。
    - **缺少**：处理发送消息和生成回复的业务逻辑。

### 数据表状态
数据库表 `chat_sessions` 和 `messages` 已经创建，且结构符合需求，无需修改。

## 3. 代码实现思路

### 架构设计
遵循现有的 `API -> Service -> DB` 分层架构。

1.  **API Layer (`endpoints/chat.py`)**:
    - 新增 `POST /sessions/{session_id}/messages` 接口。
    - 接收用户消息内容，调用 Service 层处理，返回生成的 AI 回复消息（或包含用户消息和 AI 消息的列表）。

2.  **Service Layer (`services/chat_service.py`)**:
    - 新增 `send_message` 方法。
    - **步骤 1**: 创建并保存用户的 `Message` (role='user')。
    - **步骤 2**: (Mock) 生成 AI 回复内容（例如："我收到了你的消息：{user_content}"）。
    - **步骤 3**: 创建并保存 AI 的 `Message` (role='assistant')。
    - **步骤 4**: 返回 AI 的消息对象。

3.  **Schema Layer (`schemas/chat.py`)**:
    - 新增 `MessageCreate` 模型，用于接收前端发送的消息内容。

### 变更规划

#### 1. 修改 `server/app/schemas/chat.py`
- **新增** `MessageCreate` 类：
  ```python
  class MessageCreate(BaseModel):
      content: str
  ```

#### 2. 修改 `server/app/services/chat_service.py`
- **新增** `send_message` 函数：
  - 参数：`db: Session`, `session_id: int`, `message_in: MessageCreate`
  - 逻辑：
    1. 校验 Session 是否存在。
    2. 实例化 `Message` (User) -> `db.add` -> `db.commit`。
    3. 模拟延迟 (可选，或直接返回)。
    4. 实例化 `Message` (Assistant) -> `db.add` -> `db.commit`。
    5. 返回 Assistant Message。

#### 3. 修改 `server/app/api/endpoints/chat.py`
- **新增** 路由 `POST /sessions/{session_id}/messages`：
  - 依赖 `deps.get_db`。
  - 调用 `chat_service.send_message`。
  - 返回类型 `chat_schemas.MessageRead` (返回 AI 的回复)。

## 4. 开发实施指南

### 步骤 1: 定义 Schema
在 `server/app/schemas/chat.py` 中添加输入模型，确保 API 文档生成的准确性。

### 步骤 2: 实现 Service 逻辑
在 `server/app/services/chat_service.py` 中实现核心业务逻辑。注意处理事务，确保用户消息和 AI 回复都成功写入。
*注：当前阶段 AI 回复为 Mock 数据，建议代码中预留 `# TODO: Integrate with LLM Service` 注释。*

### 步骤 3: 暴露 API 接口
在 `server/app/api/endpoints/chat.py` 中注册路由。

### 步骤 4: 验证
- 使用 Swagger UI (`/docs`) 测试：
  1. 创建一个会话 (`POST /sessions`)。
  2. 向该会话发送消息 (`POST /sessions/{id}/messages`)。
  3. 验证返回结果是否为 AI 回复。
  4. 调用获取消息列表接口 (`GET /sessions/{id}/messages`)，确认数据库中同时存在用户消息和 AI 回复。
