# Story: 多供应商配置管理 (Multi-Provider Configuration)

## 1. 需求详情 (Requirement Details)

### 1.1 背景
当前系统的 LLM 配置和 Embedding 配置采用的是“单例模式”，用户只能配置一个全局的 LLM 和一个全局的 Vector Model。
随着用户需求的多样化，用户可能同时拥有多个厂商的 API Key（如同时使用 OpenAI 和 智谱），并希望在不同场景下（或测试对比时）快速切换，而无需反复输入 Key 和 URL。
此外，聊天功能和记忆功能将来可能需要分别指定不同的模型（例如：聊天用高性能的 GPT-4，记忆提取用便宜的 MiniMax）。

### 1.2 目标
- **多配置管理**：允许用户创建、保存、编辑多个 LLM 和 Embedding 厂商的配置信息。
- **预设填充**：为不仅限于 OpenAI 的主流厂商（智谱、Anthropic、魔搭、MiniMax）提供预设的 Base URL，简化配置流程。
- **引用式选择**：在“聊天设置”和“记忆设置”中，通过下拉列表选择已配置好的供应商，实现配置与使用的解耦。

---

## 2. 用户故事 (User Stories)

### US-1: LLM 供应商列表管理
**作为** 一名用户，
**我希望** 在“LLM 设置”页签中看到一个配置列表，并能添加新的供应商配置，
**以便于** 我同时保存 OpenAI、智谱和本地模型的配置，方便随时调用。

### US-2: LLM 供应商预设
**作为** 一名用户，
**我希望** 当我选择“智谱”或“MiniMax”等供应商时，系统自动填好 Base URL，
**以便于** 我只需要去申请 API Key 和输入模型名称就能使用，不用去查文档找 URL。

### US-3: Embedding 供应商列表管理
**作为** 一名用户，
**我希望** 能够管理多个向量化模型配置（如 OpenAI 和 本地 Ollama），
**以便于** 我在不同环境或成本考量下切换记忆系统的后端。

### US-4: 绑定业务场景
**作为** 一名用户，
**我希望** 在“聊天设置”中选择“当前聊天模型”，在“记忆设置”中选择“当前向量模型”，
**以便于** 明确指定各个功能模块底层使用的具体资源。

---

## 3. 功能范围 (Functional Scope)

### 3.1 后端修改 (Backend)

#### 数据模型变更 (LLMConfig)
- 现有 `LLMConfig` 表结构需要升级，支持多条记录。
- 新增字段：
    - `provider`: string (枚举: openai, zhipu, anthropic, modelscope, minimax, openai_compatible)
    - `config_name`: string (用户自定义别名，如 "我的智谱", "公司OpenAI")
    - **`is_active`: boolean (标识该配置是否被全局选中，或通过 chat_settings 引用，此处建议仅作为 display helper，实际引用由 chat_settings 决定)**
    - **模型能力标识 (Boolean 字段)**:
        - `capability_vision`: 是否支持视觉/多模态
        - `capability_search`: 是否支持联网/搜索
        - `capability_reasoning`: 是否支持推理/深度思考 (CoT)
        - `capability_function_call`: 是否支持工具调用
- **迁移策略**：将现有的单条记录迁移为列表中的第一条，默认 provider 为 `openai`，能力默认全 false 或根据模型名猜测。

#### 数据模型变更 (SystemSettings / ChatSettings / MemorySettings)
- 在系统设置（或各模块设置）中，增加“当前激活的配置 ID”字段：
    - Chat Settings 增加: `active_llm_config_id` (ForeignKey -> llm_configs.id)
    - Memory Settings 增加: `active_embedding_config_id` (ForeignKey -> embedding_settings.id)
    - *注意：Memory Settings 原本直接读取 embedding settings 的逻辑需要改为读取这个 ID 指向的配置。*

