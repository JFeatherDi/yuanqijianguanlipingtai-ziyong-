<script setup>
/**
 * 器件流转：每笔出库形成一条独立领用链，展示历任持有人、转交次数、
 * 当前持有与完整轨迹；支持部分转交（产生分支）与归还（回补库存）。
 *
 * 跨页搜索：关键词在服务端过滤后再分页（器件名、规格、历任持有人），
 * 输入防抖 250ms，关键词变化后回到第一页，并用请求序号丢弃过期响应。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import AppModal from '@/components/ui/AppModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PanelCard from '@/components/ui/PanelCard.vue'
import { custodyApi } from '@/api/endpoints'
import { useRefreshSignal } from '@/composables/useRefresh'
import { useToastStore } from '@/stores/toast'
import { display, formatDateTime, formatQuantity } from '@/utils/format'

const PAGE_SIZE = 10
const DEBOUNCE_MS = 250

const toast = useToastStore()
const refreshSignal = useRefreshSignal()
const route = useRoute()
const router = useRouter()

const rows = ref([])
const total = ref(0)
const pages = ref(1)
const page = ref(1)
const loading = ref(false)
const keyword = ref('')
const loaded = ref(false)
/** 只看逾期：从路由查询参数初始化，便于仪表盘「逾期未还」卡片直达 */
const onlyOverdue = ref(route.query.overdue === '1')

/** 原生日期选择器下限：新约定不能落在过去 */
const todayStr = new Date().toLocaleDateString('sv-SE')

const expandedId = ref(null)
const detail = ref(null)
const detailLoading = ref(false)

let debounceTimer = null
let requestSeq = 0

const EVENT_META = {
  out: { label: '出库领用', icon: 'arrow-up', tone: 'tag--warn' },
  transfer: { label: '转交', icon: 'trend', tone: 'tag--blue' },
  return: { label: '归还入库', icon: 'arrow-down', tone: 'tag--ok' },
}

async function load({ keepPosition = false } = {}) {
  const seq = ++requestSeq
  loading.value = true
  try {
    const res = await custodyApi.list({
      q: keyword.value.trim(),
      page: page.value,
      overdue: onlyOverdue.value ? 1 : undefined,
    })
    // 只接受最新一次请求的结果，避免旧响应覆盖新搜索
    if (seq !== requestSeq) return
    rows.value = res.data ?? []
    total.value = res.total ?? 0
    pages.value = res.pages ?? 1
    loaded.value = true
    if (!keepPosition && expandedId.value && !rows.value.some((row) => row.id === expandedId.value)) {
      expandedId.value = null
      detail.value = null
    }
  } catch (error) {
    if (seq === requestSeq) toast.error(error.message)
  } finally {
    if (seq === requestSeq) loading.value = false
  }
}

watch(keyword, () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    page.value = 1
    load()
  }, DEBOUNCE_MS)
})

watch(onlyOverdue, () => {
  page.value = 1
  load()
  // 同步进路由：刷新、转发链接后筛选状态不丢
  router.replace({ query: { ...route.query, overdue: onlyOverdue.value ? '1' : undefined } })
})

watch(refreshSignal, () => load({ keepPosition: true }))

function goPrev() {
  if (page.value <= 1 || loading.value) return
  page.value -= 1
  load()
}

function goNext() {
  if (page.value >= pages.value || loading.value) return
  page.value += 1
  load()
}

const hasFilter = computed(() => keyword.value.trim() !== '' || onlyOverdue.value)

async function toggleDetail(row) {
  if (expandedId.value === row.id) {
    expandedId.value = null
    detail.value = null
    return
  }
  expandedId.value = row.id
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await custodyApi.records(row.id)
  } catch (error) {
    toast.error(error.message)
    expandedId.value = null
  } finally {
    detailLoading.value = false
  }
}

