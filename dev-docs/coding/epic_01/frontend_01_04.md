# 前端开发文档 - Story 01-04

> **文档说明**: 本文档供 AI 编码助手在独立会话中执行。遵循原子化操作原则。

## 1. 需求全景
### 1.1 业务背景
用户需要配置 LLM (大语言模型) 的连接参数（如 API Key, Base URL），以便应用能够连接到实际的 AI 服务提供商。这是实现真实对话功能的前置条件。

### 1.2 详细功能描述
- **设置入口**: 在侧边栏底部添加“设置”按钮，点击后打开设置界面。
- **设置界面**:
    - 采用模态框 (Dialog) 形式。
    - **布局**: 左右分栏 (Master-Detail)。左侧为导航菜单（目前仅“LLM 设置”），右侧为具体配置表单。
- **LLM 配置项**:
    - **API Base URL**: 接口代理地址 (文本输入)。
    - **API Key**: 密钥 (密码输入，支持点击图标切换显示/隐藏)。
    - **Model Name**: 模型名称 (文本输入)。
- **持久化**: 所有配置项需保存到本地存储 (LocalStorage)，刷新不丢失。
- **界面联动**: 聊天输入框区域需展示当前配置的模型名称。

### 1.3 边界与异常处理
- **空值处理**: 允许字段为空，但后续 API 调用时需校验。
- **默认值**: 
    - Base URL 默认为空或提示 `https://api.openai.com/v1`。
    - Model Name 默认为 `gpt-3.5-turbo` (或其他占位符)。
- **持久化失败**: 若 LocalStorage 不可用，降级为内存存储（VueUse `useLocalStorage` 会自动处理）。

### 1.4 验收标准 (Acceptance Criteria)
- [ ] 侧边栏底部存在“设置”按钮，点击可打开设置弹窗。
- [ ] 弹窗左侧导航包含“LLM 设置”，且默认选中。
- [ ] 右侧表单包含 Base URL、API Key、Model Name 输入框。
- [ ] API Key 输入框右侧有“眼睛”图标，可切换明文/密文显示。
- [ ] 修改配置后，刷新页面数据依然存在。
- [ ] 聊天输入框区域（左下角或其他合适位置）显示当前配置的模型名称。

## 2. 预备工作
### 2.1 参考文档
- **Pinia**: 状态管理。
- **VueUse**: `useLocalStorage` 用于持久化。
- **Shadcn Vue**: 
    - `Dialog`: 弹窗容器。
    - `Input`: 输入框。
    - `Button`: 按钮。
    - `Lucide Icons`: `Settings`, `Eye`, `EyeOff`.

## 3. 现状分析快照
- **分析文件列表**:
    - `{项目根目录}/front/src/components/Sidebar.vue`: 现有侧边栏，包含静态的设置按钮。
    - `{项目根目录}/front/src/components/ChatArea.vue`: 聊天区域，需添加模型名称显示。
    - `{项目根目录}/front/src/stores/session.ts`: 现有 Session Store 参考。
    - `{项目根目录}/front/src/components/PersonaEditorDialog.vue`: 现有 Dialog 实现参考。
- **关键发现**:
    - `Sidebar.vue` 第 235 行左右已有 `<Settings :size="18" />` 按钮，但未绑定点击事件。
    - `ChatArea.vue` 的输入框区域 (`PromptInput`) 底部左侧目前为空 (`<div class="flex gap-2"></div>`)，适合放置模型名称。
    - 项目未安装 `pinia-plugin-persistedstate`，需使用 `@vueuse/core` 的 `useLocalStorage` 手动管理持久化。

## 4. 架构与逻辑设计
### 4.1 组件层次
```
App
 ├── Sidebar
 │    └── SettingsDialog (新增)
 │         ├── 侧边导航 (Tab List)
 │         └── LLM配置表单 (Tab Content)
 └── ChatArea
```

### 4.2 状态管理
**Store**: `src/stores/llm.ts` (新增)
- **State**:
    - `apiBaseUrl`: string (持久化)
    - `apiKey`: string (持久化)
    - `modelName`: string (持久化)
- **Actions**:
    - `setApiBaseUrl(url: string)`
    - `setApiKey(key: string)`
    - `setModelName(name: string)`

### 4.3 交互流程
1. **打开设置**: 用户点击 Sidebar 底部设置按钮 -> `isSettingsOpen = true` -> 渲染 `SettingsDialog`。
2. **修改配置**: 用户输入内容 -> 双向绑定到 Store (或组件内临时状态，保存时写入 Store)。*注：为简化交互，本阶段可直接双向绑定到 Store，或使用 `v-model` 绑定到组件状态，关闭/失焦时保存。鉴于设置通常即时生效或需明确保存，建议采用“即时保存”或“简单的双向绑定”模式，利用 `useLocalStorage` 的响应式特性。*
3. **查看模型**: `ChatArea` 读取 `llmStore.modelName` 并显示。

