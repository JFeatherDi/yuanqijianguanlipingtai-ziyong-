<script setup>
import ToastHost from '@/components/ui/ToastHost.vue'
</script>

<template>
  <RouterView v-slot="{ Component }">
    <component :is="Component" />
  </RouterView>
  <ToastHost />
</template>