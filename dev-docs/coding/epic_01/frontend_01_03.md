# 前端开发文档 - Story 01-03

> **文档说明**: 本文档供 AI 编码助手在独立会话中执行。遵循原子化操作原则。

## 1. 需求全景
### 1.1 业务背景
为了提供更丰富和灵活的角色扮演体验，用户需要在侧边栏直接管理 AI 人格（角色）。
不再隐藏在设置中，而是将“角色管理”提升为与“会话管理”同级的一级功能。

### 1.2 详细功能描述
- **侧边栏 Tab 布局**: 侧边栏顶部增加 Tab 切换器，分为“会话”和“角色”两个标签页。
- **会话 Tab (默认)**:
    - 保持原有的“新对话”按钮和会话历史列表。
- **角色 Tab**:
    - **新建角色入口**: 顶部提供“新建角色”按钮。
    - **角色列表**: 展示所有可用角色（预设 + 用户自定义）。
    - **角色操作**:
        - **点击**: 打开“编辑角色”弹窗（支持修改名称、描述、Prompt）。
        - **删除**: 列表项提供删除按钮（预设角色不可删除）。
        - **发起对话**: 在编辑弹窗或列表项中提供“对此角色发起对话”功能（创建新会话并指定该 personaId）。
- **数据持久化**:
    - 新增 `persona` store，支持 CRUD 操作并持久化到 LocalStorage。
    - Session 继续保存 `personaId` 和 `systemPrompt` (snapshot)。

### 1.3 边界与异常处理
- **预设角色保护**: 系统内置角色（如默认助手）禁止删除，ID 固定。
- **删除校验**: 删除角色时，若有历史会话引用该角色，不影响历史会话（因为 Session 保存了 snapshot），但无法再基于该角色创建新会话。
- **空状态**: 角色列表为空时（理论上不应发生，因有预设），显示引导文案。

### 1.4 验收标准 (Acceptance Criteria)
- [ ] AC-1: 侧边栏包含 Tab 切换（会话/角色），点击可切换视图。
- [ ] AC-2: “角色” Tab 下展示角色列表，并有“新建”按钮。
- [ ] AC-3: 点击“新建”或现有角色，弹出 Dialog，支持编辑名称、描述、System Prompt。
- [ ] AC-4: 编辑保存后，列表实时更新；删除角色后，列表项移除。
- [ ] AC-5: 能够从角色列表直接发起新对话，聊天界面 Header 显示该角色名称。

## 2. 预备工作
### 2.1 参考文档
- **shadcn-vue 组件**:
    - `Dialog`: 编辑/新建弹窗。
    - `Input`, `Textarea`: 表单输入。
    - `Button`: 交互按钮。
    - `ScrollArea`: 列表滚动。
    - *Tabs*: 项目中暂无 Tabs 组件，需使用 Button Group 或自行封装简单的 State Switch。

## 3. 现状分析快照
- **Sidebar.vue**: 
    - 目前直接渲染“新对话”和“列表”。
    - 需改造为条件渲染：`currentTab === 'sessions' ? <SessionList> : <PersonaList>`。
- **Stores**: 
    - 缺 `persona.ts`。
    - `session.ts` 需支持指定 personaId 创建会话。

## 4. 架构与逻辑设计
### 4.1 组件层次
```
Sidebar
 ├── SidebarTabs (Local State: activeTab)
 ├── SessionView (v-if="activeTab === 'sessions'")
 │    ├── NewChatButton
 │    └── SessionList
 └── PersonaView (v-if="activeTab === 'personas'")
      ├── NewPersonaButton
      ├── PersonaList
      └── PersonaEditorDialog (Shared for Create/Edit)
```

### 4.2 状态管理 (Store)
1.  **新建 `stores/persona.ts`**:
    - **State**: `personas` (Array).
    - **Actions**: 
        - `addPersona(persona)`
        - `updatePersona(id, updates)`
        - `deletePersona(id)`
        - `init()`: Load from storage, merge with presets (ensure presets exist).
    - **Model**: `Persona { id, name, description, systemPrompt, isPreset boolean }`.

2.  **修改 `stores/session.ts`**:
    - `createSession(personaId?: string)`: 
        - 接收可选参数。
        - 若传入 `personaId`，查找对应 Persona，将其 Prompt 复制到 `session.systemPrompt`。
        - 若未传入，使用默认 Persona。

