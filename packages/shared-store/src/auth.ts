import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@linxi/shared-api'
import type { User, LoginResponse } from '@linxi/shared-types'

/**
 * 认证 Store。
 *
 * 与 apiClient 的约定：
 *  - apiClient.baseURL 已是 '/api'，此处路径**不得**再带 '/api' 前缀，
 *    否则会拼出 '/api/api/xxx'。
 *  - apiClient 的响应拦截器已拆出后端统一包络的 data 层，
 *    因此返回值直接就是业务对象。
 */
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(null)
  const loading = ref(false)

  const isAuthenticated = computed(() => !!token.value)
  const currentUser = computed(() => user.value)

  async function login(username: string, password: string) {
    loading.value = true
    try {
      // 后端 /api/auth/login 使用 OAuth2PasswordRequestForm，
      // 必须以 application/x-www-form-urlencoded 提交表单字段。
      const form = new URLSearchParams()
      form.append('username', username)
      form.append('password', password)

      const res = await apiClient.post<LoginResponse>('/auth/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      })
      token.value = res.access_token
      user.value = res.user
      localStorage.setItem('token', res.access_token)
      return res
    } finally {
      loading.value = false
    }
  }

  async function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  async function fetchUser() {
    if (!token.value) return
    try {
      const res = await apiClient.get<User>('/auth/me')
      user.value = res
    } catch (error) {
      await logout()
    }
  }

  return {
    token,
    user,
    loading,
    isAuthenticated,
    currentUser,
    login,
    logout,
    fetchUser
  }
})
