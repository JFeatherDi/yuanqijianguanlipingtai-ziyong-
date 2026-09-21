/** 全局刷新信号：顶栏「刷新」按钮 -> 各视图重新拉取自己的数据。 */
import { inject, provide, ref } from 'vue'

export const REFRESH_KEY = Symbol('app-refresh')

export function provideRefreshSignal() {
  const signal = ref(0)
  provide(REFRESH_KEY, signal)
  return signal
}

export function useRefreshSignal() {
  return inject(REFRESH_KEY, ref(0))
}