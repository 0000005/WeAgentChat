# 用户故事：模拟微信消息切分交付 (Multi-Segment Message Delivery)

## 1. 需求背景
在真实的微信聊天中，用户很少发送一长段文字。相反，他们倾向于将想法切分成多条短消息发送（例如先打个招呼，再回答问题，最后追问一句）。这种"分段发送"的行为让对话显得更加自然、有节奏感。

目前 AI 的回复是作为一个整体消息返回的，这在长回复时显得非常不自然——就像在读一篇作文，而不是在和朋友聊天。

**核心原则：像真实微信一样。**

## 2. 核心目标 (User Goals)
- **社交真实感**：AI 能够像真人一样，根据对话内容自然地"分段"发送消息。
- **视觉一致性**：每一段消息在前端都显示为独立的聊天气泡，拥有各自的头像，与普通消息的间距和样式完全一致。
- **智能切分**：切分点由 AI 根据回复的语义逻辑（如转折、换题、追问）自主决定。

## 3. 详细设计 (Technical Implementation)

### 3.1 Prompt 规范 (Backend System Prompt)
修改 `server/app/prompt/chat/root_system_prompt.txt`，加入消息切分指令。

**注意**：由于系统存在"剧本化表达"开关（`script_expression`），Prompt 中的示例需要根据该开关动态调整。建议将分段指令拆分为独立的 Prompt 文件，并在 `chat_service.py` 中根据 `friend.script_expression` 选择性注入。

**要求**：
- 强制 AI 使用 `<message>` 标签包裹每一段回复。
- 严禁在标签外输出任何文字。
- 每个 `<message>` 块应是一个相对完整的表达单元。

**切分时机建议（引导 AI）**：
- 回答完一个问题，准备开始下一个话题时。
- 提供了详细信息后，进行情感关怀或反问时。
- 表达了多个独立的观点或信息点时。
- 长回复时，自然的停顿或换气点。

**示例（普通模式，未开启剧本化表达）**：
```
<message>好的，我帮你查了一下</message>
<message>这家店在市中心，口碑不错，人均80左右</message>
<message>你想什么时候去？我可以帮你看看有没有位子</message>
```

**示例（剧本化表达模式）**：
```
<message>(放下手机，抬起头看着你) 好的，我帮你查了一下</message>
<message>(指着屏幕) 这家店在市中心，口碑不错，人均80左右</message>
<message>(歪头，带着期待的眼神) 你想什么时候去？我可以帮你看看有没有位子</message>
```

#### Prompt 文件建议
为了支持两种模式，建议新增以下 Prompt 文件：
- `server/app/prompt/chat/message_segment_normal.txt`：普通模式的分段指令与示例。
- `server/app/prompt/chat/message_segment_script.txt`：剧本化表达模式的分段指令与示例。

在 `chat_service.py` 组装系统提示词时，根据 `friend.script_expression` 选择对应的 Prompt 文件注入。

### 3.2 前端解析与渲染逻辑 (Frontend Logic)

为了保持数据的一致性和简化实现，我们采取**"数据层保持原始，渲染层动态拆分"**的策略。

#### A. 解析函数 (Utility)
在 `session.ts` 或工具类中定义 `parseMessageSegments(content: string): string[]`：
- 若内容包含 `<message>` 标签，提取所有标签内的内容并过滤空行。
- 若内容不包含标签，返回包含原内容的单元素数组（兜底）。

#### B. `ChatArea.vue` —— 渲染层适配
修改消息循环逻辑。对 `assistant` 消息使用嵌套循环，每个分段都使用 `ai-elements-vue` 的核心组件包装，以保留 Markdown 和代码高亮能力：

