# Story 09-06: 群聊上下文适配 (Mock Tool Call)

> Epic: AI 多人群聊 (Group Chat)
> Priority: High
> Points: 5

## 概述
实现一种"上帝视角"式的上下文注入机制。通过伪造函数调用（Mock Tool Call），将群聊中其他成员的近期发言作为"外部观测数据"提供给当前发言的 Agent。核心目标是：**只有被@时才发言，否则输出 `<CTRL:NO_REPLY>`**，并确保这条规则以独立 prompt 片段加入群聊 system prompt。

## 用户故事

### US-1: 上下文感知
**作为** 开发中的 AI 好友，
**我希望** 能够通过某种结构化的方式看到群里其他角色刚才说了什么，
**以便** 产生连贯的社交回应，而不是各说各话。

### US-2: 角色区分
**作为** AI 模型，
**我希望** 群动态信息以"外部工具返回"的形式呈现，
**以便** 明确区分这是"背景观察"而非"用户对我的直接指令"。

### US-3: 谨慎发言
**作为** 群成员 Agent，
**我希望** 只在被@时发言，
**以便** 保持群聊中的真实社交节奏和角色边界。

## 功能范围

### 包含
- **群消息聚合**: 收集当前群组内最近的 N 条（如 10 条）非当前 Agent 的消息内容（来自数据库）。
- **Mock Tool 协议实现**: 构造符合 OpenAI 定义的 Tool Call/Result 格式消息，模拟 `get_other_members_messages`。
- **Mock is_mentioned**: 仅当该成员需要回复时，才在最后构造 `is_mentioned` 工具调用，避免 `<CTRL:NO_REPLY>` 的历史影响本轮生成。
- **Tool 注入逻辑**: 在调用 LLM 接口前，自动将这些虚拟的对话历史插入到对话窗口中。
- **发言触发规则**: 成员未被@时不触发任何 LLM 调用；当后续轮次被@时，之前未发言轮次用 `<CTRL:NO_REPLY>` 补齐（仅注入上下文，不落库）。
- **专用 Prompt 片段**: 在 `server/app/prompt/chat/` 下创建独立 prompt 片段，内容包含：`只有被@时才发言。否则输出 <CTRL:NO_REPLY>。` 并将其拼接进群聊 system prompt。

### 不包含（后续迭代）
- AI 主动发起该 Tool 的逻辑（目前仅为自动注入）

## 交互示例（伪造 Tool Call）
```
system: 你是群成员王五。只有被@时才发言。否则输出 <CTRL:NO_REPLY>。

---第一轮会话---
user: 今天有什么好股票吗？
assistant: (tool_call) get_other_members_messages()
(tool_result) 张三：科技股现在不错
assistant: <CTRL:NO_REPLY>
---第一轮会话---

---第二轮会话---
user: 茅台好像行情也不错
assistant: (tool_call) get_other_members_messages()
(tool_result) 张三：我不喝酒，我不是很看好。  \n 李四：还行吧
assistant: <CTRL:NO_REPLY>
---第二轮会话---

---第三轮会话---
user: 你觉着呢？@王五
assistant: (tool_call) is_mentioned()
(tool_result) 被提及，需要发言
assistant: 哈哈，我不炒股，你要听我的意见吗
---第三轮会话---

```

补充示例（无其他成员消息但被@）
```
user: 王五你怎么看？@王五
assistant: (tool_call) get_other_members_messages()
(tool_result) (empty)
assistant: (tool_call) is_mentioned()
(tool_result) 被提及，需要发言
assistant: 我不太懂股票，但可以帮你一起看看基本面
```

## 验收标准

- [ ] AC-1: 实现了 `get_other_members_messages` 虚拟工具及其内容生成逻辑，数据来自数据库。
- [ ] AC-2: 未被@时不触发 LLM 调用；当被@时，历史未发言轮次用 `<CTRL:NO_REPLY>` 补齐（仅上下文，不落库）。
- [ ] AC-3: 仅在需要回复时注入 `is_mentioned` 虚拟工具，并返回 `被提及，需要发言`。
- [ ] AC-4: 后端日志中可确认 AI Context 包含格式化的 Tool Result 消息。
- [ ] AC-5: 这种 Mock 逻辑不影响前端展示，前端接收到的消息流依然是纯净的。
- [ ] AC-6: 当群内没有其他消息时，仍注入 `get_other_members_messages`，但 Result 为空。
- [ ] AC-7: 在 `server/app/prompt/chat/` 中存在独立 prompt 片段，并已接入群聊 system prompt。

## 依赖关系

### 前置依赖
- Story 09-01: 群聊数据建模
- Story 09-05: 群聊消息服务接口 (API & SSE)

### 被依赖（后续）
- Story 09-08: 隐藏的群管理员 Agent 实现
