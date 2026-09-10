const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function request(url, options = {}) {
  const res = await fetch(url, {
    credentials: 'same-origin',
    ...options,
    headers: { ...(options.headers || {}) },
  })
  if (res.status === 401) {
    if (!location.hash.startsWith('#/login') && location.pathname !== '/login') {
      location.href = '/login'
    }
    throw new Error('登录已过期，请重新登录')
  }
  let data
  try {
    data = await res.json()
  } catch (e) {
    throw new Error('服务返回异常')
  }
  if (!data.ok) throw new Error(data.error || data.detail || '请求失败')
  return data.data
}

const get = (url) => request(url)
const post = (url, body) =>
  request(url, { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body || {}) })
const put = (url, body) =>
  request(url, { method: 'PUT', headers: JSON_HEADERS, body: JSON.stringify(body || {}) })
const patch = (url, body) =>
  request(url, { method: 'PATCH', headers: JSON_HEADERS, body: JSON.stringify(body || {}) })
const del = (url) => request(url, { method: 'DELETE' })

export const api = {
  // 鉴权
  login: (username, password) => post('/admin/login', { username, password }),
  logout: () => post('/admin/logout'),
  me: () => get('/admin/me'),

  // 概览与系统
  overview: () => get('/admin/overview'),
  system: () => get('/admin/system'),
  sysInfo: () => get('/admin/sys/info'),
  changePassword: (old_password, new_password) =>
    post('/admin/sys/password', { old_password, new_password }),

  // 设置
  getSettings: () => get('/admin/settings'),
  saveSettings: (data) => put('/admin/settings', data),

  // 端点
  listEndpoints: () => get('/admin/endpoints'),
  uploadEndpoint: (formData) =>
    request('/admin/endpoints/upload', { method: 'POST', body: formData }),
  pathEndpoint: (data) => post('/admin/endpoints/path', data),
  updateEndpoint: (id, data) => put(`/admin/endpoints/${id}`, data),
  deleteEndpoint: (id) => del(`/admin/endpoints/${id}`),
  replaceScript: (id, formData) =>
    request(`/admin/endpoints/${id}/upload`, { method: 'POST', body: formData }),
  tryEndpoint: (id, payload) => post(`/admin/endpoints/${id}/try`, payload),

  // 密钥
  listKeys: () => get('/admin/keys'),
  createKey: (data) => post('/admin/keys', data),
  updateKey: (id, data) => put(`/admin/keys/${id}`, data),
  deleteKey: (id) => del(`/admin/keys/${id}`),

  // 日志
  listLogs: (slug) => get(`/admin/logs${slug ? `?slug=${encodeURIComponent(slug)}` : ''}`),
  getLog: (id) => get(`/admin/logs/${id}`),
  cleanupLogs: (days) => post('/admin/logs/cleanup', { days }),
  clearLogs: () => post('/admin/logs/clear', {}),

  // 文件
  fsList: (path) => get(`/admin/fs/list?path=${encodeURIComponent(path || '')}`),
  fsRead: (path) => get(`/admin/fs/read?path=${encodeURIComponent(path)}`),
  fsWrite: (data) => post('/admin/fs/write', data),
  fsMkdir: (data) => post('/admin/fs/mkdir', data),
  fsDelete: (path) => post('/admin/fs/delete', { path }),
  fsUpload: (formData) => request('/admin/fs/upload', { method: 'POST', body: formData }),

  // 依赖
  pkgStatus: () => get('/admin/pkg/status'),
  pkgList: (manager) => get(`/admin/pkg/list?manager=${encodeURIComponent(manager)}`),
  pkgInstall: (data) => post('/admin/pkg/install', data),
  pkgTask: (id) => get(`/admin/pkg/task/${id}`),
  pkgTasks: () => get('/admin/pkg/tasks'),

  // 环境变量
  listEnv: (keyword) => get(`/admin/env${keyword ? `?keyword=${encodeURIComponent(keyword)}` : ''}`),
  createEnv: (data) => post('/admin/env', data),
  updateEnv: (id, data) => put(`/admin/env/${id}`, data),
  toggleEnv: (id) => patch(`/admin/env/${id}/toggle`),
  deleteEnv: (id) => del(`/admin/env/${id}`),

  // 镜像源
  listMirrors: (manager) =>
    get(`/admin/sys/mirrors${manager ? `?manager=${encodeURIComponent(manager)}` : ''}`),
  createMirror: (data) => post('/admin/sys/mirrors', data),
  updateMirror: (id, data) => put(`/admin/sys/mirrors/${id}`, data),
  deleteMirror: (id) => del(`/admin/sys/mirrors/${id}`),

  // 文档
  docs: () => get('/admin/docs-data'),
}

export function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let n = Number(bytes)
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024
    i += 1
  }
  return `${n.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

export function formatTime(text) {
  if (!text) return '-'
  return String(text).replace('T', ' ').slice(0, 19)
}
