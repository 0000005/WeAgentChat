# 全栈实施方案 - 查找聊天记录功能

> **文档说明**: 本文档供 AI 编码助手在独立会话中执行，涵盖从后端搜索接口到前端搜索视图及消息定位跳转的完整实现。

## 1. 需求全景
### 1.1 业务背景
用户在与 AI 長期交流过程中会产生大量消息。通过“查找聊天记录”功能，用户可以快速定位到历史对话中的特定信息，支持跨会话（包括已归档会话）搜索。

### 1.2 核心功能点
- **搜索入口**: 在聊天详情抽屉菜单中新增“查找”功能。
- **搜索交互**: 切换抽屉内容为搜索视图，支持输入关键词、回车触发、显示 loading。
- **结果展示**: 列表显示匹配的消息片段（关键词高亮）、发送者、时间。显示结果总数。
- **跳转定位**: 点击结果后，抽屉关闭，聊天区域切换到对应会话并自动滚动到该消息，高亮显示 3 秒。

### 1.3 边界与异常
- **空结果**: 显示“未找到相关聊天记录”。
- **跨会话跳转**: 如果消息在归档会话中，点击后需先切换加载该会话的消息。
- **频繁搜索**: 前端应做简单的防抖处理。

## 2. 预备工作
### 2.1 API 契约设计
- **Endpoint**: `GET /api/chat/friends/{friend_id}/search`
- **Query Params**: 
  - `keyword`: `string` (必填)
  - `skip`: `int` (默认 0)
  - `limit`: `int` (默认 100)
- **Response**: `{ items: List[MessageRead], total: int }`
  - 包含 `session_id`, `role`, `content`, `create_time` 等字段。
  - 注意：后端返回完整内容，前端负责计算 snippet 和高亮。

## 3. 现状分析
- **后端现状**:
  - `server/app/models/chat.py`: `Message` 模型已有关联 `friend_id` 和 `session_id`。
  - `server/app/api/endpoints/chat.py`: 已经有基础的消息查询接口。
  - `server/app/services/chat_service.py`: 需要新增基于关键词的过滤逻辑。
- **前端现状**:
  - `front/src/components/ChatDrawerMenu.vue`: 菜单项已定义但未实现 `search` 逻辑。
  - `front/src/components/ChatArea.vue`: 使用 `ai-elements` 的 `Conversation` 渲染消息，可通过控制滚动容器实现定位。
  - `front/src/stores/session.ts`: 存储了消息映射，但在跳转前可能需要同步后端 ID。

## 4. 核心方案设计
### 4.1 后端逻辑 (Logic & Data)
- **Service 层**:
  - 实现 `search_messages_by_friend(db, friend_id, keyword, skip, limit)`。
  - SQL 逻辑：`SELECT * FROM messages WHERE friend_id = :f_id AND content LIKE :keyword AND deleted = 0 ORDER BY create_time DESC`。
  - 返回命中行列表及 `total_count`。
- **API 层**:
  - 导出新路由，确保 `friend_id` 和 `keyword` 参数校验。

### 4.2 前端交互 (View & State)
- **Store 状态**:
  - `sessionStore.highlightMessageId`: 用于跨组件传递跳转指令。
- **UI 设计 (ChatDrawerMenu.vue)**:
  - 增加 `viewState: 'search'`。
  - 搜索框在视图进入时自动 `focus()`。
  - 列表项使用 `v-html` 渲染高亮内容。渲染 snippet（关键词位置前后截取约 35 字）。
  - 支持“返回”按钮切回主菜单。
- **交互逻辑 (ChatArea.vue)**:
  - 给消息外层容器添加 `:id="'msg-' + msg.id"`。
  - 使用 `watch( () => sessionStore.highlightMessageId )`。
  - 当有值时：
    1. `nextTick()` 等待消息列表渲染完成。
    2. 使用 `element.scrollIntoView({ behavior: 'smooth', block: 'center' })`。
    3. 消息气泡匹配 ID 时添加 `pulse-highlight` class。
    4. 3 秒后前端执行 `sessionStore.highlightMessageId = null` 移除高亮态。

