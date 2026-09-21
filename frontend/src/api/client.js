/**
 * 统一的 HTTP 客户端。
 *
 * 约定（与后端一致）：所有响应都是 { ok: boolean, ... } 的封套。
 * 这里把「网络错误 / 401 / 业务失败」统一收敛成 HttpError，调用方只需 try/catch。
 */

export class HttpError extends Error {
  constructor(message, { status = 0, payload = null } = {}) {
    super(message)
    this.name = 'HttpError'
    this.status = status
    this.payload = payload
  }
}

/** 会话失效时由 App 注册的副作用（跳转登录页），避免此模块直接依赖路由。 */
let onUnauthorized = () => {}
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

function buildUrl(path, query) {
  if (!query) return path
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    params.append(key, value)
  }
  const qs = params.toString()
  return qs ? `${path}?${qs}` : path
}

async function parseBody(response) {
  const type = response.headers.get('content-type') || ''
  if (type.includes('application/json')) {
    return response.json().catch(() => null)
  }
  return response.text().catch(() => null)
}

/**
 * 返回 401 的接口分两类，处理方式相反：
 *   - 需要会话的接口（默认 session: true）：401 说明会话没了，走 onUnauthorized()
 *     统一清会话 + 回登录页，报错文案也统一成「登录状态已失效」。
 *   - 登录接口本身（session: false）：401 是「账号或密码错误」这种业务结果，
 *     会话本来就是空的，此时既不能跳转，也不能覆盖后端给的提示。
 */
async function request(method, path, { query, body, form, signal, session: usesSession = true } = {}) {
  const options = {
    method,
    credentials: 'include', // 分离部署时携带 Session Cookie
    headers: { Accept: 'application/json' },
    signal,
  }

  if (form) {
    options.body = form
  } else if (body !== undefined) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(buildUrl(path, query), options)
  } catch (error) {
    if (error?.name === 'AbortError') throw error
    throw new HttpError('无法连接服务器，请检查网络或后端服务是否启动')
  }

  const payload = await parseBody(response)

  if (response.status === 401) {
    if (usesSession) {
      onUnauthorized()
      throw new HttpError('登录状态已失效，请重新登录', { status: 401, payload })
    }
    throw new HttpError((payload && payload.msg) || '账号或密码错误', { status: 401, payload })
  }

  if (!response.ok) {
    const message = (payload && payload.msg) || `请求失败（${response.status}）`
    throw new HttpError(message, { status: response.status, payload })
  }

  return payload
}

/** 走 <a download> 的二进制/文件下载，避免把 CSV 读进内存再拼 Blob。 */
export function download(path, query) {
  const link = document.createElement('a')
  link.href = buildUrl(path, query)
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

export const http = {
  get: (path, options) => request('GET', path, options),
  post: (path, body, options) => request('POST', path, { ...options, body }),
  put: (path, body, options) => request('PUT', path, { ...options, body }),
  delete: (path, options) => request('DELETE', path, options),
  upload: (path, form) => request('POST', path, { form }),
}