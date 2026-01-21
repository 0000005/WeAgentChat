# Story: 多供应商配置管理 (Multi-Provider Configuration)

## 1. 需求详情 (Requirement Details)

### 1.1 背景
当前系统的 LLM 配置和 Embedding 配置采用的是“单例模式”，用户只能配置一个全局的 LLM 和一个全局的 Vector Model。
随着用户需求的多样化，用户可能同时拥有多个厂商的 API Key（如同时使用 OpenAI 和 智谱），并希望在不同场景下（或测试对比时）快速切换，而无需反复输入 Key 和 URL。
此外，聊天功能和记忆功能将来可能需要分别指定不同的模型（例如：聊天用高性能的 GPT-4，记忆提取用便宜的 MiniMax）。

### 1.2 目标
- **多配置管理**：允许用户创建、保存、编辑多个 LLM 和 Embedding 厂商的配置信息。
- **预设填充**：为不仅限于 OpenAI 的主流厂商（智谱、魔搭、MiniMax）提供预设的 Base URL，简化配置流程。
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
    - `provider`: string (枚举: openai, zhipu, modelscope, minimax, openai_compatible)
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
    - **记忆生成**: 后台生成记忆摘要时，若所选 LLM 支持推理（`capability_reasoning=True`），系统在调用 LLM 时会自动透传 `enable_thinking=True` 参数（或在 Prompt 中引导推理），以提升摘要的逻辑性。

### 4.2 UI/UX 展示细节
- **状态标记**:
    - **[使用中] 标签**: 在配置列表中，如果该配置被选中为当前聊天或记忆模型，应显示明显的绿色“当前使用”标签。
    - **[验证] 图标**: 根据 `is_verified` 字段，在图标旁边显示绿色对勾（验证通过）或灰色小图标（未验证/过期）。
- **能力图标**: 在卡片一角显示功能能力图标（如眼睛、大脑、扳手等），帮助用户快速区分配置用途。

### 4.3 删除保护 (Deletion Protection)
- **规则**: 如果一个配置被 `ChatSettings.active_llm_config_id` 或 `MemorySettings.active_embedding_config_id` 引用，**禁止删除**。
- **交互**: 点击删除时，若被引用，弹出 Alert 提示：“该配置当前正在被 [聊天/记忆] 模块使用，请先切换到其他配置后再删除。”

### 4.4 初始状态与空处理 (Initialization & Empty States)
- **空列表**: 若配置列表为空，聊天/记忆设置的下拉框显示占位符“请先添加配置...”，点击可直接跳转到对应的添加 Tab。
- **默认命名**: 用户新建配置时，`config_name` 默认为供应商名称。若重复，自动追加序号（如 "智谱 #2"）。
- **数量上限**: 每个类型（LLM/Embedding）限制最多 **20** 条配置。

### 4.5 记忆设置的强约束
- **规则**: 无论 `recall_enabled` (记忆召回) 开关是否开启，**必须**选择一个有效的 Embedding 配置。
- **原因**: 向量化不仅用于“召回”，还用于后台的记忆“生成与存储”。若无配置，新产生的对话将无法转化为记忆。

### 4.6 测试与保存策略
- **规则**: “测试连接”失败**允许保存**配置。
- **交互**:
    - 测试失败后，保存时 `is_verified` 设为 false。
    - 成功后且保存后，`is_verified` 设为 true。

### 4.7 老用户数据迁移策略 (Legacy Data Migration)
为了确保老用户在升级后无需重新配置，必须在 Alembic 迁移脚本中实现以下 **无损迁移** 逻辑：

1.  **LLM 配置迁移**:
    - **检查**: 扫描 `llm_configs` 表中现有的有效记录（`deleted=False`）。
    - **转换**: 将找到的第一条记录（如有）转换为新格式：
        - `config_name`: 设为 "我的默认配置"。
        - `provider`: 默认为 `openai`。
        - **智能识别能力**:
            - 若 `model_name` 包含 `r1`, `o1`, `reasoning`, `deepseek-chat` (新版), `gpt-4o` 等关键词，则 `capability_reasoning` 默认置为 `True`。
            - 其余能力默认为 `False`。
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
| OpenAI (兼容) | `openai_compatible` | (空) | 用户自定义 |

