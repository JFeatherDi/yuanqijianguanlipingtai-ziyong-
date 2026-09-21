<script setup>
/** 库存预警：只看需要补货的器件，按缺口从大到小排。 */
import { computed } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PanelCard from '@/components/ui/PanelCard.vue'
import StatCard from '@/components/ui/StatCard.vue'
import { STATUS_META, stockStatus } from '@/domain/inventory'
import { useInventoryStore } from '@/stores/inventory'
import { download } from '@/api/client'
import { recordApi } from '@/api/endpoints'
import { formatQuantity } from '@/utils/format'

const inventory = useInventoryStore()

const flagged = computed(() => inventory.lowItems)

const outOfStock = computed(() =>
  flagged.value.filter((item) => stockStatus(item) === 'empty'),
)

const guarded = computed(() => inventory.items.filter((item) => Number(item.threshold) > 0))

/** 缺口 = 预警值 - 当前库存，用于告诉使用者「至少补多少」。 */
const shortageOf = (item) =>
  Math.max((Number(item.threshold) || 0) - (Number(item.stock) || 0), 0)

const rows = computed(() =>
  [...flagged.value].sort((a, b) => shortageOf(b) - shortageOf(a)),
)

const totalShortage = computed(() =>
  rows.value.reduce((sum, item) => sum + shortageOf(item), 0),
)

const coverRate = computed(() => {
  if (!guarded.value.length) return 0
  return (guarded.value.length - flagged.value.length) / guarded.value.length
})

const cards = computed(() => [
  {
    key: 'empty',
    title: '已缺货',
    icon: 'alert',
    value: outOfStock.value.length,
    caption: '库存为 0 且设置了预警值',
    metrics: [
      { label: '预警中', value: formatQuantity(flagged.value.length), tone: 'warn' },
      { label: '总计种类', value: formatQuantity(inventory.total) },
    ],
  },
  {
    key: 'shortage',
    title: '待补货缺口',
    icon: 'trend',
    value: totalShortage.value,
    caption: '按预警值估算的补货总量',
    metrics: [
      { label: '涉及器件', value: formatQuantity(rows.value.length), tone: 'warn' },
      { label: '平均缺口', value: formatQuantity(rows.value.length ? Math.round(totalShortage.value / rows.value.length) : 0) },
    ],
  },
  {
    key: 'guarded',
    title: '达标率',
    icon: 'shield',
    value: `${(coverRate.value * 100).toFixed(1)}%`,
    caption: '受监控器件中库存充足的比例',
    metrics: [
      { label: '受监控', value: formatQuantity(guarded.value.length) },
      {
        label: '未达标',
        value: formatQuantity(flagged.value.length),
        tone: flagged.value.length ? 'warn' : 'ok',
      },
    ],
  },
])

function toneOf(item) {
  return STATUS_META[stockStatus(item)]?.tone ?? 'tag--ghost'
}

function labelOf(item) {
  return STATUS_META[stockStatus(item)]?.label ?? '—'
}
</script>

<template>
  <div class="alerts">
    <div class="alerts__cards">
      <StatCard
        v-for="item in cards"
        :key="item.key"
        :title="item.title"
        :icon="item.icon"
        :value="item.value"
        :caption="item.caption"
        :metrics="item.metrics"
      />
    </div>

    <PanelCard title="需补货清单" flush>
      <template #tools>
        <AppButton size="sm" icon="download" @click="download(recordApi.exportPath)">
          导出清单
        </AppButton>
      </template>

      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>器件</th>
              <th>分类</th>
              <th>规格</th>
              <th>库位</th>
              <th class="right">当前库存</th>
              <th class="right">预警值</th>
              <th class="right">建议补货</th>
              <th>状态</th>
              <th class="right">操作</th>
            </tr>
          </thead>

          <tbody v-if="inventory.loading && !inventory.loaded">
            <tr v-for="index in 4" :key="index">
              <td v-for="cell in 9" :key="cell"><span class="skeleton skeleton-row" /></td>
            </tr>
          </tbody>

          <tbody v-else-if="rows.length">
            <tr v-for="item in rows" :key="item.id">
              <td class="strong">{{ item.name }}</td>
              <td>
                <span v-if="item.category" class="tag tag--blue">{{ item.category }}</span>
                <span v-else class="muted">未分类</span>
              </td>
              <td>{{ item.spec || '—' }}</td>
              <td>{{ item.location || '—' }}</td>
              <td class="right num stock">
                {{ formatQuantity(item.stock) }} {{ item.unit || '个' }}
              </td>
              <td class="right num">{{ formatQuantity(item.threshold) }}</td>
              <td class="right num shortage">+{{ formatQuantity(shortageOf(item)) }}</td>
              <td><span class="tag" :class="toneOf(item)">{{ labelOf(item) }}</span></td>
              <td class="right">
                <RouterLink :to="{ name: 'stock-in', query: { cid: item.id } }">
                  <AppButton size="sm" variant="primary" icon="arrow-down">补货</AppButton>
                </RouterLink>
              </td>
            </tr>
          </tbody>

          <tbody v-else>
            <tr>
              <td colspan="9">
                <EmptyState
                  icon="check-circle"
                  title="没有需要补货的器件"
                  desc="规则：为器件设置大于 0 的预警值后，当库存小于等于该值时会进入此清单。"
                >
                  <RouterLink :to="{ name: 'components' }">
                    <AppButton icon="chip">去设置预警值</AppButton>
                  </RouterLink>
                </EmptyState>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </PanelCard>

    <PanelCard title="预警规则">
      <ul class="rules">
        <li class="rules__item">
          <span class="tag tag--ghost">未设阈值</span>
          <span>预警值填 0 表示不监控，该器件永远不会进入预警清单。</span>
        </li>
        <li class="rules__item">
          <span class="tag tag--warn">预警</span>
          <span>0 &lt; 库存 ≤ 预警值，建议尽快补货。</span>
        </li>
        <li class="rules__item">
          <span class="tag tag--danger">缺货</span>
          <span>库存 ≤ 0，已经完全用尽。</span>
        </li>
        <li class="rules__item">
          <span class="tag tag--ok">正常</span>
          <span>库存 &gt; 预警值，无需处理。</span>
        </li>
      </ul>
    </PanelCard>
  </div>
</template>

<style scoped>
.alerts {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.alerts__cards {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--sp-3);
}

.stock {
  color: var(--c-text);
  font-weight: 600;
}

.shortage {
  color: var(--c-warn);
  font-weight: 700;
}

.skeleton-row {
  display: block;
  height: 14px;
  width: 70%;
}

.rules {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.rules__item {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  font-size: var(--fs-sm);
  color: var(--c-text-sub);
}

.rules__item .tag {
  flex: none;
  margin-top: 1px;
}

@media (max-width: 1024px) {
  .alerts__cards {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>