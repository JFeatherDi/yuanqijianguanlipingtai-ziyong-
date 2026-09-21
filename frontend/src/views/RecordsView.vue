<script setup>
/** 操作记录：服务端分页 + 类型/关键字筛选 + 导出。 */
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import PanelCard from '@/components/ui/PanelCard.vue'
import RecordTable from '@/components/RecordTable.vue'
import { download } from '@/api/client'
import { recordApi } from '@/api/endpoints'
import { useRefreshSignal } from '@/composables/useRefresh'
import { useToastStore } from '@/stores/toast'

const PAGE_SIZE = 50

const TYPE_OPTIONS = [
  { value: '', label: '全部类型' },
  { value: 'in', label: '入库' },
  { value: 'out', label: '出库' },
  { value: 'init', label: '初始化' },
  { value: 'import', label: '导入' },
]

const toast = useToastStore()
const refreshSignal = useRefreshSignal()

const rows = ref([])
const total = ref(0)
const loading = ref(false)
const keyword = ref('')
const type = ref('')
const offset = ref(0)
let debounceTimer = null

const pageCount = computed(() => Math.max(Math.ceil(total.value / PAGE_SIZE), 1))
const pageIndex = computed(() => Math.floor(offset.value / PAGE_SIZE) + 1)
const hasPrev = computed(() => offset.value > 0)
const hasNext = computed(() => offset.value + PAGE_SIZE < total.value)

async function load() {
  loading.value = true
  try {
    const res = await recordApi.list({
      q: keyword.value.trim(),
      type: type.value,
      limit: PAGE_SIZE,
      offset: offset.value,
    })
    rows.value = res.data ?? []
    total.value = res.total ?? 0
  } catch (error) {
    rows.value = []
    total.value = 0
    toast.error(error.message)
  } finally {
    loading.value = false
  }
}

// 关键字输入做防抖，避免每敲一个字就打一次接口
watch(keyword, () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    offset.value = 0
    load()
  }, 250)
})

watch(type, () => {
  offset.value = 0
  load()
})

watch(offset, load)

watch(refreshSignal, () => {
  offset.value = 0
  load()
})

onMounted(load)
onBeforeUnmount(() => clearTimeout(debounceTimer))

function goPrev() {
  offset.value = Math.max(offset.value - PAGE_SIZE, 0)
}

function goNext() {
  offset.value = Math.min(offset.value + PAGE_SIZE, Math.max(total.value - 1, 0))
}

function exportCsv() {
  download(recordApi.exportPath)
  toast.info('正在导出元器件清单 CSV')
}
</script>

<template>
  <PanelCard title="操作记录" flush>
    <template #tools>
      <input
        v-model="keyword"
        class="input input-search records__search"
        type="search"
        placeholder="搜索器件名称或规格"
        aria-label="搜索记录"
      />
      <select v-model="type" class="select records__select" aria-label="按类型筛选">
        <option v-for="item in TYPE_OPTIONS" :key="item.value" :value="item.value">
          {{ item.label }}
        </option>
      </select>
      <AppButton size="sm" icon="download" @click="exportCsv">导出清单</AppButton>
    </template>

    <RecordTable :rows="rows" :loading="loading" />

    <template #footer>
      <span class="records__total">
        共 <b class="num">{{ total }}</b> 条记录
        <span v-if="total">· 第 <b class="num">{{ pageIndex }}</b> / {{ pageCount }} 页</span>
      </span>
      <div class="spacer" />
      <AppButton size="sm" icon="chevronLeft" :disabled="!hasPrev || loading" @click="goPrev">
        上一页
      </AppButton>
      <AppButton size="sm" :disabled="!hasNext || loading" @click="goNext">
        下一页
      </AppButton>
    </template>
  </PanelCard>
</template>

<style scoped>
.records__search {
  width: 200px;
}

.records__select {
  width: auto;
  min-width: 110px;
}

.records__total {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
}

.records__total b {
  color: var(--c-text);
}

@media (max-width: 720px) {
  .records__search {
    width: 100%;
  }
}
</style>