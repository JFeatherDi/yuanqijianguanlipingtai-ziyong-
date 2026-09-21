<script setup>
/**
 * 元器件列表：检索 / 排序 / 增删改 / 快捷出入库。
 * 筛选与排序都是本地派生 —— 数据量在实验室量级，交互因此可以做到零延迟。
 */
import { computed, ref, watch } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppModal from '@/components/ui/AppModal.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PanelCard from '@/components/ui/PanelCard.vue'
import ComponentFormModal from '@/components/ComponentFormModal.vue'
import { download } from '@/api/client'
import { recordApi } from '@/api/endpoints'
import { STATUS_META, stockStatus } from '@/domain/inventory'
import { useInventoryStore } from '@/stores/inventory'
import { useRefreshSignal } from '@/composables/useRefresh'
import { useToastStore } from '@/stores/toast'
import { display, formatQuantity } from '@/utils/format'

const inventory = useInventoryStore()
const toast = useToastStore()
const refreshSignal = useRefreshSignal()

const formOpen = ref(false)
const editing = ref(null)
const pendingDelete = ref(null)
const deleting = ref(false)
const sort = ref({ key: 'name', dir: 'asc' })

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'low', label: '仅看预警' },
  { value: 'ok', label: '库存正常' },
]

const rows = computed(() => {
  const list = [...inventory.visible]
  const factor = sort.value.dir === 'asc' ? 1 : -1
  const key = sort.value.key
  return list.sort((a, b) => {
    if (key === 'stock') return ((Number(a.stock) || 0) - (Number(b.stock) || 0)) * factor
    return String(a[key] ?? '').localeCompare(String(b[key] ?? ''), 'zh-Hans-CN') * factor
  })
})

const hasFilter = computed(
  () => Boolean(inventory.keyword || inventory.category || inventory.status),
)

function toggleSort(key) {
  if (sort.value.key === key) {
    sort.value = { key, dir: sort.value.dir === 'asc' ? 'desc' : 'asc' }
  } else {
    sort.value = { key, dir: 'asc' }
  }
}

function ariaSort(key) {
  if (sort.value.key !== key) return 'none'
  return sort.value.dir === 'asc' ? 'ascending' : 'descending'
}

function openCreate() {
  pendingDelete.value = null
  editing.value = null
  formOpen.value = true
}

function openEdit(item) {
  pendingDelete.value = null
  editing.value = item
  formOpen.value = true
}

function requestDelete(item) {
  formOpen.value = false
  pendingDelete.value = item
}

async function confirmDelete() {
  if (!pendingDelete.value || deleting.value) return
  deleting.value = true
  try {
    await inventory.remove(pendingDelete.value.id)
    toast.success(`已删除「${pendingDelete.value.name}」`)
    pendingDelete.value = null
  } catch (error) {
    toast.error(error.message)
  } finally {
    deleting.value = false
  }
}

function exportCsv() {
  download(recordApi.exportPath)
  toast.info('正在导出 CSV')
}

watch(refreshSignal, () => inventory.load({ silent: true }).catch((error) => toast.error(error.message)))

function toneOf(item) {
  return STATUS_META[stockStatus(item)]?.tone ?? 'tag--ghost'
}

function labelOf(item) {
  return STATUS_META[stockStatus(item)]?.label ?? '—'
}
</script>

