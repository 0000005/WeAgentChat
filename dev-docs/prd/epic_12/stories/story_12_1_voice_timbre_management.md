# Story 12-1: 语音音色库与数据库设计

> Epic: Epic 12: 语音消息能力
> Priority: High
> Points: 3

## 概述
本 Story 负责建立语音合成的基础数据层。我们需要解析提供的音色文档（HTML/Markdown），在数据库中构建一个音色表（Voice Timbre），存储所有支持的音色信息（如名称、ID、性别、分类、试听地址等），并提供后端 API 供前端查询。

## 用户故事

### US-1: 音色数据初始化
**作为** 系统开发者，
**我希望** 系统启动或初始化时能自动将 `qwen-tts-dev.md` 和 `tts-sample.html` 中的音色数据导入数据库，
**以便** 系统拥有完整的可用音色列表。

### US-2: 获取音色列表
**作为** 前端应用，
**我希望** 能通过 API 获取所有可用音色及其详情（包括试听 URL），
**以便** 在设置界面展示给用户进行选择。

## 功能范围

### 包含
-   数据库表设计 `voice_timbre`。
-   数据解析脚本/逻辑：解析 `qwen-tts-dev.md` 和 `tts-sample.html` 提取音色信息。
-   后端 API：`GET /api/voice/timbres` 返回音色列表。
-   支持字段：音色ID（`voice`参数）、名称（中文名）、描述、性别（从描述推断）、预览音频 URL、支持的模型列表。

### 不包含
-   音色文件的实时上传/下载（仅使用阿里云提供的公网 URL）。
-   用户自定义音色（复刻）的管理（后续迭代）。
-   前端代码的编写（后续迭代）。

## 验收标准

- [ ] AC-1: 数据库中存在 `voice_timbres` 表，字段包含 `voice_id`, `name`, `description`, `gender`, `preview_url`, `supported_models`, `category`。
- [ ] AC-2: 系统初始化后，表中应包含 `tts-sample.html` 中列出的所有音色（如 Cherry, Serena, Ethan 等）。
- [ ] AC-3: 提供 API `GET /api/voice/timbres`，返回 JSON 格式的音色列表。
- [ ] AC-4: 音色信息的 `preview_url` 必须是有效的阿里云公网地址，前端可直接播放。
- [ ] AC-5: 数据解析逻辑能正确处理 HTML 表格结构，提取出中文名称和对应 ID。

## 依赖关系

### 前置依赖
- 无

### 被依赖（后续）
- Story 12-2: 全局语音设置界面 (需要音色列表供选择)
- Story 12-3: 好友语音个性化配置 (需要音色列表供选择)

## 备注
-   `tts-sample.html` 文件包含音色 ID (如 `Cherry`) 和音频 URL。
-   `qwen-tts-dev.md` 包含模型说明，本 Story 主要关注音色列表，模型字段可先存储为 JSON 字符串或关联表，目前主要关注 `qwen3-tts-instruct-flash` 支持的音色。