---

## 6. 验收测试用例 (Acceptance Test Cases)
用于与浏览器配合进行端到端验证。

### TC-01: LLM 配置 - 添加与预设填充
**前置条件**: 打开设置 -> LLM 设置
1. 点击“添加配置”按钮（或“+”号）。
2. 在“供应商”下拉框中选择 `智谱 (Zhipu AI)`。
3. **验证**: Base URL 自动变更为 `https://open.bigmodel.cn/api/paas/v4`。
4. **验证**: 配置名称自动填入 `智谱 (Zhipu AI)` (若无重名)。
5. 修改供应商为 `OpenAI`。
6. **验证**: Base URL 自动变更为 `https://api.openai.com/v1`。
7. 输入有效的 API Key 和 Model Name (e.g. `gpt-4o`)。
8. 点击“保存”。
9. **验证**: 配置列表中出现新卡片，Toast 提示保存成功。

### TC-02: LLM 配置 - 测试连接与能力验证
**前置条件**: 有一个已保存的 OpenAI 配置
1. 编辑该配置，故意修改 API Key 为错误值。
2. 点击“测试连接”。
3. **验证**: 出现错误提示 Toast，且不阻碍再次保存。
4. 修正 API Key 为正确值，勾选 `推理能力 (Reasoning)`。
5. 点击“测试连接”。
6. **验证**: 提示测试成功。
7. 保存并返回列表。
8. **验证**: 卡片上出现“已验证”对勾图标，以及代表推理能力的图标。

### TC-03: Embedding 配置 - 数据强约束
**前置条件**: 打开设置 -> 记忆设置
1. 尝试将“选择向量模型”置空（如果 UI 允许）或删除当前选中的 Embedding 配置。
2. 在 Embedding 设置 Tab，尝试删除当前正在被“记忆设置”选中的配置。
3. **验证**: 弹出删除保护警告：“该配置当前正在被记忆模块使用...”，删除失败。
4. 新建一个 Embedding 配置 (e.g. Ollama)。
5. 回到“记忆设置”，切换向量模型为新的配置。
6. 回到 Embedding 设置 Tab，删除旧的配置。
7. **验证**: 删除成功，列表项消失。

### TC-04: 聊天与记忆的独立配置绑定
**前置条件**: 系统中有 2 个不同 LLM (A: GPT-4, B: DeepSeek) 和 2 个不同 Embedding (X: OpenAI, Y: Ollama)
1. 进入“聊天设置”，选择“聊天模型”为 **A**。
2. 进入“记忆设置”，选择“向量模型”为 **Y**。
3. 发起一段对话。
4. (开发者工具/日志验证): 聊天接口 `/api/chat/completions` 调用的是 **A** 的 BaseURL。
5. (开发者工具/日志验证): 后台记忆生成/RAG 检索调用的是 **Y** 的接口。
6. 进入“聊天设置”，切换模型为 **B**。
7. 再次对话。
8. **验证**: 聊天接口响应变为 **B**，且不需要重新输入 Key。

### TC-05: 推理能力的UI联动
**前置条件**: 配置 LLM-1 `capability_reasoning=False`, LLM-2 `capability_reasoning=True`
1. 在“聊天设置”中选择 **LLM-1**。
2. **验证**: 下方的“启用深度思考模式”开关应为**不可用/置灰**状态。
3. 切换模型为 **LLM-2**。
4. **验证**: “启用深度思考模式”开关变为**可用**状态。
5. 开启“深度思考模式”。
6. 发送消息。
7. **验证**: 应该能看到思维链/Reasoning 的输出（如果前端已实现该显示组件）。

### TC-06: 默认迁移验证 (Smoke Test)
**前置条件**: 这是一个从旧版本升级上来的环境 (DB 中有旧数据)
1. 打开“LLM 设置”。
2. **验证**: 存在一个名为“我的默认配置”的条目。
3. **验证**: 其 Provider 为 `openai`。
4. **验证**: 如果旧模型名是 `gpt-4o`，验证其 `推理能力` 是否被勾选（根据规则）。
5. 打开“聊天设置”。
6. **验证**: “当前聊天模型”已自动选中这个默认配置，而非为空。

