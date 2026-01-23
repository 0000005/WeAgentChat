# Memobase LLM 兼容性测试执行情况（阶段性总结）

日期：2026-01-21
更新日期：2026-01-22

## 已完成
- 新增 Memobase 多供应商 LLM 兼容性测试：`server/tests/test_memobase_llm_providers.py`
  - 使用环境变量注入各供应商 base_url / api_key / model
  - 调用 `app.vendor.memobase_server.llms.llm_complete` 做最小化请求
- 修复 Memobase OpenAI 适配层对 GPT-5 的采样参数兼容：
  - `server/app/vendor/memobase_server/llms/openai_model_llm.py`
  - GPT-5 模型会移除 `temperature/top_p`，避免 400 报错

## 测试执行
- 命令（使用 venv）：
  - `./server/venv/Scripts/python -m pytest server/tests/test_memobase_llm_providers.py -q`
- 结果：全部 7 项失败
- 失败原因：统一为 `ConnectError`，无法建立连接（未返回 HTTP 响应）
  - 典型日志：`Error in llm_complete: Connection error.`
  - 各供应商都未连通：OpenAI / Gemini / ModelScope / Minimax / Zhipu / DeepSeek

## 2026-01-22 复测（使用实际配置）
- 环境变量（仅 base_url + model，API Key 已注入但不记录）：
  - OpenAI：`https://api.openai.com/v1`，`gpt-5.2` / `gpt-4.1-nano`
  - Gemini：`https://generativelanguage.googleapis.com/v1beta`，`models/gemini-3-flash-preview`
  - ModelScope：`https://api-inference.modelscope.cn/v1`，`Qwen/Qwen3-235B-A22B-Instruct-2507`
  - Minimax：`https://api.minimaxi.com/v1`，`MiniMax-M2.1`
  - Zhipu：`https://api.z.ai/api/coding/paas/v4/`，`glm-4.7`
  - DeepSeek：`https://api.deepseek.com/v1`，`deepseek-chat`
- 结果：4 通过 / 3 失败
  - 通过：`openai_gpt_4_1_nano` / `modelscope_qwen3_235b_a22b` / `minimax_m2_1` / `deepseek_chat`
  - 失败：
    - `openai_gpt_5_2`：400，提示 `max_tokens` 不支持，需改用 `max_completion_tokens`
    - `gemini_3_flash_preview`：请求 200，但返回内容为空（`content=None`），断言失败
    - `zhipu_glm_4_7`：请求 200，`result.data()` 为空字符串导致断言失败（返回 `reasoning_content`）
- 额外日志：`project_cost_token_billing` 在测试环境无 DB bind，触发 `UnboundExecutionError`（不影响断言但会污染日志）

## 2026-01-22 复测（修复后）
- 关键修复：
  - GPT-5.2：`max_tokens` -> `max_completion_tokens`
  - Gemini：OpenAI base_url 自动补 `/openai`；消息 `content` 包装为多段文本；`max_tokens` 下限提升到 64
  - Zhipu：超时提高到 600s；空内容时回退 `reasoning_content`
- 结果：7/7 通过（仍有测试环境 billing 异步报错噪音）

## 2026-01-22 记忆生成链路验证（多供应商）
- 方法：基于 `server/tests/data/memory_test/scenario1_mixed.txt`，调用 `MemoService.insert_chat` + `flush_buffer`，再拉取 `get_user_profiles`/`get_recent_memories`。
- 配置：`MEMOBASE_ENABLE_EVENT_EMBEDDING=false`（仅验证抽取，不含向量化）；project_id 使用 `__root__`。
- 结果：各供应商均生成 Profile 与 Event（数量不代表质量，仅证明链路可用）
  - OpenAI (`gpt-4.1-nano`)：profiles=3，events=3
  - Gemini (`models/gemini-3-flash-preview`)：profiles=3，events=3
  - ModelScope (`Qwen/Qwen3-235B-A22B-Instruct-2507`)：profiles=3，events=3
  - Minimax (`MiniMax-M2.1`)：profiles=3，events=3
  - Zhipu (`glm-4.7`)：profiles=3，events=3
  - DeepSeek (`deepseek-chat`)：profiles=3，events=3
- 备注：此验证覆盖“记忆抽取/入库”，不覆盖向量检索与召回效果评估。

## 结论（当前阶段）
- 连通性问题已解除，所有供应商最小化调用通过。
- 记忆抽取链路在 `scenario1_mixed` 下多供应商验证通过（embedding 关闭）。
- 仍有测试环境噪音：
  - `project_cost_token_billing` 在测试环境无 DB bind 的异步报错

## 待办建议（下次恢复时）
1) 评估 Gemini 最小 `max_tokens` 下限（当前强制 >= 64），确认是否需要更细分的阈值或可配置化。
2) Zhipu：确认 `reasoning_content` 回退是否符合产品预期（思考/非思考模式的统一输出策略）。
3) 测试环境可临时禁用 `project_cost_token_billing` 或补齐 DB bind，避免异步报错噪音。

## 变更文件
- `server/tests/test_memobase_llm_providers.py`
- `server/app/vendor/memobase_server/llms/openai_model_llm.py`
- `server/app/vendor/memobase_server/llms/utils.py`
