<script setup>
/**
 * 器件选择器：搜索框 + 结果列表。
 * 为什么不用原生 select：器件数量可达数百，且需要同时展示规格/库位/库存。
 */
import { computed, ref } from 'vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import { STATUS_META, stockStatus } from '@/domain/inventory'
import { formatQuantity } from '@/utils/format'

const props = defineProps({
  modelValue: { type: [Number, String, null], default: null },
  components: { type: Array, default: () => [] },
  placeholder: { type: String, default: '输入名称、分类或规格搜索' },
})

const emit = defineEmits(['update:modelValue'])

const keyword = ref('')

const results = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  const list = text
    ? props.components.filter((item) =>
        [item.name, item.category, item.spec, item.location]
          .filter(Boolean)
          .some((field) => String(field).toLowerCase().includes(text)),
      )
    : props.components
  // 上限 60 条，避免一次渲染过多行
  return list.slice(0, 60)
})

const selected = computed(
  () => props.components.find((item) => item.id === Number(props.modelValue)) ?? null,
)

function pick(item) {
  emit('update:modelValue', item.id)
}

function toneOf(item) {
  return STATUS_META[stockStatus(item)]?.tone ?? 'tag--ghost'
}

function labelOf(item) {
  return STATUS_META[stockStatus(item)]?.label ?? ''
}
</script>

<template>
  <div class="picker">
    <div class="picker__search">
      <input
        v-model="keyword"
        class="input input-search"
        type="search"
        :placeholder="placeholder"
        aria-label="搜索器件"
      />
    </div>

    <ul class="picker__list" role="listbox" aria-label="器件列表">
      <li v-for="item in results" :key="item.id">
        <button
          type="button"
          class="picker__row"
          :class="{ 'is-selected': item.id === Number(modelValue) }"
          role="option"
          :aria-selected="item.id === Number(modelValue)"
          @click="pick(item)"
        >
          <span class="picker__main">
            <span class="picker__name">{{ item.name }}</span>
            <span class="picker__meta">
              <span v-if="item.spec">{{ item.spec }}</span>
              <span v-if="item.location">· {{ item.location }}</span>
              <span v-if="!item.spec && !item.location">未填写规格/库位</span>
            </span>
          </span>
          <span class="picker__stock">
            <span class="tag" :class="toneOf(item)">{{ labelOf(item) }}</span>
            <span class="picker__qty num">{{ formatQuantity(item.stock) }}</span>
            <span class="picker__unit">{{ item.unit || '个' }}</span>
          </span>
        </button>
      </li>

      <li v-if="!results.length" class="picker__empty">
        <AppIcon name="search" :size="16" />
        {{ components.length ? '没有匹配的器件' : '暂无器件，请先到「元器件列表」新增' }}
      </li>
    </ul>

    <p v-if="selected" class="picker__current">
      已选择：<b>{{ selected.name }}</b>
      <span v-if="selected.spec">（{{ selected.spec }}）</span>
      <span class="muted">· 当前库存 {{ formatQuantity(selected.stock) }} {{ selected.unit || '个' }}</span>
    </p>
  </div>
</template>

<style scoped>
.picker {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  min-width: 0;
}

.picker__list {
  border: 1px solid var(--c-border);
  border-radius: var(--radius);
  max-height: 320px;
  overflow-y: auto;
  background: var(--c-surface);
}

.picker__row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  width: 100%;
  padding: 8px var(--sp-3);
  border: none;
  border-bottom: 1px solid var(--c-border-soft);
  border-left: 3px solid transparent;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background var(--dur) var(--ease-out);
}

.picker__row:hover {
  background: var(--c-surface-alt);
}

.picker__row.is-selected {
  background: var(--c-primary-soft);
  border-left-color: var(--c-primary);
}

.picker__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.picker__name {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.picker__meta {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.picker__stock {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: none;
}

.picker__qty {
  font-size: var(--fs-sm);
  font-weight: 700;
  color: var(--c-primary-deep);
}

.picker__unit {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
}

.picker__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: var(--sp-6) var(--sp-3);
  font-size: var(--fs-sm);
  color: var(--c-text-mute);
}

.picker__current {
  font-size: var(--fs-xs);
  color: var(--c-text-sub);
}
</style>