### 4.3 交互流程
1.  **切换 Tab**: 用户点击“角色”，视图切换。
2.  **新建角色**: 
    - 点击“新建” -> 打开 Dialog (Empty Form)。
    - 填写 Name, Prompt -> Save -> `personaStore.addPersona` -> List Updates.
3.  **编辑角色**:
    - 点击角色卡片 -> 打开 Dialog (Filled Form)。
    - 修改 -> Save -> `personaStore.updatePersona`.
4.  **发起对话**:
    - 在角色卡片上点击“聊天”图标（或 Dialog 底部按钮）。
    - 调用 `sessionStore.createSession(persona.id)`。
    - 自动切换回“会话” Tab，并选中新会话。

## 5. 详细变更清单
| 序号 | 操作类型 | 文件绝对路径 | 变更摘要 |
|------|----------|--------------|----------|
| 1    | 新增     | `{项目根目录}/src/stores/persona.ts` | 人格 Store (CRUD) |
| 2    | 修改     | `{项目根目录}/src/stores/session.ts` | createSession 支持指定 persona |
| 3    | 新增     | `{项目根目录}/src/components/PersonaEditorDialog.vue` | 角色编辑/新建弹窗 |
| 4    | 修改     | `{项目根目录}/src/components/Sidebar.vue` | 实现 Tab 切换及角色列表视图 |
| 5    | 修改     | `{项目根目录}/src/components/ChatArea.vue` | 展示角色名称 (同前) |

## 6. 分步实施指南 (Atomic Steps)

### 步骤 1: 创建人格 Store
- **操作文件**: `{项目根目录}/src/stores/persona.ts`
- **操作描述**:
    1.  定义接口 `Persona`.
    2.  State: `personas`.
    3.  Init Logic: 检查 LocalStorage，若空则写入预设 (Default, Coder, Writer)。预设标记 `isPreset: true`。
    4.  Implement CRUD actions.
- **验证方法**: Console 测试 store 方法。

### 步骤 2: 升级 Session Store
- **操作文件**: `{项目根目录}/src/stores/session.ts`
- **操作描述**:
    1.  `createSession` 增加参数 `targetPersonaId`。
    2.  逻辑：根据 ID 获取 Persona (需引入 personaStore)，复制 `systemPrompt` 到 Session。
    3.  Action `updateSessionPrompt`: 允许在聊天中微调（可选，Story未明确禁止，保留以防万一）。
- **验证方法**: `createSession('coder-id')` 应创建带有代码 Prompt 的会话。

### 步骤 3: 实现角色编辑弹窗
- **操作文件**: `{项目根目录}/src/components/PersonaEditorDialog.vue`
- **操作描述**:
    1.  基于 `Dialog`。
    2.  Props: `open` (v-model), `personaId` (Optional, null for create).
    3.  Form: Name (Input), Description (Input), System Prompt (Textarea).
    4.  Save Handler: 判断是 Create 还是 Update。
    5.  "Chat" Button: 仅在 Edit 模式显示，点击调用 `createSession` 并 Emit `start-chat` 事件。
- **验证方法**: 独立引入 App.vue 测试 UI。

### 步骤 4: 重构 Sidebar 实现 Tab
- **操作文件**: `{项目根目录}/src/components/Sidebar.vue`
- **操作描述**:
    1.  引入 `PersonaEditorDialog` 和 `usePersonaStore`。
    2.  State: `currentTab` ('sessions' | 'personas').
    3.  **Template Header**: 增加两个 Button (Tab Trigger)，样式区分激活态。
    4.  **Content Area**:
        - `v-if="currentTab === 'sessions'"`: 保留原有代码（New Chat + Grouped List）。
        - `v-else`: 渲染 Persona List。
            - "New Persona" Button.
            - List Item: Name, Desc. Click -> Open Dialog.
            - Delete Button (prevent if `isPreset`).
    5.  处理 `start-chat` 事件: 关闭 Dialog, switch tab to 'sessions', select new session.
- **验证方法**: 完整流程测试：切换 Tab -> 新建角色 -> 编辑角色 -> 发起对话。

## 7. 验收测试
- [ ] **TC-01**: Sidebar 顶部可见“会话/角色”切换，默认“会话”。
- [ ] **TC-02**: 切换到“角色”，看到预设列表。
- [ ] **TC-03**: 新建角色 "TestRole"，输入 Prompt，保存成功。
- [ ] **TC-04**: 点击 "TestRole"，弹出编辑框，点击“发起对话”。
- [ ] **TC-05**: 自动跳转回“会话”列表，选中新会话，且 Header 显示 "TestRole"。