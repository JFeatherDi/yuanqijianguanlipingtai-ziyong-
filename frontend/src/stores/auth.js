import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '@/api/endpoints'

export const useAuthStore = defineStore('auth', () => {
  const user = ref('')
  const ready = ref(false)
  const pending = ref(false)

  const isAuthenticated = computed(() => Boolean(user.value))
  const initial = computed(() => (user.value ? user.value.charAt(0).toUpperCase() : '?'))

  /** 用一次性会话探测决定初始路由，避免刷新时闪一下登录页。 */
  async function loadSession() {
    try {
      const res = await authApi.me()
      user.value = res.user ?? ''
    } catch {
      user.value = ''
    } finally {
      ready.value = true
    }
    return isAuthenticated.value
  }

  async function login(username, password, captcha) {
    pending.value = true
    try {
      const res = await authApi.login({ username, password, captcha })
      user.value = res.user ?? username
      return res
    } finally {
      pending.value = false
    }
  }

  async function logout() {
    try {
      await authApi.logout()
    } finally {
      clear()
    }
  }

  function clear() {
    user.value = ''
  }

  return { user, ready, pending, isAuthenticated, initial, loadSession, login, logout, clear }
})