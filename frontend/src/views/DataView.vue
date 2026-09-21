<script setup>
/**
 * 数据管理：Excel / CSV 批量导入、导出、模板下载。
 * 导入规则与后端 services/importer.py 的表头别名表保持一致。
 */
import { computed, ref } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppIcon from '@/components/ui/AppIcon.vue'
import PanelCard from '@/components/ui/PanelCard.vue'
import { download } from '@/api/client'
import { recordApi } from '@/api/endpoints'
import { useInventoryStore } from '@/stores/inventory'
import { useToastStore } from '@/stores/toast'
import { formatQuantity } from '@/utils/format'

const ACCEPT = '.csv,.xlsx,.xlsm'

const COLUMNS = [
  { name: '名称', required: true, note: '必填，同名同规格视为同一器件' },
  { name: '分类', required: false, note: '例如 电阻 / 电容 / 芯片' },
  { name: '规格', required: false, note: '例如 0805 1%' },
  { name: '单位', required: false, note: '缺省为「个」' },
  { name: '位置', required: false, note: '例如 A柜-1层' },
  { name: '库存', required: false, note: '数字，缺省 0' },
  { name: '预警值', required: false, note: '数字，0 表示不预警' },
  { name: '备注', required: false, note: '自由文本' },
]

const inventory = useInventoryStore()
const toast = useToastStore()

const fileInput = ref(null)
const selected = ref(null)
const dragging = ref(false)
const uploading = ref(false)

