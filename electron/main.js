const { app, BrowserWindow, dialog, Tray, Menu, ipcMain, nativeImage, shell } = require('electron')
const path = require('path')
const fs = require('fs')
const net = require('net')
const http = require('http')
const { spawn } = require('child_process')
const treeKill = require('tree-kill')

let backendProcess = null
let mainWindow = null
let tray = null
let isQuitting = false
let ipcReady = false
let isBootstrapping = false

// Tray flash state
let trayFlashTimer = null
let isFlashing = false
const FLASH_INTERVAL_MS = 500

const DEV_SERVER_URL = process.env.DOU_DOUCHAT_DEV_SERVER_URL || 'http://localhost:5173'
const HEALTH_PATH = '/api/health'
const BACKEND_START_TIMEOUT_MS = 45000

// Ensure Windows shell / shortcuts bind to our app identity for correct icon & notifications
app.setAppUserModelId('com.weagent.chat')

const gotSingleInstanceLock = app.requestSingleInstanceLock()
if (!gotSingleInstanceLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
      return
    }
    app.whenReady().then(() => {
      if (!isBootstrapping && !mainWindow) {
        bootstrap()
      }
    })
  })
}

function resolveAppIconPath(filename = 'icon.ico') {
  const baseDir = app.isPackaged
    ? path.join(app.getAppPath(), 'electron')
    : __dirname
  return path.join(baseDir, 'icons', filename)
}

function resolveTrayIconPath() {
  return resolveAppIconPath('icon.ico')
}

function resolveTrayFlashIconPath() {
  return resolveAppIconPath('icon_flash.ico')
}

function startTrayFlash() {
  if (isFlashing || !tray) return
  isFlashing = true

  const normalIcon = nativeImage.createFromPath(resolveTrayIconPath())
  const flashIcon = nativeImage.createFromPath(resolveTrayFlashIconPath())
  let showNormal = true

  trayFlashTimer = setInterval(() => {
    tray.setImage(showNormal ? flashIcon : normalIcon)
    showNormal = !showNormal
  }, FLASH_INTERVAL_MS)

  // Also activate taskbar flashing (Windows standard behavior)
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

  // Restore normal icon
  if (tray) {
    const normalIcon = nativeImage.createFromPath(resolveTrayIconPath())
    tray.setImage(normalIcon)
  }

  // Stop taskbar flashing
  if (mainWindow) {
    mainWindow.flashFrame(false)
  }
}

function createTray() {
  if (tray) return tray
  const iconPath = resolveTrayIconPath()
  const trayIcon = nativeImage.createFromPath(iconPath)
  tray = new Tray(trayIcon)
  tray.setToolTip('WeAgentChat')

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示主界面',
      click: () => {
        if (!mainWindow) return
        mainWindow.show()
        mainWindow.focus()
      },
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        isQuitting = true
        app.quit()
      },
    },
  ])

  tray.setContextMenu(contextMenu)
  tray.on('click', () => {
    stopTrayFlash() // Stop flashing when tray is clicked
    if (!mainWindow) return
    mainWindow.show()
    mainWindow.focus()
  })

  return tray
}

function createSplashWindow() {
  const splash = new BrowserWindow({
    width: 420,
    height: 260,
    frame: false,
    resizable: false,
    transparent: false,
    show: true,
    backgroundColor: '#f1f4f6',
  })
  splash.loadFile(path.join(__dirname, 'splash.html'))
  return splash
}

function shouldStartHidden() {
  const settings = app.getLoginItemSettings()
  return Boolean(settings.wasOpenedAtLogin || settings.wasOpenedAsHidden)
}

function createMainWindow() {
  const windowIcon = resolveAppIconPath('icon.ico')
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 980,
    minHeight: 640,
    show: false,
    backgroundColor: '#e9edf0',
    icon: windowIcon,
    frame: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (app.isPackaged) {
    const indexPath = path.join(app.getAppPath(), 'front', 'dist', 'index.html')
    mainWindow.loadFile(indexPath)
  } else {
    mainWindow.loadURL(DEV_SERVER_URL)
  }

  mainWindow.on('close', (event) => {
    if (isQuitting) return
    event.preventDefault()
    mainWindow.hide()
  })

  mainWindow.on('show', () => {
    mainWindow.setSkipTaskbar(false)
  })

  mainWindow.on('hide', () => {
    mainWindow.setSkipTaskbar(true)
  })

  mainWindow.on('maximize', () => sendWindowState(mainWindow))
  mainWindow.on('unmaximize', () => sendWindowState(mainWindow))
  mainWindow.on('focus', () => {
    stopTrayFlash() // Stop flashing when window gains focus
  })
  mainWindow.on('closed', () => {
    mainWindow = null
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (shouldOpenExternal(url)) {
      shell.openExternal(url)
      return { action: 'deny' }
    }
    return { action: 'allow' }
  })

  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (shouldOpenExternal(url)) {
      event.preventDefault()
      shell.openExternal(url)
    }
  })

  return mainWindow
}

