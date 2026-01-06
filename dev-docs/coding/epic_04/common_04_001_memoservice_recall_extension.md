# 全栈实施方案 - MemoService 记忆召回能力扩展

> **文档说明**: 本文档专注于增强 `MemoService` 的底层检索能力，为上层回忆 Agent 提供语义化的 Profile 搜索和带标签过滤的 Event Gist 搜索。

## 1. 需求全景
### 1.1 业务背景
为了实现准确的记忆召回，系统需要能够：
1. 从全局 Profile 中检索与当前话题相关的个人偏好。
2. 从海量的历史事件（Event Gists）中，精准找出与**当前好友**相关的往事（隐私隔离）。

### 1.2 核心功能点
- **功能 A: Profile 语义检索**: 实现 `search_profiles` 方法，利用 LLM 从全量 Profile 中挑选出最相关的条目。
- **功能 B: 带标签的 Event 检索**: 实现 `search_memories_with_tags` 方法，结合向量相似度搜索和 SQLite JSON1 标签过滤（`friend_id`）。
- **功能 C: 组合召回接口**: 实现 `recall_memory` 方法，作为外部调用的统一入口。

## 2. 预备工作
### 2.1 参考逻辑
- **Profile 过滤**: 参考 `server/app/vendor/memobase_server/controllers/post_process/profile.py` 中的 `filter_profiles_with_chats`。
- **SQLite 标签过滤**: 参考 `server/app/services/memo/bridge.py` 中的 `filter_friend_event_gists` 处理 `json_each` 的逻辑。

### 2.2 必要的依赖导入
- `from app.vendor.memobase_server.controllers.post_process.profile import filter_profiles_with_chats`
- `from app.vendor.memobase_server.llms.embeddings import get_embedding`（用于 Event 搜索）
- `from app.vendor.memobase_server.controllers.event_gist import serialize_embedding`（SQLite 向量格式化）
- `from app.vendor.memobase_server.models.database import UserEvent, UserEventGist`（数据库模型）

## 3. 现状分析
- **关键文件**: `server/app/services/memo/bridge.py`
- **现状**: 
    - `search_memories` 仅支持向量搜索，不支持标签过滤。
    - `get_user_profiles` 仅支持返回全量，不支持根据语义筛选。
    - `filter_friend_event_gists` 仅支持按时间倒序列表，不支持相似度搜索。

## 4. 核心方案设计
### 4.1 后端逻辑 (Logic & Data)
- **search_profiles_semantic**: 
    - 接收 `query` 字符串。
    - 将 `query` 封装为 `OpenAICompatibleMessage`。
    - 调用 `filter_profiles_with_chats` 获取最相关的 Profile 条目坐标。
- **search_memories_with_tags**:
    - 结合 `search_user_event_gists` 的向量计算逻辑。
    - 在 SQL `WHERE` 子句中加入对 `UserEvent.event_data` 中 `friend_id` 标签的判定。
- **recall_memory**:
    - 并行调用上述两个检索能力，整理成 PRD 定义的输出格式。

## 5. 变更清单
| 序号 | 领域 | 操作类型 | 文件绝对路径 | 变更摘要 |
|:---|:---|:---|:---|:---|
| 1 | 后端 | 修改 | `server/app/services/memo/bridge.py` | 增加 `search_profiles_semantic`, `search_memories_with_tags`, `recall_memory` 接口 |

## 6. 分步实施指南 (Atomic Steps)

### 步骤 1: 实现 Profile 语义检索接口
- **操作文件**: `server/app/services/memo/bridge.py`
- **逻辑描述**: 
    1. 增加类方法 `search_profiles_semantic(cls, user_id, space_id, query, topk=5)`。
    2. 将 `query` 包装成 `OpenAICompatibleMessage` 列表：`[{"role": "user", "content": query}]`（模拟用户提问的上下文）。
    3. 调用 `get_user_profiles` 获取全量 profiles。
    4. 调用 `filter_profiles_with_chats(user_id, space_id, profiles, messages, max_filter_num=topk)` 筛选最相关的条目。
    5. 返回筛选后的 profile 列表（`UserProfilesData` 格式）。

### 步骤 2: 实现带标签过滤的向量搜索接口
- **操作文件**: `server/app/services/memo/bridge.py`
- **逻辑描述**: 
    1. 增加类方法 `search_memories_with_tags(cls, user_id, space_id, query, friend_id, topk=5, similarity_threshold=0.5)`。
    2. 复用 `search_user_event_gists` 的逻辑获取 query embedding。
    3. 构建 SQL：
        - `JOIN UserEvent ON UserEventGist.event_id = UserEvent.id`
        - `WHERE friend_id 标签匹配` (使用 `EXISTS` 与 `json_each`)
        - `ORDER BY vec_distance_cosine`
    4. 返回 `UserEventGistsData` 结果。

### 步骤 3: 封装 recall_memory 统一能力
- **操作文件**: `server/app/services/memo/bridge.py`
- **逻辑描述**:
    1. 增加异步类方法 `recall_memory(cls, user_id, space_id, query, friend_id, topk_profile=5, topk_event=5, threshold=0.5, timeout=3.0)`。
    2. 使用 `asyncio.wait_for(asyncio.gather(...), timeout=timeout)` 包装并行搜索，确保召回不超过指定时间（默认 3 秒）。
    3. 如果超时，记录日志并返回空结果或部分结果（取决于哪个先完成）。
    4. 格式化结果为字典：
        ```python
        {
            "profiles": [{"topic": ..., "content": ..., "updated_at": ...}, ...],
            "events": [{"date": ..., "content": ...}, ...]
        }
        ```
    5. 捕获所有异常并包装为 `MemoServiceException`，避免召回失败影响主对话流。

## 7. 验收标准
- [x] 调用 `recall_memory` 能同时返回相关的 Profile 条目和属于指定好友的历史事件条目。
- [x] 当切换 `friend_id` 时，返回的历史事件记忆随之改变。
- [x] 检索结果具备语义相关性（不是全量返回）。

