# 全栈实施方案 - 记忆与聊天相关系统配置项

> **文档说明**: 本文档负责建立记忆召回和聊天展示的配置管理体系，涵盖后端存储初始化、前端状态管理以及 UI 交互界面。

## 1. 需求全景
### 1.1 业务背景
用户需要能够根据不同场景（如纯净对话 vs 系统调试）自由开启/关闭记忆召回功能，并调整检索的精细度。同时，开发者和高级用户希望能通过前端界面观察到 AI 的思维链和工具调用过程。Profile 将直接注入 System Prompt，不再依赖检索参数。

### 1.2 核心功能点
- **后端配置项初始化**: 在 `system_settings` 表中预设记忆和聊天的默认配置。
- **配置持久化接口**: 通过现有的 `SettingsAPI` 实现配置的读取与更新。
- **前端设置 Tab 扩展**: 在设置对话框中完善"记忆设置"并新增"聊天设置"。

## 2. 预备工作
### 2.1 依赖分析
- **后端**: `server/app/services/settings_service.py` 处理 `initialize_defaults`。
- **前端 Store**: `front/src/stores/settings.ts` 负责状态同步。
- **前端 UI**: `front/src/components/SettingsDialog.vue` 负责渲染交互。

### 2.2 UI 组件查询
在实施前端 UI 时，需要确认以下组件的使用方法：
- **Switch 组件**: 来自 `shadcn-vue`，用于开关类配置（如启用记忆召回）。
- **Input 组件**: 用于数字输入（`type="number"`），处理 TopK 和搜索轮数。
- **Slider 组件**: 来自 `shadcn-vue`，用于相似度阈值（0-1 范围）。

建议在实施步骤 3 前，先查阅 [shadcn-vue 官方文档](https://www.shadcn-vue.com/docs/components/switch) 确认 API。

## 3. 现状分析
- **后端**: 仅有 `session` 和基础 `chat` 配置。
- **前端 Store**: 只有 `passiveTimeout` 和 `enableThinking`。
- **前端 UI**: "记忆设置" Tab 只有会话超时设置，没有召回参数。

## 4. 核心方案设计
### 4.1 后端逻辑 (Logic & Data)
- **Settings 扩充**:
    - `memory` 组: `recall_enabled` (bool, true), `search_rounds` (int, 3), `event_topk` (int, 5), `similarity_threshold` (float, 0.5)。
    - `chat` 组: `show_tool_calls` (bool, false), `show_thinking` (bool, false)。

### 4.2 前端交互 (View & State)
- **useSettingsStore**:
    - 新增上述所有配置项的 `ref` 状态。
    - 实现 `fetchMemoryRecallSettings` / `saveMemoryRecallSettings`。
    - 实现 `fetchChatDisplaySettings` / `saveChatDisplaySettings`。
- **SettingsDialog.vue**:
    - **记忆设置 Tab**: 增加开关按钮、计数器 (Number Input) 和滑动条 (Slider)。
    - **聊天设置 Tab**: 新增此标签页，显示展示类开关。

## 5. 变更清单
| 序号 | 领域 | 操作类型 | 文件绝对路径 | 变更摘要 |
|:---|:---|:---|:---|:---|
| 1 | 后端 | 修改 | `server/app/services/settings_service.py` | `initialize_defaults` 增加记忆/展示配置项 |
| 2 | 前端 | 修改 | `front/src/stores/settings.ts` | 扩充配置项状态和存取 Action |
| 3 | 前端 | 修改 | `front/src/components/SettingsDialog.vue` | 完善记忆设置 UI，新增聊天设置 Tab |

## 6. 分步实施指南 (Atomic Steps)

### 步骤 1: 初始化后端默认配置
- **操作文件**: `server/app/services/settings_service.py`
- **逻辑描述**: 
    1. 在 `initialize_defaults` 方法的 `defaults` 列表中增加新配置项。
    2. 确保 `memory` 组包含召回开关、轮数、Event TopK、阈值。
    3. 确保 `chat` 组包含显示工具调用、显示思维链。

### 步骤 2: 扩展前端 Store 状态
- **操作文件**: `front/src/stores/settings.ts`
- **逻辑描述**: 
    1. 定义 `recallEnabled`, `searchRounds`, `eventTopk`, `similarityThreshold` 等响应式变量。
    2. 定义 `showToolCalls`, `showThinking` 响应式变量。
    3. 编写 `fetchMemorySettings` 和 `saveMemorySettings` 调用 `fetchSettings`/`saveSettings`。
    4. 更新 `fetchChatSettings` 和 `saveChatSettings` 映射更多字段。

### 步骤 3: 改造设置对话框 UI
- **操作文件**: `front/src/components/SettingsDialog.vue`
- **逻辑描述**: 
    1. 在左侧侧边栏新增「聊天设置」按钮，并将现有逻辑中的 `activeTab` 指向它。
    2. **记忆部分**: 在 `v-if="activeTab === 'memory'"` 下，使用 `Switch` 组件表现启用状态，`Input type="number"` 处理各 TopK，`Slider` 组件处理阈值。
    3. **聊天部分**: 增加 `v-else-if="activeTab === 'chat'"` 模板，放入显示思维链、显示工具调用的 `Switch` 组件。
    4. 更新 `onMounted` 和 `handleSave` 确保新配置被正确加载和按需存盘。

## 7. 验收标准
- [ ] 进入设置页面，可看到新增的「聊天设置」Tab。
- [ ] 在「记忆设置」中修改参数并保存后，刷新页面能获取到保存后的值。
- [ ] 后端数据库 `system_settings` 表在系统启动后自动生成了新配置项。
