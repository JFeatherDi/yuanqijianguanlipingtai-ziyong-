import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { componentApi } from '@/api/endpoints'
import { stockStatus } from '@/domain/inventory'

/** 元器件主数据：一次加载全量，之后的筛选、统计、建议项都在本地派生。 */
export const useInventoryStore = defineStore('inventory', () => {
  const items = ref([])
  const loading = ref(false)
  const loaded = ref(false)
  const error = ref('')

  const keyword = ref('')
  const category = ref('')
  const status = ref('') // '' | 'low' | 'ok'

  const total = computed(() => items.value.length)

  const totalStock = computed(() =>
    items.value.reduce((sum, item) => sum + (Number(item.stock) || 0), 0),
  )

  const lowItems = computed(() => {
    const flagged = items.value.filter((item) => ['low', 'empty'].includes(stockStatus(item)))
    return flagged.sort((a, b) => Number(a.stock) - Number(b.stock))
  })

  const lowCount = computed(() => lowItems.value.length)

  const visible = computed(() => {
    const text = keyword.value.trim().toLowerCase()
    return items.value.filter((item) => {
      if (category.value && (item.category || '') !== category.value) return false
      if (status.value === 'low' && !['low', 'empty'].includes(stockStatus(item))) return false
      if (status.value === 'ok' && stockStatus(item) !== 'ok') return false
      if (!text) return true
      return [item.name, item.category, item.spec, item.location, item.remark]
        .filter(Boolean)
        .some((field) => String(field).toLowerCase().includes(text))
    })
  })

  /** 输入建议：从已加载数据派生，无需额外请求。 */
  const options = computed(() => {
    const collect = (key) =>
      [...new Set(items.value.map((item) => (item[key] || '').trim()).filter(Boolean))].sort()
    return {
      categories: collect('category'),
      locations: collect('location'),
      units: collect('unit'),
    }
  })

  function byId(id) {
    return items.value.find((item) => item.id === Number(id)) ?? null
  }

  async function load({ silent = false } = {}) {
    if (!silent) loading.value = true
    error.value = ''
    try {
      const res = await componentApi.list()
      items.value = res.data ?? []
      loaded.value = true
    } catch (err) {
      error.value = err.message
      throw err
    } finally {
      loading.value = false
    }
  }

  async function create(payload) {
    const res = await componentApi.create(payload)
    await load({ silent: true })
    return res
  }

  async function update(id, payload) {
    const res = await componentApi.update(id, payload)
    await load({ silent: true })
    return res
  }

  async function remove(id) {
    const res = await componentApi.remove(id)
    await load({ silent: true })
    return res
  }

  function resetFilters() {
    keyword.value = ''
    category.value = ''
    status.value = ''
  }

  return {
    items,
    loading,
    loaded,
    error,
    keyword,
    category,
    status,
    total,
    totalStock,
    lowItems,
    lowCount,
    visible,
    options,
    byId,
    load,
    create,
    update,
    remove,
    resetFilters,
  }
})