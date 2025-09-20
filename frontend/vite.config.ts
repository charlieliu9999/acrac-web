import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    allowedHosts: ['frontend', 'localhost', '127.0.0.1'],
    proxy: {
      // 本地开发时，将 /api 代理到后端（直连容器映射端口 8001）
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://localhost:8001',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
