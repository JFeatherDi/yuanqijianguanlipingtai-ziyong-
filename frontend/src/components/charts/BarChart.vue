<script setup>
/**
 * 分组柱状图（纯 SVG，无第三方图表库）。
 *
 * 为什么手写：颜色令牌必须与设计稿逐像素一致，且内网部署不能依赖 CDN。
 * 自适应：ResizeObserver 监听容器宽度，按实际像素重算布局，文字不会被拉伸。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { formatNumber, formatShortDate } from '@/utils/format'

const props = defineProps({
  data: { type: Array, default: () => [] }, // [{ date, inbound, outbound }]
  keys: { type: Array, default: () => [] }, // [{ key, label, color }]
  height: { type: Number, default: 216 },
  ariaLabel: { type: String, default: '出入库趋势图' },
})

const PAD = { top: 14, right: 12, bottom: 28, left: 46 }
const TICKS = 5

const host = ref(null)
const width = ref(640)
const hovered = ref(-1)
let observer = null

onMounted(() => {
  if (!host.value) return
  observer = new ResizeObserver(([entry]) => {
    width.value = Math.max(entry.contentRect.width || 0, 260)
  })
  observer.observe(host.value)
  width.value = Math.max(host.value.clientWidth || 0, 260)
})

onBeforeUnmount(() => observer?.disconnect())

const plotWidth = computed(() => Math.max(width.value - PAD.left - PAD.right, 10))
const plotHeight = computed(() => Math.max(props.height - PAD.top - PAD.bottom, 10))
const baseline = computed(() => PAD.top + plotHeight.value)

/** 把峰值向上取整到「好看」的刻度，避免坐标轴出现 237 这种数字。 */
const maxValue = computed(() => {
  const peak = Math.max(
    0,
    ...props.data.flatMap((row) => props.keys.map((key) => Number(row[key.key]) || 0)),
  )
  if (peak <= 0) return 10
  const magnitude = 10 ** Math.floor(Math.log10(peak))
  const normalized = peak / magnitude
  const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10
  return step * magnitude
})

const ticks = computed(() =>
  Array.from({ length: TICKS + 1 }, (_, index) => (maxValue.value / TICKS) * index),
)

const bandWidth = computed(() => plotWidth.value / Math.max(props.data.length, 1))
const groupWidth = computed(() => Math.min(bandWidth.value * 0.58, 44))
const barWidth = computed(() => groupWidth.value / Math.max(props.keys.length, 1))

/** X 轴标签按可用宽度抽稀，最多显示约 8 个。 */
const labelStep = computed(() => {
  const capacity = Math.max(Math.floor(plotWidth.value / 58), 1)
  return Math.max(Math.ceil(props.data.length / capacity), 1)
})

const scaleY = (value) => baseline.value - ((Number(value) || 0) / maxValue.value) * plotHeight.value

function barRect(rowIndex, keyIndex, key) {
  const bandCenter = bandWidth.value * rowIndex + bandWidth.value / 2
  const x = bandCenter - groupWidth.value / 2 + barWidth.value * keyIndex
  const value = Number(props.data[rowIndex][key.key]) || 0
  const y = scaleY(value)
  return { x, y, width: Math.max(barWidth.value - 3, 2), height: Math.max(baseline.value - y, 0) }
}

const tooltip = computed(() => {
  if (hovered.value < 0) return null
  const row = props.data[hovered.value]
  if (!row) return null
  const bandCenter = bandWidth.value * hovered.value + bandWidth.value / 2
  return {
    row,
    left: PAD.left + bandCenter,
    entries: props.keys.map((key) => ({
      label: key.label,
      color: key.color,
      value: Number(row[key.key]) || 0,
    })),
  }
})
</script>

