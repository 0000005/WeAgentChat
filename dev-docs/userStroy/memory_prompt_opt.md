完整需求（整理版）

  背景
  - 当前传给 Memobase 的 chatHistory 是全量会话（用户 + 好友/assistant 多轮）。
  - Memobase 默认抽取逻辑更像“只基于用户话语”。
  - 导致好友/assistant 内容污染用户 profile。

  目标

  - 继续使用全量会话输入。
  - 通过 prompt 约束，只记录真实用户(ROLE=user)的事实，忽略好友/assistant 自述或设定。

  要改的 prompt（仅中文）
  1. server/app/vendor/memobase_server/prompts/zh_summary_entry_chats.py
  2. server/app/vendor/memobase_server/prompts/zh_extract_profile.py
  3. server/app/vendor/memobase_server/prompts/event_tagging.py

  Few-shot 要求

  - 必须是真实多轮对话，user 与 assistant 交替多轮。
  - few-shot 不出现在 system prompt。
  - few-shot 作为“history_messages”形式出现，结构类似：

    system: 规则说明（不含 few-shot）
    user: <few-shot 输入A>
    assistant: <few-shot 输出A>
    user: <few-shot 输入B>
    assistant: <few-shot 输出B>

  约束

  - system prompt 仅放规则、格式、注意事项，不放示例对话。
  - 输出必须严格以“真实用户事实”为准，来源不明则不写入。

  实现前提（记录用）

  - 目前调用只传 system_prompt + prompt，history_messages 为空。
  - 若要满足“few-shot 不在 system prompt”，需要在调用处把 few-shot 放进 history_messages。