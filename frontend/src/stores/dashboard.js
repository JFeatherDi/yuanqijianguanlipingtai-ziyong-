import { ref } from 'vue'
import { defineStore } from 'pinia'
import { recordApi, statsApi } from '@/api/endpoints'

export const RANGE_OPTIONS = [
  { id: 'today', label: '今天', days: 1 },
  { id: 'week', label: '近 7 天', days: 7 },
  { id: 'month', label: '近 30 天', days: 30 },
]

const DEFAULT_RANGE = 'week'

/** 主页看板数据：概览指标、分类分布、出入库趋势、最近动态。 */
export const useDashboardStore = defineStore('dashboard', () => {
  const overview = ref(null)
  const categories = ref([])
  const series = ref([])
  const recent = ref([])
  const range = ref(DEFAULT_RANGE)
  const loading = ref(false)
  const flowLoading = ref(false)

  const daysOf = (id) => RANGE_OPTIONS.find((item) => item.id === id)?.days ?? 7

  async function loadFlow() {
    flowLoading.value = true
    try {
      const res = await statsApi.flow(daysOf(range.value))
      series.value = res.data ?? []
    } finally {
      flowLoading.value = false
    }
  }

  async function load(force = false) {
    if (loading.value && !force) return
    loading.value = true
    try {
      const [overviewRes, categoryRes, recentRes] = await Promise.all([
        statsApi.overview(),
        statsApi.categories(),
        recordApi.list({ limit: 8 }),
      ])
      overview.value = overviewRes.data ?? null
      categories.value = categoryRes.data ?? []
      recent.value = recentRes.data ?? []
      await loadFlow()
    } finally {
      loading.value = false
    }
  }

  async function setRange(id) {
    range.value = id
    await loadFlow()
  }

  return { overview, categories, series, recent, range, loading, flowLoading, load, loadFlow, setRange }
})