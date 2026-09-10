# API 文档（朱雀 API 网关）

本文档逐端点记录网关自身的 HTTP 接口。除「脚本端点（公开调用）」外，所有 `/admin/*` 接口都需要**管理员会话 Cookie**（由 `/admin/login` 签发），否则返回 `401 unauthorized`。

统一说明：

- **基础地址**：面板部署在哪里，接口就在哪里。例如面板地址 `http://host:8000`，则 `POST http://host:8000/admin/login`。
- **统一响应封套**：成功与业务失败都返回 `200` + 如下结构（HTTP 状态码仅用于传输层错误，如 400/401/404/422/500）：

```json
{ "ok": true, "error": null, "data": { }, "meta": { } }
```

  - `ok`：布尔，业务是否成功。
  - `error`：业务错误码字符串（见文末「错误码表」），成功时为 `null`。
  - `data`：业务数据。
  - `meta`：仅脚本端点返回，含 `slug` / `duration_ms` / `request_id`。

- **鉴权**：
  - 管理接口：请求头 `Cookie: session=<token>`（登录后由浏览器自动携带）。
  - 脚本端点：`X-API-Key: <key>` 请求头，或查询参数 `?api_key=<key>`。

- **通用请求体**：`/admin/*` 的写接口（POST/PUT/PATCH/DELETE 带 body）均使用 `application/json`。文件上传接口（`/admin/endpoints/upload`、`/admin/endpoints/{id}/upload`、`/admin/fs/upload`）使用 `multipart/form-data`。

---

## 目录

