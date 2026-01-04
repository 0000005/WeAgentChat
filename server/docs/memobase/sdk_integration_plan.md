# Memobase SDK 嵌入改造方案 (SDK Integration Plan)

## 1. 目标与背景
`mem-system` 目前作为一个独立的 FastAPI 服务运行。为了降低系统复杂度、减少 HTTP 通信开销并提升整体可靠性，计划将其改造为 SDK 模式，直接嵌入到 `DouDouChat` 的主后端 (`server/`) 中。

实现后的效果：
- **单进程运行**：主后端进程启动时，自动初始化并运行记忆系统。
- **函数级调用**：通过简单的 Python 异步调用获取上下文和存储记忆。
- **配置统一**：记忆系统的所有参数（如 LLM Key）通过主后端的配置文件管理。

---

## 2. 核心挑战与应对策略

### 2.1 消除模块副作用 (Side Effects)
**现状**：`connectors.py` 在导入时会立即执行数据库连接和建表逻辑。
**策略**：将数据库初始化逻辑封装进显式的 `init_memobase_db(url)` 函数。改为“懒加载”模式，只有当主应用显式启动 SDK 时才建立连接。

### 2.2 背景任务管理 (Background Workers)
**现状**：`mem-system` 依赖 `buffer_background.py` 中的无限循环来处理异步记忆提取。
**策略**：利用 FastAPI 的 `Lifespan` 机制。在 SDK 层提供 `start_buffer_worker()` 方法，由主应用在启动阶段通过 `asyncio.create_task` 挂载。

### 2.3 配置桥接与转换
**现状**：`memobase` 内部使用一套复杂的 `env.py` 和 `config.yaml` 体系。
**策略**：在集成层定义一个 `Adapter`。由主应用的 `settings` 构造出 `memobase` 预期的 `Config` 对象并注入，不再让 SDK 独立读取文件。

### 2.4 返回值处理 (Promise Objects)
**现状**：`memobase` 控制层采用自定义的 `Promise` 对象返回结果（包含 ok, code, msg, data）。
**策略**：在 SDK Bridge 层实现统一的 `unwrap` 逻辑。将错误状态转换为标准的 Python 异常，确保主业务逻辑调用简洁。

---

## 3. 改造路线图 (Roadmap)

### Phase 0: 基础设施与环境准备 (Completed ✅)
- [x] **代码物理归属**：将 `mem-system/memobase_server` 下的代码复制到 `server/app/vendor/memobase_server`。
- [x] **依赖对齐**：将 `numpy`, `sqlite-vec`, `structlog`, `tiktoken`, `typeguard` 等必要依赖合并至主项目 `requirements.txt`。
- [x] **配置项扩展**：在 `server/app/core/config.py` 的 `Settings` 类中添加 `MEMOBASE_*` 相关配置字段。
- [x] 统一依赖管理的方式，将 `mem-system` 的依赖管理方式与主项目对齐。

### Phase 1: 核心模块去副作用化 (Decoupling) ✅
- [x] **重构 `connectors.py`**：
    - 将 `Session`、`DB_ENGINE` 设为 `None`。
    - 移除模块级的 `create_all()`。
    - 实现全局初始化入口。
- [x] **重构 `env.py`**：
    - 允许外部通过 `Config(**params)` 直接实例化。
    - 确保不再强制搜索本地 `config.yaml`。

### Phase 2: 生命周期与后台任务适配 (Runtime) ✅
- [x] **挂载点设计**：在主项目的 `lifespan` 钩子中增加 SDK 初始化调用。
- [x] **Worker 整合**：
    - 导出 `process_buffer_background` 任务 (在 `buffer_background.py` 中实现了 `start_memobase_worker`)。
    - 确保该任务能够响应 `CancelledError` 实现优雅退出。

### Phase 3: SDK 桥接服务层开发 (The Bridge) ✅
- [x] **定义 `MemoService` 类**：
    - 提供静态方法映射常用的记忆功能（Profile 获取、Context 检索、Blob 插入）。
    - 封装 `project_id` 的默认逻辑（从 Space 上下文获取）。
    - 负责所有 `async` 函数的 `Promise` 解包。

### Phase 4: 数据库自动化管理 (Migrations) ✅
- [x] **迁移逻辑集成**：
    - 使用 Alembic 独立管理 `memobase.db`。
    - 在主后端初始化脚本中，增加对 `vendor/memobase_server` env 下的 Alembic 升级命令调用。


---

## 4. 关键代码片段示例 (伪代码)

### SDK 初始化逻辑
```python
# app/services/memo/bridge.py
async def initialize_memo_sdk():
    # 1. 转换配置
    mb_config = map_settings_to_memobase(settings)
    # 2. 初始化数据库
    from app.vendor.memobase_server.connectors import init_db
    init_db(settings.MEMO_DB_URL)
    # 3. 启动后台处理
    background_task = asyncio.create_task(run_buffer_worker())
    return background_task
```

### 业务调用示例
```python
# 调用点：聊天逻辑
profile = await MemoService.get_user_context(user_id=user_id, project_id=space_id)
# 内部 unwrap:
# p = await controllers.context.get_user_context(...)
# if not p.ok(): raise MemoSystemException(p.msg())
# return p.data()
```

---

## 5. 后续确认清单 (Checklist)
- [ ] 验证 `sqlite-vec` 扩展在主项目的 Python 环境中加载路径是否正确。
  - 需在真实环境运行 `insert_chat` 或 `search_memories` 进行验证。
- [x] 确保主项目的 `alembic` 不会误扫 `vendor` 目录下的迁移脚本。
  - ✅ 已验证：主项目 `alembic/env.py` 使用 `app.db.base.Base.metadata`，与 Memobase 的 `REG.metadata` 完全隔离。
- [ ] 确认并测试大并发下，SDK 版的 sqlite 连接池稳定性。
  - 建议使用 `locust` 或 `k6` 进行压力测试。
