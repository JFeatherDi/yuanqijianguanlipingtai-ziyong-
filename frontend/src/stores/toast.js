import { ref } from 'vue'
import { defineStore } from 'pinia'

const DEFAULT_DURATION = 3200
const TONE_BY_KIND = {
  success: 'success',
  error: 'error',
  warning: 'warning',
  info: 'info',
}

/** 全局提示：唯一的消息出口，避免各视图各自造弹层。 */
export const useToastStore = defineStore('toast', () => {
  const items = ref([])
  let seq = 0
  const timers = new Map()

  function dismiss(id) {
    const timer = timers.get(id)
    if (timer) {
      clearTimeout(timer)
      timers.delete(id)
    }
    items.value = items.value.filter((item) => item.id !== id)
  }

  function push(message, kind = 'info', duration = DEFAULT_DURATION) {
    if (!message) return
    const id = ++seq
    const tone = TONE_BY_KIND[kind] ?? 'info'
    items.value = [...items.value, { id, message: String(message), tone }]
    // 用 setTimeout 统一管理自动消失；移出焦点，不打断屏幕阅读器
    timers.set(
      id,
      setTimeout(() => dismiss(id), Math.max(duration, 2000)),
    )
    return id
  }

  const success = (message, duration) => push(message, 'success', duration)
  const error = (message, duration) => push(message, 'error', duration ?? 4200)
  const warning = (message, duration) => push(message, 'warning', duration)
  const info = (message, duration) => push(message, 'info', duration)

  return { items, push, dismiss, success, error, warning, info }
})