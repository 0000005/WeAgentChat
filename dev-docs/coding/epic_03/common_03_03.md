# 全栈实施方案 - Story 03-03: 记忆列表功能

> **文档说明**: 本文档供 AI 编码助手在独立会话中执行，涵盖从后端过滤 API 到前端 UI 的完整闭环。

## 1. 需求全景
### 1.1 业务背景
用户希望在抽屉菜单中查看 AI 为当前好友记录的所有重要事件记忆。这些记忆是基于对话内容自动提取的，展示形式为简洁的文字摘要（Gists）。

### 1.2 核心功能点
- **好友维度过滤**: 必须仅展示与当前好友相关的记忆。
- **摘要展示**: 使用 Memobase 的 `event_gists` 数据源。
- **时间范围**: 获取近 365 天内的记忆。
- **状态管理**: 包含加载中、空状态（暂无记忆）和错误重试。

### 1.3 边界与异常
- **标签关联**: 依赖于 `chat_service.py` 在归档时正确设置了 `fields={"friend_id": str(friend_id)}`。
- **数据一致性**: 归档过程是异步的，用户刚结束聊天可能不会立即看到新记忆。

## 2. 预备工作
### 2.1 API 契约设计

**获取指定好友的事件摘要列表**
- **Endpoint**: `GET /api/memory/events_gists`
- **Query Params**:
  - `friend_id`: `int` (必填) - 用于标签过滤
  - `limit`: `int` (可选，默认 50)
- **Response**: 返回 `UserEventGistsData` (SDK 原生模型)
```json
{
  "gists": [
    {
      "id": "uuid",
      "gist_data": { "content": "- 用户提到他最近在学习 Vue3。" },
      "created_at": "2026-01-05T...",
      "updated_at": "..."
    }
  ],
  "events": []
}
```

## 4. 现状分析
- **后端现状**:
  - `server/app/services/memo/bridge.py`: 已有 `MemoService`，但缺少按标签过滤 Gists 的方法。
  - `server/app/vendor/memobase_server/controllers/event.py`: 包含 `filter_user_events` 函数，支持 `event_tag_equal` 过滤。
  - `server/app/api/endpoints/profile.py`: 挂载于 `/api/memory`，是添加新接口的最佳位置。
- **前端现状**:
  - `front/src/components/ChatDrawerMenu.vue`: 已实现基础抽屉架构，`viewState` 逻辑已预留。

## 5. 核心方案设计
### 5.1 后端逻辑 (Logic & Data)
1. **MemoService 扩展**: 在 `bridge.py` 中新增 `get_friend_event_gists` 方法。
   - 首先调用 `filter_user_events` 并传入 `event_tag_equal={"friend_id": str(friend_id)}`。
   - 由于该函数返回的是 `UserEvent` 对象列表，需要进一步获取这些 Event 关联的 `UserEventGist`。
   - 考虑到性能，可以直接在 `MemoService` 中实现一个 Join 查询。
2. **API 路由**: 在 `profile.py` 中新增路由处理函数。

### 5.2 前端交互 (View & State)
1. **Store 适配**: 在 `session.ts` 或新创建的 `memory.ts` store 中管理记忆状态，或者直接在组件内按需加载。本次建议在组件内本地管理。
2. **API 调用**: 创建 `front/src/api/memory.ts` 封装请求。
3. **UI 实现**: 切换到 `memories` 视图时，显示带返回按钮的 Header 和由 `MemoryCard` 组成的列表。

## 6. 变更清单
| 序号 | 领域 | 操作类型 | 文件绝对路径 | 变更摘要 |
|:---|:---|:---|:---|:---|
| 1 | 后端 | 修改 | `server/app/services/memo/bridge.py` | 新增 `filter_friend_event_gists` 方法 |
| 2 | 后端 | 修改 | `server/app/api/endpoints/profile.py` | 新增 `GET /events_gists` 接口 |
| 3 | 前端 | 新增 | `front/src/api/memory.ts` | 封装记忆获取接口 |
| 4 | 前端 | 修改 | `front/src/components/ChatDrawerMenu.vue` | 实现记忆列表展示逻辑 |

## 7. 分步实施指南

### 步骤 1: 扩展 MemoService 过滤方法
- **操作文件**: `server/app/services/memo/bridge.py`
- **逻辑描述**:
  1. 引入对应的模型和控制器。
  2. 实现 `filter_friend_event_gists(user_id, space_id, friend_id, topk)` 函数。
  3. **核心实现**: 
     - 使用 SQLAlchemy `Session` 开启查询。
     - 查询 `UserEventGist` 模型。
     - Join `UserEvent` 模型。
     - 过滤条件：`UserEvent.user_id`, `UserEvent.project_id` 以及 `UserEvent.event_data` 中包含指定 `friend_id` 标签。
     - 时间范围限制：`UserEvent.created_at > (now - 365 days)`。
     - 按创建时间倒序排列。

### 步骤 2: 实现后端 API 接口
- **操作文件**: `server/app/api/endpoints/profile.py`
- **逻辑描述**:
  1. 新增路由 `@router.get("/events_gists", response_model=UserEventGistsData)`。
  2. 接收 `friend_id: int` 和 `limit: int = 50` 参数。
  3. 调用 `MemoService.filter_friend_event_gists` 并返回结果。

### 步骤 3: 前端 API 与视图开发
- **操作文件**: `front/src/api/memory.ts`, `front/src/components/ChatDrawerMenu.vue`
- **逻辑描述**:
  1. **API**: 导出 `getFriendMemories(friendId: number)` 函数。
  2. **组件 Script**:
     - `memoryList` 响应式引用。
     - `fetchMemories` 使用 `try-catch` 包裹 API 调用。
     - `handleMenuClick` 时触发加载。
  3. **组件 Template**:
     - 渲染记忆列表。
     - **记忆内容清洗**: 去掉 Gist 内容开头的 `- ` 符号。
     - **时间展示**: 使用组件内已有的 `formatTime`。
     - **空状态**: 当列表为空时显示引导话术。

## 8. 验收标准
- [ ] 仅显示与当前聊天好友 ID 匹配的记忆（跨好友切换验证）。
- [ ] 记忆内容展示为简洁的文本摘要。
- [ ] 列表按时间从新到旧排序。
- [ ] 加载过程中有状态提示，失败有重试按钮。
