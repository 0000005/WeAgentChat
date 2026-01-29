# Epic 10 群聊自驱模式 - 后端开发文档

> 目标：自驱逻辑**与普通群聊解耦**，以独立编排与状态机驱动“头脑风暴 / 决策 / 辩论”三类模式，同时保证与现有群聊消息体系可共存。

## 1. 范围与原则

- **逻辑层解耦**：自驱不复用普通群聊的自动发言逻辑，采用独立服务与状态流。
- **消息共享**：自驱产出的消息写入群聊消息表，但必须有可识别标记（见第 5.3 节）。
- **配置不可变**：运行期间不允许修改配置，仅暂停/继续/终止。
- **Prompt 不硬编码**：所有提示词放在 `server/app/prompt/` 并用 `load_prompt` 读取。

## 1.1 现状要点（来自现有代码）

- 普通群聊 API：`server/app/api/endpoints/group_chat.py`，路径 `/api/chat/group/{group_id}/messages`。
- 普通群聊服务：`server/app/services/group_chat_service.py`
  - 使用 `chat/group_manager.txt` + few-shot 选择回复成员（`_select_speakers_by_manager`）。
  - SSE 事件：`start`、`meta_participants`、`message`、`thinking`、`tool_call`、`done` 等。
  - 该逻辑**依赖群聊上下文编排**，不适合复用到自驱模式。
- 群聊消息结构：`GroupMessage.message_type` 仅支持 `text/system/@`（见 `server/app/schemas/group.py`）。

## 2. 推荐模块拆分

### 2.1 新增服务层
- `server/app/services/group_auto_drive_service.py`
  - 负责状态机、轮次调度、上下文编排、下一发言者选择、结束条件判断
  - **不复用** `GroupChatService` 的 GroupManager 逻辑与 prompt

### 2.2 API 端点
建议新增独立 router，避免挤压 `group_chat.py`：
- `server/app/api/endpoints/group_auto_drive.py`

路由示例：
- `POST /api/group/auto-drive/start`
- `POST /api/group/auto-drive/pause`
- `POST /api/group/auto-drive/resume`
- `POST /api/group/auto-drive/stop`
- `GET /api/group/auto-drive/state`

> 若决定沿用 `group_chat.py`，仍必须保持业务逻辑完全走 `group_auto_drive_service`。

### 2.3 与普通群聊的隔离边界（Hybrid 核心）
- **上下文编排不同**：自驱是“自动轮次 + 角色定位 + 阶段控制”，普通群聊是“被动触发 + GroupManager 选人”。
- **system prompt 不同**：自驱必须使用独立 prompt 集合（辩论/头脑风暴/决策）。
- **流与状态不混用**：自驱 SSE 与普通群聊 SSE 分流，避免 `streaming` 状态互相污染。

## 3. 核心状态机

状态：
- `Idle` → `Running` → `Pausing` → `Paused` → `Ended`

关键规则：
- `Paused` 允许用户插话
- `Pausing` 表示等待当前生成结束，结束后进入 `Paused`
- 达到 `turn_limit` 后进入 `Ended`，并触发总结/判定

## 3.1 会话隔离（避免污染普通群聊）

现有 `GroupChatService.get_or_create_session_for_group` 会基于 `GroupSession.last_message_time` 自动续/分 session。  
**自驱模式启动时应强制新建会话**，避免复用普通群聊的活跃会话，从而不影响“会话超时”逻辑。

约束规则（确认版）：
- **归属关系**：自驱会话仍归属当前 `group_id`，但 `session_type` 必须为 `debate / brainstorm / decision`。
- **结束标记**：自驱流程结束（达到 turn_limit 或用户终止）时，必须将该 `GroupSession.ended = true`。
- 普通群聊只处理 `session_type = normal`。

## 4. 轮次与调度规则（后端实现）

### 4.1 轮次口径
- 头脑风暴/决策：**每位成员发言一次 = 1 轮**
- 辩论：**正反双方各完成一次发言 = 1 轮**

### 4.2 辩论顺序
- 正方先发言
- 一辩指派：按 `member_id` ASCII 升序
- 自由交锋：正A → 反A → 正B → 反B ... 固定循环

### 4.3 头脑风暴/决策调度
- 发言人由**群管理员调度**决定（后端按调度名单或调度策略执行）

## 5. 数据结构（后端侧）

### 5.1 配置（AutoDriveConfig）
- `mode`：brainstorm / decision / debate
- `topic`：模式特化字段
- `roles`：成员列表 / 正反方列表
- `turn_limit`：发言上限
- `end_action`：总结 / 胜负判定 / 两者
- `judge_id` / `summary_by`：允许用户自己或指定成员

