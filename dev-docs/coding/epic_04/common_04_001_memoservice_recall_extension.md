# 全栈实施方案 - MemoService 记忆召回能力扩展

> **文档说明**: 本文档专注于增强 `MemoService` 的底层检索能力，为上层回忆 Agent 提供带标签过滤的 Event Gist 搜索（Profile 将直接注入 System Prompt，不再参与检索）。

## 1. 需求全景
### 1.1 业务背景
为了实现准确的记忆召回，系统需要能够：
1. 将全量 Profile 直接注入 System Prompt（不做召回检索）。
2. 从海量的历史事件（Event Gists）中，精准找出与**当前好友**相关的往事（隐私隔离）。

### 1.2 核心功能点
- **功能 A: 带标签的 Event 检索**: 实现 `search_memories_with_tags` 方法，结合向量相似度搜索和 SQLite JSON1 标签过滤（`friend_id`）。
- **功能 B: 组合召回接口**: 实现 `recall_memory` 方法，作为外部调用的统一入口（仅返回 Events）。

## 2. 预备工作
### 2.1 参考逻辑
- **SQLite 标签过滤**: 参考 `server/app/services/memo/bridge.py` 中的 `filter_friend_event_gists` 处理 `json_each` 的逻辑。

### 2.2 必要的依赖导入
- `from app.vendor.memobase_server.llms.embeddings import get_embedding`（用于 Event 搜索）
- `from app.vendor.memobase_server.controllers.event_gist import serialize_embedding`（SQLite 向量格式化）
- `from app.vendor.memobase_server.models.database import UserEvent, UserEventGist`（数据库模型）

## 3. 现状分析
- **关键文件**: `server/app/services/memo/bridge.py`
- **现状**: 
    - `search_memories` 仅支持向量搜索，不支持标签过滤。
    - `filter_friend_event_gists` 仅支持按时间倒序列表，不支持相似度搜索。

## 4. 核心方案设计
### 4.1 后端逻辑 (Logic & Data)
- **search_memories_with_tags**:
    - 结合 `search_user_event_gists` 的向量计算逻辑。
    - 在 SQL `WHERE` 子句中加入对 `UserEvent.event_data` 中 `friend_id` 标签的判定。
- **recall_memory**:
    - 调用 `search_memories_with_tags`，整理成 PRD 定义的输出格式（仅 Events）。

## 5. 变更清单
| 序号 | 领域 | 操作类型 | 文件绝对路径 | 变更摘要 |
|:---|:---|:---|:---|:---|
| 1 | 后端 | 修改 | `server/app/services/memo/bridge.py` | 增加 `search_memories_with_tags`, `recall_memory` 接口（仅 Events） |

## 6. 分步实施指南 (Atomic Steps)

### 步骤 1: 实现带标签过滤的向量搜索接口
- **操作文件**: `server/app/services/memo/bridge.py`
- **逻辑描述**: 
    1. 增加类方法 `search_memories_with_tags(cls, user_id, space_id, query, friend_id, topk=5, similarity_threshold=0.5)`。
    2. 复用 `search_user_event_gists` 的逻辑获取 query embedding。
    3. 构建 SQL：
        - `JOIN UserEvent ON UserEventGist.event_id = UserEvent.id`
        - `WHERE friend_id 标签匹配` (使用 `EXISTS` 与 `json_each`)
        - `ORDER BY vec_distance_cosine`
    4. 返回 `UserEventGistsData` 结果。

### 步骤 2: 封装 recall_memory 统一能力
- **操作文件**: `server/app/services/memo/bridge.py`
- **逻辑描述**:
    1. 增加异步类方法 `recall_memory(cls, user_id, space_id, query, friend_id, topk_event=5, threshold=0.5, timeout=3.0)`。
    2. 使用 `asyncio.wait_for(asyncio.gather(...), timeout=timeout)` 包装并行搜索，确保召回不超过指定时间（默认 3 秒）。
    3. 如果超时，记录日志并返回空结果或部分结果（取决于哪个先完成）。
    4. 格式化结果为字典：
        ```python
        {
            "events": [{"date": ..., "content": ...}, ...]
        }
        ```
    5. 捕获所有异常并包装为 `MemoServiceException`，避免召回失败影响主对话流。

## 7. 验收标准
- [x] 调用 `recall_memory` 能返回属于指定好友的历史事件条目。
- [x] 当切换 `friend_id` 时，返回的历史事件记忆随之改变。
- [x] 检索结果具备语义相关性（不是全量返回）。

