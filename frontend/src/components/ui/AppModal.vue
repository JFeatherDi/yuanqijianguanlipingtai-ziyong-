<script setup>
/**
 * 弹窗：Teleport 到 body，隔离层级与滚动上下文。
 * 无障碍：role=dialog + aria-modal、Esc 关闭、打开时聚焦、关闭后焦点归还。
 */
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: String, default: '540px' },
  closeOnBackdrop: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'closed'])

const panel = ref(null)
let lastFocused = null

function close() {
  emit('update:modelValue', false)
}

function onBackdrop() {
  if (props.closeOnBackdrop) close()
}

function onKeydown(event) {
  if (event.key === 'Escape') {
    event.stopPropagation()
    close()
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      lastFocused = document.activeElement
      document.body.style.overflow = 'hidden'
      window.addEventListener('keydown', onKeydown)
      await nextTick()
      // 优先聚焦第一个表单控件；没有表单控件时退而聚焦按钮，最后才是面板本身。
      // 顺序很重要：如果直接把 button 放进第一个选择器，焦点会落在右上角的关闭按钮上。
      const target =
        panel.value?.querySelector(
          'input:not([type=hidden]):not([disabled]), select:not([disabled]), textarea:not([disabled])',
        ) ??
        panel.value?.querySelector('button:not([disabled]), [tabindex]:not([tabindex="-1"])') ??
        panel.value
      target?.focus?.()
    } else {
      document.body.style.overflow = ''
      window.removeEventListener('keydown', onKeydown)
      lastFocused?.focus?.()
      lastFocused = null
      emit('closed')
    }
  },
)

onBeforeUnmount(() => {
  document.body.style.overflow = ''
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="modelValue" class="modal" @click.self="onBackdrop">
        <div
          ref="panel"
          class="modal__panel"
          :style="{ width }"
          role="dialog"
          aria-modal="true"
          :aria-label="title || undefined"
          tabindex="-1"
        >
          <header class="modal__head">
            <h2 class="modal__title">{{ title }}</h2>
            <button class="modal__close" type="button" aria-label="关闭" @click="close">
              <AppIcon name="close" :size="16" />
            </button>
          </header>

          <div class="modal__body">
            <slot />
          </div>

          <footer v-if="$slots.footer" class="modal__foot">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  background: rgba(20, 30, 42, 0.48);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 48px var(--sp-4) var(--sp-6);
  overflow-y: auto;
}

.modal__panel {
  max-width: 100%;
  background: var(--c-surface);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-3);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 96px);
}

.modal__panel:focus {
  outline: none;
}

.modal__head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: 0 var(--sp-4);
  height: 48px;
  border-bottom: 1px solid var(--c-border-soft);
  background: var(--c-primary-band);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  flex: none;
}

.modal__title {
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--c-text-on-primary);
}

.modal__close {
  margin-left: auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: var(--radius);
  background: transparent;
  color: rgba(255, 255, 255, 0.85);
  cursor: pointer;
  transition: background var(--dur) var(--ease-out);
}

.modal__close:hover {
  background: rgba(255, 255, 255, 0.18);
  color: #fff;
}

.modal__body {
  padding: var(--sp-5) var(--sp-4);
  overflow-y: auto;
}

.modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4);
  border-top: 1px solid var(--c-border-soft);
  background: var(--c-surface-alt);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
  flex: none;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity var(--dur) var(--ease-out);
}

.modal-enter-active .modal__panel,
.modal-leave-active .modal__panel {
  transition: transform var(--dur) var(--ease-out), opacity var(--dur) var(--ease-out);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal__panel,
.modal-leave-to .modal__panel {
  opacity: 0;
  transform: translateY(-10px);
}

@media (max-width: 640px) {
  .modal {
    padding: var(--sp-3);
  }

  .modal__panel {
    max-height: calc(100vh - 24px);
  }
}
</style>