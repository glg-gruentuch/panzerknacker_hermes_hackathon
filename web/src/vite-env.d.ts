/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_MODE?: 'mock' | 'live' | 'static'
  readonly VITE_BACKEND_URL?: string
}
