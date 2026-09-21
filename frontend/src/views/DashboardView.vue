<script setup>
/**
 * 主页看板 —— 布局与配色严格对齐参考图：
 *   第 1 行：4 张蓝色标题条指标卡
 *   第 2 行：实时动态 | 分类库存占比 | 库存总览（含环形图）
 *   第 3 行：出入库趋势（分段切换 + 分组柱状图）
 *   第 4 行：库存预警清单
 */
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import AppButton from '@/components/ui/AppButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import PanelCard from '@/components/ui/PanelCard.vue'
import ProgressBar from '@/components/ui/ProgressBar.vue'
import SegmentedControl from '@/components/ui/SegmentedControl.vue'
import StatCard from '@/components/ui/StatCard.vue'
import BarChart from '@/components/charts/BarChart.vue'
import DonutChart from '@/components/charts/DonutChart.vue'
import { RANGE_OPTIONS, useDashboardStore } from '@/stores/dashboard'
import { useInventoryStore } from '@/stores/inventory'
import { useRefreshSignal } from '@/composables/useRefresh'
import { useToastStore } from '@/stores/toast'
import { STATUS_META, stockStatus, txLabel, txTone } from '@/domain/inventory'
import { formatPercent, formatQuantity, formatTime } from '@/utils/format'

const dashboard = useDashboardStore()
const inventory = useInventoryStore()
const toast = useToastStore()
const refreshSignal = useRefreshSignal()

const { overview, categories, series, recent, range, loading, flowLoading } = storeToRefs(dashboard)

const rangeOptions = RANGE_OPTIONS
const chartKeys = [
  { key: 'inbound', label: '入库', color: '#93c2ec' },
  { key: 'outbound', label: '出库', color: '#2f7fd1' },
]

const topCategories = computed(() => categories.value.slice(0, 6))
const alerts = computed(() => inventory.lowItems.slice(0, 6))

const stats = computed(() => {
  const data = overview.value
  if (!data) return []
  return [
    {
      key: 'kinds',
      title: '元器件种类',
      icon: 'chip',
      value: data.kinds,
      caption: '已登记器件',
      metrics: [
        { label: '已分类', value: formatQuantity(data.categories) },
        {
          label: '未分类',
          value: formatQuantity(data.uncategorized),
          tone: data.uncategorized > 0 ? 'warn' : undefined,
        },
      ],
    },
    {
      key: 'stock',
      title: '总库存量',
      icon: 'box',
      value: data.total_stock,
      caption: '所有器件库存合计',
      metrics: [
        { label: '累计入库', value: formatQuantity(data.inbound_total) },
        { label: '累计出库', value: formatQuantity(data.outbound_total), tone: 'warn' },
      ],
    },
    {
      key: 'low',
      title: '库存预警',
      icon: 'alert',
      value: data.low_count,
      caption: '低于或等于预警值',
      metrics: [
        { label: '受监控', value: formatQuantity(data.guarded_count) },
        {
          label: '达标率',
          value: formatPercent(data.guarded_rate),
          tone: data.guarded_rate >= 80 ? 'ok' : 'warn',
        },
      ],
    },
    {
      key: 'ops',
      title: '操作记录',
      icon: 'history',
      value: data.total_ops,
      caption: '累计出入库次数',
      metrics: [
        { label: '今日', value: formatQuantity(data.today_ops) },
        { label: '近 24 小时', value: formatQuantity(data.recent_ops) },
      ],
    },
  ]
})

async function reload() {
  try {
    await Promise.all([dashboard.load(true), inventory.load({ silent: true })])
  } catch (error) {
    toast.error(error.message)
  }
}

onMounted(reload)
watch(refreshSignal, reload)

function alertTone(item) {
  return STATUS_META[stockStatus(item)]?.tone ?? 'tag--ghost'
}

function alertLabel(item) {
  return STATUS_META[stockStatus(item)]?.label ?? '—'
}
</script>