function shouldOpenExternal(url) {
  if (!url) return false
  if (url.startsWith('file://')) return false
  if (url.startsWith(DEV_SERVER_URL)) return false
  if (url.startsWith('http://127.0.0.1') || url.startsWith('http://localhost')) {
    return false
  }
  return true
}

function findAvailablePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address()
      server.close(() => resolve(port))
    })
    server.on('error', reject)
  })
}

function resolveBackendExecutable(backendDir) {
  const explicit = process.env.DOU_DOUCHAT_BACKEND_EXE
  if (explicit && fs.existsSync(explicit)) {
    return explicit
  }

  const tryFindExe = (dir) => {
    const candidates = [
      'wechatagent.exe',
      'WeAgentChat-server.exe',
      'WeAgentChat-backend.exe',
      'server.exe',
      'backend.exe',
    ]

    for (const name of candidates) {
      const candidate = path.join(dir, name)
      if (fs.existsSync(candidate)) return candidate
    }

    const files = fs.readdirSync(dir)
    const exe = files.find((file) => file.toLowerCase().endsWith('.exe'))
    if (exe) return path.join(dir, exe)

    return null
  }

  const directExe = tryFindExe(backendDir)
  if (directExe) return directExe

  const candidates = [
    'wechatagent.exe',
    'WeAgentChat-server.exe',
    'WeAgentChat-backend.exe',
    'server.exe',
    'backend.exe',
  ]

  if (fs.existsSync(backendDir)) {
    const entries = fs.readdirSync(backendDir, { withFileTypes: true })
    for (const entry of entries) {
      if (!entry.isDirectory()) continue
      const nestedExe = tryFindExe(path.join(backendDir, entry.name))
      if (nestedExe) return nestedExe
    }
  }

  return null
}

function waitForBackend(port, timeoutMs = BACKEND_START_TIMEOUT_MS) {
  const deadline = Date.now() + timeoutMs

  return new Promise((resolve, reject) => {
    const attempt = () => {
      if (Date.now() > deadline) {
        reject(new Error('Backend startup timeout'))
        return
      }

      const req = http.get(
        {
          hostname: '127.0.0.1',
          port,
          path: HEALTH_PATH,
          timeout: 2000,
        },
        (res) => {
          if (res.statusCode === 200) {
            res.resume()
            resolve()
            return
          }
          res.resume()
          setTimeout(attempt, 1000)
        },
      )

      req.on('error', () => {
        setTimeout(attempt, 1000)
      })

      req.on('timeout', () => {
        req.destroy()
        setTimeout(attempt, 1000)
      })
    }

    attempt()
  })
}

