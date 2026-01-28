# splite_session_ts开发文档

## 背景与现状
- `front/src/stores/session.ts` 约 938 行、职责高度耦合：类型定义、消息解析工具、状态与计算属性、拉取/分页、会话管理、SSE 流式处理、群内正在输入、撤回/重生成等全部集中在一个文件。
- 现状导致维护成本高、定位问题困难、改动容易牵一发动全身。

## 目标
- 将 `session.ts` 拆成多个职责清晰的模块，降低耦合。
- 保持现有行为不变（接口/功能/交互一致）。
- Pinia store 作为“编排层”，仅负责状态与组合各模块函数。

## 拆分方向（一步到位）

### 目标文件结构
```
front/src/
  stores/
    session.ts                       # 入口 Pinia store（瘦身）
    session.fetch.ts                 # 拉取/分页/同步相关
    session.sessions.ts              # 会话管理相关
    session.stream.friend.ts         # 好友流式消息处理
    session.stream.group.ts          # 群聊流式消息处理
  types/
    chat.ts                           # Message / ToolCall / GroupTypingUser
  utils/
    chat.ts                           # parseMessageSegments 等工具
```

### 模块职责划分
1) `types/chat.ts`
- 迁移 `ToolCall` / `Message` / `GroupTypingUser` 类型。
- 统一给 store / 组件 / composables 使用。

2) `utils/chat.ts`
- 迁移 `parseMessageSegments`。

3) `session.fetch.ts`（拉取/分页/同步）
- `loadMoreMessages`
- `syncLatestMessages`
- `clearFriendHistory`
- `clearGroupHistory`

4) `session.sessions.ts`（会话管理）
- `fetchFriendSessions`
- `loadSpecificSession`
- `resetToMergedView`
- `deleteSession`
- `startNewSession`
- `startNewGroupSession`
- `selectFriend`（核心切换逻辑）
- `selectGroup`（核心切换逻辑）

5) `session.stream.friend.ts`（好友流式处理）
- `sendMessage`
- `regenerateMessage`
- `recallMessage`（撤回逻辑）
- 依赖 `parseMessageSegments` 与 `ToolCall` 类型
- 处理 SSE 事件与消息聚合逻辑

6) `session.stream.group.ts`（群聊流式处理）
- `sendGroupMessage`
- 群内 typing 更新逻辑：`groupTypingUsersMap` 相关函数
- 依赖 `parseMessageSegments` 与 `GroupTypingUser`

7) `session.ts`（入口 store）
- 仅保留 state、computed，以及从模块“组装” action。

## 关键设计约束
- 模块只处理逻辑，不自行创建 Pinia store。
- 模块函数通过参数注入依赖（refs、store、API）。
- `session.ts` 是唯一触碰状态初始化的地方，避免重复创建 ref。

## 依赖注入建议（示例）
> 这里只描述结构，具体签名在实现时细化。

- `session.fetch.ts` 暴露 `createSessionFetch(deps)` 返回 `{ fetchFriendMessages, clearFriendHistory, ... }`
- `session.stream.friend.ts` 暴露 `createFriendStreamActions(deps)` 返回 `{ sendMessage, regenerateMessage, recallMessage }`
- `session.stream.group.ts` 暴露 `createGroupStreamActions(deps)` 返回 `{ sendGroupMessage, groupTypingUsersMap, groupTypingUsers, set/remove/clear }`
- `session.sessions.ts` 暴露 `createSessionActions(deps)` 返回 `{ fetchFriendSessions, selectFriend, loadSpecificSession, ... }`

> `deps` 通常包含：`state` 引用、`friendStore`、`groupStore` 以及 `settingsStore` 等。

## 需要修改的文件清单

### 新增文件
- `front/src/types/chat.ts`
- `front/src/utils/chat.ts`
- `front/src/stores/session.fetch.ts`
- `front/src/stores/session.sessions.ts`
- `front/src/stores/session.stream.friend.ts`
- `front/src/stores/session.stream.group.ts`

### 修改文件（迁移引用）
1) `front/src/stores/session.ts`
- 移除类型与工具函数定义。
- 仅保留 state/computed。
- 引入并组合各模块暴露的 actions。

2) `front/src/components/ChatArea.vue`
- `parseMessageSegments` 改为从 `@/utils/chat` 导入。
- `ToolCall` 改为从 `@/types/chat` 导入。

3) `front/src/components/GroupChatArea.vue`
- `parseMessageSegments` 改为从 `@/utils/chat` 导入。

4) `front/src/composables/useChat.ts`
- `Message` 类型改为从 `@/types/chat` 导入。

5) `front/src/components/Sidebar.vue`
- 确保 `sessionStore.streamingMap` 等计算属性或状态的引用路径正确。

6) `front/src/utils/chat.ts`
- 定义 `INITIAL_MESSAGE_LIMIT = 10` 常量并导出。

> 如需保持兼容，也可在 `session.ts` 临时 re-export 类型/工具；但建议一次性迁移完引用，避免隐性耦合。

