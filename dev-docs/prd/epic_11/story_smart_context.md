# Story: 智能上下文会话管理 (Smart Context Session Management)

## 1. 背景 (Background)
目前系统的会话管理依赖于固定的倒计时 (`passive_timeout`, 默认 30 分钟)。
- **问题**: 当用户在超时后回来继续聊天，系统会强制归档旧会话并开启新会话，导致用户不得不重新建立上下文，体验割裂。
- **痛点**: 很多时候用户只是去吃了顿饭，回来想继续刚才的话题，但被系统“一刀切”地断开了。

## 2. 目标 (Goal)
引入“智能复活 (Smart Resurrection)”机制。
将“倒计时”从一个绝对的截止线，转变为一个“检查点”。当会话超时后，利用 LLM 判断用户的新消息是否仍属于旧话题。如果是，则**复活**旧会话；否则，才创建新会话。

## 3. 用户故事 (User Story)
作为一名用户，由其在使用了被动会话管理后：
- 在短时间内（未超时）的对话，我希望系统像以前一样快速响应，不要有额外的延迟。
- 当我隔了一段时间（超时）回来继续之前的对话时，我希望系统能智能识别我是不是在“接着聊”。
  - 如果我是在接着聊，请不要打断我，让我继续在老会话里说。
  - 如果我开启了新话题，再帮我归档旧的、开启新的。

## 4. 详细需求 (Detailed Requirements)

### 4.1 设置项变更 (Settings Changes)
在“记忆设置”中增加/修改以下配置：

1.  **智能上下文开关 (`smart_context_enabled`)**:
    - 描述优化: "超时智能复活：当会话超时后，尝试智能判断是否为同一话题。若是则复活会话，不进行归档。"
    - **不再与互斥**: 此开关不再禁用 `passive_timeout`，而是依赖它。只有当 `passive_timeout` 触发时，此逻辑才生效。

2.  **智能上下文判断模型 (`smart_context_model`)**:
    - 维持原有设计（可选，为空则回退到主模型）。

### 4.2 后端逻辑变更 (Backend Logic Changes)
核心逻辑在单聊链路中实现（`server/app/services/chat_service.py`），并保持路由层轻量。

**原有逻辑**:
- *被动触发*: 用户发消息时校验 `last_message_time`。
- *主动扫描*: 后台每 30s 扫描 `elapsed > passive_timeout` 的会话并归档。

**新逻辑 (Smart Resurrection + Rollback)**:

#### 4.2.1 被动触发逻辑 (用户发送消息时)
1.  **活跃会话判定**: 获取 `friend_id` 对应的活跃会话。
    - 若无 -> 新建会话。
2.  **超时检查**: 计算 `elapsed_time = now - last_message_time`。
    - **未超时 (< 30m)** -> 直接复用会话 (无需 LLM)。
3.  **超时处理 (>= 30m)**:
    - 若 `smart_context_enabled` 为 **OFF** -> 归档旧会话，新建会话。
    - 若 `smart_context_enabled` 为 **ON** -> **触发智能复活判定**。
        - 获取 Context (最后 6 条)。
        - 调用 LLM (`context_judgment`)。
        - **Result >= 6.0 (相关)** -> **复活会话 (Resurrect)**。
            - **关键步骤**: 检查 `session.memory_generated`。
            - 若 `> 0` (已归档/生成中)，执行 **回滚 (Rollback)**：
                1. `session.memory_generated = 0` (重置状态)。
                2. 调用 `MemoService.delete_session_memories(id)` (物理删除脏记忆)。
                3. log warning: "Resurrecting archived session, memory rollback triggered."
            - 更新 `update_time`，继续使用该会话。
        - **Result < 6.0 (不相关)** -> 归档旧会话，新建会话。

#### 4.2.2 主动扫描逻辑调整 (Background Task)
为了配合智能复活，避免后台任务“过早”归档处于模糊地带的会话：
- **修改扫描阈值**: 后台定时任务仅归档 **超过 24 小时 (Hard Timeout)** 未活动的会话。
- **理由**: 
    - 30m ~ 24h 之间的会话属于“模糊期”，交由用户行为（发消息）触发被动判定。
    - 超过 24h 的会话视为“彻底结束”，由后台清理，保持数据库整洁。

#### 4.2.3 方法职责边界
- `get_or_create_session_for_friend(...)`：保持“会话获取”基础能力。
- 新增编排入口：`resolve_session_for_incoming_friend_message(db, friend_id, current_message)`：
  - 负责智能判定、复活回滚、新建归档。
- `send_message_stream(...)`：仅负责消息落库与流式回复。

#### 4.2.4 并发约束
- 以 `friend_id` 为粒度做互斥控制（锁）。
- 互斥范围覆盖：会话判定 -> (复活回滚/新建) -> 写入消息。

#### 4.2.5 异步归档副作用
- 新建会话引发的旧会话归档，必须 **异步执行**，不阻塞当前消息回复。

### 4.3 LLM 判断逻辑 (LLM Judgment) - 多维评分模式
为了提高判断的透明度和准确性，不直接让 LLM 给出二元结果，而要求其在三个维度打分（0-10 分），系统根据加权总分判定。

#### 4.3.1 定义工具 (Tool Definition)
`context_judgment` 工具：