/* ---------- 转交 / 归还 ---------- */
const transferOpen = ref(false)
const returnOpen = ref(false)
const positions = ref([])
const positionsLoading = ref(false)
const positionId = ref(null)
const holder = ref('')
const quantity = ref('')
const remark = ref('')
/** 转交的预计归还日期：选择持有点后自动带入原约定，可改可清空 */
const dueDate = ref('')
const submitting = ref(false)

const selectedPosition = computed(() =>
  positions.value.find((item) => item.id === Number(positionId.value)) ?? null,
)

watch(positionId, () => {
  dueDate.value = selectedPosition.value?.due_date || ''
})

async function openDialog(kind) {
  transferOpen.value = kind === 'transfer'
  returnOpen.value = kind === 'return'
  positionId.value = null
  holder.value = ''
  quantity.value = ''
  remark.value = ''
  positionsLoading.value = true
  try {
    const res = await custodyApi.positions({})
    positions.value = res.data ?? []
  } catch (error) {
    toast.error(error.message)
    transferOpen.value = false
    returnOpen.value = false
  } finally {
    positionsLoading.value = false
  }
}

const quantityValid = computed(() => {
  const num = Number(quantity.value)
  if (!Number.isFinite(num) || num <= 0) return false
  if (!selectedPosition.value) return true
  return num <= Number(selectedPosition.value.qty) + 1e-9
})

const transferValid = computed(
  () => Boolean(selectedPosition.value) && holder.value.trim().length > 0 && quantityValid.value,
)
const returnValid = computed(() => Boolean(selectedPosition.value) && quantityValid.value)

async function submitTransfer() {
  if (!transferValid.value || submitting.value) return
  submitting.value = true
  try {
    const res = await custodyApi.transfer({
      position_id: Number(positionId.value),
      holder: holder.value.trim(),
      qty: Number(quantity.value),
      remark: remark.value.trim(),
      due_date: dueDate.value || undefined,
    })
    toast.success(res.msg || '转交已登记')
    transferOpen.value = false
    await load({ keepPosition: true })
  } catch (error) {
    toast.error(error.message)
  } finally {
    submitting.value = false
  }
}

async function submitReturn() {
  if (!returnValid.value || submitting.value) return
  submitting.value = true
  try {
    const res = await custodyApi.giveBack({
      position_id: Number(positionId.value),
      qty: Number(quantity.value),
      remark: remark.value.trim(),
    })
    toast.success(`${res.msg || '归还已登记'}，当前库存 ${formatQuantity(res.stock)}`)
    returnOpen.value = false
    await load({ keepPosition: true })
  } catch (error) {
    toast.error(error.message)
  } finally {
    submitting.value = false
  }
}

function holderLabel(event) {
  if (event.kind === 'return') return `归还 ${formatQuantity(event.qty)} 入库`
  return `持有 ${formatQuantity(event.qty)}`
}

onMounted(() => load())
</script>

