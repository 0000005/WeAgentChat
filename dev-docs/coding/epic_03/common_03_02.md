# 全栈实施方案 - 会话列表功能

> **文档说明**: 本文档供 AI 编码助手在独立会话中执行，涵盖从后端数据库查询优化到前端多视图抽屉菜单的完整实现。目标是允许用户在抽屉中查看并切换与特定好友的历史会话。

## 1. 需求全景
### 1.1 业务背景
DouDouChat 采用“被动会话管理”，当对话中断较长时间后会自动归档。用户需要一种方式来回溯这些被归档的消息片段，而不是仅仅看到一个被拉长的时间流。

### 1.2 核心功能点
- **后端支持**: 提供按好友 ID 查询会话列表的 API，返回数据需包含消息预览、消息总数。
- **抽屉内导航**: 在 `ChatDrawerMenu` 中实现二级视图切换（主菜单 ↔ 会话列表）。
- **历史展示**: 按时间倒序排列会话，显示“起始-结束”时间区间。
- **会话切换**: 点击历史会话，`ChatArea` 刷新为该会话的片段，且对于已归档会话进入只读模式。

### 1.3 边界与异常
- **空状态**: 若从未有过对话，显示“暂无历史会话”。
- **只读模式**: 切换到非当前最活跃的会话（或已标记为 `memory_generated` 的会话）时，底部输入框应禁用。

## 2. 预备工作
### 2.1 API 契约设计
- **Endpoint**: `GET /api/chat/friends/{friend_id}/sessions`
- **Response**: `List[SessionListRead]`
  - `id`: number
  - `title`: string
  - `create_time`: datetime
  - `last_message_time`: datetime
  - `message_count`: number (该会话下的消息总数)
  - `last_message_preview`: string (最后一条消息的内容摘要)
  - `is_active`: boolean (是否是当前正在进行的最新会话)

### 2.2 参考文档
- **ui/sheet**: 用于右侧抽屉，需在 `SheetContent` 内控制视图状态。
- **lucide-vue-next**: 使用 `MessageSquare`, `ChevronLeft`, `Clock` 等图标。

## 4. 现状分析
- **后端关键依赖**: 
  - `server/app/models/chat.py`: `ChatSession` 模型已有 `memory_generated` 和 `last_message_time`。
  - `server/app/services/chat_service.py`: 已有 `get_sessions_by_friend` 但缺少统计逻辑。
- **前端关键依赖**: 
  - `front/src/stores/session.ts`: 目前仅支持 `messagesMap`（按好友 ID 存储消息，未区分会话片段）。
  - `front/src/components/ChatDrawerMenu.vue`: 目前是静态菜单。
  - `front/src/components/ChatArea.vue`: 消息渲染逻辑需要感知“只读”状态。

## 5. 核心方案 design
### 5.1 后端逻辑 (Logic & Data)
- **数据层**: 使用 SQLAlchemy 的 `func.count` 和子查询来计算每个 Session 的消息数和检索最后一条消息预览。
- **Schema**: 在 `app/schemas/chat.py` 中新增 `ChatSessionWithStats` (继承自 `ChatSessionRead`)。
- **API**: 在 `app/api/endpoints/chat.py` 中实现路由。

### 5.2 前端交互 (View & State)
- **状态管理 (`session.ts`)**:
  - 新增 `friendSessions`: 存储当前选中好友的所有会话。
  - 新增 `activeSessionId`: 标记当前 `ChatArea` 正在显示的 Session。
  - 修改 `fetchFriendMessages`: 支持传入 `sessionId`。如果缺省，则加载该好友的“最新/活跃会话”或“全量合并历史”（根据业务设定，建议列表点击后加载特定 ID）。
- **UI 设计**: 
  - `ChatDrawerMenu.vue` 中引入 `currentView` 状态 ('menu' | 'sessions')。
  - 'sessions' 视图显示列表，点击 Item 触发 `sessionStore.loadSession(id)`。
- **只读逻辑**: 
  - 若 `activeSessionId` 对应的 Session `is_archived` 为 true，显示 Input 占位符。

