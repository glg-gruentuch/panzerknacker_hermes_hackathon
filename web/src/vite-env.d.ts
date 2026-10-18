/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_MODE?: 'demo' | 'live'
  readonly VITE_BACKEND_URL?: string
}
