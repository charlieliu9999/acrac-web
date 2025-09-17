import axios from 'axios'
import { API_BASE } from '../config'

export const api = axios.create({ baseURL: API_BASE })

api.interceptors.response.use(
  (r) => r,
  (e) => {
    return Promise.reject(e)
  }
)

