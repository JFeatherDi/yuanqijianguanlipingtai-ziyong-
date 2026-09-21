<script setup>
/** 进度条：图中「生产管控」的横条，右侧固定对齐的百分比。 */
defineProps({
  value: { type: Number, default: 0 },
  max: { type: Number, default: 100 },
  ratio: { type: Number, default: null }, // 0~1，给定则直接使用
})

function ratioOf(value, max, ratio) {
  if (typeof ratio === 'number') return Math.min(Math.max(ratio, 0), 1)
  if (!max) return 0
  return Math.min(Math.max(value / max, 0), 1)
}
</script>

<template>
  <div class="progress">
    <div
      class="progress__track"
      role="progressbar"
      :aria-valuenow="Math.round(ratioOf(value, max, ratio) * 100)"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div class="progress__fill" :style="{ width: `${ratioOf(value, max, ratio) * 100}%` }" />
    </div>
    <span class="progress__value">
      <slot>{{ value }}</slot>
    </span>
  </div>
</template>