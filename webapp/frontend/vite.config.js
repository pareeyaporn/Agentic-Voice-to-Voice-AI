import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// /api/* is proxied to the FastAPI backend so the dev frontend needs no CORS
// and no hardcoded backend URL in code.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8500',
    },
  },
})
