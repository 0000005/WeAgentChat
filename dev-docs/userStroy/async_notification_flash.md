# 用户故事：异步消息/通知提醒（托盘与任务栏闪烁）

## 1. 需求背景 (Background)
在桌面端应用中，当应用处于最小化、后台运行或未聚焦状态时，用户无法直接在界面上感知到新的动态（如新消息、AI 异步生成的"新功能"解锁通知等）。为了提升产品的交互及时性并模拟微信等社交软件的成熟体验，我们需要实现 OS 级别的视觉提醒：系统托盘图标闪烁以及任务栏图标高亮闪烁。

## 2. 核心目标 (User Goals)
- **多维度提醒**：通过托盘图标和任务栏图标的双重闪烁，确保用户在任何工作场景下都不会遗漏重要通知。
- **模拟微信体验**：闪烁频率和样式高度参考 Windows 版微信，让用户感到亲切和专业。
- **焦点感知回馈**：当用户点击并激活应用窗口后，闪烁应自动停止，消除冗余提醒。

---

## 3. 现状分析 (Current State Analysis)

### 3.1 Electron 主进程 (`electron/main.js`)
- **托盘系统已就绪**：`createTray()` 已实现，使用 `electron/icons/icon.ico` 作为托盘图标。
- **窗口焦点事件**：`mainWindow.on('show')` / `mainWindow.on('hide')` 已监听，但未处理 `focus` 事件。
- **IPC 通信**：已有 `registerIpcHandlers()` 函数，支持 `window:minimize`, `window:close` 等信号。
- **缺失**：无 `notification:flash` / `notification:stop-flash` IPC 处理器；无闪烁用的透明/空白图标。

### 3.2 Preload 脚本 (`electron/preload.js`)
- **已暴露接口**：`window.WeAgentChat` 对象包含 `windowControls`, `debug`, `shell` 等命名空间。
- **缺失**：无 `notification` 命名空间来发送闪烁信号。

### 3.3 前端 Session Store (`front/src/stores/session.ts`)
- **关键代码位置**：`sendMessage()` 函数的 `done` 事件处理（约 360-385 行）。
- **已有逻辑**：当用户切换好友 (`currentFriendId.value !== friendId`) 时，会更新 `unreadCounts`。
- **缺失**：未检测 `document.hasFocus()` 状态；未调用任何 IPC 闪烁信号。

### 3.4 图标资源 (`electron/icons/`)
- **现有文件**：`icon.ico` (81KB), `icon.png` (184KB)
- **需新增**：`icon_blank.ico` 或透明图标，用于闪烁切换。

---

## 4. 详细设计 (Technical Implementation)

### 4.1 Electron 主进程改造

#### A. 新增闪烁状态管理
```javascript
// electron/main.js (新增全局变量)
let trayFlashTimer = null
let isFlashing = false
const FLASH_INTERVAL_MS = 500

// 闪烁用图标路径
function resolveTrayFlashIconPath() {
  return resolveAppIconPath('icon_blank.ico') // 透明或空白图标
}
```

#### B. 新增闪烁控制函数
```javascript
function startTrayFlash() {
  if (isFlashing || !tray) return
  isFlashing = true

  const normalIcon = nativeImage.createFromPath(resolveTrayIconPath())
  const blankIcon = nativeImage.createFromPath(resolveTrayFlashIconPath())
  let showNormal = true

  trayFlashTimer = setInterval(() => {
    tray.setImage(showNormal ? blankIcon : normalIcon)
    showNormal = !showNormal
  }, FLASH_INTERVAL_MS)

  // 同时激活任务栏闪烁
  if (mainWindow && !mainWindow.isFocused()) {
    mainWindow.flashFrame(true)
  }
}

function stopTrayFlash() {
  if (!isFlashing) return
  isFlashing = false

  if (trayFlashTimer) {
    clearInterval(trayFlashTimer)
    trayFlashTimer = null
  }

  // 恢复正常图标
  if (tray) {
    const normalIcon = nativeImage.createFromPath(resolveTrayIconPath())
    tray.setImage(normalIcon)
  }

  // 停止任务栏闪烁
  if (mainWindow) {
    mainWindow.flashFrame(false)
  }
}
```

#### C. 新增 IPC 监听器（在 `registerIpcHandlers()` 中添加）
```javascript
ipcMain.on('notification:flash', () => {
  startTrayFlash()
})

ipcMain.on('notification:stop-flash', () => {
  stopTrayFlash()
})
```

#### D. 自动停止闪烁（窗口焦点事件）
```javascript
// 在 createMainWindow() 中添加
mainWindow.on('focus', () => {
  stopTrayFlash()
})

// 托盘点击也应停止闪烁（已有 tray.on('click')，需增强）
tray.on('click', () => {
  stopTrayFlash() // 新增
  if (!mainWindow) return
  mainWindow.show()
  mainWindow.focus()
})
```

### 4.2 Preload 脚本改造

