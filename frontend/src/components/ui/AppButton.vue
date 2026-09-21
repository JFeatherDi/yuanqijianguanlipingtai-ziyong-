<script setup>
import { computed } from 'vue'
import AppIcon from './AppIcon.vue'

/**
 * 按钮：外观由 variant/size 两个维度决定，避免逐处写样式。
 * variant: default | primary | success | warn | danger | ghost
 * size: md | sm
 */
const props = defineProps({
  variant: { type: String, default: 'default' },
  size: { type: String, default: 'md' },
  icon: { type: String, default: '' },
  type: { type: String, default: 'button' },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  block: { type: Boolean, default: false },
  iconOnly: { type: Boolean, default: false },
  ariaLabel: { type: String, default: '' },
})

const classes = computed(() => [
  'btn',
  props.variant !== 'default' && `btn--${props.variant}`,
  props.size === 'sm' && 'btn--sm',
  props.iconOnly && 'btn--icon',
  props.block && 'btn--block',
  props.loading && 'is-loading',
])

const iconSize = computed(() => (props.size === 'sm' ? 13 : 14))
</script>

<template>
  <button
    :type="type"
    :class="classes"
    :disabled="disabled || loading"
    :aria-label="iconOnly ? ariaLabel : undefined"
    :title="iconOnly ? ariaLabel : undefined"
    :aria-busy="loading || undefined"
  >
    <span v-if="loading" class="btn__spinner" aria-hidden="true" />
    <AppIcon v-else-if="icon" :name="icon" :size="iconSize" />
    <span v-if="!iconOnly" class="btn__label"><slot /></span>
  </button>
</template>

<style scoped>
.btn__spinner {
  width: 13px;
  height: 13px;
  flex: none;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  opacity: 0.75;
  animation: btn-spin 0.7s linear infinite;
}

@keyframes btn-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .btn__spinner {
    animation-duration: 2s;
  }
}
</style>