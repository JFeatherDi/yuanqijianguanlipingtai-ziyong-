<script setup>
/**
 * 出入库共用面板 —— 入库与出库只有方向、文案、校验规则不同，
 * 因此合并为一个组件，由 mode 派生全部差异，避免两份几乎相同的代码。
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import PanelCard from '@/components/ui/PanelCard.vue'
import ComponentPicker from '@/components/ComponentPicker.vue'
import RecordTable from '@/components/RecordTable.vue'
import { stockApi, recordApi } from '@/api/endpoints'
import { STATUS_META, stockStatus } from '@/domain/inventory'
import { useInventoryStore } from '@/stores/inventory'
import { useRefreshSignal } from '@/composables/useRefresh'
import { useToastStore } from '@/stores/toast'
import { formatQuantity } from '@/utils/format'

const props = defineProps({
  mode: { type: String, required: true, validator: (value) => ['in', 'out'].includes(value) },
})

/** mode -> 全部差异的派生表 */
const COPY = {
  in: {
    title: '入库登记',
    verb: '入库',
    records: '最近入库记录',
    button: '确认入库',
    buttonVariant: 'primary',
    qtyLabel: '入库数量',
    qtyPlaceholder: '输入本次入库数量',
    hints: [1, 5, 10, 50],
  },
  out: {
    title: '出库领用',
    verb: '出库',
    records: '最近出库记录',
    button: '确认出库',
    buttonVariant: 'warn',
    qtyLabel: '出库数量',
    qtyPlaceholder: '输入本次出库数量',
    hints: [1, 2, 5, 10],
  },
}

const copy = computed(() => COPY[props.mode])
const route = useRoute()
const inventory = useInventoryStore()
const toast = useToastStore()
const refreshSignal = useRefreshSignal()

const selectedId = ref(null)
const quantity = ref('')
const remark = ref('')
const submitting = ref(false)
const records = ref([])
const recordsLoading = ref(false)

const selected = computed(() =>
  selectedId.value ? inventory.byId(selectedId.value) : null,
)

const available = computed(() => Number(selected.value?.stock) || 0)

const statusMeta = computed(() => STATUS_META[stockStatus(selected.value)] ?? STATUS_META.unguarded)

/** 出库不能超过当前库存 —— 前端先拦一次，后端仍有原子校验兜底。 */
const overLimit = computed(
  () => props.mode === 'out' && Number(quantity.value) > available.value,
)

const canSubmit = computed(
  () => Boolean(selected.value) && Number(quantity.value) > 0 && !overLimit.value,
)

async function loadRecords() {
  recordsLoading.value = true
  try {
    const res = await recordApi.list({ type: props.mode, limit: 12 })
    records.value = res.data ?? []
  } catch {
    records.value = []
  } finally {
    recordsLoading.value = false
  }
}

watch(() => props.mode, loadRecords, { immediate: true })
watch(refreshSignal, () => {
  loadRecords()
  inventory.load({ silent: true }).catch(() => {})
})

/** 从列表页 / 看板的「去入库」带 cid 进来时，自动选中该器件。 */
function applyQuerySelection() {
  const cid = Number(route.query.cid)
  if (cid && inventory.byId(cid)) selectedId.value = cid
}

onMounted(applyQuerySelection)
watch(() => route.query.cid, applyQuerySelection)

function fill(value) {
  quantity.value = String(value)
}

