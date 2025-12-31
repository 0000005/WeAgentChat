# DouDouChat SSE 响应结构设计文档

## 1. 概述 (Overview)

本通过 Server-Sent Events (SSE) 技术，实现流式传输 AI 的响应。该设计旨在支持“深度思考 (Chain of Thought)”、“流式文本回复”、“工具调用 (Function Calling)”以及错误处理等场景。设计参考了 OpenAI、Anthropic Claude 以及 Vercel AI SDK 的最佳实践，确保前端能灵活解析和展示。

## 2. 通信协议标准 (Protocol Standard)

- **Content-Type**: `text/event-stream`
- **Cache-Control**: `no-cache`
- **Connection**: `keep-alive`

### 2.1 基础格式
每一条 SSE 消息遵循标准格式：
```text
event: <EventKey>
data: <JSONPayload>

```
*(注意：每条消息以双换行符 `\n\n` 结尾)*

---

## 3. 事件类型定义 (Event Types)

我们定义以下几种核心事件类型 (`event`)，前端需根据事件类型分发处理逻辑。

| 事件类型 (`event`) | 用途 | 关键字段 (`data`) |
| :--- | :--- | :--- |
| `start` | 会话开始/元数据 | `session_id`, `message_id` |
| `thinking` | **思考过程**流式输出 | `delta` (思考内容片段) |
| `message` | **普通回复**流式输出 | `delta` (回复内容片段) |
| `tool_call` | **工具调用**指令 | `id`, `name`, `args` (全量或增量) |
| `tool_result` | 工具执行结果 | `id`, `result` |
| `error` | 异常报错 | `code`, `detail` |
| `done` | 传输结束 | `finish_reason`, `usage` |

---

## 4. 详细 Payload 结构示例

### 4.1 会话开始 (`start`)
在连接建立或处理开始时发送，携带本次生成的基础元数据。

```json
event: start
data: {
  "session_id": 101,
  "message_id": 5002,
  "model": "deepseek-r1"
}
```

### 4.2 思考过程 (`thinking`)
用于展示大模型的“思维链”或“推理过程”。前端通常将其渲染在可折叠的“思考中”区域。

```json
event: thinking
data: {
  "delta": "根据用户提供的信息，"
}

event: thinking
data: {
  "delta": "我需要查询当前的天气情况..."
}
```

### 4.3 普通回复 (`message`)
这是最终展示给用户的实际回答内容。

```json
event: message
data: {
  "delta": "你好，"
}

event: message
data: {
  "delta": "豆豆"
}

event: message
data: {
  "delta": "来了！"
}
```

### 4.4 工具调用 (`tool_call`)
当模型决定调用工具时触发。支持流式传输工具参数（如果模型支持），也可以是一次性发送完整的调用指令。

**场景 A：流式参数 (Streaming Args)**
```json
event: tool_call
data: {
  "stage": "start",
  "call_id": "call_abc123",
  "name": "get_weather"
}

event: tool_call
data: {
  "stage": "delta",
  "call_id": "call_abc123",
  "args_delta": "{\"loca"
}

event: tool_call
data: {
  "stage": "delta",
  "call_id": "call_abc123",
  "args_delta": "tion\": \"Shanghai\"}"
}
```

**场景 B：完整指令 (Complete Call)** (对于不支持流式参数的模型)
```json
event: tool_call
data: {
  "stage": "complete",
  "call_id": "call_abc123",
  "name": "get_weather",
  "arguments": "{\"location\": \"Shanghai\"}"
}
```

### 4.5 工具执行结果 (`tool_result`)
后端执行完工具后，将结果反馈给前端（可选，视具体交互需求而定，有时工具结果只在后端流转回模型，不直接推给前端，除非需要前端渲染卡片）。

```json
event: tool_result
data: {
  "call_id": "call_abc123",
  "result": "26°C, Sunny"
}
```

### 4.6 错误处理 (`error`)
发生严重错误导致中断时发送。

