/**
 * 接口清单：前端唯一的后端契约视图。
 * 路径集中在此，视图层不出现裸字符串 URL。
 */
import { http } from './client'

const BASE = '/api'

export const authApi = {
  // 登录接口自己不依赖会话：400 是验证码不对、401 是账号密码不对，
  // 都是业务结果而非「会话失效」，所以显式声明，别让 401 触发跳转逻辑
  login: (payload) => http.post(`${BASE}/auth/login`, payload, { session: false }),
  logout: () => http.post(`${BASE}/auth/logout`),
  me: () => http.get(`${BASE}/auth/me`),
  // 验证码交给 <img> 直接引用：浏览器会自己带 Cookie，也省掉 fetch + blob 两步
  captchaPath: `${BASE}/auth/captcha`,
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