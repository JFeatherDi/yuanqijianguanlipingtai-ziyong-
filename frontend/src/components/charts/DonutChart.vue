<script setup>
/**
 * 环形图（纯 SVG）。用 stroke-dasharray 画弧，避免手算 path 的圆弧标志位。
 * 图例同时给出数值与占比 —— 不让颜色成为唯一的区分手段。
 */
import { computed } from 'vue'
import { formatNumber, formatPercent } from '@/utils/format'

const props = defineProps({
  data: { type: Array, default: () => [] }, // [{ name, stock, share }]
  size: { type: Number, default: 168 },
  thickness: { type: Number, default: 22 },
  maxSlices: { type: Number, default: 6 },
  palette: {
    type: Array,
    default: () => ['#2f7fd1', '#5fa3e0', '#93c2ec', '#c2dcf5', '#1b5c9b', '#7fb4e8'],
  },
  ariaLabel: { type: String, default: '分类库存分布' },
})

const radius = computed(() => (props.size - props.thickness) / 2)
const circumference = computed(() => 2 * Math.PI * radius.value)

/** 超过 maxSlices 时把尾部合并成「其他」，避免环形图切片过多。 */
const slices = computed(() => {
  const rows = props.data.filter((item) => Number(item.stock) > 0)
  const total = rows.reduce((sum, item) => sum + Number(item.stock), 0)
  if (!total) return []

  const head = rows.slice(0, props.maxSlices)
  const tail = rows.slice(props.maxSlices)
  const merged =
    tail.length > 0
      ? [
          {
            name: '其他',
            stock: tail.reduce((sum, item) => sum + Number(item.stock), 0),
            kinds: tail.reduce((sum, item) => sum + (Number(item.kinds) || 0), 0),
          },
        ]
      : []

  let offset = 0
  return [...head, ...merged].map((item, index) => {
    const stock = Number(item.stock) || 0
    const ratio = stock / total
    const slice = {
      ...item,
      stock,
      ratio,
      share: formatPercent(ratio * 100),
      color: props.palette[index % props.palette.length],
      dash: ratio * circumference.value,
      offset: -offset * circumference.value,
    }
    offset += ratio
    return slice
  })
})

const totalStock = computed(() =>
  props.data.reduce((sum, item) => sum + (Number(item.stock) || 0), 0),
)
</script>

<template>
  <div class="donut">
    <div class="donut__canvas" :style="{ width: `${size}px`, height: `${size}px` }">
      <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`" role="img" :aria-label="ariaLabel">
        <g :transform="`rotate(-90 ${size / 2} ${size / 2})`">
          <circle
            :cx="size / 2"
            :cy="size / 2"
            :r="radius"
            fill="none"
            stroke="var(--c-track)"
            :stroke-width="thickness"
          />
          <circle
            v-for="slice in slices"
            :key="slice.name"
            :cx="size / 2"
            :cy="size / 2"
            :r="radius"
            fill="none"
            :stroke="slice.color"
            :stroke-width="thickness"
            :stroke-dasharray="`${slice.dash} ${circumference - slice.dash}`"
            :stroke-dashoffset="slice.offset"
            class="donut__slice"
          />
        </g>
      </svg>

      <div class="donut__center">
        <span class="donut__total num">{{ formatNumber(totalStock) }}</span>
        <span class="donut__caption">库存总量</span>
      </div>
    </div>

    <ul class="donut__legend">
      <li v-for="slice in slices" :key="slice.name" class="donut__legend-item">
        <span class="donut__legend-dot" :style="{ background: slice.color }" />
        <span class="donut__legend-name truncate" :title="slice.name">{{ slice.name }}</span>
        <span class="donut__legend-value num">{{ formatNumber(slice.stock) }}</span>
        <span class="donut__legend-share num">{{ slice.share }}</span>
      </li>
      <li v-if="!slices.length" class="donut__legend-empty">暂无可统计的库存</li>
    </ul>
  </div>
</template>

<style scoped>
.donut {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  flex-wrap: wrap;
}

.donut__canvas {
  position: relative;
  flex: none;
}

.donut__slice {
  transition: opacity var(--dur) var(--ease-out);
}

.donut__center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  pointer-events: none;
}

.donut__total {
  font-size: var(--fs-xl);
  font-weight: 700;
  color: var(--c-primary-deep);
  line-height: 1.1;
}

.donut__caption {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
}

.donut__legend {
  flex: 1;
  min-width: 150px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.donut__legend-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-xs);
  color: var(--c-text-sub);
}

.donut__legend-dot {
  width: 9px;
  height: 9px;
  border-radius: 2px;
  flex: none;
}

.donut__legend-name {
  flex: 1;
  min-width: 0;
}

.donut__legend-value {
  font-weight: 600;
  color: var(--c-text);
}

.donut__legend-share {
  width: 46px;
  text-align: right;
  color: var(--c-text-mute);
}

.donut__legend-empty {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
}
</style>