```json
event: error
data: {
  "code": "context_length_exceeded",
  "detail": "当前对话超出模型上下文限制，请清理历史消息。"
}
```

### 4.7 结束标志 (`done`)
表示本次生成完全结束。

```json
event: done
data: {
  "finish_reason": "stop",
  "usage": {
    "prompt_tokens": 50,
    "completion_tokens": 120,
    "total_tokens": 170
  }
}
```

---

## 5. 前端处理伪代码 (Frontend Handler Pseudocode)

```javascript
const eventSource = new EventSource("/api/chat/sessions/1/messages");

eventSource.addEventListener("thinking", (e) => {
  const data = JSON.parse(e.data);
  // 追加到思考区域
  ui.appendThinking(data.delta);
});

eventSource.addEventListener("message", (e) => {
  const data = JSON.parse(e.data);
  // 追加到主回复区域
  ui.appendMessage(data.delta);
});

eventSource.addEventListener("tool_call", (e) => {
  const data = JSON.parse(e.data);
  if (data.stage === 'start') {
    ui.showToolStatus(`Executing ${data.name}...`);
  }
  // 处理其他工具逻辑...
});

eventSource.addEventListener("done", (e) => {
  console.log("Stream finished", JSON.parse(e.data));
  eventSource.close();
});

eventSource.addEventListener("error", (e) => {
  ui.showError(JSON.parse(e.data).detail);
  eventSource.close();
});
```

## 6. 与 OpenAI/Vercel SDK 的兼容性说明
本结构显式区分了 `thinking` 和 `message` 事件，比 OpenAI 默认的 `content` 混排更清晰。如果后续需要对接 Vercel AI SDK，可以在后端做一个转换层，或者使用 Vercel SDK 的 `Data Stream` 协议进行适配。目前显式 Event 设计对即时聊天应用（尤其是强调拟人化和思考过程的应用）最为友好。

---

## 7. 典型场景流程示例

### 7.1 场景一：普通对话（无思考过程）
```text
event: start
data: {"session_id": 101, "message_id": 5002, "user_message_id": 5001, ...}

event: message
data: {"delta": "你好"}

event: message
data: {"delta": "，我"}

event: message
data: {"delta": "是豆豆"}

event: done
data: {"finish_reason": "stop", "usage": {...}}
```

### 7.2 场景二：带思考过程的对话（如 DeepSeek-R1）
```text
event: start
data: {"session_id": 101, "message_id": 5003, ...}

event: thinking
data: {"delta": "首先分析用户的问题..."}

event: thinking
data: {"delta": "需要考虑以下几个方面..."}

event: message
data: {"delta": "根据分析，"}

event: message
data: {"delta": "答案是..."}

event: done
data: {"finish_reason": "stop", "usage": {...}}
```

### 7.3 场景三：工具调用
```text
event: start
data: {"session_id": 101, "message_id": 5004, ...}

event: thinking
data: {"delta": "用户需要查天气，我需要调用工具"}

event: tool_call
data: {"stage": "complete", "call_id": "call_123", "name": "get_weather", "arguments": "{\"city\": \"上海\"}"}

event: tool_result
data: {"call_id": "call_123", "result": "晴天 26°C"}

event: message
data: {"delta": "上海今天天气不错，"}

event: message
data: {"delta": "晴天，温度 26°C"}

event: done
data: {"finish_reason": "stop", "usage": {...}}
```

---

## 10. 注意事项

1. **JSON 转义**：确保 `data` 字段中的 JSON 正确转义（特别是工具调用的 `arguments` 字段）
2. **流式断开重连**：SSE 支持浏览器自动重连，但需要后端提供 `id` 字段支持断点续传
3. **Token Usage**：`done` 事件中的 `usage` 信息需要从底层 LLM 响应中提取
4. **Thinking vs Message 区分**：DeepSeek-R1 等模型会在响应中明确标记 `<think>` 标签，需要后端解析后分发到不同事件
5. **数据库事务**：流式响应完成后再提交 AI 消息，避免中途断开导致不一致
