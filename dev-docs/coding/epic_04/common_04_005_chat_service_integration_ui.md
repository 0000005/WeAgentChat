# 全栈实施方案 - Chat Service 集成与 UI 展示适配

> **文档说明**: 本文档负责将记忆召回逻辑植入主对话流（SSE），并升级前端聊天界面，实现记忆召回过程的展示与主对话的结合。

## 1. 需求全景
### 1.1 业务背景
记忆召回应有可见性，但 Profile 体量有限可直接注入 System Prompt。通过在聊天流中嵌入 Event 召回过程，用户可以感知到 AI 是如何利用过往事件记忆来生成回复的，增强交互的透明度和温度。

### 1.2 核心功能点
- **功能 A: 后端流集成**: 在 `send_message_stream` 中注入 Profile 并引入 `RecallService`，动态调整 LLM 上下文。
- **功能 B: 召回过程透传**: 根据系统设置，将回忆 Agent 的思维链和工具调用通过 SSE 事件推送至前端。
- **功能 C: 前端组件适配**: 升级聊天气泡，利用 `ai-elements-vue` 展示工具调用和思维过程。

## 2. 预备工作
### 2.1 依赖分析
- **后端**: `server/app/services/chat_service.py` 修改 `send_message_stream`。
- **前端 Store**: `front/src/stores/session.ts` 升级数据结构。
- **前端 UI**: `front/src/components/ChatArea.vue` 升级渲染逻辑。

### 2.2 UI 组件查询
在实施前端 UI 时，需要确认 `ai-elements-vue` 工具组件的使用方法：
- **查询方式**: 使用 `context7` 查询 `ai-elements-vue` 中的 `Tool` 组件及其子组件（`ToolTrigger`, `ToolContent`, `ToolResult` 等）的用法。
- **参考位置**: 查看 `front/src/components/ai-elements/` 目录下已有的工具组件实现。
- **重点确认**: 组件 Props 定义、数据结构要求、展开/收起交互逻辑。

## 3. 现状分析
- **后端**: 消息流目前只有 `thinking` 和 `message` 事件，不支持 `tool` 相关事件。
- **前端 Store**: `Message` 接口缺失 `toolCalls` 字段，SSE 处理器不识别工具事件。
- **前端 UI**: 已经集成了 `ai-elements-vue` 的 `Reasoning` 组件，但未集成 `Tool` 组件。

## 4. 核心方案设计
### 4.1 后端逻辑 (Logic & Data)
- **送往主 Agent 的上下文**:
    - 原始内容: [User Message]
    - 增强后: [System Prompt: Profiles] -> [模拟的 Assistant Tool Call] -> [模拟的 Tool Result] -> [User Message]
- **SSE 事件流顺序与命名规范**:
    1. `start` - 流开始（现有）
    2. **新增事件** `tool_call` - 推送召回工具调用信息（如果开启「显示工具调用」）：
       ```json
       {"event": "tool_call", "data": {"tool_name": "recall_memory", "arguments": {...}}}
       ```
    3. **新增事件** `tool_result` - 推送召回结果（如果开启「显示工具调用」）：
       ```json
       {"event": "tool_result", "data": {"tool_name": "recall_memory", "result": {...}}}
       ```
    4. `thinking` - 回忆 Agent 或主 Agent 的思维链（如果开启「显示思维链」）
    5. `message` - 主回复的文本内容（现有）
    6. `done` - 流结束（现有）

### 4.2 前端交互 (View & State)
- **Store 升级**: 
    - 为 `Message` 接口增加 `toolCalls: Array<{name: string, args: any, result: any}>` 字段。
    - 在 SSE 处理逻辑中增加对 `tool_call` 和 `tool_result` 事件的监听：
        - `tool_call`: 创建新的工具调用记录并添加到 `toolCalls` 数组。
        - `tool_result`: 更新对应工具调用的 `result` 字段。
- **UI 升级**:
    - 在 `ChatArea.vue` 的消息循环中，当 `role === 'assistant'` 且 `msg.toolCalls.length > 0` 时，在 `Reasoning` 组件后、`MessageContent` 前渲染工具调用组件。
    - 使用 `ai-elements-vue` 的 `Tool` 组件展示每个工具调用及其结果。