async function submit() {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  try {
    const payload = {
      id: selectedId.value,
      qty: Number(quantity.value),
      remark: remark.value.trim(),
    }
    const res =
      props.mode === 'in' ? await stockApi.inbound(payload) : await stockApi.outbound(payload)

    toast.success(`${copy.value.verb}成功，${selected.value.name} 当前库存 ${formatQuantity(res.stock)}`)
    quantity.value = ''
    remark.value = ''
    await Promise.all([inventory.load({ silent: true }), loadRecords()])
  } catch (error) {
    toast.error(error.message)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="move">
    <PanelCard :title="copy.title">
      <div class="move__grid">
        <section class="move__col" aria-labelledby="move-pick-title">
          <h4 id="move-pick-title" class="move__legend">第一步 · 选择器件</h4>
          <ComponentPicker v-model="selectedId" :components="inventory.items" />
        </section>

        <section class="move__col" aria-labelledby="move-qty-title">
          <h4 id="move-qty-title" class="move__legend">第二步 · 填写{{ copy.verb }}信息</h4>

          <!-- 当前选中器件的即时反馈 -->
          <div v-if="selected" class="move__summary">
            <div class="move__summary-head">
              <span class="move__summary-name">{{ selected.name }}</span>
              <span class="tag" :class="statusMeta.tone">{{ statusMeta.label }}</span>
            </div>
            <dl class="move__facts">
              <div>
                <dt>规格</dt>
                <dd>{{ selected.spec || '—' }}</dd>
              </div>
              <div>
                <dt>库位</dt>
                <dd>{{ selected.location || '—' }}</dd>
              </div>
              <div>
                <dt>当前库存</dt>
                <dd class="move__facts-strong num">
                  {{ formatQuantity(available) }} {{ selected.unit || '个' }}
                </dd>
              </div>
              <div>
                <dt>预警值</dt>
                <dd class="num">{{ formatQuantity(selected.threshold) }}</dd>
              </div>
            </dl>
            <p v-if="props.mode === 'out'" class="move__forecast">
              本次出库后剩余
              <b class="num">{{ formatQuantity(Math.max(available - (Number(quantity) || 0), 0)) }}</b>
              {{ selected.unit || '个' }}
            </p>
          </div>

          <p v-else class="move__placeholder">
            <AppIcon name="info" :size="15" />
            请先在左侧选择一个器件
          </p>

          <div class="field">
            <label class="field__label" for="move-qty">
              {{ copy.qtyLabel }} <span class="req">*</span>
            </label>
            <div class="move__qty">
              <input
                id="move-qty"
                v-model="quantity"
                class="input"
                type="number"
                min="0"
                step="any"
                inputmode="decimal"
                :placeholder="copy.qtyPlaceholder"
                :class="{ 'input--invalid': overLimit }"
                :disabled="!selected"
                :aria-invalid="overLimit"
                @keyup.enter="submit"
              />
              <span class="move__unit">{{ selected?.unit || '个' }}</span>
            </div>
            <div class="move__hints">
              <button
                v-for="hint in copy.hints"
                :key="hint"
                type="button"
                class="move__hint"
                :disabled="!selected"
                @click="fill(hint)"
              >
                {{ hint }}
              </button>
              <button
                v-if="props.mode === 'out' && selected"
                type="button"
                class="move__hint"
                @click="fill(available)"
              >
                全部
              </button>
            </div>
            <p v-if="overLimit" class="field__error">
              出库数量超过当前库存（{{ formatQuantity(available) }}）
            </p>
          </div>

          <div class="field">
            <label class="field__label" for="move-remark">备注</label>
            <input
              id="move-remark"
              v-model="remark"
              class="input"
              :placeholder="props.mode === 'in' ? '选填，例如采购单号' : '选填，例如领用项目'"
              :disabled="!selected"
            />
          </div>

          <AppButton
            :variant="copy.buttonVariant"
            :icon="props.mode === 'in' ? 'arrow-down' : 'arrow-up'"
            :loading="submitting"
            :disabled="!canSubmit"
            block
            @click="submit"
          >
            {{ copy.button }}
          </AppButton>
        </section>
      </div>
    </PanelCard>

    <PanelCard :title="copy.records" flush>
      <template #tools>
        <AppButton size="sm" variant="ghost" icon="refresh" @click="loadRecords">刷新</AppButton>
      </template>
      <RecordTable
        :rows="records"
        :loading="recordsLoading"
        compact
        :empty-title="`还没有${copy.verb}记录`"
        :empty-desc="`完成一次${copy.verb}后，记录会自动出现在这里。`"
      />
    </PanelCard>
  </div>
</template>

<style scoped>
.move {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.move__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
  gap: var(--sp-5);
}

.move__col {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  min-width: 0;
}

.move__legend {
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--c-text-mute);
  letter-spacing: 0.3px;
}

.move__summary {
  border: 1px solid var(--c-border);
  border-left: 3px solid var(--c-primary);
  border-radius: var(--radius);
  background: var(--c-primary-softer);
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.move__summary-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.move__summary-name {
  font-size: var(--fs-md);
  font-weight: 600;
  color: var(--c-text);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.move__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-2) var(--sp-3);
  margin: 0;
}

.move__facts dt {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
}

.move__facts dd {
  margin: 1px 0 0;
  font-size: var(--fs-sm);
  color: var(--c-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.move__facts-strong {
  font-weight: 700;
  color: var(--c-primary-deep);
}

.move__forecast {
  font-size: var(--fs-xs);
  color: var(--c-text-sub);
  padding-top: var(--sp-2);
  border-top: 1px dashed var(--c-border);
}

.move__forecast b {
  color: var(--c-primary-deep);
  font-size: var(--fs-sm);
}

.move__placeholder {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: var(--sp-4);
  border: 1px dashed var(--c-border);
  border-radius: var(--radius);
  background: var(--c-surface-alt);
  font-size: var(--fs-sm);
  color: var(--c-text-mute);
}

.move__qty {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.move__unit {
  font-size: var(--fs-sm);
  color: var(--c-text-mute);
  flex: none;
}

.move__hints {
  display: flex;
  gap: var(--sp-1);
  flex-wrap: wrap;
}

.move__hint {
  height: 24px;
  padding: 0 9px;
  border: 1px solid var(--c-border);
  border-radius: var(--radius-sm);
  background: var(--c-surface);
  color: var(--c-text-sub);
  font-size: var(--fs-xs);
  font-family: var(--font-num);
  cursor: pointer;
  transition: all var(--dur) var(--ease-out);
}

.move__hint:hover:not(:disabled) {
  border-color: var(--c-primary);
  color: var(--c-primary);
  background: var(--c-primary-softer);
}

.move__hint:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

@media (max-width: 1100px) {
  .move__grid {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--sp-4);
  }
}
</style>