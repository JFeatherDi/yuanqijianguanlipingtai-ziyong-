/**
 * 接口清单：前端唯一的后端契约视图。
 * 路径集中在此，视图层不出现裸字符串 URL。
 */
import { http } from './client'

const BASE = '/api'

export const authApi = {
  login: (username, password) => http.post(`${BASE}/auth/login`, { username, password }),
  logout: () => http.post(`${BASE}/auth/logout`),
  me: () => http.get(`${BASE}/auth/me`),
}

export const componentApi = {
  list: (query) => http.get(`${BASE}/components`, { query }),
  create: (payload) => http.post(`${BASE}/components`, payload),
  update: (id, payload) => http.put(`${BASE}/components/${id}`, payload),
  remove: (id) => http.delete(`${BASE}/components/${id}`),
}

export const stockApi = {
  inbound: (payload) => http.post(`${BASE}/stock/in`, payload),
  outbound: (payload) => http.post(`${BASE}/stock/out`, payload),
}

export const recordApi = {
  list: (query) => http.get(`${BASE}/records`, { query }),
  upload: (file) => {
    const form = new FormData()
    form.append('file', file)
    return http.upload(`${BASE}/records/import`, form)
  },
  exportPath: `${BASE}/records/export`,
  templatePath: `${BASE}/records/template`,
}

export const statsApi = {
  overview: () => http.get(`${BASE}/stats/overview`),
  categories: () => http.get(`${BASE}/stats/categories`),
  flow: (days) => http.get(`${BASE}/stats/flow`, { query: { days } }),
}