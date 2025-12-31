# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**DouDouChat（豆豆）** 是一款开源的 AI 角色扮演聊天应用，致力于成为"豆包"的开源平替版本。项目当前处于**初始化阶段**，前后端目录已创建但尚未实现代码。

**开发语言：** 中文（文档和沟通）
**编码规范：** UTF-8 编码

## 技术栈

- **前端：** Vue 3 + Vite + [ai-elements-vue](https://github.com/vuepont/ai-elements-vue) + Pinia
- **后端：** Python 3.10+ + FastAPI
- **数据库：** SQLite + sqlite-vec（向量数据库）
- **通讯：** WebSocket + MCP（Model Context Protocol）

### 关于 ai-elements-vue

[ai-elements-vue](https://www.ai-elements-vue.com/) 是基于 [shadcn-vue](https://www.shadcn-vue.com/) 构建的 AI 应用组件库，专为构建 AI 原生应用而设计。它提供了以下核心组件：

- **聊天组件**：`conversation`（对话容器）、`message`（消息气泡）、`prompt-input`（高级输入框）
- **推理展示**：`chain-of-thought`（思维链）、`reasoning`（AI 推理过程）
- **工具相关**：`tool`（工具调用可视化）、`confirmation`（工具执行审批）
- **工作流**：`canvas`、`node`、`edge`（工作流可视化）
- **实用组件**：`code-block`（代码高亮）、`loader`（加载状态）、`suggestion`（快速建议）

**GitHub**: [vuepont/ai-elements-vue](https://github.com/vuepont/ai-elements-vue)

**使用文档**: 当需要使用 `ai-elements-vue` 组件时，必须先调用 `context7` 查询组件的使用方法，然后按照返回的使用方法进行实现。

## 目录结构

```
DouDouChat/
├── front/           # 前端目录（Vue 3，待开发）
├── server/          # 后端目录（FastAPI，待开发）
├── dev-docs/        # 开发文档和需求
│   └── story01/     # 开发故事
└── .claude/         # Claude Code 配置
```

**⚠️ 目录命名注意：** 实际使用 `front/` 和 `server/`，而非 README.md 中提到的 `frontend/` 和 `backend/`。

## 第一阶段开发目标（Story 01）

当前阶段专注于**前端开发**：
1. **平台：** PC Web（响应式设计）
2. **范围：** 仅前端，使用模拟数据，不连接后端
3. **功能：**
   - 聊天界面
   - 会话管理
   - 人格设置
   - LLM 配置界面

## 常用命令

### 前端（front/）
```bash
# 进入前端目录
cd front

# 安装依赖（推荐使用 pnpm）
pnpm install

# 初始化 shadcn-vue（ai-elements-vue 依赖）
npx shadcn-vue@latest init

# 安装 ai-elements-vue 组件
npx ai-elements-vue@latest

# 运行开发服务器
pnpm dev

# 构建生产版本
pnpm build
```

### 后端（server/）
```bash
# 进入后端目录
cd server

# 安装依赖
pip install -r requirements.txt

# 启动开发服务器
uvicorn main:app --reload
```

## 包管理器

**推荐使用 `pnpm`** 而非 `npm` 或 `yarn`。

## 架构说明

### 前端架构
- **响应式 PC Web 应用**
- **状态管理：** Pinia
- **UI 组件：** [ai-elements-vue](https://www.ai-elements-vue.com/)（基于 shadcn-vue 的 AI 应用组件库）
  - 使用 `conversation` 组件构建聊天界面
  - 使用 `message` 组件展示对话消息
  - 使用 `prompt-input` 组件实现智能输入框
  - 使用 `reasoning` 组件展示 AI 思考过程
- **样式：** TailwindCSS（ai-elements-vue 依赖）
- **核心模块：**
  - 聊天界面（消息列表、输入框）
  - 会话管理（创建、切换、删除对话）
  - 人格设置（AI 角色配置）
  - LLM 配置（多供应商接入）

### 后端架构（计划）
- **API：** RESTful + WebSocket
- **核心功能：**
  - 对话管理
  - 记忆系统（长期记忆、向量检索）
  - MCP 协议集成
  - 多模态交互（TTS/STT）

## 核心特性

- **多轮会话：** 支持上下文衔接
- **MCP 协议：** AI 可调用外部工具和数据
- **长期记忆：** 动态记忆捕获、自动化画像
- **多供应商接入：** LLM、TTS/STT、Embeddings

## 参考文档

- [README.md](README.md) - 项目主文档
- [GEMINI.md](GEMINI.md) - AI 项目上下文
- [dev-docs/story01/init-story.md](dev-docs/story01/init-story.md) - 第一阶段需求
