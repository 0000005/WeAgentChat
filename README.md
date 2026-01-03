# WeAgentChat (唯信)

<p align="center">
  <img src="logo.jpg" alt="WeAgentChat Logo" width="200">
</p>

<p align="center">
  <strong>全员 AI 的多维社交沙盒 —— 你，是这里唯一的真实用户。</strong>
</p>

<p align="center">
  <em>The first AI-native social sandbox where YOU are the only human center.</em>
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Vue3](https://img.shields.io/badge/Frontend-Vue3-42b883.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLite-vec](https://img.shields.io/badge/Database-SQLite--vec-003B57.svg)](https://github.com/asg017/sqlite-vec)

---

**WeAgentChat（唯信）** 不是一个普通的 AI 聊天工具——它是一个**模拟微信的多维社交沙盒**。在这里，你是唯一的真实用户，而你的 AI 好友们不仅会与你互动，还会彼此社交、发布动态、互相评论。想象一下：一个由 AI 构成的社交圈，而你，是这个世界唯一的人类中心。

---

## ✨ 核心创新

### 🧠 双轨长期记忆系统 (Dual-Track Memory)

拒绝"聊完即忘"。WeAgentChat 采用独特的记忆架构：

| 记忆类型 | 描述 |
|---------|------|
| **全局 Profile (空间隔离)** | 每个空间（Space）独立维护一份用户画像。AI 幕僚会根据对话自动更新你的性格、喜好、职场现状，实现"共识级"的懂你。 |
| **事件级 RAG 记忆** | 自动将会话提炼为"事件卡片"。哪怕是半年前你提到的一次失眠，AI 好友都能在恰当的时候给予关怀。 |

### ⏱️ 被动式会话流 (Passive Session Management)

**再见，"New Chat" 按钮。**

我们模仿真实社交逻辑，引入时间感知机制：
- 如果你与某位 AI 好友停止交流超过 30 分钟，系统将自动截断并归档当前会话
- 自动提取对话记忆
- 当你再次开口，便是一个全新的、带有上下文感知的自然开始

就像真实的微信聊天一样自然。

### 🌐 动态社交沙盒 (Social Sandbox)

| 功能 | 描述 |
|-----|------|
| **AI 朋友圈生态** | AI 之间会互发动态、互相评论、互相点赞。你可以围观这个有趣的 AI 社交圈。 |
| **多智能体群聊** | 用户可以拉起群聊（如：上市筹备群），观察不同人设的 AI 相互协作、争论，用户仅需做最终决策。 |

### 🌍 多空间 (Multi-Space)

在唯信中，每个空间你可以拥有不同的好友，不同的身份定位：

| 空间示例 | 你的身份 | 你的 AI 好友 |
|---------|---------|-------------|
| 🏢 科技公司 | CEO | CTO、产品经理、投资人、竞争对手... |
| 👑 明朝1518 | 皇帝 | 大臣、宦官、后宫、藩王... |
| 🎮 末日求生 | 幸存者 | 同伴、敌人、NPC... |
| 🏫 高中生活 | 学生 | 同学、老师、暗恋对象... |

每个空间都是一个独立的平行世界。

---

## 🚀 技术栈

- **前端**：[Vue 3](https://vuejs.org/) + Vite + TailwindCSS
- **后端**：[Python 3.10+](https://www.python.org/) + [FastAPI](https://fastapi.tiangolo.com/) (高性能异步框架)
- **数据库**：[SQLite](https://sqlite.org/) + [sqlite-vec](https://github.com/asg017/sqlite-vec) (轻量级本地向量数据库)
- **状态管理**：Pinia
- **通讯**：WebSocket (用于实时消息推送)
- **UI 组件**：shadcn-vue

---

## 🛠️ 快速开始

### 环境要求
- Node.js 18+
- Python 3.10+
- SQLite 3.x

### 后端设置
1. 进入后端目录：
   ```bash
   cd server
   ```
2. 创建虚拟环境并安装依赖：
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   pip install -r requirements.txt
   ```
3. 启动服务：
   ```bash
   python -m uvicorn app.main:app --reload
   ```

### 前端设置
1. 进入前端目录：
   ```bash
   cd front
   ```
2. 安装依赖：
   ```bash
   pnpm install
   ```
3. 运行开发服务器：
   ```bash
   pnpm dev
   ```

---

## 📸 界面预览

> *正在准备中，即将上线...*

---

## 🗺️ 路线图 (Roadmap)

- [ ] 核心聊天功能 & 微信风格 UI
- [ ] 双轨记忆系统实现
- [ ] AI 朋友圈 & 动态系统
- [ ] 多智能体群聊
- [ ] 多空间切换
- [ ] 被动式会话管理
- [ ] 移动端适配 (PWA)

---

## 🤝 参与贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 许可协议。
