const DEFAULT_DEV_PORT = '8000'

export function getApiBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const w = window as Window & {
      __BACKEND_URL__?: string
      __BACKEND_PORT__?: number | string
    }
    if (w.__BACKEND_URL__) {
      return w.__BACKEND_URL__
    }
    if (w.__BACKEND_PORT__) {
      return `http://127.0.0.1:${w.__BACKEND_PORT__}`
    }
  }

  const envUrl = import.meta.env.VITE_BACKEND_URL
  if (envUrl) return envUrl

  const envPort = import.meta.env.VITE_BACKEND_PORT ?? DEFAULT_DEV_PORT
  return `http://127.0.0.1:${envPort}`
}

export function withApiBase(path: string): string {
  return new URL(path, getApiBaseUrl()).toString()
}
