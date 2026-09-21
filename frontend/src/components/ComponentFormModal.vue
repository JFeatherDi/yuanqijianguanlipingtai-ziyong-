<script setup>
/** 新增 / 编辑器件弹窗。字段与后端 catalog.EDITABLE_FIELDS 一一对应。 */
import { computed, reactive, ref, watch } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { UNIT_SUGGESTIONS } from '@/domain/inventory'
import { useInventoryStore } from '@/stores/inventory'
import { useToastStore } from '@/stores/toast'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  component: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const inventory = useInventoryStore()
const toast = useToastStore()

const form = reactive(emptyForm())
const nameError = ref('')
const submitting = ref(false)
const openingStock = ref('0')

const isEditing = computed(() => Boolean(props.component?.id))

const unitOptions = computed(() =>
  [...new Set([...inventory.options.units, ...UNIT_SUGGESTIONS])].sort(),
)

function emptyForm() {
  return {
    name: '',
    category: '',
    spec: '',
    unit: '个',
    location: '',
    threshold: 0,
    remark: '',
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    const source = props.component ?? {}
    Object.assign(form, emptyForm(), {
      name: source.name ?? '',
      category: source.category ?? '',
      spec: source.spec ?? '',
      unit: source.unit || '个',
      location: source.location ?? '',
      threshold: source.threshold ?? 0,
      remark: source.remark ?? '',
    })
    openingStock.value = '0'
    nameError.value = ''
  },
)

// 用户一旦补上名称就立刻撤掉报错，不必等到再次提交
watch(
  () => form.name,
  (value) => {
    if (value.trim()) nameError.value = ''
  },
)

function validate() {
  const name = form.name.trim()
  if (!name) {
    nameError.value = '请输入器件名称'
    return false
  }
  nameError.value = ''
  return true
}

async function submit() {
  if (!validate() || submitting.value) return
  submitting.value = true
  try {
    const payload = {
      name: form.name.trim(),
      category: form.category.trim(),
      spec: form.spec.trim(),
      unit: form.unit.trim() || '个',
      location: form.location.trim(),
      threshold: Number(form.threshold) || 0,
      remark: form.remark.trim(),
    }

    if (isEditing.value) {
      await inventory.update(props.component.id, payload)
      toast.success('器件信息已更新')
    } else {
      await inventory.create({ ...payload, stock: Number(openingStock.value) || 0 })
      toast.success('器件已添加')
    }

    emit('saved')
    emit('update:modelValue', false)
  } catch (error) {
    toast.error(error.message)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <AppModal
    :model-value="modelValue"
    :title="isEditing ? '编辑器件' : '新增器件'"
    width="580px"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <form class="form" @submit.prevent="submit">
      <div class="field">
        <label class="field__label" for="f-name">器件名称 <span class="req">*</span></label>
        <input
          id="f-name"
          v-model="form.name"
          class="input"
          :class="{ 'input--invalid': nameError }"
          placeholder="例如：电阻 10K"
          autocomplete="off"
          :aria-invalid="Boolean(nameError)"
          aria-describedby="f-name-error"
          @blur="nameError = form.name.trim() ? '' : nameError"
        />
        <p v-if="nameError" id="f-name-error" class="field__error">{{ nameError }}</p>
      </div>

      <div class="field-grid">
        <div class="field">
          <label class="field__label" for="f-category">分类</label>
          <input
            id="f-category"
            v-model="form.category"
            class="input"
            list="dl-category"
            placeholder="例如：电阻"
            autocomplete="off"
          />
          <datalist id="dl-category">
            <option v-for="item in inventory.options.categories" :key="item" :value="item" />
          </datalist>
        </div>

        <div class="field">
          <label class="field__label" for="f-spec">规格 / 型号</label>
          <input
            id="f-spec"
            v-model="form.spec"
            class="input"
            placeholder="例如：0805 1%"
            autocomplete="off"
          />
        </div>

        <div class="field">
          <label class="field__label" for="f-unit">单位</label>
          <input id="f-unit" v-model="form.unit" class="input" list="dl-unit" autocomplete="off" />
          <datalist id="dl-unit">
            <option v-for="item in unitOptions" :key="item" :value="item" />
          </datalist>
        </div>

        <div class="field">
          <label class="field__label" for="f-location">存放位置</label>
          <input
            id="f-location"
            v-model="form.location"
            class="input"
            list="dl-location"
            placeholder="例如：A柜-1层"
            autocomplete="off"
          />
          <datalist id="dl-location">
            <option v-for="item in inventory.options.locations" :key="item" :value="item" />
          </datalist>
        </div>

        <div v-if="!isEditing" class="field">
          <label class="field__label" for="f-stock">初始库存</label>
          <input
            id="f-stock"
            v-model="openingStock"
            class="input"
            type="number"
            min="0"
            step="any"
            inputmode="decimal"
          />
          <p class="field__hint">会写入一条「初始化」流水</p>
        </div>

        <div class="field">
          <label class="field__label" for="f-threshold">预警值</label>
          <input
            id="f-threshold"
            v-model="form.threshold"
            class="input"
            type="number"
            min="0"
            step="any"
            inputmode="decimal"
          />
          <p class="field__hint">库存小于等于该值时进入预警；填 0 表示不预警</p>
        </div>
      </div>

      <div class="field">
        <label class="field__label" for="f-remark">备注</label>
        <input
          id="f-remark"
          v-model="form.remark"
          class="input"
          placeholder="选填，例如供应商、批次"
          autocomplete="off"
        />
      </div>
    </form>

    <template #footer>
      <AppButton @click="emit('update:modelValue', false)">取消</AppButton>
      <AppButton variant="primary" :loading="submitting" @click="submit">
        {{ isEditing ? '保存修改' : '确认新增' }}
      </AppButton>
    </template>
  </AppModal>
</template>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
</style>