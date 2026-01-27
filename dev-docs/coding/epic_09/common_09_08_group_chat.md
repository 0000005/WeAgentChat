# 全栈实施方案 - Story 09-08: 隐藏的群管理员 Agent

> **文档说明**: 本文档供 AI 编码助手在独立会话中执行，涵盖从数据库到 UI 的完整闭环。

## 1. 需求全景

### 1.1 业务背景
在多人群聊场景中，用户往往不总是显式指定（@）某位 AI 回复。为了模拟真实的群聊体验，系统需要一个“群管理员（Dispatcher）”角色，根据当前话题内容、历史上下文以及各群成员的人设（Persona），智能判断由谁（1~3位成员）来接话。这一机制使得群聊更具流动性和自然感。

### 1.2 核心功能点
- **群管理员调度 (Hidden Admin)**: 当用户未显式 @ 任何成员时，系统后台调用“群管理员” Agent，分析话题并决策出 1~3 位最佳发言者。
- **强制 @ 优先**: 当用户显式 @ 成员时，群管理员逻辑**完全跳过**，仅被 @ 的成员并行响应。
- **异常降级处理**: 当 @ 列表**全部无效或为空**时，自动降级为群管理员调度逻辑；若部分有效，则仅保留有效成员并发言，忽略无效项。
- **并行执行与单流多路**: 选定的多位发言者（无论是 @ 还是管理员选中）在后端并行执行 LLM/Memory 链路。
- **SSE 多发言者流式传输**: 后端将多位 AI 的生成内容（Thinking、Content、ToolCalls）混合在同一个 SSE 连接中下发，前端根据 `sender_id` 进行分拣和异步渲染。

### 1.3 边界与异常
- **发言人数限制**: 群管理员每次最少选择 1 人，最多选择 3 人。
- **上下文截断**: 送入群管理员决策的 `chatHistory` 限制为最近 20 条消息。
- **人选范围**: 群管理员只能从当前群组的有效 AI 成员中进行选择。

## 2. 预备工作

### 2.1 API 契约设计
我们沿用现有的发送消息接口，但在内部逻辑上进行增强。

- **Endpoint**: `POST /api/chat/group/{group_id}/messages`
- **Request Body** (`GroupMessageCreate`):
  - `content`: string (用户消息)
  - `mentions`: List[string] (可选，被 @ 的成员 `member_id` 列表，来源于前端 mention 选择)
  - `enable_thinking`: boolean (是否开启思考)
- **Response** (SSE Stream):
  - 维持现有 SSE 协议，重点依赖 `sender_id` 字段区分不同 AI 的事件。
  - 事件类型: `start`, `message`, `model_thinking`, `thinking`, `recall_thinking`, `tool_call`, `tool_result`, `done`, `error`。
  - **合流约定**: 除 `start` 外，所有事件必须携带 `sender_id`；允许乱序；每个发言者必须以 `done` 或 `error` 终止。

### 2.2 参考文档
- **Prompt 文件**: `server/app/prompt/chat/group_manager.txt` (已存在)
- **Few-Shot 示例**: `server/app/prompt/chat/few_shot/` (已存在)
- **模型定义**: `server/app/models/friend.py` (Friend.description 用于构建画像)

## 4. 现状分析
- **后端 (`server/app/services/group_chat_service.py`)**:
  - `send_group_message_stream` 目前仅处理显式 mentions。
  - 若 `mentions` 为空，当前逻辑是直接 yield "No AI responded" 并结束。
  - 已具备并行执行多个 AI 任务的 `asyncio.create_task` 框架。
  - 已具备 `asyncio.Queue` 聚合多路事件并 yield 的能力。
- **前端 (`front/src/stores/session.ts`)**:
  - `sendGroupMessage` 方法已实现根据 SSE 事件中的 `sender_id` 动态创建/更新本地消息（Placeholder 机制）。
  - 已支持并发接收多位 AI 的消息流。

## 5. 核心方案设计

### 5.1 后端逻辑 (Logic & Data)
1.  **新增 `_select_speakers_by_manager` 方法**:
    - **加载 Prompt**: 使用 `load_prompt("chat/group_manager.txt")` 读取 System Prompt（严禁硬编码）。
    - **加载 Few-Shots**: 使用 `load_prompt` 按**序号 1→5**读取 `chat/few_shot/group_manager_user_{i}.txt` 与 `chat/few_shot/group_manager_assistant_{i}.txt`，构建多轮对话示例。
    - **构建 Context**:
        - `memberList`: 获取群内所有 **AI 成员** (Friend)，格式化为 `{name}_{id}: {description}`。
        - `chatHistory`: 获取群内最近 20 条**文本消息**（user/friend 的最终内容），格式化为 `{sender_name}: {content}`。
    - **调用 LLM**:
        - 使用 active LLM config。
        - 要求返回 **JSON 数组**（示例：`[10, 1]`）。
        - 建议使用 JSON Mode（如果模型支持）或 Prompt 约束。
    - **解析结果**: 解析为整数数组并去重；过滤无效 ID；裁剪到 1~3；若为空/非法/异常则触发兜底。
    - **兜底策略**: 当解析失败或结果为空时，选择 1 名活跃/最近发言的 AI 成员作为保底发言者。

