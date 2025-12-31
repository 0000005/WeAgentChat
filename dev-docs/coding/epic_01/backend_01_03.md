# 后端开发文档 - Story 01-03: 人格设置界面

## 1. 需求理解与澄清

### 1.1 核心需求
用户希望在前端界面中能够查看和选择不同的 AI 人格（Persona），并且能够查看人格详情以及修改人格的 System Prompt。虽然 Story 描述中暂不包含自定义人格创建，但为了支持"增删改查"（CRUD）的通用性和后续扩展（如自定义人格），后端应提供完整的 CRUD 能力，前端按需调用。

### 1.2 关键功能点
1.  **获取人格列表**：支持获取所有未删除的人格，可能需要区分预设（is_preset）和自定义。
2.  **获取人格详情**：根据 ID 获取单个人格的详细信息。
3.  **更新人格**：主要用于更新 System Prompt，也应支持更新名称、描述等。
4.  **创建人格**：虽然前端暂无入口，但后端应实现此接口以备用（或用于初始化预设数据）。
5.  **删除人格**：逻辑删除。

### 1.3 澄清事项
- **预设人格数据**：Story 提到"预设人格数据可硬编码在前端"，但为了统一管理，建议后端在初始化数据库时注入预设数据，前端直接从接口获取，保持数据源单一。
- **数据持久化**：所有变更需持久化到 SQLite 数据库的 `personas` 表。

## 2. Codebase 现状分析

### 2.1 现有结构
- **Models**: `server/app/models/` 已有 `llm.py`，需新增 `persona.py`。
- **Schemas**: `server/app/schemas/` 已有 `llm.py`，需新增 `persona.py`。
- **Endpoints**: `server/app/api/endpoints/` 已有 `llm.py`，需新增 `persona.py`。
- **Services**: `server/app/services/` 已有 `llm_service.py`，需新增 `persona_service.py`。
- **Database**: `server/data/doudou.db` 已初始化，表结构已在 `dev-docs/prd/epic_01/table_design_epic_01.md` 中定义。

### 2.2 技术栈
- **Web 框架**: FastAPI
- **ORM**: SQLAlchemy
- **验证**: Pydantic v2
- **数据库**: SQLite

## 3. 代码实现思路

### 3.1 架构设计
遵循现有的分层架构：
1.  **API Layer (`app/api/endpoints/persona.py`)**: 处理 HTTP 请求，参数校验，调用 Service 层。
2.  **Service Layer (`app/services/persona_service.py`)**: 包含核心业务逻辑（CRUD 操作）。
3.  **Model Layer (`app/models/persona.py`)**: 定义数据库表结构映射。
4.  **Schema Layer (`app/schemas/persona.py`)**: 定义请求和响应的数据模型（DTO）。

### 3.2 核心技术方案

#### 3.2.1 数据库模型 (`Persona` Model)
根据表设计文档实现 SQLAlchemy 模型。
- 字段：`id`, `name`, `description`, `system_prompt`, `is_preset`, `create_time`, `update_time`, `deleted`.
- 逻辑删除：所有查询默认过滤 `deleted=0`。

#### 3.2.2 Pydantic Schemas
- `PersonaBase`: 基础字段 (`name`, `description`, `system_prompt`, `is_preset`).
- `PersonaCreate`: 创建时使用，继承 `PersonaBase`。
- `PersonaUpdate`: 更新时使用，字段均为 Optional。
- `Persona`: 响应模型，包含 `id`, `create_time`, `update_time`.

#### 3.2.3 Service 逻辑
- `get_personas`: 查询所有未删除的人格。
- `get_persona`: 根据 ID 查询，不存在抛 404。
- `create_persona`: 创建新记录。
- `update_persona`: 更新指定 ID 的记录。
- `delete_persona`: 软删除（设置 `deleted=1`）。

### 3.3 变更规划

| 文件路径 | 变更类型 | 说明 |
| :--- | :--- | :--- |
| `server/app/models/persona.py` | 新增 | 定义 Persona 数据库模型 |
| `server/app/models/__init__.py` | 修改 | 导出 Persona 模型 |
| `server/app/schemas/persona.py` | 新增 | 定义 Pydantic 数据验证模型 |
| `server/app/services/persona_service.py` | 新增 | 实现 CRUD 业务逻辑 |
| `server/app/api/endpoints/persona.py` | 新增 | 定义 API 路由接口 |
| `server/app/api/api.py` | 修改 | 注册 persona router |

## 4. 开发实施指南

### Step 1: 定义数据模型
1.  创建 `server/app/models/persona.py`。
2.  引入 `Base` 和 SQLAlchemy 类型。
3.  实现 `Persona` 类，包含所有定义字段。
4.  在 `server/app/models/__init__.py` 中导入。

### Step 2: 定义 Pydantic Schemas
1.  创建 `server/app/schemas/persona.py`。
2.  定义 `PersonaBase`, `PersonaCreate`, `PersonaUpdate`, `Persona` 类。

### Step 3: 实现 Service 层
1.  创建 `server/app/services/persona_service.py`。
2.  编写 `create_persona`, `get_persona`, `get_personas`, `update_persona`, `delete_persona` 函数。
3.  确保处理数据库 Session。

### Step 4: 实现 API 端点
1.  创建 `server/app/api/endpoints/persona.py`。
2.  定义 Router `router = APIRouter()`。
3.  实现 GET `/`, POST `/`, GET `/{id}`, PUT `/{id}`, DELETE `/{id}` 接口。
4.  注入 `db` 依赖。

### Step 5: 注册路由
1.  修改 `server/app/api/api.py`。
2.  引入 `persona` 模块。
3.  使用 `api_router.include_router(persona.router, prefix="/personas", tags=["personas"])`。

### Step 6: 数据库迁移/初始化
由于项目处于早期阶段，且使用 SQLite，如果表不存在，可以通过 `server/app/db/init_db.py` 逻辑或手动执行 SQL 创建表。建议检查 `init_db.py` 是否会自动创建所有继承自 `Base` 的表。

*(注：根据现有 `server/app/db/init_db.py`，通常会调用 `Base.metadata.create_all`，只要 Model 被正确导入，重启服务即可自动建表)*
