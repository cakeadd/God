import { defineStore } from 'pinia'

import {
  changePassword as changePasswordRequest,
  getCurrentUser,
  login as loginRequest,
  register as registerRequest,
  updateCurrentUser,
} from '../api/auth'
import { clearTokens, getAccessToken, setTokens } from '../utils/tokenStorage'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    accessToken: getAccessToken(),
    initialized: false,
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.accessToken),
    displayName: (state) => state.user?.nickname || state.user?.username || '',
  },
  actions: {
    async login(credentials) {
      const response = await loginRequest(credentials)
      setTokens(response.data)
      this.accessToken = response.data.access
      await this.fetchCurrentUser()
    },
    async register(data) {
      const response = await registerRequest(data)
      setTokens(response.data)
      this.accessToken = response.data.access
      this.user = response.data.user
      return this.user
    },
    async fetchCurrentUser() {
      const response = await getCurrentUser()
      this.user = response.data
      return this.user
    },
    async updateProfile(data) {
      const response = await updateCurrentUser(data)
      this.user = response.data
      return this.user
    },
    async changePassword(data) {
      await changePasswordRequest(data)
    },
    async initialize() {
      if (this.initialized) return
      try {
        // 页面刷新后用本地 token 恢复用户，并让后端确认登录状态仍然有效。
        if (this.accessToken) {
          await this.fetchCurrentUser()
        }
      } catch {
        this.logout()
      } finally {
        this.initialized = true
      }
    },
    logout() {
      clearTokens()
      this.accessToken = null
      this.user = null
      this.initialized = true
    },
  },
})
