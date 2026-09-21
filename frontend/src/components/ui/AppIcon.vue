<script setup>
/**
 * 图标：统一的 SVG 图标族（线性、圆角端点、单一线宽）。
 * 约束：全站不使用 emoji 作为图标 —— emoji 跨平台渲染不可控、无法继承颜色。
 */
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: [Number, String], default: 16 },
  strokeWidth: { type: Number, default: 1.75 },
})

// 每个图标只描述内部图形，外层 <svg> 属性由组件统一提供
const ICONS = {
  dashboard:
    '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
  chip:
    '<rect x="7" y="7" width="10" height="10" rx="1.5"/><rect x="10.2" y="10.2" width="3.6" height="3.6" rx="0.6"/><path d="M10 3.2v3.8M14 3.2v3.8M10 17v3.8M14 17v3.8M3.2 10h3.8M3.2 14h3.8M17 10h3.8M17 14h3.8"/>',
  box:
    '<path d="M20.5 8.6v6.8a1.5 1.5 0 0 1-.8 1.3l-6.9 3.8a1.5 1.5 0 0 1-1.6 0l-6.9-3.8a1.5 1.5 0 0 1-.8-1.3V8.6a1.5 1.5 0 0 1 .8-1.3l6.9-3.8a1.5 1.5 0 0 1 1.6 0l6.9 3.8a1.5 1.5 0 0 1 .8 1.3Z"/><path d="M3.9 7.7 12 12.2l8.1-4.5M12 12.2V20.6"/>',
  'arrow-down': '<path d="M12 3.5v12.2m0 0 4.4-4.4M12 15.7l-4.4-4.4M4.5 20.5h15"/>',
  'arrow-up': '<path d="M12 20.5V8.3m0 0 4.4 4.4M12 8.3l-4.4 4.4M4.5 3.5h15"/>',
  alert: '<path d="M10.3 4.3 2.7 17.4a1.9 1.9 0 0 0 1.7 2.9h15.2a1.9 1.9 0 0 0 1.7-2.9L13.7 4.3a1.9 1.9 0 0 0-3.4 0Z"/><path d="M12 9.5v4.3M12 17.1h.01"/>',
  history: '<path d="M3.5 6h17M3.5 12h17M3.5 18h11"/>',
  database:
    '<path d="M12 3.2c4.3 0 7.8 1.2 7.8 2.6S16.3 8.4 12 8.4 4.2 7.2 4.2 5.8 7.7 3.2 12 3.2Z"/><path d="M4.2 5.8v12.4c0 1.4 3.5 2.6 7.8 2.6s7.8-1.2 7.8-2.6V5.8"/><path d="M4.2 12c0 1.4 3.5 2.6 7.8 2.6s7.8-1.2 7.8-2.6"/>',
  sliders: '<path d="M20 7.5h-9.5M13.5 16.5H4"/><circle cx="7.8" cy="7.5" r="2.8"/><circle cx="16.2" cy="16.5" r="2.8"/>',
  search: '<circle cx="11" cy="11" r="6.8"/><path d="M20.4 20.4 15.7 15.7"/>',
  plus: '<path d="M12 5.2v13.6M5.2 12h13.6"/>',
  minus: '<path d="M5.2 12h13.6"/>',
  edit: '<path d="M16.4 4.1a2.1 2.1 0 0 1 3 3L7.6 18.9l-4.1 1.1 1.1-4.1Z"/><path d="M14.6 5.9l3.5 3.5"/>',
  trash:
    '<path d="M4 7h16M9.5 7V4.9a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1V7"/><path d="M6.5 7l.8 12.1a1.5 1.5 0 0 0 1.5 1.4h6.4a1.5 1.5 0 0 0 1.5-1.4L17.5 7"/><path d="M10.4 10.8v6.2M13.6 10.8v6.2"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  logout: '<path d="M15 16.6l4.6-4.6L15 7.4M19.6 12H9"/><path d="M11.2 4.6H6.6A1.6 1.6 0 0 0 5 6.2v11.6a1.6 1.6 0 0 0 1.6 1.6h4.6"/>',
  user: '<circle cx="12" cy="8.2" r="3.6"/><path d="M4.9 20.2a7.3 7.3 0 0 1 14.2 0"/>',
  refresh: '<path d="M20.4 12a8.4 8.4 0 1 1-2.5-6"/><path d="M20.6 4.2v5h-5"/>',
  check: '<path d="M4.8 12.6 9.6 17.4 19.4 6.8"/>',
  filter: '<path d="M3.8 5.5h16.4l-6.4 7.4v5.5l-3.6 1.8v-7.3Z"/>',
  calendar:
    '<rect x="3.5" y="5" width="17" height="15.5" rx="1.8"/><path d="M3.5 9.8h17M8 3.4v3.6M16 3.4v3.6"/>',
  panel: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M9.6 4.5v15"/>',
  pie: '<path d="M12 3.3a8.7 8.7 0 1 0 8.7 8.7H12Z"/><path d="M14.9 2.6a8.7 8.7 0 0 1 6.5 6.5h-6.5Z"/>',
  chart: '<path d="M3.5 3.8v16.4h17"/><path d="M7.6 17.4v-4.6M11.6 17.4V9.2M15.6 17.4v-6.6M19.6 17.4v-11"/>',
  download: '<path d="M12 3.6v11.2m0 0 4.2-4.2M12 14.8l-4.2-4.2M4.5 19.6h15"/>',
  upload: '<path d="M12 15.4V4.2m0 0 4.2 4.2M12 4.2 7.8 8.4M4.5 19.6h15"/>',
  file: '<path d="M14.2 3.6H7.6A1.6 1.6 0 0 0 6 5.2v13.6a1.6 1.6 0 0 0 1.6 1.6h8.8a1.6 1.6 0 0 0 1.6-1.6V7.4Z"/><path d="M14.2 3.6v3.8H18M9.4 12.6h5.2M9.4 16h3.6"/>',
  eye: '<path d="M2.6 12S6.1 5.6 12 5.6 21.4 12 21.4 12 17.9 18.4 12 18.4 2.6 12 2.6 12Z"/><circle cx="12" cy="12" r="2.9"/>',
  'eye-off':
    '<path d="M4.2 4.2 19.8 19.8"/><path d="M9.9 6.1A8.9 8.9 0 0 1 12 5.9c5.9 0 9.4 6.1 9.4 6.1a17.7 17.7 0 0 1-3.4 4.1M6.7 7.9A17.5 17.5 0 0 0 2.6 12s3.5 6.1 9.4 6.1c1.2 0 2.3-.2 3.3-.6"/><path d="M10.5 10.7a2.9 2.9 0 0 0 4.1 4.1"/>',
  lock: '<rect x="4.6" y="10.4" width="14.8" height="10" rx="2"/><path d="M8.2 10.4V7.9a3.8 3.8 0 0 1 7.6 0v2.5"/>',
  building:
    '<path d="M4.6 20.5V4.6a1 1 0 0 1 1-1h7.8a1 1 0 0 1 1 1v15.9"/><path d="M14.4 20.5V10.2h3.9a1 1 0 0 1 1 1v9.3M3.2 20.5h17.6"/><path d="M8 7.6h3M8 11h3M8 14.4h3"/>',
  info: '<circle cx="12" cy="12" r="8.7"/><path d="M12 11v5.6M12 7.7h.01"/>',
  'check-circle': '<circle cx="12" cy="12" r="8.7"/><path d="M8.3 12.3 10.9 15l5-5.6"/>',
  'alert-circle': '<circle cx="12" cy="12" r="8.7"/><path d="M12 7.7v5.4M12 16.3h.01"/>',
  'close-circle': '<circle cx="12" cy="12" r="8.7"/><path d="M9.2 9.2 14.8 14.8M14.8 9.2 9.2 14.8"/>',
  clock: '<circle cx="12" cy="12" r="8.7"/><path d="M12 7.3V12l3.1 2.1"/>',
  trend: '<path d="M3.5 16.6 9.2 10.9l3.4 3.4 7.9-7.9"/><path d="M15.6 6.4h4.9v4.9"/>',
  menu: '<path d="M3.6 7h16.8M3.6 12h16.8M3.6 17h16.8"/>',
  chevronDown: '<path d="M6 9.4 12 15.4l6-6"/>',
  chevronRight: '<path d="M9.4 6 15.4 12l-6 6"/>',
  chevronLeft: '<path d="M14.6 6 8.6 12l6 6"/>',
  inbox:
    '<path d="M3.6 13.4 6.4 5a1.6 1.6 0 0 1 1.5-1.1h8.2A1.6 1.6 0 0 1 17.6 5l2.8 8.4v4.4a1.6 1.6 0 0 1-1.6 1.6H5.2a1.6 1.6 0 0 1-1.6-1.6Z"/><path d="M3.6 13.4h4.2l1.1 2.3h6.2l1.1-2.3h4.2"/>',
  hash: '<path d="M4.5 9h15M4.5 15h15M9.6 4.4 7.6 19.6M16.4 4.4l-2 15.2"/>',
  tag: '<path d="M11.4 3.5H5.2a1.7 1.7 0 0 0-1.7 1.7v6.2a1.7 1.7 0 0 0 .5 1.2l7.4 7.4a1.7 1.7 0 0 0 2.4 0l6.2-6.2a1.7 1.7 0 0 0 0-2.4l-7.4-7.4a1.7 1.7 0 0 0-1.2-.5Z"/><path d="M8.1 8.1h.01"/>',
  clipboard:
    '<path d="M9.4 4.4H7.6A1.6 1.6 0 0 0 6 6v13.2a1.6 1.6 0 0 0 1.6 1.6h8.8a1.6 1.6 0 0 0 1.6-1.6V6a1.6 1.6 0 0 0-1.6-1.6h-1.8"/><rect x="9.4" y="2.8" width="5.2" height="3.2" rx="1"/><path d="M9.4 11.6h5.2M9.4 15.2h3.2"/>',
  help: '<circle cx="12" cy="12" r="8.7"/><path d="M9.7 9.4a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1.1.9-1.1 1.6v.4M12 16.5h.01"/>',
  shield:
    '<path d="M12 3.2 5 6.1v5.5c0 4 2.9 7.6 7 9.2 4.1-1.6 7-5.2 7-9.2V6.1Z"/><path d="M9.3 12.1 11.4 14l3.4-3.8"/>',
}

const content = computed(() => ICONS[props.name] ?? ICONS.help)
</script>

<template>
  <svg
    class="icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="strokeWidth"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
    v-html="content"
  />
</template>

<style scoped>
.icon {
  display: block;
  flex: none;
}
</style>