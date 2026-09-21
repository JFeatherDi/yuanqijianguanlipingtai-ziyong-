import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { setUnauthorizedHandler } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

import './styles/tokens.css'
import './styles/base.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// 任何接口返回 401 都由这里统一收口：清会话 + 回登录页
setUnauthorizedHandler(() => {
  const auth = useAuthStore()
  auth.clear()
  if (router.currentRoute.value.name !== 'login') {
    router.replace({ name: 'login' })
  }
})

const auth = useAuthStore()
auth.loadSession().finally(() => app.mount('#app'))