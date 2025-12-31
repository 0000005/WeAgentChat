# 前端开发文档 - Story 01-01

> **文档说明**: 本文档供 AI 编码助手在独立会话中执行。遵循原子化操作原则。

## 1. 需求摘要
- **核心目标**: 在现有 UI 基础上，接入 `ai-elements-vue` 组件库，并实现核心聊天交互（发送、模拟接收、滚动）。
- **验收标准**:
  - [ ] `ChatArea.vue` 使用 `Conversation`, `Message`, `PromptInput` 等 `ai-elements-vue` 组件重构。
  - [ ] 用户发送消息后，立即显示在界面上。
  - [ ] 发送后 1-2 秒显示模拟 AI 回复。
  - [ ] AI 回复具备打字机效果（流式输出模拟）。
  - [ ] 消息列表自动滚动到底部。
  - [ ] 输入为空时禁止发送。

## 2. 预备工作
### 2.1 依赖检查
- [x] 确保已安装包: `ai` (Vercel AI SDK Core), `vue`
- [x] 确保文件存在: 
    - `e:/workspace/code/DouDouChat/front/src/components/ai-elements/conversation/index.ts`
    - `e:/workspace/code/DouDouChat/front/src/components/ai-elements/message/index.ts`
    - `e:/workspace/code/DouDouChat/front/src/components/ai-elements/prompt-input/index.ts`
    - `e:/workspace/code/DouDouChat/front/src/components/ai-elements/loader/index.ts`

### 2.2 参考文档
- **核心组件用法**:
    - **Conversation**: 容器组件，利用 `vue-stick-to-bottom` 自动处理滚动。
      ```vue
      <Conversation>
        <ConversationContent>
          <Message v-for="m in messages" ... />
        </ConversationContent>
      </Conversation>
      ```
    - **Message**: 消息展示组件。
      ```vue
      <Message :from="msg.role"> <!-- role: 'user' | 'assistant' -->
        <MessageContent>{{ msg.content }}</MessageContent>
      </Message>
      ```
    - **PromptInput**: 输组件。
      ```vue
      <PromptInput @submit="handleSubmit">
        <PromptInputTextarea v-model="input" />
        <PromptInputSubmit />
      </PromptInput>
      ```

## 3. 现状分析快照
- **分析文件列表**:
    - `e:/workspace/code/DouDouChat/front/src/components/ChatArea.vue` (上次修改: 2025-12-29, 包含硬编码 UI 和 mock 数据)
    - `e:/workspace/code/DouDouChat/front/src/App.vue` (布局容器)
- **关键发现**:
    - `ChatArea.vue` 目前使用手动编写的 HTML/Tailwind 实现消息气泡和输入框，未利用已有的 `ai-elements` 组件。
    - 消息数据 `messages` 是组件内定义的 `ref`，包含硬编码的示例数据。
    - 缺少打字机效果逻辑。

## 4. 架构与逻辑设计

### 4.1 组件层次
- **ChatArea** (Smart Component)
    - **Conversation** (from `ai-elements`)
        - **ConversationContent**
            - **Message** (v-for messages)
                - **MessageAvatar** (可选)
                - **MessageContent**
                - **Loader** (当 AI 正在思考且无内容时显示)
    - **PromptInput** (from `ai-elements`)
        - **PromptInputTextarea**
        - **PromptInputActions** / **PromptInputSubmit**

### 4.2 状态管理 (Composable: `useMockChat`)
为了保持组件逻辑纯净，且模仿 Vercel AI SDK 的 `useChat` API 风格，我们将逻辑抽取到 Composable 中。

**File**: `e:/workspace/code/DouDouChat/front/src/composables/useMockChat.ts`

- **State**:
    - `messages`: `Ref<Message[]>` (Message: `{ id, role, content, createdAt }`)
    - `input`: `Ref<string>`
    - `status`: `Ref<'idle' | 'streaming' | 'submitted'>`
