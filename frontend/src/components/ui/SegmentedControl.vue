<script setup>
/** 分段切换：图中「今天 / 近7天 / 近30天」的样式。 */
defineProps({
  modelValue: { type: [String, Number], required: true },
  options: { type: Array, required: true }, // [{ id, label }]
  ariaLabel: { type: String, default: '切换范围' },
})

const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <div class="segmented" role="group" :aria-label="ariaLabel">
    <button
      v-for="option in options"
      :key="option.id"
      type="button"
      class="segmented__item"
      :class="{ 'is-active': option.id === modelValue }"
      :aria-pressed="option.id === modelValue"
      @click="emit('update:modelValue', option.id)"
    >
      {{ option.label }}
    </button>
  </div>
</template>