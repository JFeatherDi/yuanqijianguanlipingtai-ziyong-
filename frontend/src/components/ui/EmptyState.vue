<script setup>
/** 空状态：说明「为什么空」以及「下一步做什么」。 */
import AppIcon from './AppIcon.vue'

defineProps({
  icon: { type: String, default: 'inbox' },
  title: { type: String, default: '暂无数据' },
  desc: { type: String, default: '' },
})
</script>

<template>
  <div class="empty">
    <AppIcon :name="icon" :size="34" class="empty__icon" />
    <p class="empty__title">{{ title }}</p>
    <p v-if="desc" class="empty__desc">{{ desc }}</p>
    <div v-if="$slots.default" class="empty__action">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty__action {
  margin-top: var(--sp-2);
}
</style>