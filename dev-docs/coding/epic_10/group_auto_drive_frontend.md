# Epic 10 群聊自驱模式 - 前端开发文档

> 目标：在不破坏现有群聊体验的前提下，把“自驱模式（头脑风暴 / 决策 / 辩论）”融入 `GroupChatArea`，并通过独立状态与事件流驱动运行态 UI。

## 1. 范围与原则

- **体验层合并**：入口与展示完全在群聊 UI 内（单一入口 + 运行态栏）。
- **逻辑层解耦**：前端不复用普通群聊的“自动轮询/自动发言”逻辑，仅作为状态与消息展示层。
- **运行中不可改配置**：UI 必须锁定配置表单。
- **单气泡输出**：自驱模式下每次发言只渲染一个消息气泡。

## 2. 相关页面与模块

- `front/src/components/GroupChatArea.vue`：主 UI 承载（入口按钮、配置弹窗、运行态栏）
- `front/src/stores/session.stream.group.ts`：SSE 事件接收与消息流编排
- `front/src/stores/session.ts`：全局会话状态入口
- `front/src/types/chat.ts`：消息 / 事件类型定义
- `front/src/api/group.ts`：群聊 SSE 与消息 API（现有）
- 新增 `front/src/api/group-auto-drive.ts`（或扩展 `group.ts`）：自驱模式控制 API

## 2.1 现状要点（来自现有代码）

- `GroupChatArea.vue` 对 **assistant 消息**调用 `parseMessageSegments` 逐段拆分渲染。
- `session.stream.group.ts` 用 `groupApi.sendGroupMessageStream` 处理 SSE，事件包含 `start`、`meta_participants`、`message`、`thinking`、`tool_call`、`done` 等。
- `session.stream.group.ts` 在 `done` 时用 `parseMessageSegments` 计算未读条数。
- `GroupChatArea.vue` 底部“正在输入中”提示依赖 `sessionStore.isStreaming` 与 `groupTypingUsers`。

> 这些行为会影响“单气泡输出、运行态展示与自驱流隔离”，必须明确改动点。

## 3. UI 交互设计落地

### 3.1 入口（仅一个）
- **位置**：`GroupChatArea` 输入区工具栏
- **按钮**：`自驱`
  - 未运行：打开“模式配置弹窗”
  - 运行中：打开“运行面板（含暂停/继续/终止）”
> 现有工具栏按钮在 `GroupChatArea.vue` 的 `.input-toolbar` 内（Emoji + 新会话），新增入口插入同一行即可。

### 3.2 配置弹窗（极简 + 模式特化）
公共字段：
- 模式：头脑风暴 / 决策 / 辩论
- 题目：按模式分字段
- 参与成员
- 发言上限（turn_limit）
- 结束动作（总结 / 胜负判定 / 两者）

模式特化字段：
- 头脑风暴：主题 / 目标 / 约束
- 决策：决策问题 / 候选方案（多行） / 评估标准
- 辩论：辩题（主题陈述）/ 正方立场 / 反方立场

校验规则：
- 辩论正反人数 1~2 且必须相等
- 运行中配置不可修改（仅允许终止后重开）

### 3.3 运行态展示（消息列表上方）
- 状态栏（类群公告）：
  - 左：模式标签 + 题目摘要
  - 中：阶段 + 进度（例：自由交锋 3/12）
  - 右：暂停 / 继续 / 终止
  - 次行提示：下一位发言者
- **暂停**：当前有回复生成时显示“等待收尾”，结束后进入“暂停中”
> 现有消息区结构在 `GroupChatArea.vue` 的 `.chat-messages-container` 内，状态栏应插入在“Vector Warning Banner”之后、消息列表之前。

### 3.4 辩论模式角色标识
- 头像角标：正方（绿“正”）/ 反方（红“反”）
- 昵称后缀标签：正方 / 反方

### 3.5 插话规则（交互）
- **任何时刻**允许用户插话
- 暂停中：输入框可用
  - 插话不自动触发下一轮
