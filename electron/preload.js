const { contextBridge } = require('electron')

const backendPortRaw = process.env.DOU_DOUCHAT_BACKEND_PORT
const backendPort = backendPortRaw ? Number(backendPortRaw) : undefined
const backendUrl =
  process.env.DOU_DOUCHAT_BACKEND_URL || (backendPort ? `http://127.0.0.1:${backendPort}` : undefined)

contextBridge.exposeInMainWorld('__BACKEND_PORT__', backendPort)
contextBridge.exposeInMainWorld('__BACKEND_URL__', backendUrl)
contextBridge.exposeInMainWorld('doudouchat', {
  backendPort,
  backendUrl,
})
