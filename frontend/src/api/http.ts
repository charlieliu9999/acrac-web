import axios from 'axios'

// 统一使用相对路径，由 Nginx 代理 /api 到后端，避免因构建环境变量配置错误导致的双前缀问题
// 前端不再读取 VITE_API_BASE，部署层面通过反向代理治理
export const api = axios.create({ baseURL: '' })

api.interceptors.response.use(
  (r) => r,
  (e) => Promise.reject(e)
)

