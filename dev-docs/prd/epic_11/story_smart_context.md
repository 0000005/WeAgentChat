# Story: 智能上下文会话管理 (Smart Context Session Management)

## 1. 背景
当前系统已从“固定超时即强制切会话”升级为“超时检查点 + 智能复活”。
会话是否延续，不再只看 30 分钟固定规则，而是由 `session.passive_timeout` 配置驱动，并在必要时由 LLM 判定相关性。

## 2. 当前范围与状态
- 第一阶段（单聊）已落地。
- 第二阶段（群聊）暂未纳入本 Story 的实现范围。

## 3. 配置项（已实现）
配置来源：`system_settings`。

- `session.passive_timeout`（秒）
- `session.smart_context_enabled`（bool）
- `session.smart_context_model`（string，空则回退聊天主模型）

前端入口：`front/src/components/SettingsDialog.vue`（记忆设置页中的“会话过期时间 / 超时智能复活 / 判断模型”）。

## 4. 单聊主链路（已实现）
核心入口：`server/app/services/chat_service.py`。
路由入口：`POST /api/chat/friends/{friend_id}/messages`。

### 4.1 并发约束
- 以 `friend_id` 为粒度加锁。
- 锁范围覆盖：会话选择/复活判定 -> 建会话/归档/回滚 -> 首个 SSE 事件准备。

### 4.2 两种发送模式
- 模式 A：`/api/chat/sessions/{session_id}/messages`
  - 直接向指定会话发送，不触发智能会话选择。
- 模式 B：`/api/chat/friends/{friend_id}/messages`
  - 由后端选择（或创建）目标会话，可能触发智能上下文流程。

### 4.3 手动新建会话的“强制新会话”语义（已实现）
前端点击“新建会话”后，下一条好友消息会带一次性参数：`force_new_session=true`。

后端收到该参数后：
- 跳过 `resolve_session_for_incoming_friend_message(...)`。
- 直接走新会话路径并发送消息。
- 不触发智能上下文 judgment。

说明：新会话创建复用 `create_session(...)` 现有策略；若已存在该好友“空活跃会话”，会复用这个空会话 ID（这属于新会话路径内的去重行为，不是复用旧归档上下文）。

### 4.4 自动会话选择流程（`force_new_session=false`）
编排函数：`resolve_session_for_incoming_friend_message(db, friend_id, current_message)`。

0. 读取并校验 `passive_timeout`。
- 非法或 <=0 时回退到 1800 秒，并记录 warning 日志。

1. 获取该好友最新会话（不区分活跃/归档）。
- 若不存在：创建新会话并返回。

2. 若“最新会话是归档态（memory_generated != 0）”。
- 若该会话有 `last_message_time` 且 `elapsed < passive_timeout`：
  - 直接复活（无需 LLM）。
- 否则：
  - `smart_context_enabled=false` -> 新建会话。
  - `smart_context_enabled=true` -> 对该归档会话做 judgment：
    - 相关：复活归档会话。
    - 不相关/失败：新建会话。

3. 若“最新会话是活跃态但空会话（`last_message_time is None` 且消息数为 0）”。
- 会检查最近归档候选会话。
- `smart_context_enabled=true`：
  - 对归档候选做 judgment，相关则切回归档候选。
- `smart_context_enabled=false`：
  - 保留当前空活跃会话，不做判断。

4. 若“最新会话是普通活跃会话（有 `last_message_time`）”。
- `elapsed < passive_timeout`：直接复用，不做 judgment。
- `elapsed >= passive_timeout`：
  - `smart_context_enabled=false` -> 归档旧会话 + 新建会话。
  - `smart_context_enabled=true` -> judgment：
    - 相关：复用旧会话。
    - 不相关/失败：归档旧会话 + 新建会话。

## 5. LLM 判定逻辑（已实现）
判定函数：`_judge_smart_context_relevance(...)`。

### 5.1 Agents + Tool 调用
- 使用 OpenAI Agents：`Agent` + `Runner.run`。
- 强制工具：`context_judgment(topic_relevance, intent_continuity, entity_reference)`。
- Prompt 文件外置：`server/app/prompt/chat/smart_context_judgment.txt`。

### 5.2 评分公式
- `Score = topic_relevance*0.4 + intent_continuity*0.4 + entity_reference*0.2`
- 阈值：`Score >= 6.0` 视为相关。

### 5.3 模型与 provider 兼容
- 模型选择优先级：
  - `session.smart_context_model` 指定配置
  - 否则回退 `chat.active_llm_config_id`
- 已使用 `server/app/services/provider_rules.py` 统一 provider 差异：
  - LiteLLM 路由判定
  - Gemini model/base_url 归一化
  - `reasoning_effort` 支持判定
  - 采样参数及 provider 差异处理

### 5.4 失败兜底（Fail-Safe）
以下场景全部兜底为“不相关 -> 新建会话”：
- 缺少可用 LLM 配置
- 模型不支持 function call
- 工具未调用或 payload 非法
- LLM 调用失败/超时/异常

当前 LLM 调用超时：20 秒。
异常日志会输出 `error_type` 与完整堆栈。

## 6. 复活回滚与记忆删除（已实现）
当复活目标会话 `memory_generated != 0` 时：
- 会将 `memory_generated` 重置为 `0`。
- 清空 `memory_error`。
- 调度删除该 session 对应的 Memobase 记忆。

注意：删除为异步调度（不阻塞当前回复）。
- 调度：`_schedule_session_memory_deletion(session_id)`
- 执行：`MemoService.delete_session_memories(...)`

## 7. 后台归档任务（已实现）
后台扫描只处理 hard-timeout：
- 常量：`HARD_ARCHIVE_TIMEOUT_SECONDS = 24 * 60 * 60`
- 仅归档活跃会话（`memory_generated == 0`）且 `last_message_time < now-24h`

30 分钟到 24 小时之间的会话由“用户发消息时的被动判定”处理。

## 8. 日志可观测性（已实现）
主要看 `server/logs/app.log`：
- `[SmartContext] ...` 服务级决策日志
- `force_new_session` 请求与分支日志
- judgment 调用/得分/兜底日志
- 回滚与异步记忆删除日志

`server/logs/prompt.log` 仅在实际触发 Agent judgment 时才会出现对应提示词追踪。

## 9. 验收标准（与当前代码一致）

### 9.1 基础行为
- `passive_timeout` 可配置且参与所有超时判定。
- 未超时消息不触发 judgment。

### 9.2 智能上下文
- 超时 + 开关关闭：归档并新建。
- 超时 + 开关开启 + 相关：复用/复活。
- 超时 + 开关开启 + 不相关或异常：新建。

### 9.3 归档会话纳入判定
- 归档会话会被纳入候选。
- 满足条件可复活并触发异步记忆清理。

### 9.4 手动新建强制新会话
- 点击“新建会话”后下一条好友消息带 `force_new_session=true`。
- 该次发送跳过 judgment。

## 10. 主要代码落点
- `server/app/api/endpoints/chat.py`
- `server/app/services/chat_service.py`
- `server/app/services/provider_rules.py`
- `server/app/prompt/chat/smart_context_judgment.txt`
- `front/src/api/chat.ts`
- `front/src/stores/session.ts`
- `front/src/stores/session.sessions.ts`
- `front/src/stores/session.stream.friend.ts`
- `front/src/stores/settings.ts`
- `front/src/components/SettingsDialog.vue`