## 6. 变更清单
| 序号 | 领域 | 操作类型 | 文件绝对路径 | 变更摘要 |
|:---|:---|:---|:---|:---|
| 1 | 后端 | 修改 | `server/app/schemas/chat.py` | 新增 `ChatSessionReadWithStats` 包含预览和计数 |
| 2 | 后端 | 修改 | `server/app/services/chat_service.py` | 增强 `get_sessions_by_friend` 包含关联统计 |
| 3 | 后端 | 修改 | `server/app/api/endpoints/chat.py` | 新增 `read_friend_sessions` 接口 |
| 4 | 前端 | 修改 | `front/src/api/chat.ts` | 增加 `getFriendSessions` 方法 |
| 5 | 前端 | 修改 | `front/src/stores/session.ts` | 增加 Session 列表管理及按 Session 切换消息的 Action |
| 6 | 前端 | 修改 | `front/src/components/ChatDrawerMenu.vue` | 实现多视图切换及会话列表渲染 |
| 7 | 前端 | 修改 | `front/src/components/ChatArea.vue` | 根据 Session 状态禁用输入框 |

## 7. 分步实施指南 (Atomic Steps)

### 步骤 1: 后端 Schema 与 Service 增强
- **操作文件**: `server/app/schemas/chat.py` 和 `server/app/services/chat_service.py`
- **逻辑描述**: 
  1. 在 Schema 中定义 `ChatSessionReadWithStats`。
  2. 修改 `get_sessions_by_friend`：使用 `db.query(ChatSession, func.count(Message.id), ...)` 进行联表查询，或者在 Service 层遍历结果集手动填充（Session 数量通常不多）。建议使用 Python 聚合以保持逻辑清晰。
- **验证方法**: 写个临时测试脚本或之后通过 Swagger 检查。

### 步骤 2: 后端 API Endpoint 实现
- **操作文件**: `server/app/api/endpoints/chat.py`
- **逻辑描述**: 添加 `@router.get("/friends/{friend_id}/sessions")`，调用步骤 1 的增强方法。
- **验证方法**: 访问 `/docs` 测试该接口是否返回正确的 `message_count` 和 `last_message_preview`。

### 步骤 3: 前端 API 与 Store 更新
- **操作文件**: `front/src/api/chat.ts` 和 `front/src/stores/session.ts`
- **逻辑描述**: 
  1. `api/chat.ts`: 实现 `getFriendSessions(friendId)`。
  2. `stores/session.ts`: 引入 `currentSessions` ref。
  3. 实现 `fetchFriendSessions(friendId)` 和 `loadSpecificSession(sessionId)`。
  4. `loadSpecificSession` 应该清空当前消息并从 `/api/chat/sessions/{id}/messages` 加载。

### 步骤 4: 抽屉菜单 UI 改造 (View Switching)
- **操作文件**: `front/src/components/ChatDrawerMenu.vue`
- **逻辑描述**: 
  1. 引入 `const viewState = ref<'main' | 'sessions'>('main')`。
  2. 当点击“会话列表”菜单项时，设置 `viewState.value = 'sessions'` 并触发 store 加载。
  3. 实现 `SessionListView` 子模板，包含“返回”按钮。
  4. 列表渲染：根据 PRD 样式，显示时间范围、消息数、预览。
- **验证方法**: 手动点击菜单，确认视图能正确切换、加载并显示列表。

### 步骤 5: 聊天区只读模式控制
- **操作文件**: `front/src/components/ChatArea.vue`
- **逻辑描述**: 
  1. 从 `sessionStore` 获取当前 Session 的归档状态（可以通过 `currentSessions` 中匹配到的 ID 获取）。
  2. 如果已归档，禁用 `PromptInput`，并在其上方或内部显示提示文字：“此会话已归档，如需继续请发起新对话”。
- **验证方法**: 切换到旧会话，检查输入框是否禁用。

## 8. 验收标准
- [ ] 能在抽屉中看到过去所有的对话片段。
- [ ] 列表显示最后一条消息（如：用户: 你好）。
- [ ] 点击历史片段，中间聊天区域内容随之更新。
- [ ] 历史片段下输入框不可用。
- [ ] 抽屉内点击“返回”能回到功能菜单。