```python
{
    "type": "function",
    "function": {
        "name": "context_judgment",
        "description": "评估用户新消息与现有对话历史的关联程度，按维度打分。",
        "parameters": {
            "type": "object",
            "properties": {
                "topic_relevance": {
                    "type": "integer",
                    "description": "主题相关度 (0-10)。10=完全同一话题，5=话题自然延伸，0=完全无关的新话题。",
                    "minimum": 0,
                    "maximum": 10
                },
                "intent_continuity": {
                    "type": "integer",
                    "description": "意图连续性 (0-10)。10=直接回应/追问/补充，0=生硬的意图跳跃或无视上文。",
                    "minimum": 0,
                    "maximum": 10
                },
                "entity_reference": {
                    "type": "integer",
                    "description": "指代与实体引用 (0-10)。10=显式指代或复用关键实体，0=无上下文实体引用。",
                    "minimum": 0,
                    "maximum": 10
                }
            },
            "required": ["topic_relevance", "intent_continuity", "entity_reference"]
        }
    }
}
```

#### 4.3.2 Prompt 管理与规范
- 禁止在代码中硬编码该判定 Prompt。
- Prompt 文件放置：`server/app/prompt/chat/smart_context_judgment.txt`
- 加载方式：`get_prompt("chat/smart_context_judgment.txt")`
- Prompt 需明确：必须调用 `context_judgment`。

#### 4.3.3 结果判定逻辑 (Decision Logic)
系统接收到 LLM 的评分后，执行以下计算：

**加权公式**:
`Score = (topic_relevance * 0.4) + (intent_continuity * 0.4) + (entity_reference * 0.2)`

**判定阈值**:
- **Score >= 6.0**: 判定为 **强相关 (复活)** -> 复用会话（触发潜在回滚）。
- **Score < 6.0**: 判定为 **弱相关** -> 归档并新建会话。

边界规则：
- `Score == 6.0` 视为相关（复活）。

#### 4.3.4 工具调用兜底策略
若发生以下任一情况，默认采取 **保守策略（新建会话）**：
- LLM 未按要求调用 `context_judgment`。
- tool 返回缺字段/非法值。
- 调用超时/失败/解析异常。
*(理由：已超时且无法判断，按传统逻辑归档最安全)*

### 4.4 性能考量 (Performance Considerations)
- **零延迟**: 正常对话（< 30m）不触发智能判定。
- **后台减负**: 主动扫描仅处理 >24h 的死会话，大幅减少不必要的数据库与 LLM 开销。
- **数据一致**: 回滚机制保证了“复活”操作的原子性和数据纯净度。

### 4.5 实施路径 (Implementation Roadmap)
本 Story **包含单聊与群聊两个阶段**，按两次实现上线：

1.  **第一阶段：单聊系统 (Private Chat Phase)**
    - 实现设置界面的开关与模型选择。
    - 接入单聊智能复活逻辑（含回滚、Tool、兜底）。
    - 调整后台定时任务扫描阈值为 24h。

2.  **第二阶段：群聊系统 (Group Chat Phase)**
    - 将智能复活逻辑扩展到群聊。
    - 群聊 Context 增加发送者维度。
    - 保持一致的阈值与并发约束。

### 4.4 性能与并发
- **并发控制**: 依然需要以 `friend_id` 为粒度的并发锁，防止在 LLM 判断期间用户发了第二条消息导致状态不一致。
- **兜底策略**: 若 LLM 调用失败/超时，**策略选择**：
  - *建议*: **保守策略 (Fail-Safe to New Session)**。因为已经超时了，且判断服务挂了，按传统逻辑处理（新建）是符合用户预期的最安全做法。
  - *或者*: **激进策略**：默认复活。
  - *本 Story 采纳*: **保守策略**（超时且判断失败 -> 新建会话）。

## 5. 验收标准 (Acceptance Criteria)

### 5.1 设置与基础
1.  **设置界面**:
    - [ ] `smart_context_enabled` 开启时，`passive_timeout` **依然可见且可编辑**（不再互斥）。
    - [ ] 提示文案准确传达“超时后尝试复活”的含义。

2.  **功能测试 - 未超时场景**:
    - [ ] 无论开关是否开启，在超时时间内发送消息，**绝不**触发 LLM 判断，直接进入当前会话。

### 5.2 功能测试 - 超时场景
前置条件：构造一个已超时的活跃会话（修改 DB 时间或设短超时）。

1.  **开关 OFF**:
    - [ ] 超时后发消息 -> 自动归档旧会话，新建会话。

2.  **开关 ON - 场景 A (相关)**:
    - [ ] 发送高度相关消息（如：“刚才那代码再发一遍”）。
    - [ ] 预期：**不创建新会话**，旧会话 `last_message_time` 更新，消息追加到旧会话。

3.  **开关 ON - 场景 B (不相关)**:
    - [ ] 发送完全无关消息（如：“今天天气不错”）。
    - [ ] 预期：旧会话归档，**创建新会话**，消息在新会话中。

4.  **开关 ON - 场景 C (异常兜底)**:
    - [ ] 模拟 LLM 接口超时/报错。
    - [ ] 预期：降级处理，按超时逻辑归档旧会话，新建会话。

## 6. 代码与文件落点
- 涉及文件同上 (`chat_service.py`, `settings.ts`, 等)。
- 重点关注 `resolve_session_for_incoming_message` 中的 `if is_timeout` 分支逻辑。