## 5. 详细变更清单
| 序号 | 操作类型 | 文件绝对路径 | 变更摘要 |
|------|----------|--------------|----------|
| 1    | 新增     | `{项目根目录}/front/src/stores/llm.ts` | 创建 LLM 配置 Store，实现持久化 |
| 2    | 新增     | `{项目根目录}/front/src/components/SettingsDialog.vue` | 新增设置弹窗组件，包含 LLM 配置表单 |
| 3    | 修改     | `{项目根目录}/front/src/components/Sidebar.vue` | 引入 SettingsDialog，绑定设置按钮点击事件 |
| 4    | 修改     | `{项目根目录}/front/src/components/ChatArea.vue` | 在输入框下方显示当前模型名称 |

## 6. 分步实施指南 (Atomic Steps)

### 步骤 1: 创建 LLM Store
- **操作文件**: `{项目根目录}/front/src/stores/llm.ts`
- **操作描述**:
    1. 定义 `useLlmStore`。
    2. 使用 `ref` 定义 `apiBaseUrl`, `apiKey`, `modelName`。
    3. 使用 `@vueuse/core` 的 `useLocalStorage` 包装这些 ref，以实现自动持久化。
    4. 设置默认值：`modelName` 默认为 "gpt-3.5-turbo"。
- **验证方法**: 在控制台执行 `const store = useLlmStore(); store.modelName = 'test';` 刷新页面后检查值是否保留。

### 步骤 2: 创建 SettingsDialog 组件
- **操作文件**: `{项目根目录}/front/src/components/SettingsDialog.vue`
- **操作描述**:
    1. 引入 `Dialog` 系列组件 (参考 `PersonaEditorDialog.vue`)。
    2. 定义 `props`: `open` (boolean)。
    3. 定义 `emits`: `update:open`。
    4. 布局设计：
        - 使用 `flex` 布局，左侧宽约 150px (border-r)，右侧自适应。
        - 左侧：垂直按钮列表，目前仅一个 "LLM 设置" 按钮 (高亮选中状态)。
        - 右侧：表单区域。
    5. 表单实现：
        - **API Base URL**: Label + Input (text).
        - **API Key**: Label + Input (password) + Toggle Button (Eye/EyeOff icon). *提示：可以将 Button 绝对定位在 Input 右侧，或使用 Flex 布局组合 Input 和 Button。*
        - **Model Name**: Label + Input (text).
    6. 数据绑定：直接绑定到 `useLlmStore` 的状态，或使用组件内 `ref` 并在 `watch` 中同步（鉴于 `useLocalStorage` 是响应式的，直接绑定 `v-model="llmStore.apiBaseUrl"` 最简单且符合 Story 需求）。
- **验证方法**: 临时在 App.vue 引入并显示，检查布局和输入是否工作。

### 步骤 3: 集成到 Sidebar
- **操作文件**: `{项目根目录}/front/src/components/Sidebar.vue`
- **操作描述**:
    1. 导入 `SettingsDialog.vue`。
    2. 添加状态 `isSettingsOpen` (ref boolean)。
    3. 在模板底部 `<Settings />` 按钮处添加 `@click="isSettingsOpen = true"`。
    4. 在模板末尾引入 `<SettingsDialog v-model:open="isSettingsOpen" />`。
- **验证方法**: 点击侧边栏设置按钮，弹窗正常弹出；点击遮罩或关闭按钮可关闭。

### 步骤 4: 更新 ChatArea 显示模型名称
- **操作文件**: `{项目根目录}/front/src/components/ChatArea.vue`
- **操作描述**:
    1. 导入 `useLlmStore`。
    2. 在 `<PromptInput>` 内部的左下角插槽区域 (`<div class="flex gap-2"></div>`)。
    3. 添加一个显示元素（如 `<span class="text-xs text-gray-400 font-medium">`）。
    4. 内容绑定 `llmStore.modelName`。
    5. *可选*：添加一个小的图标（如 `Bot` 或 `Sparkles`）在文字前。
- **验证方法**: 检查输入框左下角是否显示了在设置中配置的模型名称。

## 7. 验收测试
- [ ] **Case 1**: 打开应用，点击左下角设置按钮，看到设置弹窗。
- [ ] **Case 2**: 在设置弹窗中输入 Model Name 为 "gpt-4"，关闭弹窗。
- [ ] **Case 3**: 观察聊天界面输入框下方，应显示 "gpt-4"。
- [ ] **Case 4**: 刷新页面，打开设置弹窗，Model Name 仍为 "gpt-4"。
- [ ] **Case 5**: 输入 API Key，点击眼睛图标，能在明文/密文间切换。
