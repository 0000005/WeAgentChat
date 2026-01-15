# Profile ChatFlow 分层测试方案

目标：把“chatHistory -> profile”长链路拆解成可控、可复现、可回归的分层测试，覆盖多场景、多对话数据，定位偏差来源。

## 总体原则
- 分层测试优先：summary -> extract -> merge -> organize/re_summary -> event_tagging。
- 全程真实调用 LLM：不做 mock，直接验证实际行为与效果。
- 记录中间产物：每层都产出可读的“中间结果”，便于回放与比对。
- 多场景覆盖：同一层至少 3-5 个场景用例，覆盖边界与异常。

## 测试分层与关注点

### 1) Summary 层：`entry_chat_summary`
目标：把 chatHistory 压缩成合理的 `user_memo_str`，不丢失关键事实。
关注点：
- 是否融合当前已有 profile 语境。
- 是否符合事件主题要求（`event_theme_requirement`）。
- 结果为空时是否合理。
对应 prompt：
- `server/app/vendor/memobase_server/prompts/summary_entry_chats.py`
- `server/app/vendor/memobase_server/prompts/zh_summary_entry_chats.py`
输入：
- chatHistory + 当前 profiles + profile 槽位配置。
输出：
- `user_memo_str`（文本）。

### 2) Extract 层：`extract_topics`
目标：从 `user_memo_str` 中抽取结构化 facts（topic/subtopic/memo）。
关注点：
- 抽取完整性：关键事实是否全部被抽到。
- 抽取准确性：topic/subtopic 是否落到正确槽位。
- 过滤机制：`allowed_topic_subtopics` 是否生效。
对应 prompt：
- `server/app/vendor/memobase_server/prompts/extract_profile.py`
- `server/app/vendor/memobase_server/prompts/zh_extract_profile.py`
输入：
- `user_memo_str` + profile 槽位配置。
输出：
- `fact_contents` / `fact_attributes`。

### 3) Merge 层：`merge_or_valid_new_memos`（当前为 yolo）
目标：对每条 fact 决定 UPDATE/APPEND/ABORT。
关注点：
- 当已有 profile 存在时，合并策略是否合理。
- ABORT 是否仅在无效内容出现时触发。
- `profile_validate_mode` 关闭时是否跳过校验并直接 ADD。
对应 prompt（当前实际调用 yolo 版本）：
- `server/app/vendor/memobase_server/prompts/merge_profile_yolo.py`
- `server/app/vendor/memobase_server/prompts/zh_merge_profile_yolo.py`
备用 prompt（非 yolo，需手动切换调用）：
- `server/app/vendor/memobase_server/prompts/merge_profile.py`
- `server/app/vendor/memobase_server/prompts/zh_merge_profile.py`
输入：
- facts + 当前 profiles。
输出：
- `add` / `update` / `update_delta` / `delete`。

### 4) Organize 层：`organize_profiles`
目标：当某 topic 下 subtopic 过多时进行重组。
关注点：
- 触发条件：`> CONFIG.max_profile_subtopics` 是否生效。
- 重组后内容是否被去重、归并合理。
对应 prompt：
- `server/app/vendor/memobase_server/prompts/organize_profile.py`

### 5) Re-summary 层：`re_summary`
目标：当单条 memo 过长时摘要压缩。
关注点：
- 触发条件：`> CONFIG.max_pre_profile_token_size`。
- 摘要后是否保留核心信息。
对应 prompt：
- `server/app/vendor/memobase_server/prompts/summary_profile.py`

### 6) Event Tagging 层：`tag_event`
目标：从摘要中生成事件标签，便于后续检索。
关注点：
- 标签是否覆盖关键主题。
- 失败时是否返回空标签并记录日志。
对应 prompt：
- `server/app/vendor/memobase_server/prompts/event_tagging.py`

## 场景用例设计（建议最少 12-15 个）

### A. 生活作息与偏好类（基础场景）
1. 晚睡 + 黑咖啡偏好（常规）
2. 改作息：从“早睡”变“晚睡”（更新）
3. 否定偏好：从“喜欢甜食”变“最近戒糖”（更新）

### B. 工作与压力类（更新/追加）
4. 连续加班两周（追加）
5. 由“兼职”变为“全职”（替换/更新）
6. 只提及“最近很忙”但无具体事实（可能 ABORT）

### C. 关系与身份类（多槽位）
7. 新增“家人”信息（新增）
8. 朋友关系变化（更新）

### D. 多事实混合（覆盖多 topic）
9. 一段对话同时包含工作/作息/饮食（抽取完整性）
10. 同 topic 多 subtopic（organize 触发）

### E. 边界与异常（稳定性）
11. `user_memo_str` 为空（流程终止）
12. facts 全部不在允许槽位（extract 过滤）
13. 单条 memo 超长（re_summary 触发）
14. LLM 输出无法解析（merge ABORT/日志）
15. 事件标签为空（tag_event 返回空）

## 对话数据构造模板（示例格式）
每个用例建议包含：
- **聊天记录**：时间序列 + 说话人
- **当前 profiles**：至少 1-3 条已存在内容
- **期望抽取**：期望的 facts（topic/subtopic/memo）
- **期望合并**：UPDATE/APPEND/ADD/ABORT 结果
- **预期事件标签**

## 执行策略（分层 + 端到端）
1. **分层单测**：
   - Summary：固定 chatHistory，真实调用 LLM
   - Extract：固定 `user_memo_str`，真实调用 LLM
   - Merge：固定 facts + profiles，真实调用 LLM
2. **端到端回放**：
   - 用 3-5 个用例跑完整 `process_blobs`
   - 记录中间产物，定位偏差层

## 产物与回归
- 用例数据：保存为独立 json/yaml，便于复用。
- 结果快照：保存中间产物（memo/facts/merge动作）。
- 回归策略：修复后复跑覆盖同类用例。

## 下一步（可选）
- 增加一个“对话样本集”文件夹，统一管理多场景数据。
 - 增加“真实 LLM 测试注意事项”，例如成本/随机性/日志回放。

## 真实 LLM 测试注意事项
- 建议固定 `temperature`，并尽量固定模型版本，减少波动。
- 对每次测试保存 prompt/response 日志，方便复盘与回归比对。
- 对“主观性较强”的输出，优先检查结构与关键信息是否覆盖，而不是完全字面一致。