### 5.2 运行态（AutoDriveState）
- `status` / `phase`
- `current_round` / `current_turn`
- `next_speaker_id`
- `pause_reason`（如“等待收尾”）
- `started_at` / `ended_at`

> 建议持久化到 DB（可新表）以支持断线恢复与跨端同步。

### 5.3 群聊消息标记（必须）
**不修改 `GroupMessage.message_type`**，保持现有 `text/system/@` 语义不变。  
自驱消息的识别依赖以下两处：
- `GroupSession.session_type`（`normal / debate / brainstorm / decision`）
- `GroupMessage.debate_side`（仅辩论消息填 `affirmative / negative`）

涉及改动：
- `server/app/models/group.py`（新增 `session_type` 与 `debate_side`）
- `server/app/schemas/group.py`（为 `GroupSessionRead` 增加 `session_type` 字段）
- `front/src/api/group.ts`（`GroupSessionRead` / `GroupMessageRead`）
- `front/src/types/chat.ts`（`GroupSession` / `Message`）

### 5.4 题目与正反方的保存（必须）
自驱模式的**题目信息与正反方分配不应塞进消息内容**，应作为配置持久化，便于恢复与展示。

建议新增表（示例名）：`group_auto_drive_runs`（或 `group_auto_drive_config`）：
- `id`
- `group_id`
- `session_id`（对应自驱新建的 `GroupSession`）
- `mode`：`debate / brainstorm / decision`
- `topic_json`：题目字段（按模式结构化保存）
- `roles_json`：成员角色与顺序
  - 辩论示例：`{ "affirmative": ["12","45"], "negative": ["33","81"], "order": ["12","33","45","81"] }`
  - 头脑风暴/决策示例：`{ "participants": ["12","33","45"], "dispatcher_id": "user" }`
- `turn_limit`
- `end_action`
- `judge_id` / `summary_by`
- `status` / `started_at` / `ended_at`

说明：
- **正反方保存位置**：`roles_json`（成员→阵营映射），前端按 `sender_id` 反查阵营即可。
- **题目信息保存位置**：`topic_json`（按模式字段结构化存储）。
- **消息表冗余**：在 `GroupMessage` 增加可空字段 `debate_side`（`affirmative / negative`），仅辩论消息写入，其他模式为空；

## 6. Prompt 设计与加载

目录建议：
- `server/app/prompt/auto_drive/brainstorm_system.txt`
- `server/app/prompt/auto_drive/decision_system.txt`
- `server/app/prompt/auto_drive/debate_system.txt`
- `server/app/prompt/auto_drive/debate_judge.txt`
- `server/app/prompt/auto_drive/summary.txt`

加载方式：
- `get_prompt("auto_drive/brainstorm_system.txt")`（`get_prompt` 包装了 `load_prompt`）

约束点：
- 200 字限制为**软限制**（提示词提醒，不硬截断）
- 辩论阶段性提示（立论 / 自由交锋 / 总结）

## 7. 与群聊消息体系的连接

- 自驱生成消息写入群聊消息表
- 使用第 5.3 节的**持久化标记**，保证历史消息可识别
- 插话消息仍按普通用户消息保存
- 自驱消息与普通消息**混排展示**，“开始/结束分割线”由 **`GroupSession` 的创建/结束** 生成，不新增 system 消息、不改写 `GroupMessage.message_type`。
- 后端负责**多表关联查询**（`GroupMessage` + `GroupSession`），在返回消息列表时附带必要的 `session_type`/`debate_side` 等信息，前端不做关联计算。

## 8. SSE 事件设计

**强约束：自驱 SSE 的事件与数据格式必须完全遵循普通群聊 SSE 协议**  
只能在此基础上**新增事件或新增字段**，**不得修改**已有事件名与既有字段结构，确保兼容性。

新增事件（可选）：
- `auto_drive_state`：运行态更新
- `auto_drive_message`：自驱消息（单气泡）
- `auto_drive_error`：终止或异常原因

前端只订阅，不做业务判断。

> 建议独立 SSE 路由（如 `/api/group/auto-drive/stream`），避免与 `/api/chat/group/{id}/messages` 的事件混流。

## 9. 插话与 @ 规则

- **插话永远允许**
- 插话 `@` 成员：立即触发被 @ 成员回复（不打乱主序列）
- 用户点击“继续”：回到原顺序继续

## 10. 异常与保护

- LLM 超时：进入 `Paused` 并提示原因
- 成员离开：不中断当前运行，仅记录系统提示
- 配置变更：运行中拒绝修改并返回错误码

## 11. 测试建议

- 状态机流转（Running → Pausing → Paused → Running → Ended）
- 轮次计数口径校验（讨论/辩论）
- 固定顺序与一辩指派
- 插话与 @ 回复的优先级
- 断线恢复后状态一致性