- 插话 `@` 成员：被 @ 成员**立即回复**
- 点击“继续”后按原顺序继续运行

### 3.6 与普通群聊流隔离（Hybrid 前端层）
- 自驱模式的启动/暂停/继续/终止 **不得复用** `sendGroupMessageStream`。
- 用户插话需走**独立的自驱接口**（仅入库/更新上下文），避免触发 `GroupManager` 选人逻辑。
- 自驱运行态 UI 与普通群聊的 `isStreaming`、`groupTypingUsers` **分离维护**，避免出现“正在思考谁来回复…”的误提示。

## 4. 状态与数据结构（前端侧）

### 4.1 建议新增类型
在 `front/src/types/chat.ts` 增补（示意）：
- `AutoDriveConfig`：mode/topic/roles/turnLimit/endAction
- `AutoDriveState`：status/phase/currentTurn/nextSpeaker/roundIndex
- `AutoDriveEvent`：SSE 事件类型（启动、状态变更、结束、报错）
- `GroupSession.sessionType`：用于区分 `normal / debate / brainstorm / decision`
- `Message.debateSide`：用于标记 `affirmative / negative`（仅辩论消息）

### 4.2 Store 状态建议
`session.ts` 或独立 store（若复杂度上升）：
- `autoDriveByGroupId`（map）
- `autoDrivePanelOpen`（运行面板显示态）
- `autoDriveEditingConfig`（弹窗本地状态）

## 5. 消息渲染规则调整

- **自驱消息不拆分**：在 `GroupChatArea.vue` 渲染层根据 `sessionType` 判断属于自驱会话时 **跳过** `parseMessageSegments`。
- `session.stream.group.ts` 的未读计数使用 `parseMessageSegments`，自驱消息应强制计为 **1**，避免“多段气泡”的逻辑污染。
- 保持普通群聊消息行为不变。

## 6. API 对接（前端视角）

建议新增或扩展 API（示例）：
- `POST /api/group/auto-drive/start`
- `POST /api/group/auto-drive/pause`
- `POST /api/group/auto-drive/resume`
- `POST /api/group/auto-drive/stop`
- `GET /api/group/auto-drive/state?group_id=...`
- `POST /api/group/auto-drive/interject`（用户插话，写入上下文但不触发普通群聊回复）

> 现有群聊接口位于 `front/src/api/group.ts` 且走 `/api/chat/group/{group_id}/messages`。自驱必须独立走新路由，避免复用 `GroupChatService.send_group_message_stream`。

## 7. SSE 事件接入

**强约束：自驱 SSE 的事件与数据格式必须完全遵循普通群聊 SSE 协议**  
只允许在现有协议基础上**新增事件或新增字段**，不允许修改老事件名与字段结构。

在 `session.stream.group.ts` 或独立自驱流处理中处理以下事件（示例命名）：
- `auto_drive_state`：状态刷新
- `auto_drive_message`：自驱生成的消息（单气泡）
- `auto_drive_error`：中断原因提示

事件驱动更新：
- 更新状态栏
- 追加消息（与普通群聊共享消息列表，但依赖 `sessionType` + `debateSide` 做自驱标识）

> 建议新增 `session.stream.group.auto_drive.ts` 专门消费自驱 SSE，避免污染普通群聊 `streamingMap` 与 `groupTypingUsersMap`。

## 8. 异常与边界

- 网络断开：状态栏显示“已断开”，重新连接后拉取 `state`
- 运行中切群：恢复时必须拉取当前自驱状态
- 成员变化：运行中配置不可变，成员变动仅记录为系统提示，不改变当前序列

## 9. 前端验收清单

- 单入口按钮在工具栏位置正确
- 配置弹窗按模式显示题目字段
- 辩论模式正反人数校验、头像与昵称标识正确
- 状态栏固定在消息列表上方
- 暂停与插话规则生效
- 自驱消息始终单气泡
