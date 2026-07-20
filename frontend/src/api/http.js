import axios from 'axios'

import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
} from '../utils/tokenStorage'

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'

const http = axios.create({
  baseURL,
  timeout: 15000,
})

let refreshPromise = null

http.interceptors.request.use((config) => {
  const accessToken = getAccessToken()
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    const refreshToken = getRefreshToken()

    if (
      error.response?.status !== 401 ||
      originalRequest?._retry ||
      !refreshToken
    ) {
      return Promise.reject(error)
    }

    originalRequest._retry = true

    try {
      // 并发请求同时遇到 401 时只刷新一次，其余请求等待同一个结果。
      if (!refreshPromise) {
        refreshPromise = axios.post(`${baseURL}/auth/refresh/`, {
          refresh: refreshToken,
        })
      }
      const response = await refreshPromise
      const accessToken = response.data.access
      setAccessToken(accessToken)
      originalRequest.headers.Authorization = `Bearer ${accessToken}`
      return http(originalRequest)
    } catch (refreshError) {
      clearTokens()
      if (window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
      return Promise.reject(refreshError)
    } finally {
      refreshPromise = null
    }
  },
)

export default http