<template>
  <div class="dash">
    <!-- 第 1 行：指标卡 -->
    <div class="dash__stats">
      <template v-if="loading && !stats.length">
        <div v-for="index in 4" :key="index" class="band-card">
          <div class="band-card__band skeleton skeleton--band" />
          <div class="band-card__body skeleton skeleton--body" />
        </div>
      </template>
      <template v-else>
        <StatCard
          v-for="item in stats"
          :key="item.key"
          :title="item.title"
          :icon="item.icon"
          :value="item.value"
          :caption="item.caption"
          :metrics="item.metrics"
        />
      </template>
    </div>

    <!-- 第 2 行：三块核心面板 -->
    <div class="dash__row">
      <!-- 实时动态 -->
      <PanelCard title="实时动态" flush>
        <template #tools>
          <RouterLink class="dash__more" :to="{ name: 'records' }">全部记录</RouterLink>
        </template>
        <ul v-if="recent.length" class="feed">
          <li v-for="row in recent" :key="row.id" class="feed__item">
            <span class="feed__time num">{{ formatTime(row.created_at) }}</span>
            <span class="feed__body">
              <span class="feed__top">
                <b class="feed__name truncate" :title="row.name">{{ row.name }}</b>
                <span class="tag" :class="txTone(row.type)">{{ txLabel(row.type) }}</span>
              </span>
              <span class="feed__meta">
                {{ row.spec || '无规格' }} · {{ row.operator || '系统' }}
                <b :class="Number(row.delta) >= 0 ? 'feed__up' : 'feed__down'">
                  {{ Number(row.delta) >= 0 ? '+' : '' }}{{ formatQuantity(row.delta) }}
                </b>
              </span>
            </span>
          </li>
        </ul>
        <EmptyState
          v-else
          icon="clock"
          title="暂无动态"
          desc="完成一次入库或出库后，这里会实时显示。"
        />
      </PanelCard>

      <!-- 分类库存占比 -->
      <PanelCard title="分类库存占比">
        <p class="dash__caption">分类库存汇总（按库存量降序）</p>
        <ul v-if="topCategories.length" class="ranks">
          <li v-for="item in topCategories" :key="item.name" class="ranks__item">
            <span class="ranks__name truncate" :title="item.name">{{ item.name }}</span>
            <ProgressBar :ratio="item.share / 100">
              <span class="num">{{ formatPercent(item.share) }}</span>
            </ProgressBar>
            <span class="ranks__value num" :title="`${item.kinds} 种器件`">
              {{ formatQuantity(item.stock) }}
            </span>
          </li>
        </ul>
        <EmptyState v-else icon="chart" title="暂无分类数据" desc="为器件填写分类后即可看到占比。" />
      </PanelCard>

      <!-- 库存总览 -->
      <PanelCard title="库存总览">
        <div class="kpi-strip">
          <div class="kpi">
            <span class="kpi__label">物料种类</span>
            <span class="kpi__value">{{ formatQuantity(overview?.kinds ?? 0) }}</span>
          </div>
          <div class="kpi">
            <span class="kpi__label">库存总量</span>
            <span class="kpi__value">{{ formatQuantity(overview?.total_stock ?? 0) }}</span>
          </div>
          <div class="kpi">
            <span class="kpi__label">预警中</span>
            <span class="kpi__value kpi__value--warn">{{ formatQuantity(overview?.low_count ?? 0) }}</span>
          </div>
          <div class="kpi">
            <span class="kpi__label">受监控</span>
            <span class="kpi__value">{{ formatQuantity(overview?.guarded_count ?? 0) }}</span>
          </div>
        </div>

        <div class="dash__donut">
          <DonutChart :data="categories" />
        </div>
      </PanelCard>
    </div>

    <!-- 第 3 行：出入库趋势 -->
    <PanelCard title="出入库趋势">
      <template #tools>
        <SegmentedControl
          :model-value="range"
          :options="rangeOptions"
          aria-label="选择统计范围"
          @update:model-value="dashboard.setRange($event)"
        />
        <AppButton size="sm" icon="search" :loading="flowLoading" @click="dashboard.loadFlow()">
          查询
        </AppButton>
      </template>
      <BarChart
        :data="series"
        :keys="chartKeys"
        aria-label="最近出入库数量趋势"
        :height="230"
      />
    </PanelCard>

    <!-- 第 4 行：库存预警清单 -->
    <PanelCard title="库存预警清单" flush>
      <template #tools>
        <span class="tag tag--warn">{{ inventory.lowCount }} 项待处理</span>
        <RouterLink class="dash__more" :to="{ name: 'alerts' }">查看全部</RouterLink>
      </template>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>器件</th>
              <th>规格</th>
              <th>库位</th>
              <th class="right">当前库存</th>
              <th class="right">预警值</th>
              <th>状态</th>
              <th class="right">操作</th>
            </tr>
          </thead>
          <tbody v-if="alerts.length">
            <tr v-for="item in alerts" :key="item.id">
              <td class="strong">{{ item.name }}</td>
              <td>{{ item.spec || '—' }}</td>
              <td>{{ item.location || '—' }}</td>
              <td class="right num">{{ formatQuantity(item.stock) }} {{ item.unit || '个' }}</td>
              <td class="right num">{{ formatQuantity(item.threshold) }}</td>
              <td><span class="tag" :class="alertTone(item)">{{ alertLabel(item) }}</span></td>
              <td class="right">
                <RouterLink :to="{ name: 'stock-in', query: { cid: item.id } }">
                  <AppButton size="sm" variant="ghost" icon="arrow-down">去入库</AppButton>
                </RouterLink>
              </td>
            </tr>
          </tbody>
          <tbody v-else>
            <tr>
              <td colspan="7">
                <EmptyState
                  icon="check-circle"
                  title="所有受监控器件库存充足"
                  desc="当库存小于等于预警值时，会自动出现在这里。"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </PanelCard>
  </div>
