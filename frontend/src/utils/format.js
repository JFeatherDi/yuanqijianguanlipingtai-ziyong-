/** 数值与日期格式化。列表、图表、导出共用同一套规则。 */

const NUM_FMT = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 })

/** 1234.5 -> "1,234.5"；整数不显示小数位。 */
export function formatNumber(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return NUM_FMT.format(num)
}

/** 库存等可能出现长小数的场景：最多 2 位，绝不显示 "100.00"。 */
export function formatQuantity(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return Number.isInteger(num) ? String(num) : NUM_FMT.format(num)
}

export function formatPercent(value, digits = 1) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return `${num.toFixed(digits)}%`
}

/** "2026-09-21 13:05:48" -> "2026-09-21 13:05" */
export function formatDateTime(value) {
  if (!value) return '—'
  const text = String(value).replace('T', ' ')
  return text.length >= 16 ? text.slice(0, 16) : text
}

/** 只取时间部分，用于「实时动态」列表。 */
export function formatTime(value) {
  if (!value) return '—'
  const text = String(value).replace('T', ' ')
  return text.length >= 16 ? text.slice(11, 16) : text
}

/** 图表 X 轴：2026-09-21 -> 09-21，避免标签拥挤。 */
export function formatShortDate(value) {
  const text = String(value ?? '')
  return text.length >= 10 ? text.slice(5) : text
}

/** 表格单元格的安全展示：空值统一成 "—"。 */
export function display(value) {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

/** 带符号的库存变化量。 */
export function formatDelta(delta) {
  const num = Number(delta)
  if (!Number.isFinite(num)) return '—'
  const sign = num > 0 ? '+' : ''
  return `${sign}${formatQuantity(num)}`
}