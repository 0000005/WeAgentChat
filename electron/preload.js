const { contextBridge, ipcRenderer } = require('electron')

const backendPortRaw = process.env.DOU_DOUCHAT_BACKEND_PORT
const backendPort = backendPortRaw ? Number(backendPortRaw) : undefined
const backendUrl =
  process.env.DOU_DOUCHAT_BACKEND_URL || (backendPort ? `http://127.0.0.1:${backendPort}` : undefined)

contextBridge.exposeInMainWorld('__BACKEND_PORT__', backendPort)
contextBridge.exposeInMainWorld('__BACKEND_URL__', backendUrl)
contextBridge.exposeInMainWorld('doudouchat', {
  backendPort,
  backendUrl,
  isElectron: true,
  windowControls: {
    minimize: () => ipcRenderer.send('window:minimize'),
    toggleMaximize: () => ipcRenderer.send('window:toggle-maximize'),
    close: () => ipcRenderer.send('window:close'),
    getState: () => ipcRenderer.invoke('window:get-state'),
    showSystemMenu: (position) => ipcRenderer.send('window:show-system-menu', position),
    onState: (callback) => {
      if (typeof callback !== 'function') return () => {}
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('window:state', listener)
      return () => ipcRenderer.removeListener('window:state', listener)
    },
  },
})