<template>
  <figure class="chart">
    <div ref="host" class="chart__canvas">
      <svg
        :width="width"
        :height="height"
        :viewBox="`0 0 ${width} ${height}`"
        role="img"
        :aria-label="ariaLabel"
      >
        <!-- 网格线与 Y 轴刻度 -->
        <g class="chart__grid">
          <template v-for="tick in ticks" :key="tick">
            <line :x1="PAD.left" :x2="width - PAD.right" :y1="scaleY(tick)" :y2="scaleY(tick)" />
            <text :x="PAD.left - 8" :y="scaleY(tick) + 3.5" text-anchor="end">{{ formatNumber(tick) }}</text>
          </template>
        </g>

        <!-- 柱体 -->
        <g>
          <template v-for="(row, rowIndex) in data" :key="row.date ?? rowIndex">
            <rect
              v-for="(key, keyIndex) in keys"
              :key="key.key"
              v-bind="barRect(rowIndex, keyIndex, key)"
              rx="2"
              :fill="key.color"
              :opacity="hovered === -1 || hovered === rowIndex ? 1 : 0.45"
              class="chart__bar"
            />
          </template>
        </g>

        <!-- X 轴标签 -->
        <g class="chart__axis">
          <template v-for="(row, index) in data" :key="`x-${row.date ?? index}`">
            <text
              v-if="index % labelStep === 0"
              :x="PAD.left + bandWidth * index + bandWidth / 2"
              :y="baseline + 17"
              text-anchor="middle"
            >
              {{ formatShortDate(row.date) }}
            </text>
          </template>
        </g>

        <!-- 悬停热区：整条 band，命中面积更大 -->
        <g>
          <rect
            v-for="(row, index) in data"
            :key="`hit-${row.date ?? index}`"
            :x="PAD.left + bandWidth * index"
            :y="PAD.top"
            :width="bandWidth"
            :height="plotHeight"
            fill="transparent"
            @mouseenter="hovered = index"
            @mouseleave="hovered = -1"
          />
        </g>
      </svg>

      <div
        v-if="tooltip"
        class="chart__tip"
        :style="{ left: `${tooltip.left}px` }"
        role="presentation"
      >
        <p class="chart__tip-title">{{ tooltip.row.date }}</p>
        <p v-for="entry in tooltip.entries" :key="entry.label" class="chart__tip-row">
          <span class="chart__tip-dot" :style="{ background: entry.color }" />
          <span class="chart__tip-label">{{ entry.label }}</span>
          <span class="chart__tip-value num">{{ formatNumber(entry.value) }}</span>
        </p>
      </div>

      <p v-if="!data.length" class="chart__empty">暂无出入库数据</p>
    </div>

    <figcaption class="chart__legend">
      <span v-for="key in keys" :key="key.key" class="chart__legend-item">
        <span class="chart__legend-dot" :style="{ background: key.color }" />
        {{ key.label }}
      </span>
    </figcaption>
  </figure>
</template>

<style scoped>
.chart {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.chart__canvas {
  position: relative;
  width: 100%;
}

.chart__bar {
  transition: opacity var(--dur) var(--ease-out);
}

.chart__grid line {
  stroke: var(--c-border-soft);
  stroke-width: 1;
}

.chart__grid text {
  font-size: 11px;
  font-family: var(--font-num);
  fill: var(--c-text-mute);
}

.chart__axis text {
  font-size: 11px;
  font-family: var(--font-num);
  fill: var(--c-text-mute);
}

.chart__tip {
  position: absolute;
  top: 4px;
  transform: translateX(-50%);
  min-width: 132px;
  padding: 8px 10px;
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-2);
  pointer-events: none;
  z-index: var(--z-dropdown);
}

.chart__tip-title {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
  margin-bottom: 4px;
}

.chart__tip-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-xs);
  line-height: 1.7;
}

.chart__tip-dot {
  width: 7px;
  height: 7px;
  border-radius: 2px;
  flex: none;
}

.chart__tip-label {
  color: var(--c-text-sub);
}

.chart__tip-value {
  margin-left: auto;
  font-weight: 600;
  color: var(--c-text);
}

.chart__empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--fs-sm);
  color: var(--c-text-mute);
}

.chart__legend {
  display: flex;
  gap: var(--sp-4);
  justify-content: center;
  font-size: var(--fs-xs);
  color: var(--c-text-sub);
}

.chart__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.chart__legend-dot {
  width: 9px;
  height: 9px;
  border-radius: 2px;
}
</style>