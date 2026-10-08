<script setup>
/**
 * 系统设置：运行信息 + 管理员的普通用户账号管理。
 * 本项目没有可写的配置接口，运行信息保持只读，不伪造任何可编辑但实际不生效的开关。
 */
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PanelCard from '@/components/ui/PanelCard.vue'
import { userApi } from '@/api/endpoints'
import { useAuthStore } from '@/stores/auth'
import { useInventoryStore } from '@/stores/inventory'
import { useToastStore } from '@/stores/toast'
import { display, formatDateTime, formatQuantity } from '@/utils/format'

const auth = useAuthStore()
const inventory = useInventoryStore()
const toast = useToastStore()
const router = useRouter()

const signingOut = ref(false)

/* ---------- 普通用户管理（仅管理员可见） ---------- */
const users = ref([])
const usersLoading = ref(false)
const newUsername = ref('')
const newPassword = ref('')
const creating = ref(false)
const resetTarget = ref(null)
const resetPassword = ref('')
const resetBusy = ref(false)
const deleteTarget = ref(null)
const deleteBusy = ref(false)

async function loadUsers() {
  if (!auth.isAdmin) return
  usersLoading.value = true
  try {
    const res = await userApi.list()
    users.value = res.data ?? []
  } catch {
    // 非管理员或会话失效时静默忽略，界面本就不展示该卡片
  } finally {
    usersLoading.value = false
  }
}

async function createUser() {
  const username = newUsername.value.trim()
  if (!username || creating.value) return
  creating.value = true
  try {
    const res = await userApi.create({ username, password: newPassword.value })
    toast.success(res.msg || '用户已创建')
    newUsername.value = ''
    newPassword.value = ''
    await loadUsers()
  } catch (error) {
    toast.error(error.message)
  } finally {
    creating.value = false
  }
}

function askReset(user) {
  resetTarget.value = user
  resetPassword.value = ''
}

async function confirmReset() {
  if (!resetTarget.value || resetBusy.value) return
  resetBusy.value = true
  try {
    const res = await userApi.setPassword(resetTarget.value.id, {
      password: resetPassword.value,
    })
    toast.success(res.msg || '密码已重置')
    resetTarget.value = null
  } catch (error) {
    toast.error(error.message)
  } finally {
    resetBusy.value = false
  }
}

function askDelete(user) {
  deleteTarget.value = user
}

async function confirmDelete() {
  if (!deleteTarget.value || deleteBusy.value) return
  deleteBusy.value = true
  try {
    const res = await userApi.remove(deleteTarget.value.id)
    toast.success(res.msg || '用户已删除')
    deleteTarget.value = null
    await loadUsers()
  } catch (error) {
    toast.error(error.message)
  } finally {
    deleteBusy.value = false
  }
}

const account = computed(() => [
  { label: '当前账号', value: auth.user || '—' },
  { label: '角色', value: auth.isAdmin ? '管理员' : '普通用户' },
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
    title: '六位小数归整',
    desc: '库存与流转数量统一按六位小数校验与归整，0.3 分次转交不再出现浮点残量。',
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
    title: '生产级并发限制',
    desc: '使用 waitress 监听，最多 8 个工作线程、20 个连接，避免进程堆积。',
  },
]

