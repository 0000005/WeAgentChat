# 前端开发文档 - Story 01-02

> **文档说明**: 本文档供 AI 编码助手在独立会话中执行。遵循原子化操作原则。

## 1. 需求全景
### 1.1 业务背景
在 Story 01-01 中，我们实现了单会话的模拟聊天。本 Story 旨在将聊天能力扩展为**多会话管理**。用户需要能够创建新对话、在多个历史对话间自由切换、删除不再需要的对话，并且所有对话记录及消息必须持久化在本地。

### 1.2 详细功能描述
- **多会话状态管理**:
    - 使用 Pinia 存储会话列表（Sessions）和消息映射（Message Map）。
    - 消息映射以 `sessionId` 为键，存储该会话的所有消息数组。
- **持久化策略**:
    - 监听 Store 变化，自动将数据同步至 `localStorage`（键名：`doudou_chat_storage`）。
    - 应用启动时从本地加载数据，若为空则初始化一个默认会话。
- **新建与切换**:
    - 点击“新对话”按钮：生成唯一 `sessionId`，标题默认为“新对话”，并自动切换至该会话。
    - 点击列表项：根据 ID 加载对应的消息流。
- **删除逻辑**:
    - 通过右键或操作菜单触发。
    - 需弹出二次确认对话框（Dialog）。
- **标题自动更新**:
    - 当一个标题为“新对话”的会话收到第一条用户消息时，自动截取消息前 15 个字符作为新标题。

### 1.3 边界与异常处理
- **删除唯一会话**: 如果删除后列表变为空，应立即自动创建一个新的“新对话”。
- **LocalStorage 容量限制**: 若写入失败，在控制台报错并提示用户，但不崩溃。
- **数据结构兼容**: 系统初始化时需校验本地数据的有效性，防止旧格式数据导致崩溃。

### 1.4 验收标准 (Acceptance Criteria)
- [ ] 侧边栏实时从 Store 读取会话列表并正确分组（今天/更早）。
- [ ] 点击“新对话”后，ChatArea 立即清空，侧边栏出现新项并处于选中态。
- [ ] 切换会话时，消息加载无延迟且滚动位置重置或到底。
- [ ] 会话删除后，相关消息记录在 `localStorage` 中同步清除。
- [ ] 刷新页面后，最后一个处于激活状态的会话仍保持激活。

## 2. 预备工作
### 2.1 参考文档
- **Pinia Setup Store**: 引用自 context7/vuejs/pinia 文档。
- **nanoid**: 用于生成 UUID。
- **UI 组件用法**:
    - `DropdownMenu`: 用于会话操作菜单。
    - `Dialog`: 用于删除确认。

## 3. 现状分析快照
- **分析文件列表**:
    - `e:/workspace/code/DouDouChat/front/src/components/Sidebar.vue`: 目前使用静态 `chatHistory` 数组，第 61-71 行是会话项渲染。
    - `e:/workspace/code/DouDouChat/front/src/composables/useMockChat.ts`: 第 11-18 行定义了局部的 `messages` ref，需要重构为读取 Store。
    - `e:/workspace/code/DouDouChat/front/src/components/ChatArea.vue`: 直接调用 `useMockChat`。
- **关键发现**:
    - 项目中尚未创建 `stores` 目录。
    - `Sidebar.vue` 缺乏删除逻辑和上下文菜单触发器。

## 4. 架构与逻辑设计
### 4.1 组件层次
- **Sidebar**
    - **Header** (包含“新对话”按钮)
    - **ScrollArea**
        - **SessionItem** (包含 DropdownMenu 用于操作)
- **ChatArea**
    - **Header** (显示当前会话名)
    - **Conversation** (绑定当前会话的消息)

### 4.2 状态管理 (Session Store)
**Store 定位**: `e:/workspace/code/DouDouChat/front/src/stores/session.ts`
- **State 定义**:
    - `sessions`: `Session[]` (`{ id, title, createdAt }`)
    - `messagesMap`: `Record<string, Message[]>`
    - `currentSessionId`: `string`
- **Actions**:
    - `createSession()`: 新建并设为当前。
    - `selectSession(id)`: 切换当前 ID。
    - `deleteSession(id)`: 删除并处理切换逻辑。
    - `addMessageToCurrent(message)`: 追加消息并更新标题。