#### API 调整
- `GET /api/llm/configs`: 获取配置列表。
- `POST /api/llm/configs`: 创建新配置。
- `PUT /api/llm/configs/{id}`: 更新指定配置。
- `POST /api/llm/configs/{id}/test`: 测试指定配置。
- 调整 `/api/settings/chat` 和 `/api/settings/memory` 以支持保存激活的 config_id。

### 3.2 前端修改 (Frontend - SettingsDialog)

#### Tab 1: LLM 设置 (重构)
- **左侧/顶部**：显示已添加的 LLM 配置列表（卡片或列表项）。
- **新增/编辑区**：
    - **供应商下拉框**：
        - 智谱 (Zhipu AI) -> `https://open.bigmodel.cn/api/paas/v4`
        - OpenAI -> `https://api.openai.com/v1`
        - Anthropic -> (需确认是否走 OpenAI 兼容层或独立处理，暂按 OpenAI 兼容层处理或特定 URL)
        - 魔搭 (ModelScope) -> `https://api-inference.modelscope.cn/v1`
        - MiniMax -> `https://api.minimax.chat/v1`
        - OpenAI (兼容) -> (空，用户自填)
    - **配置名称**：默认填入供应商名，可修改。
    - **API Key** & **Model Name** & **Base URL**。
    - **模型能力 (Checkboxes)**:
        - [ ] 视觉能力 (Vision)
        - [ ] 联网能力 (Browsing)
        - [ ] 推理能力 (Reasoning)
        - [ ] 工具调用 (Tool Call)
- **动作**：保存、删除、测试连接。

#### Tab 2: 向量化设置 (重构)
- 类似于 LLM 设置，改为列表管理。
- 利用现有 `embedding_settings` 表的多行能力。
- 供应商保持现有：OpenAI, Jina, LMStudio, Ollama。

#### Tab 3: 记忆设置 (修改)
- 移除原本直接配置 Embedding 参数的界面。
- 新增 **"选择向量模型"** 下拉框：列出 Tab 2 中已配置的有效 Embedding 配置。
- 展示选中配置的只读概览（如：模型名、维度）。

#### Tab 4: 聊天设置 (修改)
- 新增 **"选择聊天模型"** 下拉框：列出 Tab 1 中已配置的有效 LLM 配置。

---

## 4. 业务规则与交互细节 (Business Rules & Interaction Details)

### 4.1 模型能力的应用 (Capability Usage)
这些 Boolean 字段目前主要用于前端展示图标，部分字段开始控制后端业务逻辑：
- **`capability_vision` / `capability_search` / `capability_function_call`**: 本阶段仅用于记录和 UI 展示（如在列表上显示支持图标），**暂不影响业务逻辑**。
- **`capability_reasoning`**: **启用业务控制**。
    - **聊天设置**: 仅当为 true 时，聊天设置中的“启用深度思考模式”开关才可用（否则置灰并提示模型不支持）。
    - **记忆生成**: 后台生成记忆摘要时，若所选 LLM 支持推理，系统可自动利用推理能力提升摘要质量（具体 Prompt 策略待定，本期只需透传此标识）。

### 4.2 删除保护 (Deletion Protection)
- **规则**: 如果一个配置被 `ChatSettings.active_llm_config_id` 或 `MemorySettings.active_embedding_config_id` 引用，**禁止删除**。
- **交互**: 点击删除时，若被引用，弹出 Alert 提示：“该配置当前正在被 [聊天/记忆] 模块使用，请先切换到其他配置后再删除。”

### 4.3 初始状态与空处理 (Initialization & Empty States)
- **空列表**: 若配置列表为空，聊天/记忆设置的下拉框显示占位符“请先添加配置...”，点击可直接跳转到对应的添加 Tab。
- **默认命名**: 用户新建配置时，`config_name` 默认为供应商名称。若重复，自动追加序号（如 "智谱 #2"）。
- **数量上限**: 每个类型（LLM/Embedding）限制最多 **20** 条配置。