<template>
  <PanelCard title="器件流转" flush>
    <template #tools>
      <input
        v-model="keyword"
        class="input input-search custody__search"
        type="search"
        placeholder="搜索器件、规格或历任持有人"
        aria-label="搜索流转记录"
      />
      <button
        type="button"
        class="custody__chip"
        :class="{ 'is-active': onlyOverdue }"
        :aria-pressed="onlyOverdue"
        @click="onlyOverdue = !onlyOverdue"
      >
        <AppIcon name="clock" :size="13" />
        只看逾期
      </button>
      <AppButton size="sm" variant="ghost" icon="arrow-down" @click="openDialog('return')">
        归还
      </AppButton>
      <AppButton size="sm" variant="ghost" icon="arrow-up" @click="openDialog('transfer')">
        转交
      </AppButton>
      <AppButton size="sm" variant="ghost" icon="refresh" @click="load({ keepPosition: true })">
        刷新
      </AppButton>
    </template>

    <div class="custody">
      <p class="custody__intro">
        每次出库领用形成一条独立流转链，申请人即初始持有人；转交可部分分出并保留分支路径，归还回补仓库库存。
      </p>

      <!-- 链条列表 -->
      <div v-if="rows.length" class="custody__list">
        <article v-for="row in rows" :key="row.id" class="chain" :class="{ 'is-open': expandedId === row.id }">
          <button type="button" class="chain__head" @click="toggleDetail(row)">
            <div class="chain__main">
              <div class="chain__title">
                <span class="strong">{{ row.name || '已删除' }}</span>
                <span v-if="row.spec" class="muted">{{ row.spec }}</span>
                <span class="tag tag--ghost">链 #{{ row.id }}</span>
                <span v-if="row.overdue_days" class="tag tag--danger">
                  已逾期 {{ row.overdue_days }} 天
                </span>
              </div>
              <div class="chain__meta">
                <span><b class="num">{{ formatQuantity(row.initial_qty) }}</b> {{ row.unit || '个' }} · 申请人 {{ display(row.applicant) }}</span>
                <span>当前在外 <b class="num">{{ formatQuantity(row.holding_total) }}</b></span>
                <span>已归还 <b class="num">{{ formatQuantity(row.returned_total) }}</b></span>
                <span>转交 <b class="num">{{ row.transfer_count }}</b> 次</span>
                <span v-if="row.due_date" :class="{ 'chain__due-overdue': row.overdue_days }">
                  预计归还 <b class="num">{{ row.due_date }}</b>
                </span>
              </div>
              <div class="chain__holders">
                <AppIcon name="user" :size="13" />
                <span class="chain__holder" v-for="(holder, index) in row.holdings" :key="holder.holder">
                  {{ holder.holder }}<i class="num"> {{ formatQuantity(holder.qty) }}</i><template v-if="index < row.holdings.length - 1">、</template>
                </span>
                <span v-if="!row.holdings.length" class="muted">已全部归还</span>
              </div>
            </div>
            <div class="chain__side">
              <span class="num chain__time">{{ formatDateTime(row.last_activity || row.created_at) }}</span>
              <AppIcon :name="expandedId === row.id ? 'chevronDown' : 'chevronRight'" :size="16" />
            </div>
          </button>

          <div v-if="expandedId === row.id" class="chain__detail">
            <div v-if="detailLoading" class="chain__loading">加载轨迹中…</div>
            <template v-else-if="detail">
              <ol class="trail">
                <li v-for="event in detail.events" :key="event.id" class="trail__item">
                  <span class="tag" :class="EVENT_META[event.kind]?.tone || 'tag--ghost'">
                    {{ EVENT_META[event.kind]?.label || event.kind }}
                  </span>
                  <span class="trail__body">
                    <b>{{ display(event.holder) }}</b>
                    <span class="muted">{{ holderLabel(event) }}</span>
                    <span v-if="event.remark" class="muted">· {{ event.remark }}</span>
                  </span>
                  <span class="num trail__time">{{ formatDateTime(event.created_at) }}</span>
                </li>
              </ol>
            </template>
          </div>
        </article>
      </div>

      <div v-else-if="loaded" class="custody__empty">
        <EmptyState
          :icon="hasFilter ? 'search' : 'inbox'"
          :title="hasFilter ? '没有匹配的流转记录' : '还没有流转记录'"
          :desc="hasFilter ? '换个关键词试试：支持器件名、规格与所有历任持有人。' : '完成一次出库领用后，这里会出现对应的流转链。'"
        />
      </div>

      <div v-else class="custody__empty">
        <EmptyState icon="clock" title="正在加载…" desc="正在获取流转记录。" />
      </div>
    </div>

    <template #footer>
      <span class="custody__total">
        共 <b class="num">{{ total }}</b> 条流转链
        <span v-if="total">· 第 <b class="num">{{ page }}</b> / {{ pages }} 页</span>
        <span v-if="keyword">· 已按关键词过滤</span>
        <span v-if="onlyOverdue" class="custody__overdue-note">· 只显示逾期未还</span>
      </span>
      <div class="spacer" />
      <AppButton size="sm" icon="chevronLeft" :disabled="page <= 1 || loading" @click="goPrev">
        上一页
      </AppButton>
      <AppButton size="sm" :disabled="page >= pages || loading" @click="goNext">下一页</AppButton>
    </template>
  </PanelCard>

  <!-- 转交 -->
  <AppModal :model-value="transferOpen" title="登记转交" @update:model-value="transferOpen = $event">
    <div class="form">
      <div class="field">
        <label class="field__label" for="transfer-position">转出持有点</label>
        <select id="transfer-position" v-model.number="positionId" class="select" :disabled="positionsLoading">
          <option :value="null" disabled>{{ positionsLoading ? '正在加载…' : '选择器件与当前持有人' }}</option>
          <option v-for="item in positions" :key="item.id" :value="item.id">
            {{ item.name }}{{ item.spec ? `（${item.spec}）` : '' }} — {{ item.holder }} 持有 {{ formatQuantity(item.qty) }}
          </option>
        </select>
      </div>
      <div class="field">
        <label class="field__label" for="transfer-holder">接收人 <span class="req">*</span></label>
        <input id="transfer-holder" v-model="holder" class="input" maxlength="120" placeholder="例如：李四 / 课题组名" />
      </div>
      <div class="field">
        <label class="field__label" for="transfer-qty">转交数量 <span class="req">*</span></label>
        <input
          id="transfer-qty"
          v-model="quantity"
          class="input"
          type="number"
          min="0"
          step="0.000001"
          :placeholder="selectedPosition ? `当前持有 ${formatQuantity(selectedPosition.qty)}` : '先选择持有点'"
          :disabled="!selectedPosition"
        />
        <p v-if="selectedPosition && !quantityValid" class="field__error">
          数量必须大于 0 且不超过当前持有量（{{ formatQuantity(selectedPosition.qty) }}）
        </p>
      </div>
      <div class="field">
        <label class="field__label" for="transfer-remark">备注</label>
        <input id="transfer-remark" v-model="remark" class="input" placeholder="选填" />
      </div>

      <div class="field">
        <label class="field__label" for="transfer-due">预计归还日期</label>
        <input id="transfer-due" v-model="dueDate" class="input" type="date" :min="todayStr" />
        <p class="form__note">
          {{ selectedPosition?.due_date ? `留空将沿用原约定 ${selectedPosition.due_date}，也可改约新日期` : '选填；原持有点未约定日期，留空即可' }}
        </p>
      </div>
      <p class="form__note">支持部分转交：只转一部分时，原持有人会保留剩余数量，两条路径都完整留痕。</p>
    </div>
    <template #footer>
      <AppButton variant="ghost" @click="transferOpen = false">取消</AppButton>
      <AppButton variant="primary" :loading="submitting" :disabled="!transferValid" @click="submitTransfer">
        确认转交
      </AppButton>
    </template>
  </AppModal>

  <!-- 归还 -->
  <AppModal :model-value="returnOpen" title="登记归还" @update:model-value="returnOpen = $event">
    <div class="form">
      <div class="field">
        <label class="field__label" for="return-position">归还持有点</label>
        <select id="return-position" v-model.number="positionId" class="select" :disabled="positionsLoading">
          <option :value="null" disabled>{{ positionsLoading ? '正在加载…' : '选择器件与当前持有人' }}</option>
          <option v-for="item in positions" :key="item.id" :value="item.id">
            {{ item.name }}{{ item.spec ? `（${item.spec}）` : '' }} — {{ item.holder }} 持有 {{ formatQuantity(item.qty) }}
          </option>
        </select>
      </div>
      <div class="field">
        <label class="field__label" for="return-qty">归还数量 <span class="req">*</span></label>
        <input
          id="return-qty"
          v-model="quantity"
          class="input"
          type="number"
          min="0"
          step="0.000001"
          :placeholder="selectedPosition ? `当前持有 ${formatQuantity(selectedPosition.qty)}` : '先选择持有点'"
          :disabled="!selectedPosition"
        />
        <p v-if="selectedPosition && !quantityValid" class="field__error">
          数量必须大于 0 且不超过当前持有量（{{ formatQuantity(selectedPosition.qty) }}）
        </p>
      </div>
      <div class="field">
        <label class="field__label" for="return-remark">备注</label>
        <input id="return-remark" v-model="remark" class="input" placeholder="选填" />
      </div>
      <p class="form__note">归还数量会立即回补仓库库存，并写入一条「归还」类型的流水。</p>
    </div>
    <template #footer>
      <AppButton variant="ghost" @click="returnOpen = false">取消</AppButton>
      <AppButton variant="primary" :loading="submitting" :disabled="!returnValid" @click="submitReturn">
        确认归还
      </AppButton>
    </template>
  </AppModal>
