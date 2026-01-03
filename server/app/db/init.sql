-- DouDouChat Database Initialization Script

-- 1. Friend Table (好友/AI 角色)
CREATE TABLE IF NOT EXISTS friends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    system_prompt TEXT,
    is_preset INTEGER NOT NULL DEFAULT 0,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER NOT NULL DEFAULT 0
);

-- Trigger for updating update_time in friends
CREATE TRIGGER IF NOT EXISTS tr_friends_update_time
AFTER UPDATE ON friends
BEGIN
    UPDATE friends SET update_time = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- 2. Chat Sessions Table (会话)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    friend_id INTEGER NOT NULL,
    title TEXT DEFAULT '新对话',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (friend_id) REFERENCES friends(id)
);

CREATE TRIGGER IF NOT EXISTS tr_chat_sessions_update_time
AFTER UPDATE ON chat_sessions
BEGIN
    UPDATE chat_sessions SET update_time = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_friend_id ON chat_sessions(friend_id);

-- 3. Messages Table (消息)
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    friend_id INTEGER,
    role TEXT NOT NULL, -- user, assistant, system
    content TEXT NOT NULL,
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id),
    FOREIGN KEY (friend_id) REFERENCES friends(id)
);

CREATE TRIGGER IF NOT EXISTS tr_messages_update_time
AFTER UPDATE ON messages
BEGIN
    UPDATE messages SET update_time = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);

-- 4. LLM Configs Table (LLM 配置)
CREATE TABLE IF NOT EXISTS llm_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    base_url TEXT,
    api_key TEXT,
    model_name TEXT DEFAULT 'gpt-3.5-turbo',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted INTEGER NOT NULL DEFAULT 0
);

CREATE TRIGGER IF NOT EXISTS tr_llm_configs_update_time
AFTER UPDATE ON llm_configs
BEGIN
    UPDATE llm_configs SET update_time = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

-- Seed Data: Default Friends
INSERT INTO friends (name, description, system_prompt, is_preset) VALUES 
('全能助手', '温和、专业且乐于助人的 AI 助手。', '你是一个全能的 AI 助手，名叫豆豆（DouDou）。请以专业、友好且简洁的方式回答用户的问题。', 1),
('编程专家', '精通多种编程语言和架构设计的技术大牛。', '你是一个经验丰富的软件架构师和编程专家。你会提供高质量、符合最佳实践的代码示例，并能深入浅出地解释复杂的技术概念。', 1),
('创意作家', '富有想象力，擅长文学创作和灵感启发。', '你是一个才华横溢的创意作家。你擅长讲故事、写诗、润色文案，并能从独特的角度提供创意启发。', 1);
