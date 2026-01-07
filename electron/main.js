const { app, BrowserWindow, dialog } = require('electron')
const path = require('path')
const fs = require('fs')
const net = require('net')
const http = require('http')
const { spawn } = require('child_process')
const treeKill = require('tree-kill')

let backendProcess = null

const DEV_SERVER_URL = process.env.DOU_DOUCHAT_DEV_SERVER_URL || 'http://localhost:5173'
const HEALTH_PATH = '/api/health'
const BACKEND_START_TIMEOUT_MS = 45000

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

function createMainWindow() {
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 980,
    minHeight: 640,
    show: false,
    backgroundColor: '#e9edf0',
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

  return mainWindow
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

  const candidates = [
    'wechatagent.exe',
    'doudouchat-server.exe',
    'doudouchat-backend.exe',
    'server.exe',
    'backend.exe',
  ]

  for (const name of candidates) {
    const candidate = path.join(backendDir, name)
    if (fs.existsSync(candidate)) return candidate
  }

  if (fs.existsSync(backendDir)) {
    const files = fs.readdirSync(backendDir)
    const exe = files.find((file) => file.toLowerCase().endsWith('.exe'))
    if (exe) return path.join(backendDir, exe)
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
      DOUDOUCHAT_DATA_DIR: dataDir,
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

async function bootstrap() {
  const splash = createSplashWindow()

  try {
    const port = await startBackend()
    await waitForBackend(port)

    const mainWindow = createMainWindow()
    mainWindow.once('ready-to-show', () => {
      splash.close()
      mainWindow.show()
    })
  } catch (error) {
    dialog.showErrorBox('Startup Failed', error instanceof Error ? error.message : 'Unknown error')
    app.quit()
  }
}

app.whenReady().then(bootstrap)

app.on('before-quit', stopBackend)
app.on('window-all-closed', () => {
  stopBackend()
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    bootstrap()
  }
})
