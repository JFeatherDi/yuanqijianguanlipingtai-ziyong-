<script setup>
/** 全局提示宿主：挂载在 App 根部，供所有视图共用。 */
import { storeToRefs } from 'pinia'
import AppIcon from './AppIcon.vue'
import { useToastStore } from '@/stores/toast'

const toast = useToastStore()
const { items } = storeToRefs(toast)

const ICON_BY_TONE = {
  success: 'check-circle',
  error: 'alert-circle',
  warning: 'alert',
  info: 'info',
}
</script>

<template>
  <!-- aria-live=polite：不夺取焦点，但会被屏幕阅读器播报 -->
  <div class="toasts" role="status" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="item in items" :key="item.id" class="toast" :class="`toast--${item.tone}`">
        <AppIcon :name="ICON_BY_TONE[item.tone]" :size="16" class="toast__icon" />
        <span class="toast__text">{{ item.message }}</span>
        <button class="toast__close" type="button" aria-label="关闭提示" @click="toast.dismiss(item.id)">
          <AppIcon name="close" :size="13" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toasts {
  position: fixed;
  top: 60px;
  right: var(--sp-4);
  z-index: var(--z-toast);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  width: min(340px, calc(100vw - 32px));
  pointer-events: none;
}

.toast {
  pointer-events: auto;
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  padding: 10px var(--sp-3);
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-left: 3px solid var(--c-primary);
  border-radius: var(--radius);
  box-shadow: var(--shadow-2);
  font-size: var(--fs-sm);
  color: var(--c-text);
}

.toast--success {
  border-left-color: var(--c-success);
}

.toast--success .toast__icon {
  color: var(--c-success);
}

.toast--error {
  border-left-color: var(--c-danger);
}

.toast--error .toast__icon {
  color: var(--c-danger);
}

.toast--warning {
  border-left-color: var(--c-warn);
}

.toast--warning .toast__icon {
  color: var(--c-warn);
}

.toast--info .toast__icon {
  color: var(--c-primary);
}

.toast__icon {
  margin-top: 1px;
}

.toast__text {
  flex: 1;
  min-width: 0;
  word-break: break-word;
  line-height: 1.45;
}

.toast__close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  margin: -2px -4px 0 0;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--c-text-mute);
  cursor: pointer;
}

.toast__close:hover {
  background: var(--c-surface-alt);
  color: var(--c-text);
}

.toast-enter-active,
.toast-leave-active {
  transition: opacity var(--dur) var(--ease-out), transform var(--dur) var(--ease-out);
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateX(16px);
}
</style>