const fileMeta = computed(() => {
  if (!selected.value) return ''
  const kb = selected.value.size / 1024
  return kb >= 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb.toFixed(0)} KB`
})

const stats = computed(() => [
  { label: '元器件种类', value: formatQuantity(inventory.total) },
  { label: '总库存量', value: formatQuantity(inventory.totalStock) },
  { label: '预警项', value: formatQuantity(inventory.lowCount), tone: inventory.lowCount ? 'warn' : '' },
  { label: '已有分类', value: formatQuantity(inventory.options.categories.length) },
])

function pick(file) {
  if (!file) return
  const suffix = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!ACCEPT.split(',').includes(suffix)) {
    toast.warning('仅支持 .csv / .xlsx / .xlsm 文件')
    return
  }
  selected.value = file
}

function openPicker() {
  fileInput.value?.click()
}

function onFileChange(event) {
  pick(event.target.files?.[0])
  event.target.value = ''
}

function onDrop(event) {
  dragging.value = false
  pick(event.dataTransfer?.files?.[0])
}

async function submit() {
  if (!selected.value || uploading.value) return
  uploading.value = true
  try {
    const res = await recordApi.upload(selected.value)
    toast.success(`导入完成：处理 ${res.imported} 条，跳过 ${res.skipped} 条空行`)
    selected.value = null
    await inventory.load({ silent: true })
  } catch (error) {
    toast.error(error.message)
  } finally {
    uploading.value = false
  }
}

function exportAll() {
  download(recordApi.exportPath)
  toast.info('正在导出元器件清单')
}

function downloadTemplate() {
  download(recordApi.templatePath)
  toast.info('正在下载导入模板')
}

async function refresh() {
  try {
    await inventory.load()
    toast.success('数据已刷新')
  } catch (error) {
    toast.error(error.message)
  }
}
</script>

<template>
  <div class="data">
    <div class="data__grid">
      <!-- 导入 -->
      <PanelCard title="批量导入">
        <p class="data__lead">
          支持 <b>Excel (.xlsx / .xlsm)</b> 与 <b>CSV</b>。表头顺序不限，中英文列名均可识别；
          <b>名称 + 规格</b>都相同的行会累加到已有库存，而不是新建重复器件。
        </p>

        <div
          class="drop"
          :class="{ 'is-dragging': dragging }"
          role="button"
          tabindex="0"
          aria-label="选择或拖入要导入的文件"
          @click="openPicker"
          @keydown.enter="openPicker"
          @keydown.space.prevent="openPicker"
          @dragover.prevent="dragging = true"
          @dragenter.prevent="dragging = true"
          @dragleave="dragging = false"
          @drop.prevent="onDrop"
        >
          <AppIcon name="upload" :size="26" class="drop__icon" />
          <p class="drop__title">把文件拖到这里，或点击选择</p>
          <p class="drop__hint">单个文件不超过 8 MB</p>

          <p v-if="selected" class="drop__file">
            <AppIcon name="file" :size="14" />
            <span class="truncate">{{ selected.name }}</span>
            <span class="muted">{{ fileMeta }}</span>
          </p>
        </div>

        <input
          ref="fileInput"
          class="sr-only"
          type="file"
          :accept="ACCEPT"
          aria-hidden="true"
          tabindex="-1"
          @change="onFileChange"
        />

        <div class="data__actions">
          <AppButton
            variant="primary"
            icon="check"
            block
            :loading="uploading"
            :disabled="!selected"
            @click="submit"
          >
            {{ selected ? '确认导入' : '请先选择文件' }}
          </AppButton>
        </div>

        <h4 class="data__sub">可识别的列</h4>
        <ul class="columns">
          <li v-for="column in COLUMNS" :key="column.name" class="columns__item">
            <span class="tag" :class="column.required ? 'tag--blue' : 'tag--ghost'">
              {{ column.name }}{{ column.required ? ' *' : '' }}
            </span>
            <span class="columns__note">{{ column.note }}</span>
          </li>
        </ul>
      </PanelCard>

      <!-- 导出 -->
      <div class="data__side">
        <PanelCard title="导出与模板">
          <div class="data__stack">
            <AppButton icon="download" block @click="exportAll">导出全部元器件 (CSV)</AppButton>
            <AppButton icon="file" block @click="downloadTemplate">下载导入模板 (CSV)</AppButton>
            <AppButton icon="refresh" block @click="refresh">刷新元器件数据</AppButton>
          </div>

          <p class="data__note">
            导出按「分类 → 名称」排序，使用 UTF-8 带 BOM 编码，Excel 直接打开不会中文乱码。
            导出内容是当前元器件清单与库存，不含历史流水。
          </p>

          <div class="data__divider" />

          <div class="kpi-strip">
            <div v-for="item in stats" :key="item.label" class="kpi">
              <span class="kpi__label">{{ item.label }}</span>
              <span class="kpi__value" :class="{ 'kpi__value--warn': item.tone === 'warn' }">
                {{ item.value }}
              </span>
            </div>
          </div>
        </PanelCard>

        <PanelCard title="导入前的检查">
          <ul class="tips">
            <li class="tips__item">
              <AppIcon name="check-circle" :size="15" />
              <span>先点「下载导入模板」，按模板列填好数据，成功率最高。</span>
            </li>
            <li class="tips__item">
              <AppIcon name="check-circle" :size="15" />
              <span>「库存」列填的是<strong>本次增量</strong>，不是覆盖值。</span>
            </li>
            <li class="tips__item">
              <AppIcon name="check-circle" :size="15" />
              <span>导入会写入流水，可在「操作记录」页按类型「导入」追溯。</span>
            </li>
            <li class="tips__item">
              <AppIcon name="alert-circle" :size="15" />
              <span>名称为空的行会被跳过；导入前建议先导出一份做备份。</span>
            </li>
          </ul>
        </PanelCard>
      </div>
    </div>
  </div>
</template>

<style scoped>
.data {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.data__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--sp-3);
  align-items: start;
}

.data__side {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.data__lead {
  font-size: var(--fs-sm);
  color: var(--c-text-sub);
  line-height: 1.7;
  margin-bottom: var(--sp-4);
}

.data__lead b {
  color: var(--c-text);
}

/* ---------- 拖放区 ---------- */
.drop {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: var(--sp-6) var(--sp-4);
  border: 1px dashed var(--c-border);
  border-radius: var(--radius-md);
  background: var(--c-surface-alt);
  cursor: pointer;
  transition: border-color var(--dur) var(--ease-out), background var(--dur) var(--ease-out);
}

.drop:hover {
  border-color: var(--c-primary);
  background: var(--c-primary-softer);
}

.drop.is-dragging {
  border-color: var(--c-primary);
  border-style: solid;
  background: var(--c-primary-soft);
}

.drop__icon {
  color: var(--c-primary);
}

.drop__title {
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--c-text);
}

.drop__hint {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
}

.drop__file {
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  margin-top: var(--sp-2);
  padding: 5px 10px;
  border-radius: var(--radius);
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  font-size: var(--fs-xs);
  color: var(--c-text-sub);
}

.data__actions {
  margin-top: var(--sp-3);
}

.data__sub {
  margin-top: var(--sp-5);
  padding-top: var(--sp-4);
  border-top: 1px solid var(--c-border-soft);
  font-size: var(--fs-sm);
  font-weight: 600;
  color: var(--c-text);
}

.columns {
  margin-top: var(--sp-3);
  display: grid;
  gap: var(--sp-2);
}

.columns__item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}

.columns__item .tag {
  flex: none;
  min-width: 62px;
  justify-content: center;
}

.columns__note {
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.data__stack {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.data__note {
  margin-top: var(--sp-3);
  font-size: var(--fs-xs);
  color: var(--c-text-mute);
  line-height: 1.7;
}

.data__divider {
  height: 1px;
  background: var(--c-border-soft);
  margin: var(--sp-4) 0;
}

.kpi__value--warn {
  color: var(--c-warn);
}

.tips {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.tips__item {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  font-size: var(--fs-sm);
  color: var(--c-text-sub);
  line-height: 1.6;
}

.tips__item svg {
  margin-top: 2px;
  color: var(--c-primary);
  flex: none;
}

.tips__item strong {
  color: var(--c-text);
}

@media (max-width: 900px) {
  .data__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>