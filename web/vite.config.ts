import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, /api/* is proxied to the backend so the browser never needs CORS.
// Point VITE_BACKEND_URL at wherever the Python service runs.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': { target: env.VITE_BACKEND_URL || 'http://localhost:8000', changeOrigin: true },
      },
    },
  }
})
