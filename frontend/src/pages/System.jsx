import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Descriptions,
  Form,
  Input,
  Message,
  Modal,
  Popconfirm,
  Progress,
  Select,
  Switch,
  Table,
  Tabs,
  Tag,
} from '@arco-design/web-react'
import { IconPlus, IconRefresh } from '@arco-design/web-react/icon'
import { api, formatBytes, formatTime } from '../api.js'

const MANAGER_LABEL = { pip: 'Python (pip)', npm: 'Node.js (npm)', apt: 'Linux (apt)' }

/* ------------------------------------------------------------ 镜像源 */
function MirrorSources() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [visible, setVisible] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRows(await api.listMirrors())
    } catch (e) {
      Message.error(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ manager: 'pip', enabled: true, sort: 0 })
    setVisible(true)
  }

  const openEdit = (row) => {
    setEditing(row)
    form.setFieldsValue({ ...row })
    setVisible(true)
  }

  const submit = async () => {
    let values
    try {
      values = await form.validate()
    } catch (e) {
      return
    }
    try {
      if (editing) await api.updateMirror(editing.id, values)
      else await api.createMirror(values)
      Message.success('已保存')
      setVisible(false)
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  const remove = async (row) => {
    try {
      await api.deleteMirror(row.id)
      Message.success('已删除')
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  const toggle = async (row, checked) => {
    try {
      await api.updateMirror(row.id, { enabled: checked })
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  return (
    <div>
      <div className="toolbar">
        <Button type="primary" icon={<IconPlus />} onClick={openCreate}>
          添加镜像源
        </Button>
        <span style={{ flex: 1 }} />
        <Button icon={<IconRefresh />} onClick={load} loading={loading}>
          刷新
        </Button>
      </div>

      <div style={{ marginBottom: 10, fontSize: 13, color: '#86909c' }}>
        在这里添加的源会立即出现在「依赖管理 → 安装依赖」的镜像源选项中。
      </div>

      <Table
        rowKey="id"
        loading={loading}
        data={rows}
        pagination={false}
        scroll={{ x: 800 }}
        columns={[
          {
            title: '依赖类型',
            dataIndex: 'manager',
            width: 130,
            render: (v) => <Tag color="arcoblue">{MANAGER_LABEL[v] || v}</Tag>,
          },
          { title: '标识', dataIndex: 'name', width: 120, render: (v) => <span className="mono">{v}</span> },
          { title: '名称', dataIndex: 'label', width: 150 },
          {
            title: '地址',
            dataIndex: 'url',
            ellipsis: true,
            render: (v) => (v ? <span className="mono">{v}</span> : <span className="text-weak">系统默认</span>),
          },
          {
            title: '启用',
            dataIndex: 'enabled',
            width: 90,
            render: (v, r) => <Switch size="small" checked={!!v} onChange={(c) => toggle(r, c)} />,
          },
          {
            title: '操作',
            width: 130,
            fixed: 'right',
            render: (_, r) => (
              <div className="row-actions">
                <Button size="mini" onClick={() => openEdit(r)}>
                  编辑
                </Button>
                <Popconfirm title="确认删除该镜像源？" onOk={() => remove(r)}>
                  <Button size="mini" status="danger">
                    删除
                  </Button>
                </Popconfirm>
              </div>
            ),
          },
        ]}
      />

      <Modal
        title={editing ? '编辑镜像源' : '添加镜像源'}
        visible={visible}
        onOk={submit}
        onCancel={() => setVisible(false)}
        okText="保存"
        cancelText="取消"
        style={{ width: 520 }}
      >
        <Form form={form} layout="vertical">
          <Form.Item label="依赖类型" field="manager" rules={[{ required: true }]}>
            <Select
              options={[
                { label: 'Python (pip)', value: 'pip' },
                { label: 'Node.js (npm)', value: 'npm' },
                { label: 'Linux (apt)', value: 'apt' },
              ]}
            />
          </Form.Item>
          <Form.Item
            label="标识"
            field="name"
            rules={[{ required: true, message: '请输入标识' }]}
            extra="字母数字、下划线、连字符，同类型下唯一"
          >
            <Input placeholder="tuna" className="mono" />
          </Form.Item>
          <Form.Item label="名称" field="label" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="清华 TUNA" />
          </Form.Item>
          <Form.Item
            label="地址"
            field="url"
            extra="pip / npm 填完整地址；Linux(apt) 填镜像主机名，如 mirrors.tuna.tsinghua.edu.cn"
          >
            <Input placeholder="https://pypi.tuna.tsinghua.edu.cn/simple" className="mono" />
          </Form.Item>
          <Form.Item label="排序" field="sort">
            <Input type="number" placeholder="0" />
          </Form.Item>
          <Form.Item label="启用" field="enabled" triggerPropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

/* ------------------------------------------------------------ 系统信息 */
function SystemInfo() {
  const [info, setInfo] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      setInfo(await api.sysInfo())
    } catch (e) {
      Message.error(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  if (!info) return <div>加载中...</div>

  const memPercent = info.memory_usage_percent || 0
  const diskPercent = info.disk_usage_percent || 0

  return (
    <div>
      <div className="toolbar">
        <span style={{ flex: 1 }} />
        <Button icon={<IconRefresh />} onClick={load} loading={loading}>
          刷新
        </Button>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="label">后端启动时间</div>
          <div className="value" style={{ fontSize: 17 }}>{info.backend?.started_at}</div>
          <div className="sub">已运行 {info.backend?.uptime}</div>
        </div>
        <div className="stat-card">
          <div className="label">系统启动时间</div>
          <div className="value" style={{ fontSize: 17 }}>{info.os?.booted_at}</div>
          <div className="sub">已运行 {info.os?.uptime}</div>
        </div>
        <div className="stat-card">
          <div className="label">内存使用率</div>
          <div className="value">{memPercent}%</div>
          <div className="sub">
            {formatBytes(info.memory_used)} / {formatBytes(info.memory_total)}
          </div>
        </div>
        <div className="stat-card">
          <div className="label">磁盘使用率</div>
          <div className="value">{diskPercent}%</div>
          <div className="sub">
            {formatBytes(info.disk_used)} / {formatBytes(info.disk_total)}
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>前端架构</h3>
        </div>
        <Descriptions
          column={2}
          data={[
            { label: '框架', value: info.frontend?.framework },
            { label: 'UI 组件库', value: info.frontend?.ui },
            { label: '构建工具', value: info.frontend?.bundler },
            { label: '语言', value: info.frontend?.language },
          ]}
        />
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>后端架构</h3>
        </div>
        <Descriptions
          column={2}
          data={[
            { label: '框架', value: info.backend?.framework },
            { label: '语言', value: info.backend?.language },
            { label: '服务器', value: info.backend?.server },
            { label: '数据库', value: info.backend?.database },
            { label: '启动时间', value: info.backend?.started_at },
            { label: '运行时长', value: info.backend?.uptime },
          ]}
        />
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>运行环境</h3>
        </div>
        <Descriptions
          column={2}
          data={[
            { label: 'Node.js', value: info.runtime?.node_version },
            { label: 'npm', value: info.runtime?.npm_version },
            { label: 'pip', value: info.runtime?.pip_version },
            { label: 'Python', value: info.runtime?.python_version },
          ]}
        />
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>操作系统</h3>
        </div>
        <Descriptions
          column={2}
          data={[
            { label: '系统', value: `${info.os?.system} ${info.os?.release}` },
            { label: '架构', value: info.os?.machine },
            { label: '主机名', value: info.os?.hostname },
            { label: 'CPU 核心', value: `${info.os?.cpu_count} 核` },
            { label: 'CPU 使用率', value: `${info.cpu_usage}%` },
            { label: '平台', value: info.os?.platform },
          ]}
        />
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>资源占用</h3>
        </div>
        <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))' }}>
          <div>
            <div style={{ marginBottom: 6, fontSize: 13, color: '#86909c' }}>内存</div>
            <Progress percent={Math.min(100, memPercent)} />
          </div>
          <div>
            <div style={{ marginBottom: 6, fontSize: 13, color: '#86909c' }}>磁盘</div>
            <Progress percent={Math.min(100, diskPercent)} status={diskPercent > 90 ? 'danger' : 'normal'} />
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>数据统计</h3>
        </div>
        <Descriptions
          column={2}
          data={[
            { label: '端点数', value: info.counts?.endpoints },
            { label: '密钥数', value: info.counts?.api_keys },
            { label: '环境变量数', value: info.counts?.env_vars },
            { label: '调用日志数', value: info.counts?.logs },
            { label: '数据库大小', value: formatBytes(info.db_size) },
            { label: '统计时间', value: formatTime(new Date().toISOString()) },
          ]}
        />
      </div>
    </div>
  )
}

/* ------------------------------------------------------------ 安全设置 */
function Security() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    let values
    try {
      values = await form.validate()
    } catch (e) {
      return
    }
    if (values.new_password !== values.confirm_password) {
      Message.error('两次输入的新密码不一致')
      return
    }
    setLoading(true)
    try {
      await api.changePassword(values.old_password, values.new_password)
      Message.success('密码已更新，下次登录请使用新密码')
      form.resetFields()
    } catch (e) {
      Message.error(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel" style={{ maxWidth: 520 }}>
      <div className="panel-head">
        <h3>修改密码</h3>
      </div>
      <div style={{ marginBottom: 16, fontSize: 13, color: '#86909c' }}>
        为安全起见，修改密码前必须先验证当前密码。
      </div>
      <Form form={form} layout="vertical" onSubmit={submit}>
        <Form.Item
          label="当前密码"
          field="old_password"
          rules={[{ required: true, message: '请输入当前密码' }]}
        >
          <Input.Password placeholder="请输入当前密码" />
        </Form.Item>
        <Form.Item
          label="新密码"
          field="new_password"
          rules={[
            { required: true, message: '请输入新密码' },
            { minLength: 6, message: '新密码至少 6 位' },
          ]}
        >
          <Input.Password placeholder="至少 6 位" />
        </Form.Item>
        <Form.Item
          label="确认新密码"
          field="confirm_password"
          rules={[{ required: true, message: '请再次输入新密码' }]}
        >
          <Input.Password placeholder="再次输入新密码" />
        </Form.Item>
        <Button type="primary" long loading={loading} onClick={submit}>
          确认修改
        </Button>
      </Form>
    </div>
  )
}

/* ------------------------------------------------------------ 日志设置 */
function LogSettings() {
  const [retention, setRetention] = useState(30)
  const [enabled, setEnabled] = useState(false)
  const [logCount, setLogCount] = useState(null)
  const [saving, setSaving] = useState(false)
  const [cleaning, setCleaning] = useState(false)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [s, ov] = await Promise.all([api.getSettings(), api.overview()])
      const rtd = parseInt(s.log_retention_days, 10) || 0
      setEnabled(rtd > 0)
      setRetention(rtd > 0 ? rtd : 30)
      setLogCount(ov.counts?.logs ?? null)
    } catch (e) {
      Message.error(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const save = async () => {
    setSaving(true)
    try {
      const days = enabled ? Math.max(1, retention) : 0
      await api.saveSettings({ log_retention_days: days })
      Message.success(enabled ? `已启用：保留最近 ${days} 天` : '已关闭自动清理')
      load()
    } catch (e) {
      Message.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  const runNow = async () => {
    if (!enabled) {
      Message.warning('请先启用自动清理并设置保留天数')
      return
    }
    setCleaning(true)
    try {
      const r = await api.cleanupLogs(retention)
      Message.success(`已清理 ${r.deleted} 条，剩余 ${r.remaining} 条`)
      load()
    } catch (e) {
      Message.error(e.message)
    } finally {
      setCleaning(false)
    }
  }

  const presets = [3, 7, 15, 30]

  return (
    <div style={{ maxWidth: 640 }}>
      <div className="toolbar">
        <span style={{ flex: 1 }} />
        <Button icon={<IconRefresh />} onClick={load} loading={loading}>
          刷新
        </Button>
      </div>

      <div className="panel" style={{ marginTop: 12 }}>
        <div className="panel-head">
          <h3>日志自动清理</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          <span style={{ width: 120, color: '#4e5969' }}>启用自动清理</span>
          <Switch checked={enabled} onChange={setEnabled} />
          <span className="text-weak">
            关闭后所有调用日志永久保留（仅可手动清理）
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <span style={{ width: 120, color: '#4e5969' }}>保留天数</span>
          <InputNumber
            min={1}
            max={3650}
            disabled={!enabled}
            value={retention}
            onChange={setRetention}
            style={{ width: 160 }}
            suffix="天"
          />
          <div style={{ display: 'flex', gap: 6 }}>
            {presets.map((p) => (
              <Button
                key={p}
                size="mini"
                disabled={!enabled}
                type={retention === p ? 'primary' : 'secondary'}
                onClick={() => setRetention(p)}
              >
                {p} 天
              </Button>
            ))}
          </div>
        </div>
        <div style={{ fontSize: 13, color: '#86909c', margin: '4px 0 16px 132px' }}>
          例：设为 3 天，则每天自动删除 3 天前的调用日志。任务由后端每小时检查一次。
        </div>
        <div style={{ display: 'flex', gap: 12 }}>
          <Button type="primary" loading={saving} onClick={save}>
            保存设置
          </Button>
          <Button loading={cleaning} onClick={runNow}>
            立即按策略清理
          </Button>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>当前日志</h3>
        </div>
        <Descriptions
          column={2}
          data={[
            { label: '调用日志总数', value: logCount === null ? '加载中…' : logCount },
            { label: '当前策略', value: enabled ? `保留最近 ${retention} 天` : '未开启自动清理' },
          ]}
        />
        <div style={{ marginTop: 12, fontSize: 13, color: '#86909c' }}>
          手动彻底清理请到「调用日志」页面，使用右上角「清空全部」；按时间清理用「清理」按钮。
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------ 页面主体 */
export default function SystemPage() {
  const [tab, setTab] = useState('mirrors')

  return (
    <div className="panel">
      <Tabs activeTab={tab} onChange={setTab}>
        <Tabs.TabPane key="mirrors" title="镜像源" />
        <Tabs.TabPane key="info" title="系统信息" />
        <Tabs.TabPane key="security" title="安全设置" />
        <Tabs.TabPane key="logs" title="日志" />
      </Tabs>
      <div style={{ marginTop: 12 }}>
        {tab === 'mirrors' && <MirrorSources />}
        {tab === 'info' && <SystemInfo />}
        {tab === 'security' && <Security />}
        {tab === 'logs' && <LogSettings />}
      </div>
    </div>
  )
}
