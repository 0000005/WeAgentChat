# 全栈实施方案 - 回忆 Agent 与 MCP 格式封装

> **文档说明**: 本文档专注于实现一个独立的"回忆 Agent"，它负责在主对话产生前，通过多步思维和工具调用召回相关记忆，并将结果格式化为标准的 MCP 工具调用链，以便主助手无缝集成。

## 1. 需求全景
### 1.1 业务背景
Profile 体量有限，可直接注入 System Prompt；Event Gists 才需要精确召回。我们需要一个"聪明"的助手，在后台先理解用户意图，再有针对性地调取特定好友的历史事件记忆。

### 1.2 核心功能点
- **功能 A: 回忆 Agent 推理流**: 启动一个专用的 `RecallAgent`。
- **功能 B: 多轮召回策略**: 根据用户设置的「搜索轮数」，Agent 可进行多步思考，对 Event Gists 做多步检索优化。
- **功能 C: MCP 格式转换**: 将召回结果转换为 `tool_call`（助手发起请求）和 `tool_result`（系统返回结果）的对话片段。

## 2. 预备工作
### 2.1 依赖分析
- **Agent 框架**: 使用 `agents` (即 `openai-agents`)。
- **检索底层**: 依赖 `MemoService.recall_memory` (来自：dev-docs\coding\epic_04\common_04_001_memoservice_recall_extension.md)。
- **系统设置**: 需要读取 `memory` 组下的 `search_rounds` 等参数（来自：dev-docs\coding\epic_04\common_04_002_system_settings_memory_chat.md）。
- **LLM 配置**: 回忆 Agent 使用与主对话相同的 `LLMConfig`（从数据库读取），确保模型一致性。

### 2.2 框架 API 确认
根据 `openai-agents` 库的设计，`Runner.run()` 会自动执行多轮对话直到 Agent 返回最终结果或达到内部限制。控制搜索轮数的方式是通过 Agent 的 `instructions` 提示词引导其在 N 轮后停止。

## 3. 核心方案设计
### 3.1 回忆 Agent 设计
- **Instructions**: "你是一名记忆专家。你的任务是根据用户的提问，调用 `recall_memory` 工具召回相关的过往事件（Events）。你可以根据第一轮搜到的信息进行追问或深入搜索，直到找到最相关的记忆。最后只需结束通话，无需直接回答用户提问。"
- **Tools**: 绑定 `MemoService.recall_memory` 包装成的函数。

### 3.2 流程逻辑
1. **初始化**: 准备 `RecallAgent` 实例，配置 LLM 客户端（与主对话共用 `LLMConfig`）。
2. **执行召回**: 使用 `Runner.run(agent, messages)`，其中 `messages` 是经过格式化处理的当前会话所有聊天记录（包含当前用户的提问）。Agent 会根据完整的对话上下文自动进行多轮搜索。
3. **轮数控制**: 通过在 instructions 中添加类似 "你最多可以调用工具 {search_rounds} 次" 的引导词来限制搜索次数。
4. **数据提取**:
    - 从运行结果的 `messages` 中提取所有 `tool_call` 和对应的 `tool_result`。
    - 汇聚 Agent 的 `reasoning` 内容（如果有）。
5. **格式化**: 构造一个模拟的工具调用片段：
    - `message_a (assistant)`: 包含一个 `recall_memory` 的 tool_call。
    - `message_b (tool)`: 包含合并后的 `events` 内容（JSON 格式）。

## 4. 变更清单
| 序号 | 领域 | 操作类型 | 文件绝对路径 | 变更摘要 |
|:---|:---|:---|:---|:---|
| 1 | 后端 | 新增 | `server/app/services/recall_service.py` | 实现 `RecallService` 协调回忆 Agent 的执行 |

## 5. 分步实施指南 (Atomic Steps)

### 步骤 1: 构建 RecallService 框架
- **操作文件**: `server/app/services/recall_service.py`
- **逻辑描述**: 
    1. 引入必要模块
    2. 实现 `perform_recall(db, user_id, space_id, messages, friend_id)` 异步方法。
    3. 从数据库获取 `LLMConfig` 和 `memory` 组的系统设置（`search_rounds`, `event_topk`, `threshold`）。
    4. **参数绑定逻辑**：定义内部工具函数 `tool_recall(...)`。通过**闭包 (Closure)** 机制，使工具函数能够直接访问外部作用域的 `user_id`、`space_id` 和 `friend_id`。
    5. **Runner 调用说明**：`Runner.run(agent, messages)` 本身不需要 Memobase 的用户信息作为参数；这些信息已预先绑定在 Agent 的 `tools` 逻辑中。
    6. 使用 `set_default_openai_client` 配置与主对话相同的 LLM。

### 步骤 2: 实现 Agent 推理逻辑
- **操作文件**: `server/app/services/recall_service.py`
- **逻辑描述**: 
    1. 配置 `RecallAgent` 的 `instructions`，包含：
        - 角色定义："你是一名记忆专家..."。
        - 任务说明：基于提供的**完整对话历史**，调用 `recall_memory` 工具搜索与当前话题最相关的记忆。
        - **轮数引导**："你最多可以调用工具 {search_rounds} 次，找到相关记忆后立即结束。"。
    2. 绑定 `tool_recall` 函数到 Agent 的 `tools` 列表。
    3. 使用 `Runner.run(agent, messages)` 执行推理（非流式）。其中 `messages` 应转换为 `openai-agents` 可接受的消息对象列表。
    4. 收集运行结果中的所有 `messages` 对象。

### 步骤 3: 封装 MCP 语义片段
- **操作文件**: `server/app/services/recall_service.py`
- **逻辑描述**: 
    1. 遍历 `Runner.run` 的 `messages`。
    2. 创建一个新的 `assistant` 消息，放入模拟的 `tool_calls`（含 `recall_memory`）。
    3. 创建一个配套的 `tool` 消息，放入合并后的 JSON 结果（仅 Events）。
    4. 将这两个消息对象返回给调用者。

## 6. 验收标准
- [ ] 调用 `RecallService.perform_recall` 返回的是一个包含两条消息（assistant/tool）的列表。
- [ ] 这两条消息可以被直接追加到 `agent_messages` 中并能被主 LLM 正确解析。
- [ ] 如果 Agent 进行了两轮搜索，返回的是合并后的最终结果，而不是两组重复数据。