</template>

<style scoped>
.custody {
  display: flex;
  flex-direction: column;
}

.custody__intro {
  margin: 0;
  padding: var(--sp-3) var(--sp-3) 0;
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
}

.custody__search {
  width: 210px;
}

.custody__list {
  display: flex;
  flex-direction: column;
  padding: var(--sp-3);
  gap: var(--sp-2);
}

.chain {
  border: 1px solid var(--c-border);
  border-radius: var(--radius);
  background: var(--c-surface);
  transition: border-color var(--dur) var(--ease-out);
}

.chain.is-open {
  border-color: var(--c-primary);
}

.chain__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  width: 100%;
  padding: var(--sp-3);
  background: none;
  border: none;
  cursor: pointer;
  text-align: left;
  font: inherit;
  color: inherit;
}

.chain__main {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  min-width: 0;
}

.chain__title {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.chain__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1) var(--sp-3);
  font-size: var(--fs-xs);
  color: var(--c-text-sub);
}

.chain__meta b {
  color: var(--c-primary-deep);
}

.chain__holders {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: var(--sp-1);
  font-size: var(--fs-xs);
  color: var(--c-text-sub);
}

.chain__holder i {
  font-style: normal;
  color: var(--c-text-mute);
}

.chain__side {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex: none;
  color: var(--c-text-mute);
}