</template>

<style scoped>
.dash {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.dash__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--sp-3);
}

.dash__row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr) minmax(0, 1.15fr);
  gap: var(--sp-3);
  align-items: stretch;
}

.dash__caption {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
  margin-bottom: var(--sp-3);
}

.dash__more {
  font-size: var(--fs-xs);
  color: var(--c-primary);
}

.dash__donut {
  margin-top: var(--sp-4);
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border-soft);
}

/* ---------- 实时动态 ---------- */
.feed {
  max-height: 268px;
  overflow-y: auto;
}

.feed__item {
  display: flex;
  align-items: stretch;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--c-border-soft);
}

.feed__item:last-child {
  border-bottom: none;
}

.feed__time {
  flex: none;
  width: 46px;
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--c-primary);
  padding-top: 1px;
}

.feed__body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.feed__top {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}

.feed__name {
  font-size: var(--fs-sm);
  color: var(--c-text);
}

.feed__meta {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}

.feed__up {
  color: var(--c-success);
  font-family: var(--font-num);
}

.feed__down {
  color: var(--c-warn);
  font-family: var(--font-num);
}

/* ---------- 分类占比 ---------- */
.ranks {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.ranks__item {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) 62px;
  align-items: center;
  gap: var(--sp-3);
}

.ranks__name {
  font-size: var(--fs-xs);
  color: var(--c-text-sub);
}

.ranks__value {
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--c-text);
  text-align: right;
}

.kpi__value--warn {
  color: var(--c-warn);
}

.skeleton--band {
  height: var(--band-h);
}

.skeleton--body {
  height: 74px;
}

/* ---------- 响应式 ---------- */
@media (max-width: 1280px) {
  .dash__row {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }
}

@media (max-width: 1024px) {
  .dash__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 820px) {
  .dash__row {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 560px) {
  .dash__stats {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>