<template>
  <div class="list">
    <!-- 工具条 -->
    <PanelCard>
      <div class="toolbar">
        <input
          v-model="inventory.keyword"
          class="input input-search toolbar__search"
          type="search"
          placeholder="搜索名称、分类、规格、库位"
          aria-label="搜索器件"
        />

        <select v-model="inventory.category" class="select toolbar__select" aria-label="按分类筛选">
          <option value="">全部分类</option>
          <option v-for="item in inventory.options.categories" :key="item" :value="item">
            {{ item }}
          </option>
        </select>

        <select v-model="inventory.status" class="select toolbar__select" aria-label="按库存状态筛选">
          <option v-for="item in statusOptions" :key="item.value" :value="item.value">
            {{ item.label }}
          </option>
        </select>

        <AppButton
          v-if="hasFilter"
          variant="ghost"
          icon="close"
          size="sm"
          @click="inventory.resetFilters()"
        >
          清除筛选
        </AppButton>

        <span class="toolbar__count num">
          {{ rows.length }} / {{ inventory.total }} 项
        </span>

        <div class="toolbar__actions">
          <AppButton icon="download" @click="exportCsv">导出</AppButton>
          <RouterLink :to="{ name: 'data' }">
            <AppButton icon="upload">批量导入</AppButton>
          </RouterLink>
          <AppButton variant="primary" icon="plus" @click="openCreate">新增器件</AppButton>
        </div>
      </div>
    </PanelCard>

    <!-- 列表 -->
    <PanelCard title="元器件清单" flush>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th :aria-sort="ariaSort('category')">
                <button type="button" class="th-sort" @click="toggleSort('category')">
                  分类
                </button>
              </th>
              <th :aria-sort="ariaSort('name')">
                <button type="button" class="th-sort" @click="toggleSort('name')">
                  名称
                </button>
              </th>
              <th>规格 / 型号</th>
              <th>单位</th>
              <th>库位</th>
              <th class="right" :aria-sort="ariaSort('stock')">
                <button type="button" class="th-sort" @click="toggleSort('stock')">
                  库存
                </button>
              </th>
              <th class="right">预警值</th>
              <th>备注</th>
              <th class="right">操作</th>
            </tr>
          </thead>

          <!-- 加载骨架 -->
          <tbody v-if="inventory.loading && !inventory.loaded">
            <tr v-for="index in 6" :key="index">
              <td v-for="cell in 9" :key="cell"><span class="skeleton skeleton-row" /></td>
            </tr>
          </tbody>

          <tbody v-else-if="rows.length">
            <tr v-for="item in rows" :key="item.id">
              <td>
                <span v-if="item.category" class="tag tag--blue">{{ item.category }}</span>
                <span v-else class="muted">未分类</span>
              </td>
              <td class="strong">{{ item.name }}</td>
              <td>{{ display(item.spec) }}</td>
              <td>{{ item.unit || '个' }}</td>
              <td>{{ display(item.location) }}</td>
              <td class="right">
                <span class="cell-stock">
                  <span class="tag" :class="toneOf(item)">{{ labelOf(item) }}</span>
                  <b class="num cell-stock__value">{{ formatQuantity(item.stock) }}</b>
                </span>
              </td>
              <td class="right num">{{ formatQuantity(item.threshold) }}</td>
              <td class="truncate cell-remark" :title="item.remark || ''">
                {{ display(item.remark) }}
              </td>
              <td>
                <div class="data-table__actions">
                  <RouterLink :to="{ name: 'stock-in', query: { cid: item.id } }">
                    <AppButton size="sm" icon-only icon="arrow-down" variant="ghost" aria-label="入库" />
                  </RouterLink>
                  <RouterLink :to="{ name: 'stock-out', query: { cid: item.id } }">
                    <AppButton size="sm" icon-only icon="arrow-up" variant="ghost" aria-label="出库" />
                  </RouterLink>
                  <AppButton
                    size="sm"
                    icon-only
                    icon="edit"
                    variant="ghost"
                    aria-label="编辑"
                    @click="openEdit(item)"
                  />
                  <AppButton
                    size="sm"
                    icon-only
                    icon="trash"
                    variant="ghost"
                    aria-label="删除"
                    @click="requestDelete(item)"
                  />
                </div>
              </td>
            </tr>
          </tbody>

          <tbody v-else>
            <tr>
              <td colspan="9">
                <EmptyState
                  :icon="hasFilter ? 'search' : 'inbox'"
                  :title="hasFilter ? '没有匹配的器件' : '还没有登记任何器件'"
                  :desc="
                    hasFilter
                      ? '换个关键词，或清除筛选条件后再试。'
                      : '可以手动新增，也可以在「数据管理」页用 Excel / CSV 批量导入。'
                  "
                >
                  <AppButton v-if="hasFilter" @click="inventory.resetFilters()">清除筛选</AppButton>
                  <AppButton v-else variant="primary" icon="plus" @click="openCreate">
                    新增器件
                  </AppButton>
                </EmptyState>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </PanelCard>

    <ComponentFormModal v-model="formOpen" :component="editing" />

    <!-- 删除确认 -->
    <AppModal
      :model-value="Boolean(pendingDelete)"
      title="删除器件"
      width="420px"
      @update:model-value="pendingDelete = null"
    >
      <p class="confirm">
        确定要删除
        <b>{{ pendingDelete?.name }}</b>
        <span v-if="pendingDelete?.spec">（{{ pendingDelete.spec }}）</span>
        吗？
      </p>
      <p class="confirm__warn">
        该器件的全部出入库流水会一并删除，此操作不可恢复。
      </p>

      <template #footer>
        <AppButton @click="pendingDelete = null">取消</AppButton>
        <AppButton variant="danger" :loading="deleting" @click="confirmDelete">确认删除</AppButton>
      </template>
    </AppModal>
  </div>
</template>

<style scoped>
.list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.toolbar__search {
  flex: 1;
  min-width: 200px;
  max-width: 320px;
}

.toolbar__select {
  width: auto;
  min-width: 120px;
}

.toolbar__count {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
  white-space: nowrap;
}

.toolbar__actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.th-sort {
  border: none;
  background: transparent;
  padding: 0;
  font: inherit;
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--c-text-mute);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}

.th-sort:hover {
  color: var(--c-primary);
}

.data-table thead th[aria-sort='ascending'] .th-sort::after {
  content: '↑';
}

.data-table thead th[aria-sort='descending'] .th-sort::after {
  content: '↓';
}

.data-table thead th[aria-sort='ascending'] .th-sort,
.data-table thead th[aria-sort='descending'] .th-sort {
  color: var(--c-primary);
}

.cell-stock {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  justify-content: flex-end;
}

.cell-stock__value {
  color: var(--c-primary-deep);
  font-weight: 700;
}

.cell-remark {
  max-width: 180px;
}

.skeleton-row {
  display: block;
  height: 14px;
  width: 70%;
}

.confirm {
  font-size: var(--fs-md);
  color: var(--c-text);
}

.confirm b {
  color: var(--c-danger);
}

.confirm__warn {
  margin-top: var(--sp-2);
  font-size: var(--fs-sm);
  color: var(--c-text-mute);
}

@media (max-width: 900px) {
  .toolbar__actions {
    margin-left: 0;
    width: 100%;
  }
}
</style>