### 4.4 记忆设置的强约束
- **规则**: 无论 `recall_enabled` (记忆召回) 开关是否开启，**必须**选择一个有效的 Embedding 配置。
- **原因**: 向量化不仅用于“召回”，还用于后台的记忆“生成与存储”。若无配置，新产生的对话将无法转化为记忆。

### 4.5 测试与保存策略
- **规则**: “测试连接”失败**允许保存**配置。
- **交互**:
    - 测试失败仅展示红色错误提示，不禁用保存按钮。
    - 保存后，若最近一次测试失败，可以在列表项上显示一个黄/红色的警告小图标（“未验证”状态）。

### 4.6 供应商兼容性说明
- **Anthropic**: 本期仅支持 **OpenAI 兼容协议**（即 `/chat/completions` 接口）。若用户直接使用 Anthropic 原生 API，可能无法连接，UI 上应提示用户填写 OneAPI 或中转服务的兼容地址。

### 4.7 老用户数据迁移策略 (Legacy Data Migration)
为了确保老用户在升级后无需重新配置，必须在 Alembic 迁移脚本中实现以下 **无损迁移** 逻辑：

1.  **LLM 配置迁移**:
    - **检查**: 扫描 `llm_configs` 表中现有的有效记录（`deleted=False`）。
    - **转换**: 将找到的第一条记录（如有）转换为新格式：
        - `config_name`: 设为 "我的默认配置"。
        - `provider`: 默认为 `openai` (假设老用户均使用 OpenAI 兼容接口)。
        - `capability_search`/`capability_vision` 等能力字段: 默认为 `False` (安全起见)。
    - **关联**: 创建该记录后，获取其 ID，并自动更新 `system_settings` 表中的 `chat_settings` JSON，写入 `active_llm_config_id: <ID>`。

2.  **Embedding 配置迁移**:
    - **检查**: 扫描 `embedding_settings` 表中现有的有效记录。
    - **保留**: Embedding 表结构变更较小，主要任务是确保数据的连续性。
    - **关联**: 获取第一条有效记录的 ID，自动更新 `system_settings` 表中的 `memory_settings` JSON，写入 `active_embedding_config_id: <ID>`。

3.  **兜底**: 若旧表中无数据，则保持新字段为空，由前端引导用户进行初始化配置。

---

## 5. 预设参数参考 (Provider Presets)

| 供应商 (Label) | Provider Code | 预设 Base URL | 备注 |
| :--- | :--- | :--- | :--- |
| OpenAI | `openai` | `https://api.openai.com/v1` | 默认 |
| 智谱 AI | `zhipu` | `https://open.bigmodel.cn/api/paas/v4` | |
| 魔搭社区 | `modelscope` | `https://api-inference.modelscope.cn/v1` | |
| MiniMax | `minimax` | `https://api.minimax.chat/v1` | |
| Anthropic | `anthropic` | (空) | 提示用户填入 OpenAI 兼容中转地址 |
| OpenAI (兼容) | `openai_compatible` | (空) | 用户自定义 |

---

## 6. 验收标准 (Acceptance Criteria)

- [ ] **AC-1**: 多配置增删改查：用户可以添加多条 LLM/Embedding 配置，上限 20 条。
- [ ] **AC-2**: 预设填充体验：选择“智谱”等供应商自动填充 Base URL。
- [ ] **AC-3**: 业务绑定与生效：聊天设置切换 LLM 后，发送消息确实使用了新模型的 Key 和 URL。
- [ ] **AC-4**: 删除保护：试图删除当前正在使用的配置时，系统拦截并提示。
- [ ] **AC-5**: 能力门控：若选中的 LLM `capability_reasoning` 为 false，聊天设置里的“深度思考”开关应不可用。
- [ ] **AC-6**: 数据库迁移：旧版单条数据无缝迁移为列表第一条，且被默认选中，用户无感知。