- **Actions**:
    - `handleSubmit`: 处理表单提交。
    - `append(message)`: 添加用户消息，并触发 Mock 回复。
    - `mockResponse()`:
        1. 等待 1-1.5s 延迟。
        2. 创建空 assistant 消息。
        3. 模拟流式打字（setInterval 每 30-50ms 追加字符）。

### 4.3 交互流程
1.  用户在 `PromptInput` 输入文本，点击发送。
2.  触发 `handleSubmit` -> 调用 `append({ role: 'user', content })`。
3.  用户消息立即上屏，清空输入框。
4.  设置 `status = 'submitted'` (显示加载/等待状态)。
5.  延迟 1s 后，系统创建一条空内容的 `assistant` 消息。
6.  进入 `streaming` 状态，Mock 文本逐字追加到该消息 `content` 中。
7.  完成后 `status = 'idle'`。

## 5. 详细变更清单
| 序号 | 操作类型 | 文件绝对路径 | 变更摘要 |
|------|----------|--------------|----------|
| 1    | 新增     | `e:/workspace/code/DouDouChat/front/src/composables/useMockChat.ts` | 创建 Mock 聊天逻辑 Hook |
| 2    | 修改     | `e:/workspace/code/DouDouChat/front/src/components/ChatArea.vue` | 移除硬编码 UI，替换为 `ai-elements-vue` 组件，接入 `useMockChat` |

## 6. 分步实施指南 (Atomic Steps)

### 步骤 1: 实现 useMockChat Composable
- **操作文件**: `e:/workspace/code/DouDouChat/front/src/composables/useMockChat.ts` (需新建目录 `composables` 如果不存在)
- **操作描述**:
    1.  定义 `Message` 接口 (`id`, `role`, `content` 等)。
    2.  导出 `useMockChat` 函数。
    3.  实现 `handleSubmit` 和模拟 AI 回复的打字机逻辑。
    4.  Mock 回复内容可以是固定的几句话随机选择（如 "这是一个模拟回复...", "DouDou 正在思考..."）。
- **验证方法**: 
    - 暂时无法直接运行，需通过步骤 2 集成后验证，或简单编写测试脚本。

### 步骤 2: 重构 ChatArea.vue
- **操作文件**: `e:/workspace/code/DouDouChat/front/src/components/ChatArea.vue`
- **操作描述**:
    1.  引入 `useMockChat`。
    2.  引入 `ai-elements-vue` 组件: `Conversation`, `Message`, `PromptInput` 等。
    3.  **替换 Template**: 删除原有 `<div class="flex-1 overflow-y-auto...">` 和输入框部分。
    4.  使用 `<Conversation>` 包裹 `<Message>` 列表。
    5.  处理 `Message` 的渲染：
        - 如果 `msg.role === 'user'`, `<Message from="user">...</Message>`
        - 如果 `msg.role === 'assistant'`, `<Message from="assistant">...</Message>`
    6.  在 `MessageContent` 中直接渲染文本。
    7.  在底部放置 `<PromptInput>`，绑定 `v-model` 到 `input`，监听 `@submit`。
    8.  **处理 Loading**: 当 `status === 'submitted'` (等待响应) 时，在消息列表最后显示一个带有 `<Loader />` 的消息或独立的 Loading 指示器。
- **验证方法**:
    - 运行 `npm run dev`。
    - 访问页面，检查 UI 是否变为 `ai-elements` 风格。
    - 发送消息，检查是否自动滚动，是否有打字机效果。

## 7. 验收测试
- [ ] **UI 检查**: 界面应使用 `ai-elements` 的组件样式（类似于 shadcn 风格）。
- [ ] **交互测试**: 输入 "Hello" -> 回车 -> 输入框清空 -> 用户消息出现 -> (1s后) -> AI 消息逐字出现。
- [ ] **滚动测试**: 发送多条消息，确保新消息出现时视口自动锁定在底部。