.chain__time {
  font-size: var(--fs-xs);
}

.chain__detail {
  border-top: 1px dashed var(--c-border);
  padding: var(--sp-3);
}

.chain__loading {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
}

.trail {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.trail__item {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
  font-size: var(--fs-xs);
}

.trail__body {
  display: flex;
  align-items: baseline;
  gap: var(--sp-1);
  min-width: 0;
  flex: 1;
  flex-wrap: wrap;
}

.trail__time {
  color: var(--c-text-mute);
  flex: none;
}

.custody__empty {
  padding: var(--sp-4);
}

.custody__total {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
}

.custody__total b {
  color: var(--c-text);
}

/* 逾期相关：筛选开关、页脚提示、过期日期强调 */
.custody__chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 11px;
  border: 1px solid var(--c-border);
  border-radius: 999px;
  background: var(--c-surface);
  color: var(--c-text-sub);
  font-size: var(--fs-xs);
  cursor: pointer;
  transition: all var(--dur) var(--ease-out);
}

.custody__chip:hover {
  border-color: var(--c-danger);
  color: var(--c-danger);
}

.custody__chip.is-active {
  border-color: var(--c-danger);
  background: var(--c-danger-soft);
  color: var(--c-danger);
}

.custody__overdue-note,
.chain__due-overdue,
.chain__due-overdue b {
  color: var(--c-danger);
}

.form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.form__note {
  margin: 0;
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
}

@media (max-width: 720px) {
  .custody__search {
    width: 100%;
  }
}
</style>