## 详细迁移映射（函数级别）

### 从 `session.ts` 移出
- 类型
  - `ToolCall` → `types/chat.ts`
  - `Message` → `types/chat.ts`
  - `GroupTypingUser` → `types/chat.ts`
- 工具
  - `parseMessageSegments` → `utils/chat.ts`

- 拉取/分页
  - `fetchFriendMessages` → `session.fetch.ts`
  - `fetchGroupMessages` → `session.fetch.ts`
  - `loadMoreMessages` → `session.fetch.ts`
  - `syncLatestMessages` → `session.fetch.ts`
- `clearFriendHistory` / `clearGroupHistory` → `session.fetch.ts`

- 会话管理
  - `fetchFriendSessions` → `session.sessions.ts`
  - `loadSpecificSession` → `session.sessions.ts`
  - `resetToMergedView` → `session.sessions.ts`
  - `deleteSession` → `session.sessions.ts`
  - `startNewSession` → `session.sessions.ts`
  - `startNewGroupSession` → `session.sessions.ts`
  - `selectFriend` / `selectGroup` → `session.sessions.ts`

- SSE 流处理
  - `sendMessage` → `session.stream.friend.ts`
  - `regenerateMessage` → `session.stream.friend.ts`
  - `recallMessage` → `session.stream.friend.ts`
  - `sendGroupMessage` → `session.stream.group.ts`

- 群内正在输入
  - `groupTypingUsersMap` / `groupTypingUsers` / `setGroupTypingUsers` / `removeGroupTypingUser` / `clearGroupTypingUsers`
  - 保留在 `session.stream.group.ts`，由 `session.ts` 引用并返回

## 风险点与注意事项
- SSE 事件顺序与边界处理（尤其是 `error`/`done` 分支）需要保持一致。
- `messagesMap` / `unreadCounts` / `streamingMap` 的写入必须继续保持响应式引用，避免复制导致引用断开。
- `sendGroupMessage` 中 `groupTypingUsersMap` 的副作用逻辑需要完整迁移。
- `syncLatestMessages` 里“去重逻辑”要保持完全一致，防止重复消息。

## 验证/回归建议
- 单聊：发送/接收、流式显示、撤回、重生成、分页加载、同步最新。
- 群聊：发送/接收、多 AI 流式合并、typing 列表更新与清空。
- 会话：切换会话、创建新会话、删除会话、清空历史。
- 未读数：在非当前对话时消息到达的未读数递增逻辑。

## 实施步骤

### 阶段一：基础拆分与引用改造
**要完成的内容**
- 新增 `front/src/types/chat.ts` 与 `front/src/utils/chat.ts`，迁移类型与 `parseMessageSegments`。
- 调整 `ChatArea.vue`、`GroupChatArea.vue`、`useChat.ts` 的导入来源。
- `session.ts` 移除类型与工具函数定义，改为从新文件引用。

**验收标准**
- `parseMessageSegments` 只在 `front/src/utils/chat.ts` 定义且无重复导出。
- `ToolCall`/`Message`/`GroupTypingUser` 只在 `front/src/types/chat.ts` 定义且引用统一。
- `session.ts` 不再包含类型/工具函数声明，只保留 import 使用。
- TypeScript 类型检查通过（无重复标识、路径错误、隐式 any）。

### 阶段二：数据拉取与会话管理拆分
**要完成的内容**
- 新增 `session.fetch.ts`、`session.sessions.ts`，迁移拉取/分页/会话管理相关函数。
- `session.ts` 仅负责 state/computed，并组合导出的 actions。
- 保证依赖注入形式统一（`deps` 传入 refs、store、API）。

**验收标准**
- `session.fetch.ts` / `session.sessions.ts` 不创建 Pinia store，仅导出基于 `deps` 的工厂函数。
- `session.ts` 不直接包含拉取/会话管理实现（仅组合 action）。
- `useSessionStore` 对外暴露的 action/状态名称保持不变（API 兼容）。
- TypeScript 类型检查通过（无循环依赖、无隐式 any、无路径错误）。

### 阶段三：流式处理与群内状态拆分
**要完成的内容**
- 新增 `session.stream.friend.ts`、`session.stream.group.ts`，迁移单聊/群聊 SSE 逻辑。
- 群内 typing 状态相关函数与 `groupTypingUsersMap` 一并迁移并保持行为。
- 完整回归 `sendMessage`、`sendGroupMessage`、`regenerateMessage`、`recallMessage` 的边界处理。

**验收标准**
- `session.stream.friend.ts` / `session.stream.group.ts` 中包含所有 SSE 事件分支（start/thinking/recall_thinking/message/tool_call/tool_result/error/done），逻辑不缺失。
- `session.ts` 不再包含 `for await` 流式循环代码。
- 群内 typing 相关状态与方法全部迁移到 `session.stream.group.ts` 并通过 store 对外暴露。
- TypeScript 类型检查通过（无隐式 any、无未导出符号）。

---

如需我继续下一步，我可以根据此文档直接开始拆分实现。