### TC-07: 边界情况 - 默认命名与数量上限
**前置条件**: 打开设置 -> LLM 设置
1. 添加一个供应商为 `智谱 AI` 的配置，保存。
2. 再次点击“添加配置”，选择供应商为 `智谱 AI`。
3. **验证**: 配置名称自动变为 `智谱 AI #2`。
4. (自动化/压力测试建议): 尝试添加超过 20 个 LLM 配置。
5. **验证**: 达到 20 个后，前端应阻断“添加”操作或保存时返回错误提示。

### TC-08: 交互细节 - OpenAI (兼容) 处理
**前置条件**: 打开设置 -> LLM 设置
1. 点击“添加配置”，供应商选择 `OpenAI (兼容)`。
2. **验证**: Base URL 字段应为**空**，且提示用户手动输入。
3. 输入非 URL 格式字符串。
4. **验证**: 前端应有基本校验提示。

### TC-09: 交互细节 - 状态标记 [使用中]
**前置条件**: 已有多个 LLM 和 Embedding 配置
1. 在“聊天设置”中选中 `我的智谱`。
2. 返回“LLM 设置”列表。
3. **验证**: `我的智谱` 配置卡片上显示明显的“使用中”或“当前聊天”绿色标签。
4. 在“记忆设置”中选中 `Jina Embedding`。
5. 返回“向量化设置”列表。
6. **验证**: `Jina Embedding` 卡片上显示代表正在被内存模块使用的标签。

### TC-10: 空状态引导
**前置条件**: 清空所有 LLM 配置
1. 进入“聊天设置”。
2. **验证**: 下拉框显示“请先添加配置...”。
3. 点击下拉框或旁边的提示。
4. **验证**: 视图自动跳转到“LLM 设置”页签，并可能自动弹出“添加”窗口。

### TC-11: 记忆设置的强约束
**前置条件**: 已有一个有效的 Embedding 配置
1. 在“记忆设置”中，关闭“开启记忆召回”开关。
2. **验证**: “选择向量模型”下拉框仍然是**必选**且生效的（因为后台生成记忆仍需向量化）。
3. 尝试在关闭召回的情况下将向量模型设为空或删除对应配置。
4. **验证**: 系统应阻止保存或提示必须选择模型。

### TC-12: Embedding 供应商预设验证
**前置条件**: 打开设置 -> 向量化设置
1. 分别切换供应商为 `OpenAI`, `Jina`, `Ollama`, `LMStudio`。
2. **验证**: 各供应商的 Base URL 应自动填充为对应的默认值（如 Ollama 默认 `http://localhost:11434/v1`）。
3. **验证**: 切换时，原本填写的 API Key 若非供应商默认值，不应被错误清空（视具体 UX 设计而定，但需验证逻辑一致性）。

---

## 7. 执行进度 (Progress Update)

### 7.1 已完成
- 后端多配置模型与迁移：`llm_configs`/`embedding_settings` 新字段 + Alembic 迁移；激活配置 ID 存储到 `system_settings`。
- 后端 API 调整：`/api/llm/configs` CRUD + 测试；Embedding 多配置接口与删除保护。
- 业务逻辑绑定：聊天/记忆使用 active config；`capability_reasoning` 门控深度思考；Memobase 记忆摘要引导推理提示。
- 前端设置页重构：LLM/向量化列表管理、供应商预设、能力图标、验证状态、使用中标记。
- 业务绑定 UI：聊天/记忆设置下拉选择 active config，空状态引导。
- 交互优化：新增配置时列表即时出现“未保存”草稿项，且可删除草稿。
- 测试修复：单测适配多配置逻辑，`pytest` 全量通过（排除 `memory_extraction_complex` 调试脚本）。
- 维护约束：`server/app/db/init.sql` 已还原，结构变更仅通过 Alembic。

### 7.2 待补充/待验证
- 向量化设置的供应商 Base URL 预设自动填充（TC-12）。
- OpenAI 兼容模式下 Base URL 格式校验提示（TC-08）。
