# 数据库表设计文档 - Epic 01: 基础聊天界面

> **文档说明**: 本文档由 AI 助手根据 Epic-01 及其 Stories 生成，定义了 DouDouChat 项目初期的核心数据库结构。

## 1. 需求概述
Epic-01 旨在构建基础聊天界面，虽然前期侧重于前端 Mock 数据，但为了后续后端对接及数据结构的一致性，需预先设计以下核心业务的数据存储方案：
1.  **角色/人格 (Personas)**: 存储 AI 的人设信息，支持预设和自定义。
2.  **会话 (Sessions)**: 管理用户的聊天上下文，关联特定的人格。
3.  **消息 (Messages)**: 存储具体的对话内容，需记录所属会话及对应人格。
4.  **LLM 配置 (LLM Configs)**: 存储模型连接参数。

## 2. 表结构设计

### 2.1 角色表 (`personas`)
用于存储 AI 角色（人格）的详细设定。

| 字段名 | 类型 | 长度 | 是否为空 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| id | bigint | 20 | NO | AUTO_INCREMENT | 主键 |
| name | varchar | 64 | NO | | 角色名称 (如 "编程助手") |
| description | varchar | 255 | YES | NULL | 角色简述 |
| system_prompt | text | - | YES | NULL | 系统提示词 (System Prompt) |
| is_preset | tinyint | 1 | NO | 0 | 是否为系统预设 (1:是, 0:否) |
| create_time | datetime | - | NO | CURRENT_TIMESTAMP | 创建时间 |
| update_time | datetime | - | NO | CURRENT_TIMESTAMP | 更新时间 |
| deleted | tinyint | 1 | NO | 0 | 逻辑删除 (1:已删, 0:正常) |

```sql
CREATE TABLE `personas` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `name` varchar(64) NOT NULL COMMENT '角色名称',
  `description` varchar(255) DEFAULT NULL COMMENT '角色描述',
  `system_prompt` text DEFAULT NULL COMMENT '系统提示词',
  `is_preset` tinyint(1) NOT NULL DEFAULT 0 COMMENT '是否为预设角色 0-否 1-是',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint(1) NOT NULL DEFAULT 0 COMMENT '逻辑删除 0-正常 1-删除',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色/人格表';
```

### 2.2 会话表 (`chat_sessions`)
用于管理用户的聊天会话上下文。

| 字段名 | 类型 | 长度 | 是否为空 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| id | bigint | 20 | NO | AUTO_INCREMENT | 主键 |
| persona_id | bigint | 20 | NO | | 关联的默认角色ID |
| title | varchar | 128 | YES | '新对话' | 会话标题 |
| create_time | datetime | - | NO | CURRENT_TIMESTAMP | 创建时间 |
| update_time | datetime | - | NO | CURRENT_TIMESTAMP | 更新时间 |
| deleted | tinyint | 1 | NO | 0 | 逻辑删除 |

```sql
CREATE TABLE `chat_sessions` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `persona_id` bigint(20) NOT NULL COMMENT '关联的角色ID',
  `title` varchar(128) DEFAULT '新对话' COMMENT '会话标题',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint(1) NOT NULL DEFAULT 0 COMMENT '逻辑删除 0-正常 1-删除',
  PRIMARY KEY (`id`),
  KEY `idx_persona_id` (`persona_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会话表';
```

### 2.3 消息表 (`messages`)
存储会话中的具体消息记录。

| 字段名 | 类型 | 长度 | 是否为空 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| id | bigint | 20 | NO | AUTO_INCREMENT | 主键 |
| session_id | bigint | 20 | NO | | 所属会话ID |
| persona_id | bigint | 20 | YES | NULL | 关联的角色ID (快照或特定发言人) |
| role | varchar | 20 | NO | | 角色: user, assistant, system |
| content | text | - | NO | | 消息内容 |
| create_time | datetime | - | NO | CURRENT_TIMESTAMP | 创建时间 |
| update_time | datetime | - | NO | CURRENT_TIMESTAMP | 更新时间 |
| deleted | tinyint | 1 | NO | 0 | 逻辑删除 |

```sql
CREATE TABLE `messages` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `session_id` bigint(20) NOT NULL COMMENT '会话ID',
  `persona_id` bigint(20) DEFAULT NULL COMMENT '角色ID',
  `role` varchar(20) NOT NULL COMMENT '发送角色(user/assistant/system)',
  `content` text NOT NULL COMMENT '消息内容',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint(1) NOT NULL DEFAULT 0 COMMENT '逻辑删除 0-正常 1-删除',
  PRIMARY KEY (`id`),
  KEY `idx_session_id` (`session_id`),
  KEY `idx_persona_id` (`persona_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='消息表';
```

### 2.4 LLM 配置表 (`llm_configs`)
存储 LLM 连接参数。

| 字段名 | 类型 | 长度 | 是否为空 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| id | bigint | 20 | NO | AUTO_INCREMENT | 主键 |
| base_url | varchar | 255 | YES | NULL | API 代理地址 |
| api_key | varchar | 255 | YES | NULL | API 密钥 (需加密存储，此处仅定义结构) |
| model_name | varchar | 128 | YES | 'gpt-3.5-turbo' | 模型名称 |
| create_time | datetime | - | NO | CURRENT_TIMESTAMP | 创建时间 |
| update_time | datetime | - | NO | CURRENT_TIMESTAMP | 更新时间 |
| deleted | tinyint | 1 | NO | 0 | 逻辑删除 |

```sql
CREATE TABLE `llm_configs` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `base_url` varchar(255) DEFAULT NULL COMMENT 'API Base URL',
  `api_key` varchar(255) DEFAULT NULL COMMENT 'API Key',
  `model_name` varchar(128) DEFAULT 'gpt-3.5-turbo' COMMENT '模型名称',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `deleted` tinyint(1) NOT NULL DEFAULT 0 COMMENT '逻辑删除 0-正常 1-删除',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='LLM配置表';
```

## 3. 关系说明
- **Personas - ChatSessions**: 一对多。一个角色可以发起多个会话。
- **Personas - Messages**: 一对多。一条消息（特别是 assistant 消息）关联到一个特定的角色。
- **ChatSessions - Messages**: 一对多。一个会话包含多条消息。

## 4. 备注与建议
- **索引**: 针对查询频繁的 `session_id` 和 `persona_id` 建立了普通索引。
- **扩展性**: `messages` 表增加 `persona_id` 使得在同一会话中切换角色或多角色对话成为可能。
- **存储**: `content` 和 `system_prompt` 使用 `text` 类型，若未来支持超长上下文或图片 Base64，需考虑更大存储类型或对象存储。
