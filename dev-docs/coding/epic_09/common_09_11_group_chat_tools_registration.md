# 群聊/单聊伪造 Tool Call + 注册真实 Tools 方案开发文档

## 背景与问题
当前群聊在构造上下文时会伪造 `function_call` / `function_call_output` 项（如 `get_other_members_messages`、`is_mentioned`、`recall_memory`），用于强制“每轮回忆”和统一群聊多角色视角。
但在实际调用模型时未注册 tools，导致模型在部分轮次输出 DSML/function_calls 文本（而不是结构化工具调用），最终被当作普通文本返回给前端。
单聊在注入 recall 相关 mock 工具项时也存在同样风险。

## 目标
- 保持“每轮强制回忆”的后端行为不变。
- 同时允许模型主动调用工具，且能得到真实/可控响应。
- 避免 `function_calls` 文本泄露到最终回复。
- 遵循系统提示词中的“每轮回忆次数上限”设置。

## 方案概述
继续保留伪造工具调用项，用于明确提示模型“工具可用”。
同时在群聊/单聊 Agent 中注册真实 tools：
- 群聊：`recall_memory`、`get_other_members_messages`、`is_mentioned`
- 单聊：`recall_memory`

模型若主动调用工具，后端返回真实结果；

## 影响范围
- 后端：`server/app/services/group_chat_service.py`、`server/app/services/chat_service.py`
- 可能涉及：`server/app/services/recall_service.py`（只读复用，不改协议）
- 前端：无需修改（已支持 tool_call/tool_result 事件）

## 详细设计

### 1) 群聊 Agent 注册 tools
在 `GroupChatService._run_group_ai_generation_task` 中构造 Agent 时，添加 tools：
- `recall_memory(query: str)`
- `get_other_members_messages()`
- `is_mentioned()`

**注意**：与单聊 `RecallService` 保持接口一致，工具名称必须严格一致。

### 2) 单聊 Agent 注册 tools
在 `chat_service._run_chat_generation_task` 中构造 Agent 时，仅添加：
- `recall_memory(query: str)`

### 3) 强制回忆与模型自主回忆
当前群聊在调用 LLM 前已执行：
- `RecallService.perform_recall(...)`
并将结果注入 `agent_messages`。

模型如果主动调用 `recall_memory`，直接执行真实检索并返回结果。
回忆次数控制由系统提示词/设置项保证（已有配置）。

### 4) get_other_members_messages / is_mentioned
- `get_other_members_messages` 返回当前轮次预先拼接的 `others_content`。
- `is_mentioned` 返回是否被 @：
  - 若 `mentions` 含当前 `friend_id`，返回“被提及，需要发言”；
  - 否则返回“未被提及，可自行判断”。

### 5) 回忆次数控制
- 回忆次数由系统提示词/设置项控制（已有配置）。
- 后端不再做额外的幂等或速率限制。

### 6) 事件输出
工具调用将通过 Agents 框架转为结构化 `tool_call` / `tool_result` 事件，前端已支持展示，不需要额外改动。

## 伪代码示例
```python
# group_chat_service.py (示意)
@function_tool(name_override="recall_memory")
async def recall_memory(query: str):
    return await MemoService.recall_memory(...)

@function_tool(name_override="get_other_members_messages")
async def get_other_members_messages():
    return others_content

@function_tool(name_override="is_mentioned")
async def is_mentioned():
    return "被提及，需要发言" if is_mentioned_flag else "未被提及，可自行判断"

agent = Agent(..., tools=[recall_memory, get_other_members_messages, is_mentioned])

# chat_service.py (示意)
@function_tool(name_override="recall_memory")
async def recall_memory(query: str):
    return await MemoService.recall_memory(...)

agent = Agent(..., tools=[recall_memory])
```

## 日志与监控
- 在工具调用返回时记录：tool_name / query。
- 若出现模型输出 DSML 文本，追加错误日志并统计次数。

## 风险与对策
- **风险**：模型在同轮内多次调用 recall 导致成本上升。
  - **对策**：由系统提示词/设置项限制每轮回忆次数。
- **风险**：工具返回的结构与模型期望不一致。
  - **对策**：确保 `recall_memory` 返回 `{events: [...]}`，与 `MemoService` 兼容。

## 测试建议
1) 群聊正常对话：无 tool_calls 文本泄露。
2) @ 触发：`is_mentioned` 被调用且返回正确。
3) 单聊正常对话：无 tool_calls 文本泄露，`recall_memory` 可被主动调用。
4) recall 强制执行 + 模型主动 recall：确保遵循回忆次数上限。
5) DeepSeek 模型：验证 tool_call 结构化输出，不再出现 DSML 文本。

## 验收标准
- 群聊回复不再出现 `<｜DSML｜function_calls>` 文本。
- 工具调用事件在前端正常展示。
- recall 仍在每轮执行，并遵循回忆次数上限。
- 单聊回复不再出现 `<｜DSML｜function_calls>` 文本，且仅注册 `recall_memory`。
