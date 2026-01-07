# 全栈实施方案 - Memobase 测试数据注入脚本

> **文档说明**: 本文档提供一个自动化 Python 脚本，用于向记忆系统注入模拟测试数据，包含 Profile 和 Event Gists，方便跨团队验证记忆召回效果。

## 1. 需求全景
### 1.1 业务背景
在开发记忆召回功能时，需要大量真实的"背景"数据来验证向量搜索的准确性和 `friend_id` 标签隔离的有效性。手动输入数据效率低下且不可重复。

### 1.2 核心功能点
- **数据批量注入**: 一键注入 10 条个人画像（Profile）和 62 条历史事件（Event）。
- **隐私隔离模拟**: 事件数据分布在不同的 `friend_id` 下（如 Friend A 有 31 条，Friend B 有 31 条）。
- **环境自适应**: 脚本应能直接运行并作用于当前开发环境的 SQLite 数据库。
- **幂等执行**: 通过 user additional_fields 写入 `seed_memories_v1` 标记，已存在则跳过注入。
- **去重注入**: 读取已存在的 chat blob 内容，避免重复写入同一条事件。

## 2. 预备工作
### 2.1 依赖分析
- **后端 API**: 依赖 `MemoService` (来自 `server/app/services/memo/bridge.py`)。
- **运行环境**: 需要在 `server/` 目录下执行，并加载虚拟环境。
- **脚本目录**: `dev-docs/scripts/`。

## 3. 核心方案设计
### 3.1 注入数据模型
- **Profile (10 条)**:
    - 分类: 职业、兴趣、生活习惯、情感状态等。
    - 内容示例: "喜欢在凌晨 2 点工作"、"对猫毛过敏"、"职业是资深 UI 设计师"。
- **Event Gists (62 条)**:
    - `friend_id=1`: 关注工作、职场建议、加班压力、项目进度。
    - `friend_id=2`: 关注生活烦恼、失眠、睡眠质量、日常琐事。
    - 每条事件都包含 `friend_id` 标签。

## 4. 变更清单
| 序号 | 领域 | 操作类型 | 文件绝对路径 | 变更摘要 |
|:---|:---|:---|:---|:---|
| 1 | 后端 | 新增 | `dev-docs/scripts/seed_memories.py` | 记忆系统数据种子脚本 |

## 5. 分步实施指南 (Atomic Steps)

### 步骤 1: 创建种子脚本
- **操作文件**: `dev-docs/scripts/seed_memories.py`
- **逻辑描述**: 
    1. 引入必要模块：
        ```python
import asyncio
import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from app.services.memo.bridge import MemoService, initialize_memo_sdk
from app.services.memo.constants import DEFAULT_USER_ID, DEFAULT_SPACE_ID
from app.vendor.memobase_server.models.blob import OpenAICompatibleMessage, BlobType
from app.vendor.memobase_server.controllers.user import get_user, update_user
from app.vendor.memobase_server.models.utils import PromiseUnpackError
```
    2. 定义测试数据结构（10 条 Profile + 62 条聊天对话）。
    3. 脚本主逻辑（**重要修正**）：
        - 调用 `MemoService.ensure_user` 确保默认用户存在。
        - 使用 `MemoService.add_user_profiles` 批量插入 Profile（分类需包含 `topic`/`sub_topic` 属性）。
        - **注入 Event 的正确方法**：构建模拟聊天对话（User/Assistant 交替），使用 `MemoService.insert_chat` 插入 Chat Blob，并在 `fields` 参数中包含 `friend_id` 等标签。
        - 调用 `MemoService.trigger_buffer_flush` 立即触发后台提取，生成 Event Gists 和 Embedding。
        - 成功注入后使用 `update_user` 写入 `seed_memories_v1` 标记，实现幂等执行。
        - 事件注入前加载已有 chat blob，避免重复写入。
    4. 打印注入结果摘要和注入的数据统计。

### 步骤 2: 验证数据注入
- **操作方法**: 
    1. 在 `server/` 目录下运行 `venv\\Scripts\\python ..\\dev-docs\\scripts\\seed_memories.py`（Windows）或 `venv/bin/python ../dev-docs/scripts/seed_memories.py`（Linux/Mac）。
    2. 使用 `sqlite3 data/memobase.db` 进入数据库，执行以下验证查询：
        ```sql
        SELECT COUNT(*) FROM user_profiles;  -- 应至少返回 10
        SELECT COUNT(*) FROM user_event_gists WHERE embedding IS NOT NULL;  -- 应至少返回 62
        SELECT json_extract(gist_data, '$.event_tags') FROM user_events LIMIT 5;  -- 检查标签格式
        ```
    3. 如果 embedding 为空，可能是后台 worker 尚未处理，等待 1 分钟后重新查询。

## 6. 验收标准
- [ ] 脚本执行无误，输出 "Successfully injected 72 memory items"。
- [ ] 数据库中 `user_profiles` 至少有 10 条记录。
- [ ] 数据库中 `user_event_gists` 至少有 62 条记录。
- [ ] 不同事件记录的原始数据中 `friend_id` 标签分布符合预期。







