interface Window {
  __BACKEND_URL__?: string
  __BACKEND_PORT__?: number | string
  doudouchat?: {
    backendPort?: number
    backendUrl?: string
    isElectron?: boolean
    windowControls?: {
      minimize: () => void
      toggleMaximize: () => void
      close: () => void
      getState: () => Promise<{ isMaximized: boolean; isMinimized: boolean }>
      showSystemMenu: (position: { x: number; y: number }) => void
      onState: (callback: (state: { isMaximized: boolean; isMinimized: boolean }) => void) => () => void
    }
  }
}