在 `window.WeAgentChat` 中新增 `notification` 命名空间：

```javascript
// electron/preload.js
contextBridge.exposeInMainWorld('WeAgentChat', {
  // ... 现有内容 ...
  notification: {
    flash: () => ipcRenderer.send('notification:flash'),
    stopFlash: () => ipcRenderer.send('notification:stop-flash'),
  },
})
```

### 4.3 前端 TypeScript 类型声明

在 `front/src/types/electron.d.ts`（或全局类型文件）中扩展：

```typescript
interface WeAgentChatAPI {
  // ... 现有类型 ...
  notification: {
    flash: () => void
    stopFlash: () => void
  }
}
```

### 4.4 Session Store 改造

修改 `front/src/stores/session.ts` 的 `sendMessage()` 函数：

```typescript
// 在 done 事件处理块中（约 360-385 行）
} else if (event === 'done') {
  // ... 现有消息处理逻辑 ...

  // 🆕 新增：检测窗口焦点状态并触发闪烁
  const shouldFlash = 
    typeof document !== 'undefined' && 
    !document.hasFocus() && 
    typeof window !== 'undefined' && 
    window.WeAgentChat?.notification?.flash

  if (shouldFlash) {
    window.WeAgentChat.notification.flash()
  }

  // ... 其余代码 ...
}
```

### 4.5 App.vue 焦点监听

在应用入口添加全局焦点监听，确保用户交互后停止闪烁：

```typescript
// front/src/App.vue (setup 或 onMounted)
onMounted(() => {
  const handleFocus = () => {
    if (window.WeAgentChat?.notification?.stopFlash) {
      window.WeAgentChat.notification.stopFlash()
    }
  }
  window.addEventListener('focus', handleFocus)
  
  onUnmounted(() => {
    window.removeEventListener('focus', handleFocus)
  })
})
```

---

## 5. 任务列表 (Task List)

### Phase 1: 资源与基础设施
- [ ] **[Asset]** 创建 `electron/icons/icon_blank.ico`（透明 16x16 图标）。
- [ ] **[Electron]** 在 `main.js` 中添加闪烁状态变量和辅助函数。
- [ ] **[Electron]** 实现 `startTrayFlash()` 和 `stopTrayFlash()` 函数。
- [ ] **[Electron]** 注册 `notification:flash` 和 `notification:stop-flash` IPC 处理器。
- [ ] **[Electron]** 在 `mainWindow.on('focus')` 和 `tray.on('click')` 中调用 `stopTrayFlash()`。

### Phase 2: 前端集成
- [ ] **[Preload]** 在 `preload.js` 中暴露 `notification` 命名空间。
- [ ] **[Types]** 更新 TypeScript 类型声明。
- [ ] **[Store]** 修改 `session.ts` 的 `sendMessage()`，在 `done` 事件中检测焦点并触发闪烁。
- [ ] **[App]** 在 `App.vue` 中添加全局 `focus` 事件监听以停止闪烁。

### Phase 3: 测试与优化
- [ ] **[Test]** 手动测试：最小化应用 → 发送消息 → 验证托盘+任务栏闪烁。
- [ ] **[Test]** 手动测试：点击托盘/任务栏 → 验证闪烁立即停止。
- [ ] **[Test]** 手动测试：多好友并发消息场景下的闪烁行为。

---

## 6. 验收标准 (Acceptance Criteria)

1. **托盘闪烁**：当收到新消息（应用非活跃/未聚焦）时，右下角托盘图标开始闪烁（500ms 间隔）。
2. **任务栏高亮**：任务栏中的应用图标变成黄色/橙色闪烁状态（Windows 标准行为）。
3. **自动停止**：
    - 用户点击任务栏图标使窗口弹出。
    - 用户点击托盘图标。
    - 窗口获得焦点（Alt+Tab 切换等）。
    - 以上任一操作均应立即停止托盘和任务栏的闪烁。
4. **资源开销**：停止闪烁后，后台计时器必须被精准销毁，不能产生内存泄露。
5. **边界情况**：
    - 多次触发闪烁不会创建多个计时器（幂等性）。
    - 应用已在前台时，收到消息不触发闪烁。

---

## 7. 相关文件索引

```
electron/
├── main.js             # IPC 信号处理、托盘闪烁逻辑、窗口焦点事件
├── preload.js          # 暴露 notification 命名空间
└── icons/
    ├── icon.ico        # 正常托盘图标（已存在）
    └── icon_blank.ico  # 闪烁用透明图标（需新增）

front/
└── src/
    ├── App.vue             # 全局焦点监听
    ├── stores/
    │   └── session.ts      # 消息接收时触发闪烁的业务逻辑
    └── types/
        └── electron.d.ts   # TypeScript 类型声明（可能需新建）
```

---

## 8. 排期建议

- **优先级**: P1 (重要体验增强)
- **预估工时**: 1d
  - Electron 主进程改造: 0.5d
  - 前端集成与测试: 0.5d
