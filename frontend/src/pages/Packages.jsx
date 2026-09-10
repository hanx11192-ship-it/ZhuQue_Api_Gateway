import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Button,
  Input,
  Message,
  Modal,
  Progress,
  Select,
  Space,
  Switch,
  Table,
  Empty,
  Tabs,
  Tag,
} from '@arco-design/web-react'
import { IconDownload, IconRefresh, IconSearch } from '@arco-design/web-react/icon'
import { api } from '../api.js'

const TABS = [
  { key: 'python', label: 'Python', manager: 'pip', placeholder: '例如 requests fastapi uvicorn' },
  { key: 'node', label: 'Node.js', manager: 'npm', placeholder: '例如 lodash axios express' },
  { key: 'linux', label: 'Linux', manager: 'apt', placeholder: '例如 curl git ffmpeg，多个用空格分隔' },
]

export default function Packages() {
  const [active, setActive] = useState('python')
  const [status, setStatus] = useState(null)
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [listError, setListError] = useState('')
  const [hint, setHint] = useState('')
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(false)

  const [installVisible, setInstallVisible] = useState(false)
  const [form, setForm] = useState({
    manager: 'pip',
    packages: '',
    source: 'official',
    break_system_packages: false,
  })
  const [installing, setInstalling] = useState(false)
  const [logs, setLogs] = useState([])
  const [taskId, setTaskId] = useState('')
  const [progress, setProgress] = useState(0)
  const pollRef = useRef(null)

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await api.pkgStatus())
    } catch (e) {
      Message.error(e.message)
    }
  }, [])

  const loadList = useCallback(async (tab) => {
    setLoading(true)
    setListError('')
    try {
      const data = await api.pkgList(tab)
      setItems(data.items || [])
      setTotal(data.total || 0)
      setListError(data.error || '')
      setHint(data.hint || '')
    } catch (e) {
      setListError(e.message)
      setHint('')
      setItems([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadStatus()
  }, [loadStatus])

  useEffect(() => {
    loadList(active)
  }, [active, loadList])

  useEffect(() => () => clearInterval(pollRef.current), [])

  const current = TABS.find((t) => t.key === active)

  const filtered = keyword
    ? items.filter((i) => (i.name || '').toLowerCase().includes(keyword.toLowerCase()))
    : items

  const sources =
    status?.sources?.[TABS.find((t) => t.key === active)?.manager || 'pip'] || []

  // 安装弹窗里按选中的依赖类型取镜像源
  const formSources = status?.sources?.[form.manager] || []

  const openInstall = () => {
    const manager = current?.manager || 'pip'
    setForm({
      manager,
      packages: '',
      source: (status?.sources?.[manager]?.[0]?.name) || 'official',
      break_system_packages: manager === 'pip' ? Boolean(status?.break_required) : false,
    })
    setInstallVisible(true)
  }

  const startInstall = async () => {
    const packages = (form.packages || '').trim()
    if (!packages) {
      Message.warning('请输入要安装的包名')
      return
    }
    setInstalling(true)
    setLogs([])
    setProgress(10)
    try {
      const data = await api.pkgInstall({
        manager: form.manager,
        packages,
        source: form.source,
        break_system_packages: form.break_system_packages,
      })
      setTaskId(data.id)
      Message.success('安装任务已启动')
      setInstallVisible(false)

      clearInterval(pollRef.current)
      pollRef.current = setInterval(async () => {
        try {
          const t = await api.pkgTask(data.id)
          setLogs(t.lines || [])
          setProgress(t.status === 'running' ? 60 : 100)
          if (t.status !== 'running') {
            clearInterval(pollRef.current)
            setInstalling(false)
            if (t.status === 'done') {
              Message.success('安装完成')
            } else {
              Message.error('安装失败，请查看日志')
            }
            loadList(active)
          }
        } catch (e) {
          clearInterval(pollRef.current)
          setInstalling(false)
        }
      }, 1500)
    } catch (e) {
      Message.error(e.message)
      setInstalling(false)
      setProgress(0)
    }
  }

  return (
    <div className="panel">
      <div className="toolbar">
        <Button type="primary" icon={<IconDownload />} onClick={openInstall}>
          依赖安装
        </Button>
        <span style={{ flex: 1 }} />
        <Input
          allowClear
          prefix={<IconSearch />}
          placeholder="搜索已安装依赖"
          style={{ width: 220 }}
          value={keyword}
          onChange={setKeyword}
        />
        <Button icon={<IconRefresh />} onClick={() => loadList(active)} loading={loading}>
          刷新
        </Button>
      </div>

      <div style={{ marginBottom: 12, display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 13 }}>
        <span className="text-weak">
          运行环境：Python {status?.pip ? <Tag color="green">可用</Tag> : <Tag color="red">不可用</Tag>}
        </span>
        <span className="text-weak">
          Node.js {status?.npm ? <Tag color="green">可用</Tag> : <Tag color="red">不可用</Tag>}
        </span>
        <span className="text-weak">
          APT {status?.apt ? <Tag color="green">可用</Tag> : <Tag color="red">不可用</Tag>}
        </span>
      </div>

      <Tabs activeTab={active} onChange={(k) => { setActive(k); setKeyword('') }}>
        {TABS.map((t) => (
          <Tabs.TabPane key={t.key} title={`${t.label}`} />
        ))}
      </Tabs>

      <div style={{ marginBottom: 8 }}>
        <Tag>共 {total} 个</Tag>
        {keyword && <Tag color="arcoblue">筛选后 {filtered.length} 个</Tag>}
        {listError && <Tag color="red">{listError}</Tag>}
        {!listError && hint && <Tag color="gray">{hint}</Tag>}
      </div>

      <Table
        rowKey={(r) => r.name}
        loading={loading}
        data={filtered}
        pagination={{ pageSize: 20, showTotal: true }}
        scroll={{ x: 600 }}
        noDataElement={<Empty description={listError || hint || '暂无数据'} />}
        columns={[
          { title: '依赖名称', dataIndex: 'name', render: (v) => <span className="mono">{v}</span> },
          { title: '版本', dataIndex: 'version', width: 220, render: (v) => <span className="mono">{v || '-'}</span> },
          {
            title: '说明',
            dataIndex: 'summary',
            ellipsis: true,
            render: (v) => v || '-',
          },
        ]}
      />

      {(installing || logs.length > 0) && (
        <div className="panel" style={{ marginTop: 16, marginBottom: 0 }}>
          <div className="panel-head">
            <h3>当前任务日志</h3>
            {taskId && <Tag className="mono">{taskId}</Tag>}
            <span className="spacer" />
            {installing && <Progress percent={progress} style={{ width: 160 }} />}
          </div>
          <pre
            className="mono"
            style={{
              background: '#0d0f12',
              color: '#d7dade',
              padding: 12,
              borderRadius: 6,
              maxHeight: 300,
              overflow: 'auto',
              margin: 0,
            }}
          >
            {logs.length ? logs.join('\n') : '等待输出...'}
          </pre>
        </div>
      )}

      <Modal
        title="安装依赖"
        visible={installVisible}
        onOk={startInstall}
        onCancel={() => setInstallVisible(false)}
        okText="开始安装"
        cancelText="取消"
        style={{ width: 520 }}
      >
        <Space direction="vertical" style={{ width: '100%' }} size={16}>
          <div>
            <div style={{ marginBottom: 6 }}>依赖类型</div>
            <Select
              value={form.manager}
              style={{ width: '100%' }}
              onChange={(v) =>
                setForm((f) => ({
                  ...f,
                  manager: v,
                  source: status?.sources?.[v]?.[0]?.name || 'official',
                  break_system_packages: v === 'pip' ? Boolean(status?.break_required) : false,
                }))
              }
              options={[
                { label: 'Python (pip)', value: 'pip' },
                { label: 'Node.js (npm)', value: 'npm' },
                { label: 'Linux (apt)', value: 'apt' },
              ]}
            />
          </div>

          <div>
            <div style={{ marginBottom: 6 }}>依赖名称</div>
            <Input
              value={form.packages}
              onChange={(v) => setForm((f) => ({ ...f, packages: v }))}
              placeholder={TABS.find((t) => t.manager === form.manager)?.placeholder}
            />
            <div style={{ marginTop: 6, fontSize: 12, color: '#86909c' }}>
              多个包用空格或逗号分隔
            </div>
          </div>

          <div>
            <div style={{ marginBottom: 6 }}>镜像源</div>
            <Select
              value={form.source}
              style={{ width: '100%' }}
              onChange={(v) => setForm((f) => ({ ...f, source: v }))}
              options={formSources.map((s) => ({ label: s.label, value: s.name }))}
            />
          </div>

          {form.manager === 'pip' && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Switch
                  size="small"
                  checked={form.break_system_packages}
                  onChange={(v) => setForm((f) => ({ ...f, break_system_packages: v }))}
                />
                <span>使用 --break-system-packages</span>
              </div>
              <div style={{ marginTop: 6, fontSize: 12, color: '#86909c' }}>
                参数仅适用于 pip（Python）。仅在出现 externally-managed 报错时开启
                {status?.break_required && <Tag color="orange">当前环境需要此参数</Tag>}
              </div>
            </div>
          )}
        </Space>
      </Modal>
    </div>
  )
}
