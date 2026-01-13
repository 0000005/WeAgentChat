# User Story: 初始好友库初始化与批量生成 (Persona Library Initialization & Batch Generation)

## 1. 背景与目标 (Background & Goals)
WeAgentChat 的核心特色之一是其丰富的 AI 好友库（Persona Library）。用户在首次使用应用时，不应面对一个空荡荡的列表，而应能从多样化的角色模板中选择并添加好友。

本计划旨在根据预设的好友清单（126 位角色），通过自动化脚本在**开发阶段**批量生成高质量的 Persona 设定（文字 & 头像），并将这些资产（Assets）集成到应用源码中，确保用户在安装应用后无需联网即可拥有完整的好友库视觉与文字体验。

---

## 2. 用户故事 (User Stories)

### US-1: 全量角色库文本生成
**作为** 系统开发者，
**我希望** 能够根据 `dev-docs/temp/preset_friends_list.md` 中定义的 126 位角色，批量生成完整的 Persona 设定（Prompt & Initial Message），
**以便于** 提供极具深度和广度的初始内容。

### US-2: 视觉体系自动化与本地化
**作为** 系统开发者，
**我希望** 自动为每个角色生成一张极具质感的头像，并将其作为**静态资产 (Static Assets)** 存储在应用源码目录中，
**以便于** 这些头像能随安装包分发到用户电脑，确保离线环境下的视觉一致性，无需用户安装后再行下载。

### US-3: 数据库一键式初始化
**作为** 系统管理员，
**我希望** 将生成的文字与**本地静态路径**通过 `INSERT` 语句保存到 `init.sql`，
**以便于** 应用首次启动时自动完成好友库的本地化加载。

---

## 3. 拟创建的好友库角色范围 (Persona Scope)

我们将根据 `dev-docs/temp/preset_friends_list.md` 中的 126 位角色进行全量生成，涵盖思想、文学、科学、商业、娱乐、虚构及国民伴侣七大领域。

---

## 4. 技术实现路线 (Implementation Roadmap)

1.  **数据解析**：直接读取 `dev-docs/temp/preset_friends_list.csv` 中的结构化数据，提取角色姓名、标签、简介。
2.  **Persona 文字生成**：
    -   使用 `server/scripts/batch_generate_personas.py`。
    -   实现断点缓存逻辑，将生成的文本实时保存至 `temp/generated_personas_text.json`。
    -   循环调用 `PersonaGeneratorService.generate_persona` 生成 Prompt 和招呼语。
    -   **生图生图**：调用外部服务生成 126 张头像。
3.  **本地化存储 (Physical Storage)**：
    -   将生成的图片保存至 `server/static/avatars/presets/`。
    -   命名规范：使用英文 ID 或拼音，例如 `kongfuzi.webp`。
    -   **这一步产生的所有图片将作为源码的一部分提交到 Git 仓库，并打包入 Electron 安装包。**
4.  **路径定义 (Path Strategy)**：
    -   在 SQL 中使用相对于静态根目录的路径，例如：`/static/avatars/presets/kongfuzi.webp`。
    -   确保 FastAPI 的 `StaticFiles` 挂载点在打包模式下依然指向正确的本地资源目录。
4.  **SQL 持续导出**：
    -   生成最终的 `server/app/db/init_persona_templates.sql`。
5.  **集成验证**：
    -   在 Electron 的打包环境中运行测试，确保头像在离线安装后能正确显示。

---

## 5. 验收标准 (Acceptance Criteria)

- [ ] **AC-1**: 完成 126 个角色的背景提取、文字生成与头像生图。
- [ ] **AC-2**: **离线可用性**：安装后的应用在断网状态下，其“好友库”角色的头像必须能正常显示（不加载裂图）。
- [ ] **AC-3**: **安装包包含资产**：验证生图产出的 `server/static/avatars/presets/` 文件夹已被包含在分发包中。
- [ ] **AC-4**: **视觉质量控制**：头像风格统一，符合对应领域的艺术调性。
- [ ] **AC-5**: `init.sql` 中的路径引用与后端静态服务挂载点完美匹配。
