<script setup>
/** 入库登记页。表单逻辑全部在 StockMovePanel 中，这里只注入方向。 */
import StockMovePanel from '@/components/StockMovePanel.vue'
</script>

<template>
  <StockMovePanel mode="in" />
</template>