const envVars = [
  { name: 'APP_PORT', value: '5000', note: '后端监听端口' },
  { name: 'APP_HOST', value: '0.0.0.0', note: '后端监听地址，0.0.0.0 表示允许局域网访问' },
  { name: 'APP_DB_PATH', value: 'backend/data.db', note: 'SQLite 数据库文件路径' },
  { name: 'APP_SECRET_KEY', value: '内置默认值', note: '会话签名密钥，正式部署务必修改' },
  { name: 'APP_USERNAME', value: 'IOTAT', note: '管理员账号（环境变量配置，不入库）' },
  { name: 'APP_PASSWORD', value: '内置默认值', note: '管理员密码，正式部署务必修改' },
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

onMounted(loadUsers)
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

    <!-- 普通用户管理：仅管理员 -->
    <PanelCard v-if="auth.isAdmin" title="普通用户" flush>
      <template #tools>
        <AppButton size="sm" variant="ghost" icon="refresh" @click="loadUsers">刷新</AppButton>
      </template>

      <div class="users__create">
        <input
          v-model="newUsername"
          class="input users__name"
          placeholder="用户名（不超过 40 字符）"
          maxlength="40"
          aria-label="新用户名"
        />
        <input
          v-model="newPassword"
          class="input users__pass"
          type="password"
          placeholder="初始密码（至少 6 位）"
          maxlength="128"
          aria-label="初始密码"
          @keyup.enter="createUser"
        />
        <AppButton variant="primary" icon="plus" :loading="creating" @click="createUser">
          创建用户
        </AppButton>
      </div>
      <p class="users__hint">
        普通用户可浏览库存并登记出入库、转交与归还；重置密码或删除账号后，该用户已登录的会话会立即失效。
      </p>

      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>创建时间</th>
              <th class="right">操作</th>
            </tr>
          </thead>
          <tbody v-if="users.length">
            <tr v-for="item in users" :key="item.id">
              <td class="strong">{{ item.username }}</td>
              <td class="num">{{ display(formatDateTime(item.created_at)) }}</td>
              <td class="right">
                <div class="data-table__actions users__actions">
                  <AppButton size="sm" icon="lock" variant="ghost" @click="askReset(item)">
                    重置密码
                  </AppButton>
                  <AppButton size="sm" icon="trash" variant="ghost" @click="askDelete(item)">
                    删除
                  </AppButton>
                </div>
              </td>
            </tr>
          </tbody>
          <tbody v-else>
            <tr>
              <td colspan="3">
                <EmptyState
                  :icon="usersLoading ? 'clock' : 'user'"
                  :title="usersLoading ? '正在加载…' : '还没有普通用户'"
                  :desc="'在上方输入用户名和初始密码，为同学或同事创建账号。'"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </PanelCard>

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

    <!-- 重置密码 -->
    <AppModal
      :model-value="Boolean(resetTarget)"
      title="重置密码"
      @update:model-value="resetTarget = null"
    >
      <template v-if="resetTarget">
        <p class="modal-text">
          为用户 <b>{{ resetTarget.username }}</b> 设置新密码，重置后该账号已登录的会话将立即失效。
        </p>
        <input
          v-model="resetPassword"
          class="input"
          type="password"
          placeholder="新密码（至少 6 位）"
          maxlength="128"
          @keyup.enter="confirmReset"
        />
      </template>
      <template #footer>
        <AppButton variant="ghost" @click="resetTarget = null">取消</AppButton>
        <AppButton
          variant="primary"
          :loading="resetBusy"
          :disabled="resetPassword.length < 6"
          @click="confirmReset"
        >
          确认重置
        </AppButton>
      </template>
    </AppModal>

    <!-- 删除用户 -->
    <AppModal
      :model-value="Boolean(deleteTarget)"
      title="删除用户"
      @update:model-value="deleteTarget = null"
    >
      <p v-if="deleteTarget" class="modal-text">
        确定删除用户 <b>{{ deleteTarget.username }}</b> 吗？
        删除后该账号将无法登录，已登录会话立即失效；其历史操作记录会保留。
      </p>
      <template #footer>
        <AppButton variant="ghost" @click="deleteTarget = null">取消</AppButton>
        <AppButton variant="danger" :loading="deleteBusy" @click="confirmDelete">确认删除</AppButton>
      </template>
    </AppModal>
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

.users__create {
  display: flex;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-3) 0;
}

.users__name {
  width: 220px;
}

.users__pass {
  width: 220px;
}

.users__hint {
  padding: var(--sp-2) var(--sp-3) var(--sp-3);
  margin: 0;
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
  border-bottom: 1px solid var(--c-border-soft);
}

.users__actions {
  justify-content: flex-end;
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

  .users__create {
    flex-direction: column;
  }

  .users__name,
  .users__pass {
    width: 100%;
  }
}
</style>
