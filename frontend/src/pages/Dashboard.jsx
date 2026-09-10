import { useEffect, useState } from 'react'
import { Message, Progress, Table, Tag } from '@arco-design/web-react'
import { IconRefresh } from '@arco-design/web-react/icon'
import { api, formatBytes } from '../api.js'

function Stat({ label, value, sub }) {
  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [sys, setSys] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [overview, system] = await Promise.all([api.overview(), api.system()])
      setData(overview)
      setSys(system)
    } catch (e) {
      Message.error(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const timer = setInterval(load, 15000)
    return () => clearInterval(timer)
  }, [])

  if (!data) return <div className="panel">加载中...</div>

  const mem = sys?.memory_usage_percent ?? 0

  return (
    <div>
      <div className="stat-grid">
        <Stat label="接口数" value={data.endpoint_count ?? 0} />
        <Stat label="密钥数" value={data.key_count ?? 0} />
        <Stat label="近 24 小时调用" value={data.total ?? 0} />
        <Stat
          label="成功率"
          value={data.total ? `${(((data.success || 0) / data.total) * 100).toFixed(1)}%` : '-'}
          sub={`失败 ${data.fail || 0} 次`}
        />
        <Stat label="平均耗时" value={`${data.avg_ms ?? 0} ms`} />
        <Stat
          label="当前并发 / 上限"
          value={`${data.runtime?.running_global ?? 0} / ${data.settings?.global_concurrency ?? '-'}`}
        />
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>运行环境</h3>
          <span className="spacer" />
          <button className="icon-btn" onClick={load} title="刷新">
            <IconRefresh />
          </button>
        </div>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'center' }}>
          <div style={{ minWidth: 220, flex: 1 }}>
            <div style={{ marginBottom: 6, color: '#86909c', fontSize: 13 }}>
              内存 {formatBytes(sys?.memory_used)} / {formatBytes(sys?.memory_total)}
            </div>
            <Progress percent={Math.min(100, Number(mem) || 0)} />
          </div>
          <div style={{ fontSize: 13, color: '#86909c' }}>
            <div>CPU：{sys?.cpu_usage ?? 0}%</div>
            <div>运行中端点：{Object.values(data.runtime?.running_by_slug || {}).filter((v) => v > 0).length}</div>
            <div>更新时间：{new Date().toLocaleTimeString()}</div>
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>近 24 小时按接口</h3>
        </div>
        <Table
          size="small"
          pagination={false}
          data={data.by_endpoint || []}
          noDataElement="暂无调用"
          columns={[
            { title: '接口', dataIndex: 'slug' },
            {
              title: '调用次数',
              dataIndex: 'calls',
              sorter: (a, b) => a.calls - b.calls,
            },
            {
              title: '失败',
              dataIndex: 'fail',
              render: (v) => (v ? <Tag color="red">{v}</Tag> : <Tag color="green">0</Tag>),
            },
          ]}
          rowKey="slug"
        />
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>近 24 小时按密钥</h3>
        </div>
        <Table
          size="small"
          pagination={{ pageSize: 10 }}
          data={data.by_key || []}
          noDataElement="暂无调用"
          columns={[
            { title: '密钥 ID', dataIndex: 'key_id' },
            { title: '调用次数', dataIndex: 'calls' },
            {
              title: '失败',
              dataIndex: 'fail',
              render: (v) => (v ? <Tag color="red">{v}</Tag> : <Tag color="green">0</Tag>),
            },
          ]}
          rowKey="key_id"
        />
      </div>
    </div>
  )
}