```html
<!-- 逻辑示意 -->
<template v-for="msg in messages" :key="msg.id">
  <!-- AI 回复：动态拆分渲染 -->
  <template v-if="msg.role === 'assistant'">
    <div v-for="(segment, sIndex) in parseMessageSegments(msg.content)" 
         :key="msg.id + '-' + sIndex" 
         class="message-group group-assistant">
      <div class="message-avatar">...</div>
      
      <!-- 复用现有组件，保持 rich text 能力 -->
      <div class="message-bubble">
        <MessageContent>
          <MessageResponse :content="segment" />
        </MessageContent>
      </div>
    </div>
  </template>
  
  <!-- 用户消息：保持单气泡 -->
  <div v-else class="message-group group-user">
    <div class="message-avatar">...</div>
    <div class="message-bubble">
      <MessageContent>
        <MessageResponse :content="msg.content" />
      </MessageContent>
    </div>
  </div>
</template>
```

**这样做的好处**：
1.  **高级功能保留**：每个分段依然支持 Markdown、公式、代码高亮等。
2.  **视觉统一**：与之前的消息样式完全一致。
3.  **侧边栏预览简化**：侧边栏预览只需正则去掉标签显示纯文本即可。

### 3.3 边缘情况处理
... (内容保持不变)

| 场景 | 处理方式 |
|------|----------|
| **AI 未使用标签** | `parseMessageSegments` 返回原内容，渲染一个气泡（兜底方案）。 |
| **标签畸形/嵌套** | 正则匹配最外层完整闭合块，余下部分作为普通文本。 |
| **空 `<message>` 块** | 过滤掉内容为空或仅含空白字符的段落。 |
| **SSE 中途断开** | 渲染层依然对 `content` 进行解析，未闭合的末尾作为最后一段展示。 |

### 3.4 数据持久化策略
- **后端不改动**：后端照常存储 AI 返回的原始 `content`（包含 `<message>` 标签）。
- **前端负责解析**：无论是实时接收还是加载历史消息，解析工作均由前端完成。

## 4. 任务列表 (Task List)

- [ ] **[Prompt]** 新增 `server/app/prompt/chat/message_segment_normal.txt`，包含普通模式的分段指令与示例。
- [ ] **[Prompt]** 新增 `server/app/prompt/chat/message_segment_script.txt`，包含剧本化表达模式的分段指令与示例。
- [ ] **[Backend]** 修改 `server/app/services/chat_service.py`，根据 `friend.script_expression` 选择性注入对应的分段 Prompt。
- [ ] **[Store]** 在 `front/src/stores/session.ts` 或相关位置新增公共解析函数 `parseMessageSegments(content: string): string[]`。
- [ ] **[UI]** 修改 `front/src/components/ChatArea.vue`：
    - 引入解析函数。
    - 在消息列表中对 `assistant` 消息使用嵌套循环渲染多段气泡。
    - 确保每个分段气泡都带有正确的头像和样式。
- [ ] **[Store]** 修改 `front/src/stores/friend.ts`：
    - 在 `updateLastMessage` 中对预览文本进行标签过滤。
- [ ] **[Test]** 验证实时回复和历史消息回放是否皆能正确分段。
- [ ] **[Test]** 验证 AI 未使用标签时的兜底渲染逻辑。
- [ ] **[Test]** 验证剧本化表达模式下的分段显示。

## 5. 验收标准 (Acceptance Criteria)
1.  AI 回复长内容时，前端显示多个连续的聊天气泡，而不是一个巨型气泡。
2.  每个气泡都带有 AI 头像，间距、样式与普通消息完全一致。
3.  加载历史消息时，之前的 AI 回复也能正确分段显示。
4.  如果 AI 没有使用 `<message>` 标签，整体内容仍能作为一段正常显示。
5.  消息发送流程保持平滑，无卡顿。
6.  开启剧本化表达的好友，其 AI 回复的分段示例应带有"(动作/神态)"描述风格。

## 6. 相关文件索引

```
server/
└── app/
    ├── prompt/
    │   └── chat/
    │       ├── root_system_prompt.txt          # 可能需微调：预留分段指令注入点
    │       ├── message_segment_normal.txt      # 新增：普通模式分段指令
    │       └── message_segment_script.txt      # 新增：剧本化表达模式分段指令
    └── services/
        └── chat_service.py                     # 修改点：根据 script_expression 注入对应 Prompt

front/
└── src/
    └── stores/
        └── session.ts                          # 修改点：解析与拆分逻辑
```
