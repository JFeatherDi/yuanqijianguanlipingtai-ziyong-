<script setup>
/**
 * 系统设置：本项目没有可写的配置接口，因此这一页只做「只读的运行信息」，
 * 不伪造任何可编辑但实际不生效的开关。
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import PanelCard from '@/components/ui/PanelCard.vue'
import { useAuthStore } from '@/stores/auth'
import { useInventoryStore } from '@/stores/inventory'
import { useToastStore } from '@/stores/toast'
import { formatQuantity } from '@/utils/format'

const auth = useAuthStore()
const inventory = useInventoryStore()
const toast = useToastStore()
const router = useRouter()

const signingOut = ref(false)

const account = computed(() => [
  { label: '当前账号', value: auth.user || '—' },
  { label: '会话有效期', value: '12 小时无操作自动失效' },
  { label: '会话续期', value: '每次请求自动续期' },
  { label: '登录限流', value: '同一 IP 连续失败 5 次锁定 5 分钟' },
])

const overview = computed(() => [
  { label: '元器件种类', value: formatQuantity(inventory.total) },
  { label: '总库存量', value: formatQuantity(inventory.totalStock) },
  { label: '预警项', value: formatQuantity(inventory.lowCount), tone: inventory.lowCount ? 'warn' : '' },
  { label: '已有分类', value: formatQuantity(inventory.options.categories.length) },
  { label: '库位数', value: formatQuantity(inventory.options.locations.length) },
])

const guarantees = [
  {
    title: 'SQLite WAL 模式',
    desc: '读不阻塞写、写不阻塞读，多人同时使用不会互相卡住。',
  },
  {
    title: '出库原子扣减',
    desc: '扣减使用 UPDATE ... WHERE stock >= ?，并发下也不会把库存扣成负数。',
  },
  {
    title: '写锁自动排队',
    desc: '数据库繁忙时最多等待 10 秒，而不是立刻抛出 database is locked。',
  },
  {
    title: '上传体积上限',
    desc: '单个请求正文最大 8 MB，防止导入超大文件拖垮小服务器。',
  },
  {
    title: '单请求超时 30 秒',
    desc: '慢请求不会无限占用工作线程。',
  },
  {
    title: '生产级并发限制',
    desc: '使用 waitress 监听，最多 8 个工作线程、20 个连接，避免进程堆积。',
  },
]

const envVars = [
  { name: 'APP_PORT', value: '5000', note: '后端监听端口' },
  { name: 'APP_HOST', value: '0.0.0.0', note: '后端监听地址，0.0.0.0 表示允许局域网访问' },
  { name: 'APP_DB_PATH', value: 'backend/data.db', note: 'SQLite 数据库文件路径' },
  { name: 'APP_SECRET_KEY', value: '内置默认值', note: '会话签名密钥，正式部署务必修改' },
  { name: 'APP_USERNAME', value: 'IOTAT', note: '登录账号' },
  { name: 'APP_PASSWORD', value: '内置默认值', note: '登录密码，正式部署务必修改' },
  { name: 'APP_SESSION_HOURS', value: '12', note: '会话有效期（小时）' },
  { name: 'APP_LOGIN_MAX_FAIL', value: '5', note: '触发锁定前的最大失败次数' },
  { name: 'APP_LOGIN_LOCK_SECONDS', value: '300', note: '锁定时长（秒）' },
  { name: 'APP_MAX_UPLOAD_MB', value: '8', note: '上传体积上限（MB）' },
  { name: 'APP_THREADS', value: '8', note: 'waitress 工作线程数' },
  { name: 'APP_CONNECTION_LIMIT', value: '20', note: '最大并发连接数（含排队）' },
  { name: 'APP_CORS_ORIGINS', value: 'http://localhost:5173', note: '允许携带 Cookie 跨域访问的前端地址' },
  { name: 'APP_STATIC_DIST', value: 'frontend/dist', note: '前端构建产物目录' },
]

async function signOut() {
  if (signingOut.value) return
  signingOut.value = true
  try {
    await auth.logout()
    toast.info('已退出登录')
    router.replace({ name: 'login' })
  } finally {
    signingOut.value = false
  }
}
</script>

<template>
  <div class="settings">
    <div class="settings__grid">
      <PanelCard title="账号信息">
        <dl class="facts">
          <div v-for="item in account" :key="item.label" class="facts__row">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>

        <div class="settings__action">
          <AppButton variant="danger" icon="logout" :loading="signingOut" @click="signOut">
            退出登录
          </AppButton>
        </div>
      </PanelCard>

      <PanelCard title="系统概况">
        <div class="kpi-strip">
          <div v-for="item in overview" :key="item.label" class="kpi">
            <span class="kpi__label">{{ item.label }}</span>
            <span class="kpi__value" :class="{ 'kpi__value--warn': item.tone === 'warn' }">
              {{ item.value }}
            </span>
          </div>
        </div>

        <p class="settings__note">
          概况数据来自当前已加载的元器件清单；点击顶栏的刷新按钮可重新拉取。
        </p>
      </PanelCard>
    </div>

    <PanelCard title="安全与并发">
      <ul class="guarantees">
        <li v-for="item in guarantees" :key="item.title" class="guarantees__item">
          <AppIcon name="shield" :size="16" class="guarantees__icon" />
          <span class="guarantees__body">
            <b class="guarantees__title">{{ item.title }}</b>
            <span class="guarantees__desc">{{ item.desc }}</span>
          </span>
        </li>
      </ul>
    </PanelCard>

    <PanelCard title="部署方式" flush>
      <div class="deploy">
        <div class="deploy__item">
          <span class="deploy__step">开发</span>
          <p>
            在 <code>frontend/</code> 执行 <code>npm run dev</code>，Vite 会把
            <code>/api</code> 代理到 <code>http://127.0.0.1:5000</code>，
            浏览器视作同源，Session Cookie 直接生效。后端在项目根目录执行
            <code>python -m backend.app</code>。
          </p>
        </div>
        <div class="deploy__item">
          <span class="deploy__step">生产</span>
          <p>
            在 <code>frontend/</code> 执行 <code>npm run build</code> 生成
            <code>frontend/dist</code>，随后只需启动 Flask：它会托管该目录的静态文件，
            并对非 <code>/api</code> 路径回退到 <code>index.html</code> 以支持前端路由。
            也可用 <code>start.sh</code> / <code>start.bat</code> 一键完成。
          </p>
        </div>
        <div class="deploy__item">
          <span class="deploy__step">跨域</span>
          <p>
            前后端分别部署在不同端口时，把前端地址加入 <code>APP_CORS_ORIGINS</code>，
            接口会返回 <code>Access-Control-Allow-Credentials</code> 以携带 Cookie。
          </p>
        </div>
      </div>
    </PanelCard>

    <PanelCard title="环境变量" flush>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>变量</th>
              <th>默认值</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in envVars" :key="item.name">
              <td class="strong"><code>{{ item.name }}</code></td>
              <td class="num">{{ item.value }}</td>
              <td>{{ item.note }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </PanelCard>
  </div>
</template>

<style scoped>
.settings {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.settings__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-3);
  align-items: start;
}

.facts {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.facts__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--sp-4);
  font-size: var(--fs-sm);
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--c-border-soft);
}

.facts__row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.facts__row dt {
  color: var(--c-text-mute);
  flex: none;
}

.facts__row dd {
  margin: 0;
  color: var(--c-text);
  font-weight: 600;
  text-align: right;
}

.settings__action {
  margin-top: var(--sp-4);
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border-soft);
}

.settings__note {
  margin-top: var(--sp-4);
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
}

.kpi__value--warn {
  color: var(--c-warn);
}

.guarantees {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-4) var(--sp-5);
}

.guarantees__item {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
}

.guarantees__icon {
  margin-top: 2px;
  color: var(--c-primary);
}

.guarantees__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.guarantees__title {
  font-size: var(--fs-sm);
  color: var(--c-text);
}

.guarantees__desc {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
  line-height: 1.65;
}

.deploy {
  display: flex;
  flex-direction: column;
}

.deploy__item {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-3);
  border-bottom: 1px solid var(--c-border-soft);
}

.deploy__item:last-child {
  border-bottom: none;
}

.deploy__step {
  flex: none;
  min-width: 44px;
  height: 22px;
  padding: 0 8px;
  border-radius: var(--radius-sm);
  background: var(--c-primary-soft);
  color: var(--c-primary-deep);
  font-size: var(--fs-xs);
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.deploy__item p {
  font-size: var(--fs-sm);
  color: var(--c-text-sub);
  line-height: 1.75;
}

code {
  font-family: var(--font-num);
  font-size: 12px;
  background: var(--c-surface-alt);
  border: 1px solid var(--c-border-soft);
  border-radius: var(--radius-sm);
  padding: 1px 5px;
  color: var(--c-primary-deep);
}

@media (max-width: 900px) {
  .settings__grid,
  .guarantees {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>