## 5. 变更清单
| 序号 | 领域 | 操作类型 | 文件绝对路径 | 变更摘要 |
|:---|:---|:---|:---|:---|
| 1 | 后端 | 修改 | `server/app/services/chat_service.py` | `send_message_stream` 插入记忆召回环节 |
| 2 | 前端 | 修改 | `front/src/stores/session.ts` | 增强 `Message` 接口与 SSE 处理逻辑 |
| 3 | 前端 | 修改 | `front/src/components/ChatArea.vue` | 引入并使用库中的工具展示组件 |

## 6. 分步实施指南 (Atomic Steps)

### 步骤 1: 后端管道集成
- **操作文件**: `server/app/services/chat_service.py`
- **逻辑描述**: 
    1. 在 `send_message_stream` 开始处读取 `memory` 和 `chat` 相关设置。
    2. 如果开启召回，获取当前会话的完整聊天记录（Messages），调用 `RecallService.perform_recall(db, user_id, space_id, messages, friend_id)` 获取召回数据和回忆 Agent 的足迹。
    3. 如果设置允许展示，将回忆 Agent 的 `thinking` 或 `tool_calls` 通过 `yield` 发送。
    4. 将 Profile 直接注入 System Prompt，并将召回结果作为 Prefix 消息注入到 `agent_messages` 中供给主 Agent。

### 步骤 2: 前端 Store 适配
- **操作文件**: `front/src/stores/session.ts`
- **逻辑描述**: 
    1. 在 `Message` 接口定义中增加：
       ```typescript
       toolCalls?: Array<{name: string, args: any, result?: any, status?: 'calling' | 'completed'}>
       ```
    2. 在 `sendMessage` 的 SSE 事件循环中增加两个分支：
       ```typescript
       else if (event === 'tool_call') {
         if (!messagesMap.value[friendId][msgIndex].toolCalls) {
           messagesMap.value[friendId][msgIndex].toolCalls = []
         }
         messagesMap.value[friendId][msgIndex].toolCalls.push({
           name: data.tool_name,
           args: data.arguments,
           status: 'calling'
         })
       } else if (event === 'tool_result') {
         const toolCall = messagesMap.value[friendId][msgIndex].toolCalls?.find(t => t.name === data.tool_name)
         if (toolCall) {
           toolCall.result = data.result
           toolCall.status = 'completed'
         }
       }
       ```
    3. 确保工具调用数据结构与后端推送的格式一致。

### 步骤 3: 完善聊天 UI 展示
- **操作文件**: `front/src/components/ChatArea.vue`
- **前置步骤**: 使用 `context7` 查询 `ai-elements-vue` 的 `Tool` 组件用法，确认 Props 和数据绑定方式。
- **逻辑描述**: 
    1. 在 `<script setup>` 中引入组件：
       ```typescript
       import { Tool, ToolHeader, ToolContent, ToolResult } from '@/components/ai-elements'
       ```
    2. 在模板的 `message-wrapper` 内部、`MessageContent` 上方，增加工具调用渲染：
       ```vue
       <div v-if="msg.toolCalls?.length" class="tool-calls-section">
         <Tool v-for="(toolCall, idx) in msg.toolCalls" :key="idx">
           <ToolHeader :name="toolCall.name" :status="toolCall.status" />
           <ToolContent :arguments="toolCall.args" />
           <ToolResult v-if="toolCall.result" :data="toolCall.result" />
         </Tool>
       </div>
       ```
    3. 针对 `recall_memory` 工具，可以自定义 `ToolResult` 的展示格式（仅 Events）。
    4. 确保工具调用区域在聊天气泡内有明显的视觉区分（颜色、边框等）。

## 7. 验收标准
- [ ] 开启「启用记忆召回」后，AI 的第一轮回复能表现出对用户过往信息的了解。
- [ ] 开启「显示工具调用」后，对话气泡上方会出现召回工具的调用状态。
- [ ] 开启「显示思维链」后，能看到回忆 Agent 搜索记忆时的推理过程。
