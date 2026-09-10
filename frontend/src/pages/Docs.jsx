import { useEffect, useMemo, useState } from 'react'
import { Message, Tag } from '@arco-design/web-react'
import { IconCopy } from '@arco-design/web-react/icon'
import { api } from '../api.js'

function buildCurl(ep, base) {
  const url = `${base}/api/run/${ep.slug}`
  const methods = (ep.http_methods || 'POST')
    .split(',')
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean)
  const verb = methods[0] || 'POST'
  const isBody = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(verb)
  if (isBody) {
    return `curl -X ${verb} "${url}" \\\n  -H "X-API-Key: YOUR_KEY" \\\n  -H "Content-Type: application/json" \\\n  -d '{"key": "value"}'`
  }
  return `curl -X ${verb} "${url}?api_key=YOUR_KEY&foo=bar"`
}

function EndpointCard({ ep, base }) {
  const curl = useMemo(() => buildCurl(ep, base), [ep, base])
  const methods = (ep.http_methods || 'POST')
    .split(',')
    .map((s) => s.trim().toUpperCase())
    .filter(Boolean)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(curl)
      Message.success('已复制调用示例')
    } catch (e) {
      Message.error('复制失败，请手动选择')
    }
  }

  return (
    <div className="doc-card">
      <div className="doc-card-head">
        <div>
          <span className="doc-slug mono">{ep.slug}</span>
          <span className="doc-name">{ep.name}</span>
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <Tag color="arcoblue">{ep.lang === 'python' ? 'Python' : 'Node.js'}</Tag>
          {methods.map((m) => (
            <Tag key={m}>{m}</Tag>
          ))}
          {!ep.enabled && <Tag color="red">已停用</Tag>}
        </div>
      </div>

      <div className="doc-meta">
        <span>超时 {ep.timeout_sec}s</span>
        <span>频率 {ep.rate_per_min}/分</span>
        <span>并发 {ep.concurrency}</span>
      </div>

      <div className="doc-curl-wrap">
        <pre className="mono doc-curl">{curl}</pre>
        <Buttonish onClick={copy}>
          <IconCopy /> 复制
        </Buttonish>
      </div>
      <div className="doc-hint">
        脚本从 <code className="mono">stdin</code> 或环境变量{' '}
        <code className="mono">API_PAYLOAD</code> 读取 JSON，向 <code className="mono">stdout</code> 打印 JSON 即作为响应；
        <code className="mono">API_QUERY</code> 提供查询参数。
      </div>
    </div>
  )
}

function Buttonish({ children, onClick }) {
  return (
    <button className="doc-copy-btn" onClick={onClick}>
      {children}
    </button>
  )
}

export default function Docs() {
  const [data, setData] = useState(null)

  useEffect(() => {
    api
      .docs()
      .then(setData)
      .catch((e) => Message.error(e.message))
  }, [])

  if (!data) return <div className="panel">加载中…</div>

  const base = data.base || ''
  const endpoints = data.endpoints || []

  return (
    <div>
      <div className="panel">
        <div className="panel-head">
          <h3>通用调用约定</h3>
        </div>
        <p style={{ margin: '4px 0' }}>
          调用地址：<code className="mono">{data.call}</code>
        </p>
        <p style={{ margin: '4px 0' }}>
          鉴权方式：请求头 <code className="mono">{data.header}</code>，或查询参数{' '}
          <code className="mono">?api_key=YOUR_KEY</code>
        </p>
        <div style={{ marginTop: 10, fontWeight: 600 }}>脚本约定</div>
        <p style={{ color: '#4e5969', lineHeight: 1.8, margin: '4px 0' }}>
          脚本从 <code className="mono">stdin</code> 或环境变量 <code className="mono">API_PAYLOAD</code> 读取
          JSON，向 <code className="mono">stdout</code> 打印 JSON 即作为响应体；超时被端点配置控制。
        </p>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>脚本端点文档（{endpoints.length}）</h3>
        </div>
        {endpoints.length === 0 ? (
          <div className="text-weak">还没有任何脚本端点，请到「端点管理」上传脚本。</div>
        ) : (
          <div className="doc-grid">
            {endpoints.map((ep) => (
              <EndpointCard key={ep.id} ep={ep} base={base} />
            ))}
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>错误码</h3>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {(data.errors || []).map((e) => (
            <Tag key={e} className="mono">
              {e}
            </Tag>
          ))}
        </div>
      </div>
    </div>
  )
}
