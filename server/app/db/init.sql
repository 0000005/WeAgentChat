-- WeAgentChat Database Initialization Script
-- Sync with Alembic migrations at server/alembic/versions

-- 1. Friend Table (好友/AI 角色)
CREATE TABLE IF NOT EXISTS friends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(64) NOT NULL,
    description VARCHAR(255),
    system_prompt TEXT,
    is_preset BOOLEAN NOT NULL DEFAULT 0,
    avatar VARCHAR(255),
    script_expression BOOLEAN NOT NULL DEFAULT 0,
    pinned_at DATETIME,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_friends_id ON friends(id);

-- 2. Friend Templates Table (好友库模板)
CREATE TABLE IF NOT EXISTS friend_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(64) NOT NULL,
    avatar VARCHAR(255),
    description TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    initial_message TEXT,
    tags TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_friend_templates_id ON friend_templates(id);

-- 3. Chat Sessions Table (会话)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    friend_id INTEGER NOT NULL,
    title VARCHAR(128) DEFAULT '新对话',
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT 0,
    -- 是否已经生成记忆
    memory_generated BOOLEAN NOT NULL DEFAULT 0,
    -- 最后一条消息的时间
    last_message_time DATETIME,
    FOREIGN KEY (friend_id) REFERENCES friends(id)
);

CREATE INDEX IF NOT EXISTS ix_chat_sessions_id ON chat_sessions(id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_friend_id ON chat_sessions(friend_id);

-- 4. Messages Table (消息)
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    friend_id INTEGER,
    role VARCHAR(20) NOT NULL, -- user, assistant, system
    content TEXT NOT NULL,
    create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id),
    FOREIGN KEY (friend_id) REFERENCES friends(id)
);

CREATE INDEX IF NOT EXISTS ix_messages_id ON messages(id);
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);

-- 5. LLM Configs Table (LLM 配置)
CREATE TABLE IF NOT EXISTS llm_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    base_url VARCHAR,
    api_key VARCHAR,
    model_name VARCHAR DEFAULT 'gpt-3.5-turbo',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_llm_configs_id ON llm_configs(id);

-- 6. Embedding Settings Table (Embedding 配置)
CREATE TABLE IF NOT EXISTS embedding_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- 提供商："openai" (默认)、"jina"、"lmstudio"、"ollama"
    embedding_provider VARCHAR DEFAULT 'openai',
    -- 密钥
    embedding_api_key VARCHAR,
    -- 地址
    embedding_base_url VARCHAR,
    -- 向量维度
    embedding_dim INTEGER DEFAULT 1024,
    -- 模型名称
    embedding_model VARCHAR DEFAULT 'BAAI/bge-m3',
    -- 最大token数
    embedding_max_token_size INTEGER DEFAULT 8000,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_embedding_settings_id ON embedding_settings(id);

-- 7. System Settings Table (系统设置)
CREATE TABLE IF NOT EXISTS system_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name VARCHAR(50) NOT NULL,
    key VARCHAR(100) NOT NULL,
    value TEXT NOT NULL,
    value_type VARCHAR(20) NOT NULL, -- int, bool, string, float, json
    description TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_system_settings_group_key UNIQUE (group_name, key)
);

CREATE INDEX IF NOT EXISTS ix_system_settings_id ON system_settings(id);
CREATE INDEX IF NOT EXISTS ix_system_settings_group_name ON system_settings(group_name);
CREATE INDEX IF NOT EXISTS ix_system_settings_key ON system_settings(key);

-- Triggers for updating update_time (SQLite)

CREATE TRIGGER IF NOT EXISTS tr_friends_update_time
AFTER UPDATE ON friends
BEGIN
    UPDATE friends SET update_time = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS tr_friend_templates_update_time
AFTER UPDATE ON friend_templates
BEGIN
    UPDATE friend_templates SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS tr_chat_sessions_update_time
AFTER UPDATE ON chat_sessions
BEGIN
    UPDATE chat_sessions SET update_time = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS tr_messages_update_time
AFTER UPDATE ON messages
BEGIN
    UPDATE messages SET update_time = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS tr_llm_configs_update_time
AFTER UPDATE ON llm_configs
BEGIN
    UPDATE llm_configs SET update_time = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS tr_embedding_settings_update_time
AFTER UPDATE ON embedding_settings
BEGIN
    UPDATE embedding_settings SET update_time = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS tr_system_settings_update_time
AFTER UPDATE ON system_settings
BEGIN
    UPDATE system_settings SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

