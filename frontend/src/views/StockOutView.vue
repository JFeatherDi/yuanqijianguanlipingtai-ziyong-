<script setup>
/** 出库领用页。表单逻辑全部在 StockMovePanel 中，这里只注入方向。 */
import StockMovePanel from '@/components/StockMovePanel.vue'
</script>

<template>
  <StockMovePanel mode="out" />
</template>