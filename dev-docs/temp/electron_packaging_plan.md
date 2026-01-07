# Electron 桌面客户端封装技术方案

## 1. 目标
将现有的 DouDouChat Web 项目（Vue 3 前端 + FastAPI 后端）封装为单体桌面应用（Windows），实现一键安装、启动，并保留原有的完整功能。

## 2. 技术选型
*   **容器框架**: Electron (最新稳定版)
*   **前端**: 现有 Vue 3 + Vite 项目
*   **后端打包**: PyInstaller (将 Python 环境和代码打包为可执行文件)
*   **构建/打包工具**: electron-builder
*   **进程管理**: Node.js `child_process` (用于在 Electron 主进程中启动 Python 后端)

## 3. 架构设计

### 3.1 运行模式
*   **开发模式 (Dev)**:
    *   启动 Vue Dev Server (localhost:5173)
    *   启动 FastAPI Dev Server (localhost:8000)
    *   启动 Electron，加载 `http://localhost:5173`
*   **生产模式 (Prod)**:
    *   Python 后端打包为独立 EXE 文件夹（包含解释器和依赖）。
    *   Vue 前端构建为静态资源 (`dist/`)。
    *   用户启动 Electron App -> Electron 主进程启动 Python EXE -> 等待后端就绪 -> Electron 加载前端静态页面。

### 3.2 目录结构调整建议
建议在根目录下新建 `electron` 目录存放相关代码，保持 `front` 和 `server` 相对独立。

```
DouDouChat/
├── electron/                 # [新增] Electron 相关代码
│   ├── main.js               # Electron 主进程入口
│   ├── preload.js            # 预加载脚本 (IPC)
│   └── icons/                # 应用图标
├── front/                    # 现有前端
├── server/                   # 现有后端
├── build/                    # [新增] 构建产物临时目录（PyInstaller产物等）
├── resources/                # [新增] 打包所需的额外资源
├── package.json              # [修改] 根目录或 front 目录添加 Electron 依赖和脚本
└── electron-builder.yml      # [新增] 打包配置文件
```

## 4. 详细实施步骤

### 4.1 后端改造与打包 (Server)
1.  **路径适配**: 
    *   数据库文件 (`doudou.db`, `memobase.db`) 和日志文件在生产环境必须存储在用户的 **AppData** 目录 (`%APPDATA%/DouDouChat`)，因为安装目录 (`Program Files`) 通常是只读的。
    *   需要修改 `server/app/core/config.py`，支持通过环境变量或启动参数 (`--data-dir`) 覆盖默认的数据存储路径。
2.  **PyInstaller 配置**: 
    *   编写 `.spec` 文件，确保包含所有 Python 依赖。
    *   **重点注意**: `sqlite-vec` 是基于 C 扩展的库，通过 `ctypes` 加载，可能需要手动在 PyInstaller 中配置 `binaries` 将其 DLL/SO 文件包含进去。
    *   目标: 生成 `onedir` 模式（文件夹形式），启动速度比 `onefile` 快且易于排查资源缺失问题。

### 4.2 前端改造 (Front)
1.  **API Base URL**: 
    *   前端请求的 API 地址目前可能是写死或基于 `.env` 的。在 Electron 环境中，后端端口可能是随机的（防止端口冲突）。
    *   **方案**: Electron 主进程在启动 Python 后端时获取端口，通过 `preload.js` 的 `contextBridge` 注入到 `window.__BACKEND_PORT__` 或类似全局变量中。前端 `api` 模块初始化时读取该变量构建 Base URL。
