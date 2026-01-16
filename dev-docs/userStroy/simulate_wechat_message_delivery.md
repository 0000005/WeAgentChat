# 用户故事：模拟微信式消息接收（消除打字机感）

## 1. 需求背景
目前 AI 回复消息采用流式渲染（打字机效果），虽然体现了 AI 的响应性，但不符合微信等社交工具的真实感。在微信中，消息是收集完毕后“整体”弹出的。此外，为了简化 UI 并更贴近社交软件，我们需要移除“显示思维链”和“显示工具调用”的配置开关。

## 2. 核心目标 (User Goals)
- **视觉真实感**：AI 消息不再一个字一个字蹦出来，而是在后台悄悄接收，完成后“砰”地一下整体显示在聊天窗口。
- **UI 纯净性**：去掉技术化过强的开关（思维链/工具调用），让界面回归社交本质。
- **消除 Loading 焦虑**：移除明显的 Loader 图标和收集中状态，直到消息准备就绪。

## 3. 详细设计 (Technical Implementation)

### 3.1 前端状态变更 (Frontend Store)

#### A. `session.ts` 逻辑重构
目前的 `sendMessage` 直接将 SSE 的 `delta` 追加到响应式的 `message.content` 中。
**修改方案**：
- 在 `sendMessage` 内部引入局部变量（Buffer）作为缓冲区：`let contentBuffer = ""` 和 `let thinkingBuffer = ""`。
- 在 SSE 循环中，仅更新缓冲区，**不更新** `messagesMap` 中的响应式对象。
- 仅在接收到 `done` 事件或流结束时，一次性将 `contentBuffer` 赋值给 `messagesMap[friendId][msgIndex].content`。
- 同步更新侧边栏预览（`friendStore.updateLastMessage`）也改为在 `done` 时触发。

#### B. `settings.ts` 配置清理
- 逻辑上仍然保留 `showThinking` 和 `showToolCalls` 的状态字段（以防后端逻辑依赖），但在前端默认将其置为 `false`。

### 3.2 UI 界面变更 (View Changes)

#### A. `SettingsDialog.vue` (设置弹窗)
- **删除入口**：删除“聊天展示设置”选项卡中的以下内容：
    - “显示思维链”开关。
    - “显示工具调用”开关。
- **保留项**：保留“启用深度思考模式”，因为这影响后端生成的质量。

#### B. `ChatArea.vue` (聊天区域)
- **移除 Loading 状态**：删除 `isMessageLoading` 判断逻辑及其对应的 `loader` 组件。
- **条件渲染优化**：由于不再显示思维链和工具，相关的 `Reasoning` 和 `Tool` 组件在正常消息流中可以不再渲染，或仅作为调试/开关内部逻辑保留。
- **消息弹出动画**：消息在 `content` 填充的那一刻平滑弹出（见 3.4 动画方案）。

### 3.3 交互状态设计

#### "对方正在输入…" 状态
利用现有的 `isStreaming` 状态，在消息完成前提供视觉反馈，即使切走也能感知：

| 位置 | 显示方式 | 触发条件 |
|------|---------|---------|
| 聊天标题栏 | 好友名称下方显示 "对方正在输入…" 灰色小字 | 当前选中的好友正在 streaming |
| 侧边栏好友列表 | 对应好友的最新消息文字显示 "对方正在输入…" | 该好友正在后台 streaming |

#### 边界情况处理：多好友并发聊天与后台接收
针对用户在接收消息过程中切换好友的场景，系统需保证以下行为：

1. **并行接收隔离**：
   - 缓冲区（Buffer）定义在 `sendMessage` 函数局部作用域内。
   - 每个好友的 SSE 请求是独立流，互不干扰。即便用户从 A 切到 B，A 的 SSE 流仍在后台向其独立的局部变量写入，不会污染 B 的窗口。
2. **切走后的行为 (Visible to Invisible)**：
   - 后台继续静默接收。
   - 侧边栏显示 "对方正在输入…"。
3. **切回后的行为 (Invisible to Visible)**：
   - 若切回时消息已完成：消息气泡伴随弹入动画直接出现。
   - 若切回时仍在接收：用户看到的依然是标题栏的 "对方正在输入…"，直到接收完毕后气泡整体弹出。
4. **未读数同步**：
   - 接收完成时，若用户不在该好友聊天页，自动标记一条未读消息，侧边栏预览由 "对方正在输入…" 变为完整消息摘要。

| 场景 | 处理方式 |
|------|---------|
| SSE 中途断开 | 将已收集的 `contentBuffer` 追加 `[连接中断]` 后立即渲染 |
| 用户切换好友 | 缓冲区与 `friendId` 绑定，切换不影响后台收集，切回时若已完成则显示 |
| 接收 `error` 事件 | 立即将错误信息渲染到消息气泡 |
| 用户关闭窗口/应用 | 无需特殊处理，下次启动重新加载历史消息 |

#### Tool Calls 处理策略
- **收集但不渲染**：Tool Calls 信息仍在后台收集并存储到 `message.toolCalls` 对象中，供调试或日志使用。
- **缓冲区设计**：`toolCallsBuffer: ToolCall[]` 同样在 `done` 时一次性赋值。

### 3.4 动画方案
消息气泡弹出时使用 CSS 过渡动画，模拟微信消息"弹入"效果：
```css
.message-bubble {
  animation: message-pop-in 0.2s ease-out;
}

@keyframes message-pop-in {
  from { opacity: 0; transform: scale(0.95) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
```

## 4. 任务列表 (Task List)

- [x] **[Doc]** 细化并生成 User Story 文档。
- [ ] **[Store]** 修改 `useSessionStore.sendMessage`：实现流式数据离屏缓存（Buffering）。
- [ ] **[UI]** 修改 `SettingsDialog.vue`：移除显示思维链和显示工具的开关。
- [ ] **[UI]** 修改 `ChatArea.vue`：
    - 移除 `loading-bubble` 和打字机渲染逻辑。
    - 添加 "对方正在输入…" 状态指示器。
    - 添加消息弹出动画 CSS。
- [ ] **[UI]** 修改 `Sidebar.vue`：在 `isStreaming` 时显示 "对方正在输入…" 预览。

## 5. 验收标准 (Acceptance Criteria)
1. 发送消息后，不再看到字符逐个出现的过程。
2. 消息在一段时间的静默等待后，整段话直接出现在气泡中，并有轻微弹入动画。
3. 等待期间，标题栏或侧边栏显示 "对方正在输入…" 状态。
4. 设置中心不再提供 "显示思维链" 和 "显示工具" 的选项。
5. SSE 中断或出错时，用户能看到明确的错误提示。

## 6. 相关文件索引

```
front/
└── src/
    ├── stores/
    │   └── session.ts          # 核心修改：消息缓冲逻辑
    ├── components/
    │   ├── ChatArea.vue        # UI 修改：移除 loader、添加动画和输入状态
    │   ├── Sidebar.vue         # UI 修改：输入状态预览
    │   └── SettingsDialog.vue  # UI 修改：移除开关
    └── api/
        └── chat.ts             # 无需修改，SSE 解析逻辑不变
```