async function startBackend() {
  if (!app.isPackaged) {
    const port = Number(process.env.DOU_DOUCHAT_BACKEND_PORT || 8000)
    process.env.DOU_DOUCHAT_BACKEND_PORT = String(port)
    return port
  }

  const backendDir = path.join(process.resourcesPath, 'backend')
  const backendExe = resolveBackendExecutable(backendDir)
  if (!backendExe) {
    throw new Error(`Backend executable not found in ${backendDir}`)
  }

  const port = await findAvailablePort()
  const dataDir = app.getPath('userData')
  process.env.DOU_DOUCHAT_BACKEND_PORT = String(port)
  process.env.DOU_DOUCHAT_DATA_DIR = dataDir

  backendProcess = spawn(backendExe, ['--port', String(port), '--data-dir', dataDir], {
    cwd: path.dirname(backendExe),
    env: {
      ...process.env,
      WeAgentChat_DATA_DIR: dataDir,
      PORT: String(port),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  backendProcess.stdout.on('data', (data) => {
    console.log(`[backend] ${data.toString().trim()}`)
  })

  backendProcess.stderr.on('data', (data) => {
    console.error(`[backend] ${data.toString().trim()}`)
  })

  backendProcess.on('exit', (code) => {
    console.log(`[backend] exited with code ${code ?? 'unknown'}`)
  })

  return port
}

function stopBackend() {
  if (backendProcess?.pid) {
    treeKill(backendProcess.pid)
    backendProcess = null
  }
}

function sendWindowState(win) {
  if (!win || win.isDestroyed()) return
  win.webContents.send('window:state', {
    isMaximized: win.isMaximized(),
    isMinimized: win.isMinimized(),
  })
}

function registerIpcHandlers() {
  if (ipcReady) return
  ipcReady = true

  ipcMain.on('window:minimize', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    win?.minimize()
  })

  ipcMain.on('window:toggle-maximize', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win) return
    if (win.isMaximized()) {
      win.unmaximize()
    } else {
      win.maximize()
    }
    sendWindowState(win)
  })

  ipcMain.on('window:close', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win) return
    win.hide()
  })

  ipcMain.handle('window:get-state', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win) {
      return { isMaximized: false, isMinimized: false }
    }
    return { isMaximized: win.isMaximized(), isMinimized: win.isMinimized() }
  })

  ipcMain.on('window:show-system-menu', (event, position) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win) return
    const isMaximized = win.isMaximized()
    const menu = Menu.buildFromTemplate([
      {
        label: '还原',
        enabled: isMaximized,
        click: () => win.unmaximize(),
      },
      {
        label: '最小化',
        click: () => win.minimize(),
      },
      {
        label: '最大化',
        enabled: !isMaximized,
        click: () => win.maximize(),
      },
      { type: 'separator' },
      {
        label: '关闭',
        click: () => win.hide(),
      },
    ])
    menu.popup({
      window: win,
      x: position?.x,
      y: position?.y,
    })
  })

  ipcMain.on('debug:toggle-devtools', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (win) {
      if (win.webContents.isDevToolsOpened()) {
        win.webContents.closeDevTools()
      } else {
        win.webContents.openDevTools()
      }
    }
  })

  ipcMain.on('shell:open-logs', async () => {
    // Determine typical log directory based on platform or app conventions
    // Generally in userData/logs or similar
    // Note: Backend might be configured to write logs elsewhere, 
    // but typically we want the Electron app's user data folder logs
    const logDir = path.join(app.getPath('userData'), 'logs')
    try {
      // Create if not exists to avoid error opening it
      if (!fs.existsSync(logDir)) {
        // If logs subdir doesn't exist, try opening just userData
        await shell.openPath(app.getPath('userData'))
      } else {
        await shell.openPath(logDir)
      }
    } catch (e) {
      console.error('Failed to open logs dir:', e)
    }
  })

  ipcMain.on('shell:open-external', async (event, url) => {
    if (url.startsWith('file://')) {
      try {
        const { fileURLToPath } = require('url')
        let filePath = fileURLToPath(url)

        // Workaround: Windows cannot open files directly inside .asar archives
        if (filePath.includes('app.asar')) {
          try {
            const fileName = path.basename(filePath)
            // Add a prefix to avoid potential name collisions
            const tempPath = path.join(app.getPath('temp'), `WeAgentChat_${fileName}`)

            // Electron's fs.readFile can transparently read from inside .asar
            const data = fs.readFileSync(filePath)
            fs.writeFileSync(tempPath, data)

            // Open the extracted temp file instead
            filePath = tempPath
          } catch (err) {
            console.error('[shell:open-external] Failed to extract file from ASAR:', err)
            // Continue to try opening original path as fallback
          }
        }

        await shell.openPath(filePath)
      } catch (e) {
        console.error('Failed to open local file:', e)
        // Fallback to openExternal if conversion fails
        await shell.openExternal(url)
      }
    } else {
      await shell.openExternal(url)
    }
  })

  // Notification flash handlers for new message alerts
  ipcMain.on('notification:flash', () => {
    startTrayFlash()
  })

  ipcMain.on('notification:stop-flash', () => {
    stopTrayFlash()
  })

  ipcMain.handle('system:set-auto-launch', (_event, enabled) => {
    app.setLoginItemSettings({
      openAtLogin: Boolean(enabled),
      openAsHidden: true,
    })
  })
}

async function bootstrap() {
  if (isBootstrapping) return
  isBootstrapping = true
  const startHidden = shouldStartHidden()
  const splash = startHidden ? null : createSplashWindow()

  try {
    const port = await startBackend()
    // 稍微激进一点的等待，每 500ms 检查一次后端是否就绪
    await waitForBackend(port)

    const mainWindow = createMainWindow()
    createTray()
    mainWindow.once('ready-to-show', () => {
      if (splash) {
        splash.close()
      }
      if (startHidden) {
        mainWindow.setSkipTaskbar(true)
        mainWindow.hide()
        return
      }
      mainWindow.show()
    })
  } catch (error) {
    dialog.showErrorBox('Startup Failed', error instanceof Error ? error.message : 'Unknown error')
    app.quit()
  } finally {
    isBootstrapping = false
  }
}

app.whenReady().then(() => {
  registerIpcHandlers()
  bootstrap()
})

app.on('before-quit', () => {
  isQuitting = true
  stopBackend()
})
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin' && !isQuitting) return
  stopBackend()
  if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    bootstrap()
  }
})












