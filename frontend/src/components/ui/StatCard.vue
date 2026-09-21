<script setup>
/**
 * 指标卡：复刻参考图中「订单 / 工单 / 任务 / 产量」的蓝色标题条卡片。
 * 结构 = 蓝色标题条 + 浅蓝主体（大数值 + 若干附属指标）。
 */
import { computed } from 'vue'
import AppIcon from './AppIcon.vue'
import { formatQuantity } from '@/utils/format'

const props = defineProps({
  title: { type: String, required: true },
  icon: { type: String, default: '' },
  value: { type: [String, Number], default: null },
  caption: { type: String, default: '' },
  metrics: { type: Array, default: () => [] }, // [{ label, value, tone?: 'warn'|'danger'|'ok' }]
  loading: { type: Boolean, default: false },
})

const TONE_CLASS = {
  warn: 'sub-metric__value--warn',
  danger: 'sub-metric__value--danger',
  ok: 'sub-metric__value--ok',
}

/**
 * 数值可能是 12 / "1234.5" / "75.0%" / "第 3 名"。
 * 只有能当成纯数字解析的才做千分位格式化，否则原样展示 ——
 * 早期版本无条件调用 formatQuantity，导致 "75.0%" 被打成 "—"。
 */
const displayValue = computed(() => {
  const raw = props.value
  if (raw === null || raw === undefined || raw === '') return '—'
  const text = typeof raw === 'number' ? raw : String(raw).trim()
  return Number.isNaN(Number(text)) ? text : formatQuantity(text)
})
</script>

<template>
  <article class="band-card">
    <header class="band-card__band">
      <AppIcon v-if="icon" :name="icon" :size="14" />
      <span>{{ title }}</span>
    </header>

    <div class="band-card__body">
      <div class="band-card__main">
        <span v-if="loading" class="skeleton band-card__skeleton" />
        <span v-else class="band-card__value">{{ displayValue }}</span>
        <span v-if="caption" class="band-card__caption">{{ caption }}</span>
      </div>

      <div class="band-card__subs">
        <div v-for="metric in metrics" :key="metric.label" class="sub-metric">
          <span class="sub-metric__label">{{ metric.label }}</span>
          <span
            class="sub-metric__value"
            :class="TONE_CLASS[metric.tone]"
          >{{ metric.value }}</span>
        </div>
      </div>
    </div>
  </article>
</template>

<style scoped>
.band-card__skeleton {
  width: 64px;
  height: 26px;
  display: inline-block;
}
</style>