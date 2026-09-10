import { useCallback, useEffect, useState } from 'react'
import { Link } from '@arco-design/web-react'
import {
  Button,
  Input,
  InputNumber,
  Message,
  Modal,
  Popconfirm,
  Select,
  Table,
  Tag,
} from '@arco-design/web-react'
import { IconDelete, IconEye, IconRefresh, IconSearch, IconStorage } from '@arco-design/web-react/icon'
import { api, formatTime } from '../api.js'

function DetailRow({ label, children, mono }) {
  return (
    <div style={{ display: 'flex', gap: 12, padding: '6px 0', borderBottom: '1px solid #f2f3f5' }}>
      <div style={{ width: 96, flex: 'none', color: '#86909c', fontSize: 13 }}>{label}</div>
      <div style={{ flex: 1, minWidth: 0, wordBreak: 'break-all' }}>{children}</div>
    </div>
  )
}

export default function Logs() {
  const [rows, setRows] = useState([])
  const [endpoints, setEndpoints] = useState([])
  const [slug, setSlug] = useState('')
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState('')

  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const [days, setDays] = useState(30)
  const [cleaning, setCleaning] = useState(false)
  const [retention, setRetention] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRows(await api.listLogs(slug))
    } catch (e) {
      Message.error(e.message)
    } finally {
      setLoading(false)
    }
  }, [slug])

  useEffect(() => {
    api.listEndpoints().then(setEndpoints).catch(() => {})
    api.getSettings().then((s) => setRetention(s.log_retention_days)).catch(() => {})
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const openDetail = async (row) => {
    setDetail(row)
    setDetailLoading(true)
    try {
      const full = await api.getLog(row.id)
      setDetail(full)
    } catch (e) {
      Message.error(e.message)
    } finally {
      setDetailLoading(false)
    }
  }

  const doCleanup = async () => {
    if (!days || days < 1) {
      Message.warning('请填写有效的保留天数')
      return
    }
    setCleaning(true)
    try {
      const r = await api.cleanupLogs(days)
      Message.success(`已清理 ${r.deleted} 条，剩余 ${r.remaining} 条`)
      load()
    } catch (e) {
      Message.error(e.message)
    } finally {
      setCleaning(false)
    }
  }

  const doClear = async () => {
    try {
      const r = await api.clearLogs()
      Message.success(`已清空全部日志，剩余 ${r.remaining} 条`)
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  const data = filter
    ? rows.filter((r) =>
        [r.slug, r.error, r.summary, r.ip, r.key_name].some((v) => String(v || '').includes(filter))
      )
    : rows

  const preBlock = (text) => (
    <pre
      className="mono"
      style={{
        background: '#f7f8fa',
        padding: 10,
        borderRadius: 6,
        maxHeight: 240,
        overflow: 'auto',
        margin: 0,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-all',
        fontSize: 12,
      }}
    >
      {text || '-'}
    </pre>
  )

  return (
    <div className="panel">
      <div className="toolbar">
        <Select
          allowClear
          placeholder="全部端点"
          style={{ width: 200 }}
          value={slug || undefined}
          onChange={(v) => setSlug(v || '')}
          options={endpoints.map((e) => ({ label: `${e.slug}（${e.name}）`, value: e.slug }))}
        />
        <Input
          allowClear
          prefix={<IconSearch />}
          placeholder="搜索内容"
          style={{ width: 220 }}
          value={filter}
          onChange={(v) => setFilter(v)}
        />
        <span style={{ flex: 1 }} />
        <Button icon={<IconRefresh />} onClick={load} loading={loading}>
          刷新
        </Button>
      </div>

      <div className="log-clean-bar">
        <span className="text-weak">
          自动清理策略：
          {retention === null ? '加载中…' : retention > 0 ? `保留最近 ${retention} 天` : '未开启（在「系统配置 → 日志」中设置）'}
        </span>
        <span style={{ flex: 1 }} />
        <InputNumber
          min={1}
          max={3650}
          value={days}
          onChange={setDays}
          style={{ width: 120 }}
          suffix="天前"
        />
        <Button onClick={doCleanup} loading={cleaning}>
          清理
        </Button>
        <Popconfirm
          title="确认清空全部调用日志？此操作不可恢复"
          onOk={doClear}
          okText="清空"
          cancelText="取消"
        >
          <Button status="danger" icon={<IconDelete />}>
            清空全部
          </Button>
        </Popconfirm>
      </div>

      <Table
        rowKey="id"
        loading={loading}
        data={data}
        pagination={{ pageSize: 20, sizeOptions: [20, 50, 100], showTotal: true }}
        scroll={{ x: 1200 }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 70, fixed: 'left' },
          { title: '时间', dataIndex: 'ts', width: 170, render: (v) => formatTime(v) },
          { title: '接口', dataIndex: 'slug', width: 130 },
          {
            title: '方法',
            dataIndex: 'method',
            width: 80,
            render: (v) => (v ? <Tag>{v}</Tag> : '-'),
          },
          {
            title: '状态',
            dataIndex: 'ok',
            width: 90,
            render: (v, r) =>
              v ? <Tag color="green">{r.status}</Tag> : <Tag color="red">{r.status}</Tag>,
          },
          { title: '耗时', dataIndex: 'duration_ms', width: 90, render: (v) => `${v} ms` },
          { title: 'IP', dataIndex: 'ip', width: 140 },
          {
            title: '密钥',
            dataIndex: 'key_name',
            width: 120,
            render: (v) => (v ? <span className="mono">{v}</span> : '-'),
          },
          {
            title: '错误',
            dataIndex: 'error',
            width: 150,
            render: (v) => (v ? <Tag color="orange">{v}</Tag> : '-'),
          },
          {
            title: '摘要',
            dataIndex: 'summary',
            ellipsis: true,
            render: (v) => <span className="mono">{v || '-'}</span>,
          },
          {
            title: '操作',
            dataIndex: 'op',
            width: 90,
            fixed: 'right',
            render: (_, r) => (
              <Button size="mini" icon={<IconEye />} onClick={() => openDetail(r)}>
                查看
              </Button>
            ),
          },
        ]}
      />

      <Modal
        title={`调用日志详情 · #${detail?.id ?? ''}`}
        visible={!!detail}
        onCancel={() => setDetail(null)}
        footer={
          <Button type="primary" onClick={() => setDetail(null)}>
            关闭
          </Button>
        }
        style={{ width: 720 }}
      >
        {detailLoading ? (
          <div className="text-weak">加载中…</div>
        ) : detail ? (
          <div>
            <DetailRow label="时间">{formatTime(detail.ts)}</DetailRow>
            <DetailRow label="接口">{detail.slug}</DetailRow>
            <DetailRow label="方法">
              {detail.method ? <Tag>{detail.method}</Tag> : '-'}
            </DetailRow>
            <DetailRow label="状态">
              <Tag color={detail.ok ? 'green' : 'red'}>{detail.status}</Tag>
              {detail.error ? ` · ${detail.error}` : ''}
            </DetailRow>
            <DetailRow label="耗时">{detail.duration_ms} ms</DetailRow>
            <DetailRow label="调用方 IP">{detail.ip || '-'}</DetailRow>
            <DetailRow label="密钥">{detail.key_name || '-'}</DetailRow>
            <div style={{ marginTop: 10, fontSize: 13, color: '#86909c' }}>请求体</div>
            {preBlock(detail.request)}
            <div style={{ marginTop: 10, fontSize: 13, color: '#86909c' }}>响应体</div>
            {preBlock(detail.response)}
            <div style={{ marginTop: 10, fontSize: 13, color: '#86909c' }}>摘要</div>
            {preBlock(detail.summary)}
          </div>
        ) : null}
      </Modal>
    </div>
  )
}
