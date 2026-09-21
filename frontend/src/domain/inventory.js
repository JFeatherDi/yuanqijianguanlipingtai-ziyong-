/** 领域字典：枚举值 -> 文案与样式。前后端共用同一份语义，避免散落各处。 */

export const TX_LABELS = {
  init: '初始化',
  in: '入库',
  out: '出库',
  import: '导入',
}

export const TX_TONES = {
  init: 'tag--blue',
  in: 'tag--ok',
  out: 'tag--warn',
  import: 'tag--ghost',
}

export function txLabel(kind) {
  return TX_LABELS[kind] ?? kind ?? '—'
}

export function txTone(kind) {
  return TX_TONES[kind] ?? 'tag--ghost'
}

/** 库存健康度判定 —— 全文唯一实现，列表、徽标、预警页共用。 */
export function stockStatus(component) {
  const stock = Number(component?.stock) || 0
  const threshold = Number(component?.threshold) || 0
  if (threshold <= 0) return 'unguarded'
  if (stock <= 0) return 'empty'
  if (stock <= threshold) return 'low'
  return 'ok'
}

export const STATUS_META = {
  empty: { label: '缺货', tone: 'tag--danger' },
  low: { label: '预警', tone: 'tag--warn' },
  ok: { label: '正常', tone: 'tag--ok' },
  unguarded: { label: '未设阈值', tone: 'tag--ghost' },
}

/** 单位建议值 —— 仅作为输入提示，不做校验限制。 */
export const UNIT_SUGGESTIONS = ['个', '只', '片', '卷', '包', '盒', '盘', '条', '套']