## 5. 变更清单清单
| 序号 | 领域 | 操作类型 | 文件绝对路径 | 变更摘要 |
|:---|:---|:---|:---|:---|
| 1 | 后端 | 修改 | `server/app/services/chat_service.py` | 新增 `search_messages_by_friend` 搜索函数 |
| 2 | 后端 | 修改 | `server/app/api/endpoints/chat.py` | 新增 `search_friend_messages` 接口 |
| 3 | 前端 | 修改 | `front/src/api/chat.ts` | 新增 `searchMessages` 接口函数 |
| 4 | 前端 | 修改 | `front/src/stores/session.ts` | 新增 `highlightMessageId` 及 `scrollToMessage` Action |
| 5 | 前端 | 修改 | `front/src/components/ChatDrawerMenu.vue` | 实现搜索视图、防抖搜索及高亮渲染 |
| 6 | 前端 | 修改 | `front/src/components/ChatArea.vue` | 实现消息定位滚动与高亮动画 |

## 6. 分步实施指南 (Atomic Steps)

### 步骤 1: 后端 Service 及 API 扩展
- **操作文件**: `server/app/services/chat_service.py`
- **逻辑描述**:
  - 实现 `search_messages_by_friend(db, friend_id, keyword, skip=0, limit=100)`。
  - 使用 `Message.content.contains(keyword)` 进行查询。
- **操作文件**: `server/app/api/endpoints/chat.py`
- **逻辑描述**:
  - 注册 `GET /friends/{friend_id}/search`。
  - 返回结果格式：`{"items": [...], "total": 12}`。
- **验证方法**: 通过 Swagger Docs (`/docs`) 输入关键词，确认返回包含 `session_id` 的消息列表。

### 步骤 2: 前端 Store 与 API 适配
- **操作文件**: `front/src/api/chat.ts`
- **逻辑描述**: 定义并导出 `searchMessages(friendId, keyword, skip, limit)`。
- **操作文件**: `front/src/stores/session.ts`
- **逻辑描述**:
  - 新增 `highlightMessageId = ref<number | null>(null)`。
  - 新增 Action `scrollToMessage(msgId, sessionId)`:
    - 逻辑：判断 `currentSessionId === sessionId` 且消息已在列表中。
    - 否则：调用 `loadSpecificSession(sessionId)`。
    - 最后：设置 `highlightMessageId.value = msgId`。
- **验证方法**: 修改 Store 变量并触发跳转逻辑，确认状态机运行正确。

### 步骤 3: 搜索 UI 实现 (ChatDrawerMenu.vue)
- **操作文件**: `front/src/components/ChatDrawerMenu.vue`
- **内容设计**:
  - 在 `viewState === 'search'` 视图中，添加带 `ref="searchInput"` 的输入框。利用 `onMounted` 或 `watch` 触发 `searchInput.value.focus()`。
  - 实现 `searchQuery` 的 `watch`，并配合 `lodash-es` 的 `debounce` 触发 API 调用。
  - 渲染结果列表：
    - 片段截取：寻找关键词在 `content` 中的索引，前取 15 字符，后取 20 字符。
    - 高亮替换：`text.replace(keyword, '<span class="text-emerald-500 font-bold">$&</span>')`。
  - 点击结果：调用 `sessionStore.scrollToMessage(...)` 并关闭抽屉。

### 步骤 4: 消息定位与动画实现 (ChatArea.vue)
- **操作文件**: `front/src/components/ChatArea.vue`
- **逻辑描述**:
  - 消息渲染模板添加 `:id="'msg-' + msg.id"`。
  - 添加 `:class="{ 'highlight-target': sessionStore.highlightMessageId === msg.id }"`。
  - 编写 `watch( () => sessionStore.highlightMessageId )`:
    - 若有值，执行 `scrollIntoView`。
    - `setTimeout(() => sessionStore.highlightMessageId = null, 3000)`。
- **样式描述**:
  - 定义 `highlight-target` 的关键帧动画：背景由高亮色平滑过渡到背景色，持续 3s。

## 7. 验收标准
- [ ] 搜索框输入关键词，300ms 后自动触发搜索并显示结果列表。
- [ ] 搜索结果显示匹配总数。
- [ ] 消息片段中关键词呈现高亮（绿色加粗）。
- [ ] 点击搜索结果，抽屉关闭，聊天窗口自动滚动到对应消息。
- [ ] 定位到的消息气泡有明显的渐淡高亮动画。
- [ ] 支持跳转到非当前活跃会话的历史消息中。