2.  **修改 `send_group_message_stream` 主流程**:
    - **Step 1**: 尝试解析 `message_in.mentions` 获取 `participants`。
    - **Step 2 (判定逻辑)**:
        - 如果 `participants` 为空（未 @ 或 @ 全部无效），调用 `_select_speakers_by_manager` 获取候选 ID。
        - 如果 `participants` 非空（即便包含部分无效），**仅保留有效成员**并跳过 Manager。
        - 根据候选 ID 从数据库查询 `Friend` 对象，重新填充 `participants`。
    - **Step 3**: 保持原有的 `for friend in participants` 并行任务创建逻辑不变。

### 5.2 前端交互 (View & State)
- **无需变更**: 经分析 `front/src/stores/session.ts`，现有的 `sendGroupMessage` 逻辑完全能够处理通过 SSE 动态推送的、未预先定义的 `sender_id` 消息。只需确保后端正确发送带有 `sender_id` 的事件即可。

## 6. 变更清单

| 序号 | 领域 | 操作类型 | 文件绝对路径 | 变更摘要 |
|:---|:---|:---|:---|:---|
| 1 | 后端 | 修改 | `server/app/services/group_chat_service.py` | 实现群管理员调度逻辑与主流程集成 |

## 7. 分步实施指南 (Atomic Steps)

### 步骤 1: 实现群管理员 Prompt 加载与上下文构建工具
- **操作文件**: `server/app/services/group_chat_service.py`
- **逻辑描述**:
  - 引入 `os` 模块用于路径操作。
  - 增加私有辅助方法 `_load_manager_context(self, db, group_id)`:
    - 查询群组所有 Friend 成员。
    - 格式化 `memberList` 字符串 (格式: `Name_ID: Description`)。
  - 增加私有辅助方法 `_load_manager_few_shots(self)`:
    - 循环 1-5，尝试读取 `prompt/chat/few_shot/group_manager_user_{i}.txt` 和 `assistant_{i}.txt`。
    - 构建为 standard message list format (`[{"role": "user", ...}, {"role": "assistant", ...}]`)。

### 步骤 2: 实现群管理员决策核心逻辑
- **操作文件**: `server/app/services/group_chat_service.py`
- **逻辑描述**:
  - 实现 `_select_speakers_by_manager(self, db, group_id, history_msgs, model_config) -> List[Friend]`:
    - 调用 `_load_manager_context` 准备 prompt 变量。
    - 获取 `group_manager.txt` 内容。
    - 组装 `input_messages`: System Prompt + Few Shots + Current User Query (包含 `memberList` 和 `chatHistory` 的 prompt 模板填充)。
    - 调用 LLM (使用 `llm_service` 或 `Agent` runner，建议简单调用即可，因为只需要 JSON)。
    - 解析 LLM 返回的 JSON，提取 `speakerId` 数组。
    - 数据库查询 `Friend` 列表返回。

### 步骤 3: 集成调度逻辑到消息发送流
- **操作文件**: `server/app/services/group_chat_service.py`
- **逻辑描述**:
  - 修改 `send_group_message_stream` 方法。
  - 在“解析 mentions”逻辑之后，添加判断：
    ```python
    if not participants:
       # 调用群管理员逻辑
       participants = await self._select_speakers_by_manager(...)
    ```
  - 确保当 mention 解析结果为空（用户输入无效ID）时也能走入此分支（即 `AC-3`）。
  - 保留原有的并行任务启动逻辑。

## 8. 验收标准
- [ ] **AC-1 (无 @ 触发)**: 向群组发送不带 @ 的消息，后端日志显示 "Group Manager selected speakers: [...]"，且前端收到 1-3 个 AI 的回复。
- [ ] **AC-2 (有 @ 触发)**: 向群组发送 `@A` 的消息，后端日志显示跳过 Manager，仅 A 回复。
- [ ] **AC-3 (部分无效 @)**: 向群组发送 `@A @InvalidUser` 消息，仅 A 回复，且不触发 Manager。
- [ ] **AC-4 (无效 @ 降级)**: 向群组发送 `@InvalidUser` 消息，后端显示降级为 Manager 选人，并有 AI 回复。
- [ ] **AC-5 (JSON 解析)**: 群管理员输出 JSON 数组，后端能鲁棒解析、去重并裁剪到 1~3。
- [ ] **AC-6 (SSE 合流)**: 多发言者并发时，事件可乱序但 `sender_id` 完整，且每个发言者都收到 `done` 或 `error` 终止事件。
- [ ] **AC-7 (上下文)**: 确认送给 Manager 的 `chatHistory` 包含最近 20 条文本消息。
