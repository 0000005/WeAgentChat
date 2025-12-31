# DouDouChat (豆豆)

<p align="center">
  <img src="logo.jpg" alt="DouDouChat Logo" width="200">
</p>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Vue3](https://img.shields.io/badge/Frontend-Vue3-42b883.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLite-vec](https://img.shields.io/badge/Database-SQLite--vec-003B57.svg)](https://github.com/asg017/sqlite-vec)

**DouDouChat（豆豆）** 是一款极简、智能的 AI 角色扮演聊天工具。**请注意，本项目名为 DouDouChat，而非“豆包”。** 我们致力于打造**豆包的开源平替**，并专注于通过**长期记忆**和**多模态交互**为用户提供深度陪伴体验。

---

## ✨ 核心特性

### 💬 智控对话
- **多轮会话管理**：支持上下文衔接，丝滑的聊天体验。
- **MCP 协议支持**：集成 Model Context Protocol，赋予 AI 调用外部工具和数据的能力。
- **沉浸式交互**：支持语音播放（TTS）与实时语音电话功能，让交流更具人性。

### 🧠 深度记忆系统
- **动态记忆捕获**：定时自动提取对话重点，形成长期记忆。
- **记忆管理**：提供完整的记忆增删改查功能，让用户掌控 AI 的大脑。
- **自动化画像**：基于对话内容自动总结并更新用户信息，实现真正的“越聊越懂你”。

### 🛠️ 高度自定义配置
- **人格设定**：灵活定义 AI 的性格、背景和说话方式。
- **多供应商接入**：
  - **LLM**：支持主流大模型商（OpenAI, Anthropic, DeepSeek 等）。
  - **语音 (TTS/STT)**：集成国内外优质语音服务。
  - **向量化 (Embeddings)**：自由选择 Embedding 模型用于记忆检索。

---

## 🚀 技术栈

- **前端**：[Vue 3](https://vuejs.org/) + Vite + [ai-elements-vue](https://www.ai-elements-vue.com/) (专为 AI 应用设计的组件库)
- **后端**：[Python 3.10+](https://www.python.org/) + [FastAPI](https://fastapi.tiangolo.com/) (高性能异步框架)
- **数据库**：[SQLite](https://sqlite.org/) + [sqlite-vec](https://github.com/asg017/sqlite-vec) (轻量级本地向量数据库，性能卓越)
- **状态管理**：Pinia
- **通讯**：WebSocket (用于实时语音与极速回复)
- **UI 基础**：shadcn-vue + TailwindCSS

### 🎨 ai-elements-vue 组件库

[ai-elements-vue](https://www.ai-elements-vue.com/) 是基于 [shadcn-vue](https://www.shadcn-vue.com/) 构建的 AI 应用组件库，提供了丰富的预构建组件：

| 组件分类 | 组件示例 | 用途 |
|---------|---------|------|
| 💬 聊天组件 | `conversation`, `message`, `prompt-input` | 构建聊天界面和消息展示 |
| 🧠 推理展示 | `chain-of-thought`, `reasoning` | 展示 AI 思考过程 |
| 🛠️ 工具相关 | `tool`, `confirmation` | 工具调用可视化与审批 |
| 📊 工作流 | `canvas`, `node`, `edge` | 工作流可视化编辑 |
| ⚙️ 实用工具 | `code-block`, `loader`, `suggestion` | 代码展示、加载状态、快速建议 |

**项目地址**: [github.com/vuepont/ai-elements-vue](https://github.com/vuepont/ai-elements-vue)

---

## 🛠️ 快速开始

### 环境要求
- Node.js 18+
- Python 3.10+
- SQLite 3.x

### 后端设置
1. 进入后端目录：
   ```bash
   cd backend
   ```
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 启动服务：
   ```bash
   uvicorn main:app --reload
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
3. 初始化 shadcn-vue（ai-elements-vue 依赖）：
   ```bash
   npx shadcn-vue@latest init
   ```
4. 安装 AI Elements Vue 组件库：
   ```bash
   npx ai-elements-vue@latest
   ```
5. 运行开发服务器：
   ```bash
   pnpm dev
   ```

---

## 📸 界面预览

> *正在准备中，即将上线...*
> (您可以根据需要在此处添加项目截图)

---

## 🗺️ 路线图 (Roadmap)
- [ ] 支持更多 MCP 插件（搜索、日历、天气等）
- [ ] 增加多端同步功能（Web/PWA/Mobile）
- [ ] 增强个性化记忆过滤算法
- [ ] 引入 RAG 知识库功能

---

## 📄 开源协议
本项目采用 [MIT License](LICENSE) 许可协议。
