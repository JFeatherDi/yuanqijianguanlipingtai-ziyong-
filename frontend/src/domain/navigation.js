/**
 * 导航结构 —— 侧边栏与路由标题的唯一事实来源。
 * 叶子项用 to，分组项用 children；两者可混用。
 */
export const NAV_ITEMS = [
  {
    id: 'home',
    label: '主页',
    icon: 'dashboard',
    to: { name: 'dashboard' },
  },
  {
    id: 'parts',
    label: '元器件管理',
    icon: 'chip',
    children: [
      { id: 'parts-list', label: '元器件列表', to: { name: 'components' } },
      { id: 'parts-alerts', label: '库存预警', to: { name: 'alerts' }, badgeKey: 'lowCount' },
    ],
  },
  {
    id: 'stock',
    label: '库存管理',
    icon: 'box',
    children: [
      { id: 'stock-in', label: '入库登记', to: { name: 'stock-in' } },
      { id: 'stock-out', label: '出库领用', to: { name: 'stock-out' } },
    ],
  },
  {
    id: 'records',
    label: '操作记录',
    icon: 'history',
    to: { name: 'records' },
  },
  {
    id: 'data',
    label: '数据管理',
    icon: 'database',
    to: { name: 'data' },
  },
  {
    id: 'settings',
    label: '系统设置',
    icon: 'sliders',
    to: { name: 'settings' },
  },
]

/** 把嵌套结构摊平成「路由名 -> 面包屑」，供顶栏使用。 */
export function buildBreadcrumbs() {
  const map = new Map()
  for (const item of NAV_ITEMS) {
    if (item.to) map.set(item.to.name, [item.label])
    for (const child of item.children ?? []) {
      map.set(child.to.name, [item.label, child.label])
    }
  }
  return map
}

export const BREADCRUMBS = buildBreadcrumbs()