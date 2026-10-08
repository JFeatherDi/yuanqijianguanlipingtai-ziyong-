import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '@/api/endpoints'

export const useAuthStore = defineStore('auth', () => {
  const user = ref('')
  const role = ref('member')
  const ready = ref(false)
  const pending = ref(false)

  const isAuthenticated = computed(() => Boolean(user.value))
  const isAdmin = computed(() => role.value === 'admin')
  const initial = computed(() => (user.value ? user.value.charAt(0).toUpperCase() : '?'))

  /** 用一次性会话探测决定初始路由，避免刷新时闪一下登录页。 */
  async function loadSession() {
    try {
      const res = await authApi.me()
      user.value = res.user ?? ''
      role.value = res.role ?? 'member'
    } catch {
      user.value = ''
      role.value = 'member'
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
      role.value = res.role ?? 'member'
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
    role.value = 'member'
  }

  return { user, role, ready, pending, isAuthenticated, isAdmin, initial, loadSession, login, logout, clear }
})