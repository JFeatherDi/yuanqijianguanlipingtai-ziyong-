import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { BREADCRUMBS } from '@/domain/navigation'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    component: () => import('@/components/layout/AppShell.vue'),
    children: [
      {
        path: '',
        name: 'dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '主页' },
      },
      {
        path: 'components',
        name: 'components',
        component: () => import('@/views/ComponentsView.vue'),
        meta: { title: '元器件列表' },
      },
      {
        path: 'alerts',
        name: 'alerts',
        component: () => import('@/views/AlertsView.vue'),
        meta: { title: '库存预警' },
      },
      {
        path: 'stock/in',
        name: 'stock-in',
        component: () => import('@/views/StockInView.vue'),
        meta: { title: '入库登记' },
      },
      {
        path: 'stock/out',
        name: 'stock-out',
        component: () => import('@/views/StockOutView.vue'),
        meta: { title: '出库领用' },
      },
      {
        path: 'records',
        name: 'records',
        component: () => import('@/views/RecordsView.vue'),
        meta: { title: '操作记录' },
      },
      {
        path: 'data',
        name: 'data',
        component: () => import('@/views/DataView.vue'),
        meta: { title: '数据管理' },
      },
      {
        path: 'settings',
        name: 'settings',
        component: () => import('@/views/SettingsView.vue'),
        meta: { title: '系统设置' },
      },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: { name: 'dashboard' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  // 首次进入（含刷新）先确认会话，避免误判成未登录
  if (!auth.ready) await auth.loadSession()

  if (to.meta.public) {
    return auth.isAuthenticated ? { name: 'dashboard' } : true
  }
  if (!auth.isAuthenticated) {
    return { name: 'login', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } }
  }
  return true
})

router.afterEach((to) => {
  const trail = BREADCRUMBS.get(to.name) ?? []
  const suffix = trail.length ? ` · ${trail[trail.length - 1]}` : ''
  document.title = `IOTAT 元器件管理平台${suffix}`
})

export default router