2.  **路由模式**: 
    *   如果打包后加载 `index.html` (file:// 协议)，Vue Router 建议使用 `Hash` 模式 (`createWebHashHistory`) 避免刷新 404 问题。或者在 Electron 中拦截协议请求做重定向。

### 4.3 Electron 主进程开发 (electron/main.js)
1.  **生命周期管理**:
    *   **启动**: 
        1. 寻找可用端口。
        2. `child_process.spawn` 启动 Python 后端可执行文件，传入端口和数据路径参数。
        3. 监听 Python 进程的 `stdout` 判断启动状态。
        4. 轮询 `/health` 接口确保服务可用。
        5. 创建 BrowserWindow 加载前端。
    *   **关闭**: 
        *   监听 `window-all-closed` 或 `before-quit` 事件，确保调用 `tree-kill` 或发送信号关闭 Python 子进程，防止僵尸进程占用端口。
2.  **加载策略**:
    *   Dev: `loadURL('http://localhost:5173')`
    *   Prod: `loadFile('path/to/front/dist/index.html')`

### 4.4 打包配置 (electron-builder)
1.  **配置**: 使用 `electron-builder.yml` 或 `package.json` 中的 `build` 字段。
2.  **资源包含 (ExtraResources)**:
    *   将 PyInstaller 生成的 `backend` 文件夹配置为 `extraResources`。这样它会被复制到安装目录的 `resources` 文件夹下，且不会被压缩进 `app.asar`（因为 Python 解释器无法直接运行 asar 中的文件）。
3.  **Hooks**:
    *   `beforePack`: 钩子脚本，自动执行 `pnpm build` (前端) 和 `pyinstaller server.spec` (后端)。

## 5. 关键难点与解决方案

| 难点 | 解决方案 |
| :--- | :--- |
| **sqlite-vec 依赖** | `sqlite-vec` 可能包含特定平台的动态链接库。需要在 PyInstaller 的 spec 文件中显式添加 `datas` 或 `binaries` 规则，确保 DLL 被正确打包并位于 Python 查找路径中。 |
| **数据库路径权限** | 绝对不能在安装目录写文件。Electron 启动 Python 时，利用 `app.getPath('userData')` 获取可写路径，并通过命令行参数传给 Python。Python 端据此初始化 SQLite 连接字符串。 |
| **端口冲突** | 生产环境不应使用固定 8000 端口。使用 `net` 模块寻找空闲端口，并通过环境变量 `PORT` 传给 Uvicorn。 |
| **启动白屏** | Python 服务启动需要时间。Electron 应先显示一个 Splash Screen (启动加载页)，后台检测到后端 `/health` 返回 200 后，再隐藏 Splash 显示主窗口。 |

## 6. 下一步行动建议
1.  **环境准备**: 在项目根目录安装 electron 开发依赖。
2.  **后端调整**: 修改 `server/app/core/config.py` 以支持动态数据目录。
3.  **POC (概念验证)**: 编写一个简单的 Electron 脚本，尝试启动现有的 Python 源码（使用系统 Python），验证通信链路。

## 7. 本次任务进度更新
### 7.1 已完成事项
*   **后端数据目录可配置**: `server/app/core/config.py` 支持 `DOUDOUCHAT_DATA_DIR` 环境变量覆盖默认数据目录。
*   **后端 CLI 入口**: 新增 `server/app/cli.py`，支持 `--port` 与 `--data-dir` 启动参数，便于 Electron 调用。
*   **前端 API 基地址适配**: 新增 `front/src/api/base.ts` 与 `front/src/env.d.ts`，统一从 Electron 注入变量/环境变量解析 API Base URL。
*   **前端 API 接口改造**: `front/src/api/*.ts` 已改为使用 `withApiBase()` 进行请求。
*   **Electron 主进程/预加载**: 新增 `electron/main.js`、`electron/preload.js`，完成端口寻找、后端启动、健康检查、窗口加载与进程回收。
*   **启动 Splash**: 新增 `electron/splash.html`，避免启动白屏。
*   **打包配置**: 新增 `electron-builder.yml` 与根目录 `package.json` (Electron 依赖与脚本)。

### 7.2 待完成事项
*   **PyInstaller spec**: 需要编写 `server.spec` 并处理 `sqlite-vec` 的 `binaries` 打包。
*   **前端路由模式**: 如需 `file://` 打包运行，需确认 Vue Router 是否切换 `Hash` 模式。
*   **CI/自动化**: 可选增加 `beforePack` 钩子自动编译前端与后端。

## 8. 打包与使用说明
### 8.1 开发模式
1.  启动后端: `cd server` 后运行 `venv\Scripts\python -m uvicorn app.main:app --reload`
2.  启动前端: `cd front` 后运行 `pnpm dev`
3.  启动 Electron: 在项目根目录运行 `pnpm electron:dev`

### 8.2 生产打包
1.  先用 PyInstaller 生成后端（产物目录需放到 `build/backend`）
2.  在项目根目录运行 `pnpm electron:build`
3.  打包产物输出到 `dist-electron/`

### 8.3 重要说明
*   生产环境下 Electron 会用 `process.resourcesPath/backend` 启动后端。
*   Electron 通过 `--data-dir` 参数将数据目录指向 `app.getPath('userData')`，避免写入只读安装目录。

### 8.4 一键打包脚本
*   使用 `scripts/package-electron.bat` 可完成后端打包、前端构建与 Electron 打包。
*   该脚本会自动检测并安装 `pyinstaller`，以及检测 `pnpm` 和依赖目录。
*   默认后端输出 EXE 名称为 `wechatagent.exe`（通过 `--name` 参数指定）。
