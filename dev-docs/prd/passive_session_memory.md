# 被动会话管理与记忆系统整合设计文档

## 1. 需求背景
在 WeAgentChat 中，我们希望模拟真实的社交体验，弱化“人工干预（如：新建会话按钮）”，强化“时间感”和“自然记忆”。
当用户停止与 AI 聊天一段时间后，本次话题应当自然结束并转化为 AI 的“长期记忆”，下次聊天则是基于记忆重新开启的新篇章。

## 2. 核心逻辑 (Product Logic)

### 2.1 被动会话管理 (Passive Session Management)
- **保留但自动化**：保留"新建会话"按钮，但自动化会话的生命周期管理，减少用户主动操作的必要性。
- **时间敏感策略**：
    - **休眠阶段 (Idle)**：当用户与好友的最后一次互动超过 **30 分钟**（默认配置名：`SESSION_IDLE_THRESHOLD`）。
    - **自动归档 (Auto-Archive)**：下一次用户发送消息时，或后台定时任务发现休眠会话时，自动执行“结束会话”逻辑。
    - **无感开启**：对用户而言，直接在聊天框输入即可，系统在后台自动完成旧会话结算和新会话创建。

### 2.2 记忆系统整合 (Memory Integration Hook)
- **归档钩子**：在会话结束（归档）时，触发 `on_session_end` 钩子。
- **上下文提取**：将本次会话的所有 `Message` 记录提取并格式化。
- **摘要生成**：
    - 调用记忆系统对应的 LLM 接口，为本次对话生成一个简短的摘要（例如：“讨论了关于周报撰写的思路”）。
    - 将摘要作为 Event 存入 Memobase 系统。
- **数据库同步**：更新 `chat_sessions` 表，将 `memory_generated` 置为 `True`，防止重复处理。

## 3. 技术实现 (Technical Implementation)

### 3.1 数据库结构
已在 `chat_sessions` 表中增加以下关键字段：
- `last_message_time` (DateTime): 记录该会话最后一条消息的时间，用于判定是否过期。
- `memory_generated` (Boolean): 标记该会话是否已完成记忆归档。

### 3.2 后端逻辑设计

**配置加载**: 所有超时和自动触发相关的参数均从数据库 `system_settings` 表动态读取，支持用户在前端设置界面实时修改。  
- `SESSION_PASSIVE_TIMEOUT`: 默认 1800 秒（30 分钟）  
- `MEMO_AUTO_TRIGGER`: 默认 `True`

#### A. 消息发送时的前置检查 (`chat_service.py`)
在 `get_or_create_session_for_friend` 函数中增强逻辑：
1. 获取该好友最近的一个活动会话。
2. 判定 `now() - session.last_message_time > THRESHOLD`。
3. 如果满足过期条件：
    - 调用 `archive_session(session_id)` 处理旧归档。
    - 创建一个新的 `ChatSession`。
4. 返回可用的会话 ID。

#### B. 异步归档逻辑 (`memo_service / chat_service`)
实现 `archive_session` 异步函数：
1. **边界检查**：
   - 如果会话消息数 < 2（仅有 system 提示或空会话），跳过归档，直接标记 `memory_generated = True`。
   - 如果 `memory_generated = True`，避免重复归档。
2. **提取消息上下文**：获取该会话所有 `role` 为 `user` 或 `assistant` 的消息。
3. **调用 Memobase SDK**：
   - **核心接口**：`MemoService.insert_chat(user_id, space_id, messages)`
   - **参数映射（方案 A：全局共享记忆）**：
     - `user_id = "default_user"`：当前真实用户（单用户模式硬编码，未来从 Session 获取）。
     - `space_id = "default"`：当前 Space ID（多 Space 未实现时硬编码）。
     - `messages`：OpenAI 兼容格式的消息列表 `[{role, content}, ...]`。
   - **添加好友标签（重要）**：
     - 通过 `BlobData` 的 `fields` 参数传递 metadata：
       ```python
       # In archive_session implementation:
       chat_blob = ChatBlob(messages=messages)
       blob_data = BlobData(
           blob_type=BlobType.chat,
           blob_data=chat_blob.get_blob_data(),
           fields={  # ← Metadata goes here
               "friend_id": str(session.friend_id),
               "friend_name": friend.name,
               "session_id": str(session.id),
               "archived_at": datetime.now().isoformat()
           }
       )
       ```
     - 这些 metadata 会被 Memobase 系统存储在 Event 中，支持通过 `fields.friend_id` 检索特定好友的记忆。
