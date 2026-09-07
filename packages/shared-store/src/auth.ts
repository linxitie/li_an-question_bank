import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiClient } from '@linxi/shared-api'
import type { User, LoginResponse } from '@linxi/shared-types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(null)
  const loading = ref(false)

  const isAuthenticated = computed(() => !!token.value)
  const currentUser = computed(() => user.value)

  async function login(username: string, password: string) {
    loading.value = true
    try {
      const formData = new FormData()
      formData.append('username', username)
      formData.append('password', password)
      
      const res = await apiClient.post<LoginResponse>('/api/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
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
      const res = await apiClient.get<User>('/api/auth/me')
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
