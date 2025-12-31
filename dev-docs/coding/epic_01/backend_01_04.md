# 后端开发文档 - Story 01-04: LLM 配置界面

## 1. 需求理解与澄清

### 核心需求
用户希望实现 LLM（大语言模型）的配置功能，虽然 Story 01-04 的原始描述中侧重于前端持久化（Pinia + LocalStorage），但作为后端开发任务，我们需要在服务端提供相应的支持，以便后续 Epic-02 进行后端 API 对接时能够直接使用。

我们需要提供 API 接口来管理 LLM 的配置信息，包括：
- API 代理地址 (Base URL)
- API 密钥 (API Key)
- 模型名称 (Model Name)

### 约束条件
- 目前仅支持配置一个 LLM 实例（虽然数据库表设计允许扩展）。
- 数据库表 `llm_configs` 已经通过 `init.sql` 定义。
- 需要遵循现有的分层架构（API -> Service -> Models/Schemas）。

### 疑问与假设
- **假设**：尽管前端暂时使用 LocalStorage，后端应实现完整的 CRUD 接口以备未来使用。
- **假设**：由于当前限制为"单实例"，我们可以在 Service 层逻辑中默认操作第一条记录，或者提供标准的 CRUD 供前端选择。为了灵活性，我们将提供标准的 CRUD 接口，并提供一个获取"默认/当前"配置的便捷逻辑（例如获取 ID 最小的有效记录）。

## 2. Codebase 现状分析

### 现有架构
- **框架**：FastAPI + Uvicorn。
- **数据库**：SQLite，目前通过 `server/app/db/init_db.py` 执行 `init.sql` 进行初始化。
- **ORM**：依赖中包含 `sqlalchemy`，但尚未建立 `Session` 和 `Base` 类，`server/app/models/` 目录目前为空（除了 `__init__.py`）。
- **目录结构**：
    - `app/api/endpoints/`：存放 API 路由。
    - `app/models/`：存放 SQLAlchemy 模型。
    - `app/schemas/`：存放 Pydantic 数据验证模型。
    - `app/services/`：存放业务逻辑（目前为空）。

### 需要补充的基础设施
- 需要配置 SQLAlchemy 的 `SessionLocal` 和 `Base` 类，以便使用 ORM 操作数据库。
- 现有的 `init.sql` 已经定义了 `llm_configs` 表，ORM 模型需要与其结构保持一致。

## 3. 代码实现思路

### 3.1 架构设计

采用经典的三层架构：
1.  **API Layer (`app/api/endpoints/llm.py`)**: 处理 HTTP 请求，参数校验，调用 Service 层。
2.  **Service Layer (`app/services/llm_service.py`)**: 处理业务逻辑（如获取默认配置、更新配置），调用 DB 层。
3.  **Data Layer (`app/models/llm.py`)**: 定义 SQLAlchemy 模型，映射数据库表。

### 3.2 核心技术方案

#### SQLAlchemy 配置
- 创建 `app/db/session.py`：配置 `create_engine` 和 `sessionmaker`。
- 创建 `app/db/base.py`：定义 `Base = declarative_base()`。

#### 模型设计 (`LLMConfig`)
- 映射 `llm_configs` 表。
- 字段：`id`, `base_url`, `api_key`, `model_name`, `create_time`, `update_time`, `deleted`.

#### 业务逻辑
- **获取配置**：由于当前限制单实例，提供 `get_default_config` 方法，查询未删除的第一条记录。如果不存在，可以返回空或默认值。
- **保存/更新配置**：
    - 如果不存在记录，则创建新记录。
    - 如果存在记录，则更新现有记录（单实例模式下）。

### 3.3 变更规划

#### 新增文件
1.  `server/app/db/session.py`: 数据库会话配置。
2.  `server/app/db/base.py`: ORM 基类配置。
3.  `server/app/models/llm.py`: LLM 配置的 ORM 模型。
4.  `server/app/schemas/llm.py`: Pydantic 模型 (Create, Update, Response)。
5.  `server/app/services/llm_service.py`: LLM 配置的业务逻辑服务。
6.  `server/app/api/endpoints/llm.py`: LLM 配置相关的 API 接口。

#### 修改文件
1.  `server/app/api/api.py`: 注册 `llm` 路由模块。
2.  `server/app/models/__init__.py`: 导出 `LLMConfig` 模型。

### 3.4 开发实施指南

1.  **基础设施搭建**
    - 在 `app/db/session.py` 中初始化 `engine` 和 `SessionLocal`。
    - 在 `app/db/base.py` 中定义 `Base` 类。

2.  **定义数据模型 (Model)**
    - 在 `app/models/llm.py` 中创建 `LLMConfig` 类，继承自 `Base`。
    - 确保字段类型与 `init.sql` 中的定义一致。

3.  **定义数据架构 (Schema)**
    - 在 `app/schemas/llm.py` 中定义：
        - `LLMConfigBase`: 包含 `base_url`, `api_key`, `model_name`。
        - `LLMConfigCreate`: 继承 Base。
        - `LLMConfigUpdate`: 继承 Base，字段可选。
        - `LLMConfig`: 继承 Base，增加 `id`, `create_time` 等字段，配置 `from_attributes = True`。

4.  **实现业务服务 (Service)**
    - 在 `app/services/llm_service.py` 中实现 `LLMService` 类。
    - 方法：
        - `get_config(db: Session) -> Optional[LLMConfig]`: 获取当前的 LLM 配置（单例模式）。
        - `update_config(db: Session, config: LLMConfigUpdate) -> LLMConfig`: 更新或创建配置。

5.  **实现 API 接口**
    - 在 `app/api/endpoints/llm.py` 中定义路由：
        - `GET /llm/config`: 获取当前配置。
        - `PUT /llm/config`: 更新当前配置。

6.  **注册路由**
    - 在 `app/api/api.py` 中将 `llm.router` 包含进来，前缀设为 `/llm`。

## 4. 询问用户
- 文档内容是否满足您的需求？
- 是否需要我现在开始执行这些变更？