4. **(可选) 立即触发摘要生成**：调用 `MemoService.trigger_buffer_flush` 强制处理该用户的记忆缓冲区。
5. **更新状态**：`memory_generated = True`，`update_time = now()`。
6. **异常处理**：
   - 如果 Memobase 调用失败，记录错误日志但**不阻塞**新会话创建。
   - 保持 `memory_generated = False`，后续由定时任务重试。

#### C. 定时任务 (Background Task)
在 `app/main.py` 的 lifespan 中启动周期性任务：
- **执行频率**：每 10 分钟扫描一次。
- **扫描逻辑**：
  ```sql
  SELECT * FROM chat_sessions 
  WHERE memory_generated = False 
    AND deleted = False
    AND last_message_time < NOW() - INTERVAL '30 minutes'
  ```
- **处理方式**：对每个符合条件的会话调用 `archive_session(session_id)`。
- **目的**：确保用户"聊完就走"的场景下，记忆仍能自动归档。

#### D. 手动新建会话 (`create_session`)
当用户通过 API 手动请求创建新会话时：
1. 检查该好友是否存在未结束的活跃会话。
2. 如果存在，立即调用 `archive_session(old_session_id)` 进行归档和记忆生成，无论时间是否过期。
3. 创建并返回新会话。

## 4. 前端交互变更
- **保留手动控制**：**保留**左侧边栏或聊天头部的"新建会话"按钮。
    - 用户保留随时手动开启新话题的权利。
    - 既然手动开启了新话题，意味着用户主观上认为上一个话题已经结束，因此**必须**触发上一次会话的记忆归档。
- **UI 提示 - 会话边界时间戳**：
    - 在发生会话切换的地方，**显示一个时间戳**（类似微信聊天记录中的时间显示）。
    - 时间戳来源：新会话的 `create_time` 或上一会话的 `last_message_time`。
    - 实现方式：前端遍历消息列表时，检测 `session_id` 变化，在边界处插入时间分隔组件。
- **数据刷新策略 (前端如何感知会话变更)**：
    - **主动场景（用户在操作时触发）**：
        - *场景描述*：用户正在聊天窗口发送消息时刚好触发了 30 分钟超时判定，或者用户手动点击了“新建会话”。
        - *处理逻辑*：后端 API 响应中会返回新的 `session_id`。前端检测到 ID 变化，立即更新本地 stored 的会话 ID 并重新渲染消息列表，从而让用户立刻看到代表新会话开始的时间分隔线。
    - **被动场景（用户不在线，后台自动执行）**：
        - *场景描述*：用户关闭软件或离开电脑 1 小时后，后台定时任务自动将过期会话归档。
        - *处理逻辑*：**无需实时推送**。当用户下一次打开该好友的聊天窗口时，前端会照常调用“获取历史消息”接口，此时自然会拉取到最新的会话状态（包含后台已生成的归档状态），界面上会自动显示出正确的时间分隔线。此处不引入 WebSocket 复杂度。
- **设置界面变更 (`SettingsDialog.vue`)**：
    - 新增 **"记忆设置"** (Memory Settings) 侧边栏选项卡。
    - 增加参数配置表单：
        - `SESSION_PASSIVE_TIMEOUT` (Input/Number): 会话过期时间（秒），默认 1800。
        - `MEMO_AUTO_TRIGGER` (Switch/Boolean): 是否自动生成记忆摘要，默认 True。
    - 需配套增加对应的前端 Store 和后端 API 接口。

## 5. 边界情况与注意事项
1. **空会话过滤**：消息数 < 2 的会话不生成记忆，仅标记为已处理。
2. **并发控制**：归档过程使用 `memory_generated` 字段防止重复处理。
3. **失败重试**：归档失败不阻塞用户体验，由定时任务自动重试。
4. **记忆共享策略（方案 A）**：
   - 所有 AI 好友共享同一个真实用户的记忆库（`user_id = "default_user"`）。
   - 每条记忆事件必须通过 `metadata.friend_id` 标记来源好友。
   - 未来可通过标签实现"仅检索与特定好友相关的记忆"。
5. **多用户/多 Space 准备**：
   - 当前 `user_id` 和 `space_id` 使用硬编码，未来需改为从 Session/Context 获取。
   - 多 Space 场景下，不同 Space 的记忆需完全隔离（如"职场"Space 与"古代宫廷"Space）。

## 6. 配置参数
| 参数名 | 默认值 | 描述 |
| :--- | :--- | :--- |
| `SESSION_PASSIVE_TIMEOUT` | 1800 (秒) | 会话判定过期的非活跃时长 (30分钟) |
| `MEMO_AUTO_TRIGGER` | `True` | 是否在会话归档时立即触发 `flush_buffer` 强制生成摘要。<br>关闭后仍会调用 `insert_chat`，但由后台异步处理（可能延迟数分钟）。 |
