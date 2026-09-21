<script setup>
/** 流水表格：操作记录页、主页动态、出入库侧栏共用同一份呈现规则。 */
import EmptyState from '@/components/ui/EmptyState.vue'
import { txLabel, txTone } from '@/domain/inventory'
import { display, formatDateTime, formatDelta } from '@/utils/format'

defineProps({
  rows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  emptyTitle: { type: String, default: '暂无操作记录' },
  emptyDesc: { type: String, default: '完成一次入库或出库后，记录会显示在这里。' },
})
</script>

<template>
  <div class="table-wrap">
    <table class="data-table" :class="{ 'is-compact': compact }">
      <thead>
        <tr>
          <th>时间</th>
          <th>器件</th>
          <th v-if="!compact">规格</th>
          <th>类型</th>
          <th class="right">变化量</th>
          <th v-if="!compact">操作人</th>
          <th v-if="!compact">备注</th>
        </tr>
      </thead>

      <tbody v-if="loading">
        <tr v-for="index in 5" :key="index">
          <td :colspan="compact ? 5 : 7"><span class="skeleton skeleton-row" /></td>
        </tr>
      </tbody>

      <tbody v-else-if="rows.length">
        <tr v-for="row in rows" :key="row.id">
          <td class="num">{{ formatDateTime(row.created_at) }}</td>
          <td class="strong">{{ display(row.name) }}</td>
          <td v-if="!compact">{{ display(row.spec) }}</td>
          <td>
            <span class="tag" :class="txTone(row.type)">{{ txLabel(row.type) }}</span>
          </td>
          <td
            class="right num"
            :class="Number(row.delta) >= 0 ? 'delta-in' : 'delta-out'"
          >{{ formatDelta(row.delta) }}</td>
          <td v-if="!compact">{{ display(row.operator) }}</td>
          <td v-if="!compact" class="truncate" :title="row.remark || ''">
            {{ display(row.remark) }}
          </td>
        </tr>
      </tbody>

      <tbody v-else>
        <tr>
          <td :colspan="compact ? 5 : 7">
            <EmptyState icon="history" :title="emptyTitle" :desc="emptyDesc" />
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.is-compact :deep(th),
.is-compact :deep(td) {
  padding: 6px var(--sp-2);
  font-size: var(--fs-xs);
}

.skeleton-row {
  display: block;
  height: 14px;
}

.delta-in {
  color: var(--c-success);
  font-weight: 600;
}

.delta-out {
  color: var(--c-warn);
  font-weight: 600;
}
</style>