1. [认证与管理](#1-认证与管理-admin)
2. [调用日志](#2-调用日志-adminlogs)
3. [设置](#3-设置-adminsettings)
4. [脚本端点管理](#4-脚本端点管理-adminendpoints)
5. [API 密钥管理](#5-api-密钥管理-adminkeys)
6. [API 文档数据](#6-api-文档数据-admindocs-data)
7. [文件管理](#7-文件管理-adminfs)
8. [环境变量](#8-环境变量-adminenv)
9. [系统配置](#9-系统配置-adminsys)
10. [依赖管理](#10-依赖管理-adminpkg)
11. [SSH 终端（WebSocket）](#11-ssh-终端-websocket)
12. [脚本端点（公开调用）](#12-脚本端点公开调用-apirunslug)
13. [错误码表](#13-错误码表)

---

## 1. 认证与管理 (`/admin`)

### `POST /admin/login`
登录并签发会话 Cookie。

**请求体**
```json
{ "username": "admin", "password": "你的密码" }
```
**响应** `200`：
```json
{ "ok": true, "error": null, "data": { "username": "admin" } }
```
登录成功会在响应里写入 `Set-Cookie: session=...; HttpOnly; Path=/`。失败返回 `401` + `{ "ok": false, "error": "invalid_credentials" }`。

### `POST /admin/logout`
注销当前会话（清除 Cookie）。`200`：`{ "ok": true, "error": null, "data": null }`。

### `GET /admin/me`
返回当前登录用户名。`200`：`{ "ok": true, "error": null, "data": { "username": "admin" } }`。

### `GET /admin/system`
返回实时系统资源（CPU/内存）。`data`：
```json
{
  "cpu_usage": 3.2,
  "memory_total": 8372043776,
  "memory_used": 3120562176,
  "memory_available": 5251481600,
  "memory_usage_percent": 37.3,
  "runtime": { "node_version": "v20.x", "npm_version": "10.x", "pip_version": "24.x", "python_version": "3.11.x" }
}
```
`runtime` 为进程生命周期内首次探测后缓存的值（避免每次请求都 spawn 子进程）。

### `GET /admin/overview`
近 24 小时调用概览与统计。`data`：
```json
{
  "total": 123, "success": 120, "fail": 3, "rate429": 1, "deny403": 0,
  "avg_ms": 14,
  "by_endpoint": [ { "slug": "echo", "calls": 100, "fail": 2 } ],
  "by_key":      [ { "key_id": 1, "calls": 80, "fail": 1 } ],
  "settings": { "global_concurrency": "8", "ip_deny": "", "log_retention_days": "0" },
  "runtime": { "node_version": "...", "npm_version": "...", "pip_version": "...", "python_version": "..." },
  "endpoint_count": 2, "key_count": 1
}
```

---

## 2. 调用日志 (`/admin/logs`)

> 每次脚本端点被调用都会记录一条日志，包含完整请求体/响应体（上限 4000 字符）、请求方法、状态码、耗时、调用方 IP 与所用密钥名。

### `GET /admin/logs`
列出最近调用日志（最多 `LOG_LIST_LIMIT=200` 条，按时间倒序）。
- 查询参数：`slug`（可选）按端点筛选。
- 响应 `data`：`call_logs` 行数组，字段：`id, ts, slug, key_id, ip, status, ok, error, duration_ms, summary, method, request, response, key_name`。

### `GET /admin/logs/{log_id}`
查看单条日志完整内容（含 `request` / `response` 全文）。不存在返回 `404 日志不存在`。

### `POST /admin/logs/cleanup`
手动清理：删除早于 `days` 天的日志。
- 请求体：`{ "days": 3 }`（`days` 必须 > 0，否则 `400 请填写有效的保留天数（大于 0）`）。
- 响应：`{ "ok": true, "data": { "deleted": 11, "remaining": 5 } }`。

### `POST /admin/logs/clear`
清空全部调用日志。响应同 cleanup 的 `{ "deleted", "remaining" }`。

---

## 3. 设置 (`/admin/settings`)

### `GET /admin/settings`
返回全部设置键值对，例如：
```json
{ "global_concurrency": "8", "ip_deny": "", "log_retention_days": "0" }
```
- `global_concurrency`：全局脚本并发上限（1–64）。
- `ip_deny`：全局拒绝的 IP 列表（换行/逗号分隔，`*` 通配）。
- `log_retention_days`：日志自动清理保留天数，`0` 表示关闭。

### `PUT /admin/settings`
更新设置（仅传入的键会被更新）。
- 请求体（字段均可选）：
```json
{ "global_concurrency": 8, "ip_deny": "1.2.3.4\n*", "log_retention_days": 3 }
```
- `log_retention_days` 合法范围 `0–3650`；`0` = 关闭自动清理。
- 响应：更新后的全部设置。

> 自动清理由后台任务每小时执行一次：当 `log_retention_days > 0` 时，删除 `ts < now - N 天` 的日志。

---

## 4. 脚本端点管理 (`/admin/endpoints`)

端点 = 一个被暴露为 HTTP 的脚本。`endpoint_public` 公共字段：`id, slug, name, lang, source, path, enabled, timeout_sec, rate_per_min, concurrency, ip_allow, ip_deny, http_methods`。

### `GET /admin/endpoints`
列出全部端点（按 id 倒序），`data` 为端点数组。

### `POST /admin/endpoints/upload`
上传脚本文件创建端点（`multipart/form-data`）。
- 表单字段：
  - `slug`（必填，URL 友好，字母数字 `_-`，≤64）
  - `name`（可选，默认同 slug）
  - `file`（必填，`.py` 或 `.js`，≤2MB）
  - `timeout_sec`（默认 30，1–300）、`rate_per_min`（默认 60）、`concurrency`（默认 2，1–32）
  - `ip_allow`、`ip_deny`（可选，IP 列表）
  - `http_methods`（默认 `GET,POST`）
  - `enabled`（默认 1）
- 文件语言由扩展名推断；`slug` 已存在返回 `400 slug 已存在`。
- 响应：`{ "ok": true, "data": <endpoint_public> }`。

### `POST /admin/endpoints/path`
用容器内已有文件路径注册端点（不复制文件）。
- 请求体：`{ "slug", "name", "path", "enabled", "timeout_sec", "rate_per_min", "concurrency", "ip_allow", "ip_deny", "http_methods" }`。
- `path` 必须是一个已存在的 `.py`/`.js` 文件；返回端点对象或 `400`（路径不存在/类型不支持）。

### `PUT /admin/endpoints/{ep_id}`
更新端点配置（不含脚本内容）。
- 请求体字段同创建（均可选，缺省保留原值）；`path` 若变化会重新校验语言。
- `404 not found` 表示端点不存在。

### `POST /admin/endpoints/{ep_id}/upload`
替换端点的脚本文件（重新上传）。字段：`file`（必填）。返回更新后的端点对象。

### `DELETE /admin/endpoints/{ep_id}`
删除端点并移除其脚本目录（`$SCRIPTS_DIR/<slug>`）。返回 `{ "ok": true, "data": null }`。

### `POST /admin/endpoints/{ep_id}/try`
在后台直接试运行该端点（不走鉴权/限流），用于调试。
- 请求体：`{ "payload": {...}, "query": {...} }`（均为对象，缺省 `{}`）。
- 响应：脚本执行结果（同执行引擎返回：`ok/error/data/exit_code/stderr/request_id`）。

---

## 5. API 密钥管理 (`/admin/keys`)

`key_public` 公共字段：`id, name, key_prefix, enabled, rate_per_min, endpoint_slugs, ip_allow`。**密钥明文仅在创建时返回一次**（`data.secret`）。

### `GET /admin/keys`
列出全部密钥（不含明文）。

### `POST /admin/keys`
创建密钥。
- 请求体：`{ "name", "enabled"(默认 true), "rate_per_min"(默认 120), "endpoint_slugs"(数组或逗号/换行字符串), "ip_allow" }`。
- 响应：`{ "ok": true, "data": { ...key_public, "secret": "sk_xxx" } }`。**务必保存 `secret`**，之后无法再取回。

### `PUT /admin/keys/{key_id}`
更新密钥（名称、启用、频率、可访问端点、IP 白名单）。返回更新后对象。

### `DELETE /admin/keys/{key_id}`
删除密钥。返回 `{ "ok": true, "data": null }`。

---

## 6. API 文档数据 (`/admin/docs-data`)

供「API 文档」页面渲染使用，返回通用调用约定 + 逐端点列表。
- 响应 `data`：
```json
{
  "call": "POST /api/run/{slug}",
  "base": "http://host:8000",
  "header": "X-API-Key: <key>",
  "response": { "ok": true, "error": null, "data": {}, "meta": { "slug": "echo", "duration_ms": 12, "request_id": "abc" } },
  "errors": [ "unauthorized", "endpoint_disabled", "ip_denied", "ip_not_allowed", "forbidden_endpoint", "rate_limited", "busy", "timeout", "runtime_missing", "invalid_json_output", "script_failed", "not_found" ],
  "endpoints": [ <endpoint_public>, ... ]
}
```
`base` 自动取当前访问入口地址。

---

## 7. 文件管理 (`/admin/fs`)

所有路径都相对于数据目录 `DATA_DIR`，**不可越界**（越界返回 `403 路径超出允许范围`）。`entry` 结构：`{ path, name, is_dir, size, mtime }`。

### `GET /admin/fs/list?path=`
列目录。返回 `{ cwd, entries[] }`。`path` 为空表示根（`DATA_DIR`）。

### `POST /admin/fs/mkdir`
新建目录。请求体 `{ "path": "sub/dir" }`。返回新建条目。

### `GET /admin/fs/read?path=file.txt`
读取文件内容（≤2MB）。返回 `{ path, content }`；超过 2MB 返回 `400 文件超过 2MB，请在终端查看`。

### `POST /admin/fs/write`
写入文件。请求体 `{ "path", "content", "overwrite"(默认 false) }`。文件已存在且未设 `overwrite` 返回 `409 文件已存在，请确认覆盖`。

### `POST /admin/fs/upload`
上传文件（`multipart/form-data`）：字段 `file` + 表单字段 `dir`（目标目录，相对 `DATA_DIR`）。文件名做安全处理，越界返回 `403`。

### `POST /admin/fs/delete`
删除文件或目录。请求体 `{ "path" }`。根目录 `""` 返回 `403 不能删除根目录`；目录递归删除。

---

## 8. 环境变量 (`/admin/env`)

`env_public` 字段：`id, name, value, remark, enabled, created_at, updated_at`。变量名规则：字母/数字/下划线，且不能以数字开头，≤128 字符。

### `GET /admin/env`
列出环境变量。
- 查询参数：`keyword`（按 变量名/值/备注 模糊匹配）、`enabled`（`"0"`/`"1"` 过滤）。
- 返回数组。

### `POST /admin/env`
新建变量。请求体 `{ "name", "value", "remark"(≤512), "enabled"(默认 true) }`。重名返回 `400 变量名 xxx 已存在`。

### `PUT /admin/env/{env_id}`
更新变量（名称/值/备注/启用状态）。

### `PATCH /admin/env/{env_id}/toggle`
启用/暂停切换（取反当前 `enabled`）。

### `DELETE /admin/env/{env_id}`
删除变量。

---

## 9. 系统配置 (`/admin/sys`)

### 镜像源 CRUD
`mirror_sources` 字段：`id, manager(pip|npm|apt), name, label, url, enabled, sort, created_at`。

- `GET /admin/sys/mirrors?manager=`：列出镜像源（`manager` 可选过滤）。
- `POST /admin/sys/mirrors`：新增。请求体 `{ "manager", "name", "label", "url", "enabled", "sort" }`。`manager` 须为 pip/npm/apt；同类型下 `name` 不可重复。
- `PUT /admin/sys/mirrors/{mid}`：更新。
- `DELETE /admin/sys/mirrors/{mid}`：删除。

> 依赖安装页会读取此处已启用的镜像源；为空时回落到代码内置默认源。

### `GET /admin/sys/info`
完整系统信息。`data` 含：
```json
{
  "frontend": { "framework": "React 18", "ui": "Arco Design 2.x", "bundler": "Vite 5", "language": "TypeScript / ES2020", "title": "朱雀 API 网关 · 管理面板", "api_base": "/admin" },
  "backend":  { "framework": "FastAPI", "language": "Python 3.11.x", "server": "Uvicorn", "database": "SQLite (WAL)", "started_at": "...", "uptime": "...", "uptime_seconds": 12345 },
  "runtime":  { "node_version": "...", "npm_version": "...", "pip_version": "...", "python_version": "..." },
  "os": { "system": "Linux", "release": "...", "machine": "x86_64", "hostname": "...", "booted_at": "...", "uptime": "...", "cpu_count": 2 },
  "cpu_usage": 3.1,
  "memory_total": ..., "memory_used": ..., "memory_available": ..., "memory_usage_percent": ...,
  "disk_total": ..., "disk_used": ..., "disk_available": ..., "disk_usage_percent": ...,
  "counts": { "endpoints": 2, "api_keys": 1, "env_vars": 3, "logs": 16 },
  "db_size": 24576
}
```

### `POST /admin/sys/password`
修改管理员密码（**必须先验证旧密码**）。
- 请求体：`{ "old_password", "new_password" }`。
- 校验：旧密码非空且正确；新密码 ≥6 位；新旧不能相同；旧密码错误返回 `400 当前密码不正确`。
- 响应：`{ "ok": true, "data": { "username": "admin" } }`。

---

## 10. 依赖管理 (`/admin/pkg`)

### `GET /admin/pkg/status`
返回各包管理器可用性、是否需 `--break-system-packages`、以及当前镜像源列表。
- `data`：`{ pip: bool, npm: bool, apt: bool, break_required: bool, sources: { pip:[...], npm:[...], apt:[...] } }`。

### `GET /admin/pkg/task/{task_id}`
查询安装任务进度。返回 `{ id, manager, status(running|done|failed), exit_code, lines[], created_at }`（`lines` 为最近 400 行日志）。不存在返回 `404 task not found`。

### `GET /admin/pkg/tasks`
最近 20 个任务的概要列表（不含日志行）。

### `POST /admin/pkg/install`
发起安装任务（后台执行，立即返回任务 id）。
- 请求体：`{ "manager": "pip|npm|apt", "packages": "包名1 包名2", "source": "官方/镜像名", "break_system_packages": false }`。
- 行为：
  - `pip`：`pip install -i <source_url> [--break-system-packages] <pkgs>`。
  - `npm`：`npm install -g --registry=<source_url> <pkgs>`。
  - `apt`：先按 `source` 改写 `/etc/apt/sources.list*` 的镜像主机，再 `apt-get update && apt-get install -y <pkgs>`。
- 响应：`{ "ok": true, "data": { "id": "<task_id>", "cmd": "..." } }`。用 `GET /admin/pkg/task/{id}` 轮询结果。安装完成会刷新依赖列表缓存。

### `GET /admin/pkg/list?manager=python|node|linux`
列出已安装依赖（带 60s TTL 缓存）。
- `manager` 取值：`python`(→pip) / `node`(→npm) / `linux`(→apt)。
- 响应 `data`：`{ manager, items:[{name, version, summary?}], total, error, hint? }`。
  - Python：用 `importlib.metadata` 枚举（比 `pip list` 快两个数量级）。
  - Node：扫描全局 `node_modules`（支持 `@scope/pkg`）。
  - Linux：`dpkg-query -W`。

---

## 11. SSH 终端（WebSocket）

### `WS /admin/ws/term`
基于 WebSocket 的 PTY 终端（xterm.js 前端）。
- 鉴权：连接时携带 `Cookie: session=<token>`，未登录返回 close code `4401`。
- 交互：
  - 前端 → 服务端：普通文本写入 PTY；以 `\x1eRESIZE:cols,rows` 开头的消息用于改变窗口尺寸。
  - 服务端 → 前端：PTY 输出（二进制帧）。
- 断开时终止对应 shell 进程。

---

## 12. 脚本端点（公开调用） `POST|GET|PUT|PATCH|DELETE /api/run/{slug}`

无需管理员会话，使用 API 密钥调用。完整鉴权/限流/并发流程见下。

### 鉴权与校验顺序
1. 全局 IP 拒绝列表（`ip_deny`）→ 命中 `403 ip_denied`。
2. 密钥：`X-API-Key` 头或 `?api_key=` 参数；缺失/禁用 → `401 unauthorized`。
3. 密钥 IP 白名单（`ip_allow`，非空时）→ 不在内 `403 ip_not_allowed`。
4. 端点存在性 → 不存在 `404 not_found`；端点停用 `403 endpoint_disabled`。
5. 密钥可访问端点白名单（`endpoint_slugs`，非空时）→ 不含本端点 `403 forbidden_endpoint`。
6. HTTP 方法在端点 `http_methods` 内 → 否则 `405 method_not_allowed`。
7. 端点级 IP 允许/拒绝 → `403 ip_not_allowed` / `403 ip_denied`。
8. 频率限制：端点 `rate_per_min` 与密钥 `rate_per_min`（滑动窗口）→ 超限 `429 rate_limited`（带 `Retry-After`）。
9. 并发限制：端点 `concurrency` 与全局 `global_concurrency`（信号量）→ 占满 `503 busy`。
10. 执行脚本，返回结果。

### 请求
- 方法：端点允许的方法之一。
- Body（POST/PUT/PATCH/DELETE）：JSON，作为 `API_PAYLOAD` 传入脚本；同时 `API_QUERY` 提供查询参数对象，`API_REQUEST_ID` 提供本次请求 ID。
- GET：参数走查询字符串（`api_key` 会被剔除，不传入脚本）。

### 脚本约定
- 优先读环境变量 `API_PAYLOAD`（JSON 字符串），为空则读 `stdin`；解析为对象。
- 读 `API_QUERY`（查询参数对象）。
- 向 `stdout` 打印**一个 JSON 对象**即作为响应 `data`。
- 退出码非 0 → `script_failed`；stdout 非合法 JSON → `invalid_json_output`；超时（端点 `timeout_sec`）→ `timeout`；解释器缺失 → `runtime_missing`。

### 响应
```json
{
  "ok": true,
  "error": null,
  "data": { "echo": { "name": "world" }, "query": { "foo": "bar" } },
  "meta": { "slug": "echo", "duration_ms": 2, "request_id": "a1b2c3d4e5f6" }
}
```
调用会被记录到 `call_logs`（含 `method/request/response/key_name`），可在「调用日志」页查看。

### curl 示例
```bash
# POST + 请求头鉴权
curl -X POST "http://host:8000/api/run/echo" \
  -H "X-API-Key: sk_xxx" \
  -H "Content-Type: application/json" \
  -d '{"name":"world"}'

# GET + 查询参数鉴权（仅当端点允许 GET）
curl "http://host:8000/api/run/echo?api_key=sk_xxx&foo=bar"
```

---

## 13. 错误码表

| error | HTTP | 含义 |
| --- | --- | --- |
| `unauthorized` | 401 | 密钥缺失或已禁用 |
| `endpoint_disabled` | 403 | 端点已停用 |
| `ip_denied` | 403 | IP 在拒绝列表 |
| `ip_not_allowed` | 403 | IP 不在允许白名单 |
| `forbidden_endpoint` | 403 | 密钥无权访问该端点 |
| `rate_limited` | 429 | 触发频率限制（带 `Retry-After`） |
| `busy` | 503 | 并发占满 |
| `timeout` | 200(ok=false) | 脚本执行超时 |
| `runtime_missing` | 200(ok=false) | 缺少 Python/Node 运行时 |
| `invalid_json_output` | 200(ok=false) | 脚本 stdout 非合法 JSON |
| `script_failed` | 200(ok=false) | 脚本非零退出 |
| `not_found` | 404 | 端点不存在 |

> 传输层错误（参数校验 422、未登录 401、资源不存在 404、服务器 500）由统一异常处理器包装为 `{ "ok": false, "error": "<中文或标识>", "data": null }`。