### 4.3 交互流程
1. **新建**: 用户点击 -> `store.createSession` -> `watch` 触发 `localStorage` 同步。
2. **发送**: 用户提交消息 -> `useMockChat` 拦截 -> 调用 `store.addMessageToCurrent` -> 更新 `messagesMap`。
3. **持久化**: 使用 `watch` 深度监听 `sessions` 和 `messagesMap`，防抖处理后存入本地。

## 5. 详细变更清单
| 序号 | 操作类型 | 文件绝对路径 | 变更摘要 |
|------|----------|--------------|----------|
| 1    | 新增     | `e:/workspace/code/DouDouChat/front/src/stores/session.ts` | 创建多会话管理中心 Store |
| 2    | 修改     | `e:/workspace/code/DouDouChat/front/src/composables/useMockChat.ts` | 重构以接入全局 Store，移除本地 Ref |
| 3    | 修改     | `e:/workspace/code/DouDouChat/front/src/components/Sidebar.vue` | 接入 Store 列表渲染，添加“新对话”和右键菜单逻辑 |
| 4    | 修改     | `e:/workspace/code/DouDouChat/front/src/components/ChatArea.vue` | 更新 header 标题显示为当前会话名 |

## 6. 分步实施指南 (Atomic Steps)

### 步骤 1: 构建 Session Store
- **操作文件**: `e:/workspace/code/DouDouChat/front/src/stores/session.ts`
- **操作描述**: 
    1. 定义接口 `Session` 和 `Message`。
    2. 实现状态初始化：尝试从本地读取 JSON，解析失败则使用默认值。
    3. 实现 `createSession` 函数，使用 `nanoid()`。
    4. 实现 `deleteSession`：如果删除的是当前项，逻辑是先找到下一个可选项并切换。
    5. 实现 `addMessageToCurrent`：向映射表中推入消息，并判断是否需要截取前 15 字作为标题。
- **验证方法**: 手动修改控制台中的 Store 状态，观察 `localStorage` 是否同步。

### 步骤 2: 重构 useMockChat
- **操作文件**: `e:/workspace/code/DouDouChat/front/src/composables/useMockChat.ts`
- **操作描述**:
    1. 引入 `useSessionStore`。
    2. 将 `messages` 定义改为返回 `computed(() => store.currentMessages)`。
    3. 在 `append` 方法中，将新消息直接通过 `store.addMessageToCurrent` 注入。
- **验证方法**: 发送消息，确认消息被正确路由到了当前活跃会话中。

### 步骤 3: 改造侧边栏 UI
- **操作文件**: `e:/workspace/code/DouDouChat/front/src/components/Sidebar.vue`
- **操作描述**:
    1. 移除静态 `chatHistory` 数组。
    2. 计算属性 `groupedSessions`：根据 `createdAt` 对 `store.sessions` 进行分组（今天/更早）。
    3. 修改模板循环，绑定 `click` 切换。
    4. 使用 `DropdownMenu` 组件包裹会话项，点击菜单项触发删除 Dialog。
    5. 接入“新对话”按钮的点击事件。
- **验证方法**: 点击“新对话”，观察侧边栏是否出现新项；点击不同会话，观察聊天主界面内容是否变化。

### 步骤 4: 接入删除确认 Dialog
- **操作文件**: `e:/workspace/code/DouDouChat/front/src/components/Sidebar.vue`
- **操作描述**:
    1. 引入 `Dialog` 及其子组件。
    2. 在底部或组件外围定义全局删除确认框，状态由局部 Ref 控制（存储待删除的 sessionId）。
    3. 实现点击“确定”后调用 `store.deleteSession` 并关闭 Dialog。
- **验证方法**: 进行删除操作，确保不会在误触后直接删除，而是需点击确认。

## 7. 验收测试
- [ ] **多开测试**: 创建 5 个会话，分别发送不同内容，切换后内容一一对应。
- [ ] **冷启动测试**: 清空浏览器的 LocalStorage，刷新，确认系统自动生成一个“新对话”。
- [ ] **持久化测试**: 在 Session A 发送一条消息，刷新，消息依然在 Session A 下。
- [ ] **标题更新测试**: 在“新对话”中发送“今天天气真不错”，观察侧边栏标题是否变为“今天天气真不错”。
