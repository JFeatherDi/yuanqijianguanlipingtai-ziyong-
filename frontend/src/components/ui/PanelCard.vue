<script setup>
/** 面板外壳：图中每个内容块的统一容器。 */
defineProps({
  title: { type: String, default: '' },
  flush: { type: Boolean, default: false },
  tint: { type: Boolean, default: false },
  grow: { type: Boolean, default: false },
})
</script>

<template>
  <section class="panel" :class="{ 'is-grow': grow }">
    <header v-if="title || $slots.tools" class="panel__head">
      <h3 v-if="title" class="panel__title">{{ title }}</h3>
      <div v-if="$slots.tools" class="panel__tools">
        <slot name="tools" />
      </div>
    </header>

    <div class="panel__body" :class="{ 'panel__body--flush': flush, 'panel__body--tint': tint }">
      <slot />
    </div>

    <footer v-if="$slots.footer" class="panel__foot">
      <slot name="footer" />
    </footer>
  </section>
</template>

<style scoped>
.is-grow {
  flex: 1;
  min-height: 0;
}
</style>