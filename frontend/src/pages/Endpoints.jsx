import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Button,
  Form,
  Input,
  Message,
  Modal,
  Popconfirm,
  Switch,
  Table,
  Tabs,
  Tag,
} from '@arco-design/web-react'
import { IconPlus, IconRefresh, IconUpload } from '@arco-design/web-react/icon'
import { api } from '../api.js'

export default function Endpoints() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [createVisible, setCreateVisible] = useState(false)
  const [createTab, setCreateTab] = useState('upload')
  const [editRow, setEditRow] = useState(null)
  const [tryRow, setTryRow] = useState(null)
  const [tryResult, setTryResult] = useState(null)
  const [tryPayload, setTryPayload] = useState('{\n  "name": "world"\n}')
  const [uploadForm] = Form.useForm()
  const [pathForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const fileRef = useRef(null)
  const replaceRef = useRef(null)
  const [replaceId, setReplaceId] = useState(null)
  const [file, setFile] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRows(await api.listEndpoints())
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
    setCreateTab('upload')
    uploadForm.resetFields()
    pathForm.resetFields()
    setFile(null)
    setCreateVisible(true)
  }

  const submitUpload = async () => {
    let values
    try {
      values = await uploadForm.validate()
    } catch (e) {
      return
    }
    if (!file) {
      Message.warning('请选择脚本文件')
      return
    }
    const fd = new FormData()
    fd.append('slug', values.slug)
    fd.append('name', values.name || values.slug)
    fd.append('timeout_sec', values.timeout_sec || 30)
    fd.append('rate_per_min', values.rate_per_min || 60)
    fd.append('concurrency', values.concurrency || 2)
    fd.append('enabled', values.enabled ? 1 : 0)
    fd.append('file', file)
    try {
      await api.uploadEndpoint(fd)
      Message.success('已上传并创建')
      setCreateVisible(false)
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  const submitPath = async () => {
    let values
    try {
      values = await pathForm.validate()
    } catch (e) {
      return
    }
    try {
      await api.pathEndpoint(values)
      Message.success('已按路径注册')
      setCreateVisible(false)
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  const openEdit = (row) => {
    setEditRow(row)
    editForm.setFieldsValue({
      name: row.name,
      enabled: row.enabled,
      timeout_sec: row.timeout_sec,
      rate_per_min: row.rate_per_min,
      concurrency: row.concurrency,
      http_methods: row.http_methods,
      ip_allow: row.ip_allow,
      ip_deny: row.ip_deny,
    })
  }

  const submitEdit = async () => {
    let values
    try {
      values = await editForm.validate()
    } catch (e) {
      return
    }
    try {
      await api.updateEndpoint(editRow.id, values)
      Message.success('已保存')
      setEditRow(null)
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  const runTry = async () => {
    let payload = {}
    try {
      payload = tryPayload.trim() ? JSON.parse(tryPayload) : {}
    } catch (e) {
      Message.error('JSON 格式错误')
      return
    }
    try {
      const res = await api.tryEndpoint(tryRow.id, { payload })
      setTryResult(res)
    } catch (e) {
      Message.error(e.message)
    }
  }

  const remove = async (row) => {
    try {
      await api.deleteEndpoint(row.id)
      Message.success('已删除')
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  const toggle = async (row, checked) => {
    try {
      await api.updateEndpoint(row.id, { enabled: checked })
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  const onReplaceFile = async (e) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f || !replaceId) return
    const fd = new FormData()
    fd.append('file', f)
    try {
      await api.replaceScript(replaceId, fd)
      Message.success('脚本已替换')
      load()
    } catch (err) {
      Message.error(err.message)
    } finally {
      setReplaceId(null)
    }
  }

  return (
    <div className="panel">
      <div className="toolbar">
        <Button type="primary" icon={<IconPlus />} onClick={openCreate}>
          新建端点
        </Button>
        <span style={{ flex: 1 }} />
        <Button icon={<IconRefresh />} onClick={load} loading={loading}>
          刷新
        </Button>
      </div>

      <input
        ref={replaceRef}
        type="file"
        style={{ display: 'none' }}
        accept=".py,.js"
        onChange={onReplaceFile}
      />

      <Table
        rowKey="id"
        loading={loading}
        data={rows}
        scroll={{ x: 1200 }}
        pagination={{ pageSize: 10 }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: '标识', dataIndex: 'slug', width: 130, render: (v) => <span className="mono">{v}</span> },
          { title: '名称', dataIndex: 'name', width: 140 },
          {
            title: '语言',
            dataIndex: 'lang',
            width: 90,
            render: (v) => <Tag color={v === 'python' ? 'blue' : 'orange'}>{v}</Tag>,
          },
          {
            title: '状态',
            dataIndex: 'enabled',
            width: 90,
            render: (v, r) => <Switch size="small" checked={v} onChange={(c) => toggle(r, c)} />,
          },
          { title: '超时', dataIndex: 'timeout_sec', width: 80 },
          { title: '频率/分', dataIndex: 'rate_per_min', width: 90 },
          { title: '并发', dataIndex: 'concurrency', width: 80 },
          {
            title: '路径',
            dataIndex: 'path',
            ellipsis: true,
            render: (v) => <span className="mono">{v}</span>,
          },
          {
            title: '操作',
            width: 230,
            fixed: 'right',
            render: (_, r) => (
              <div className="row-actions">
                <Button size="mini" onClick={() => { setTryRow(r); setTryResult(null) }}>
                  试运行
                </Button>
                <Button size="mini" onClick={() => openEdit(r)}>
                  编辑
                </Button>
                <Button
                  size="mini"
                  icon={<IconUpload />}
                  onClick={() => {
                    setReplaceId(r.id)
                    replaceRef.current?.click()
                  }}
                >
                  换脚本
                </Button>
                <Popconfirm title="删除该端点？脚本文件会一并删除" onOk={() => remove(r)}>
                  <Button size="mini" status="danger">
                    删除
                  </Button>
                </Popconfirm>
              </div>
            ),
          },
        ]}
      />

      {/* 新建端点 */}
      <Modal
        title="新建端点"
        visible={createVisible}
        onCancel={() => setCreateVisible(false)}
        footer={null}
        style={{ width: 560 }}
      >
        <Tabs activeTab={createTab} onChange={setCreateTab}>
          <Tabs.TabPane key="upload" title="上传脚本">
            <Form form={uploadForm} layout="vertical" style={{ marginTop: 12 }}>
              <Form.Item
                label="标识 slug"
                field="slug"
                rules={[{ required: true, message: '请输入标识' }]}
                extra="仅允许字母数字、下划线、短横线"
              >
                <Input placeholder="echo" />
              </Form.Item>
              <Form.Item label="名称" field="name">
                <Input placeholder="示例回显" />
              </Form.Item>
              <Form.Item label="脚本文件（.py / .js）" required>
                <input
                  type="file"
                  accept=".py,.js"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                />
                {file && (
                  <div style={{ marginTop: 6, fontSize: 12, color: '#86909c' }}>
                    已选择：{file.name}
                  </div>
                )}
              </Form.Item>
              <Form.Item label="超时（秒）" field="timeout_sec" initialValue={30}>
                <Input type="number" />
              </Form.Item>
              <Form.Item label="每分钟次数" field="rate_per_min" initialValue={60}>
                <Input type="number" />
              </Form.Item>
              <Form.Item label="并发" field="concurrency" initialValue={2}>
                <Input type="number" />
              </Form.Item>
              <Form.Item label="启用" field="enabled" initialValue={true} triggerPropName="checked">
                <Switch />
              </Form.Item>
              <Button type="primary" long onClick={submitUpload}>
                创建
              </Button>
            </Form>
          </Tabs.TabPane>

          <Tabs.TabPane key="path" title="按路径注册">
            <Form form={pathForm} layout="vertical" style={{ marginTop: 12 }}>
              <Form.Item
                label="标识 slug"
                field="slug"
                rules={[{ required: true, message: '请输入标识' }]}
              >
                <Input placeholder="echo" />
              </Form.Item>
              <Form.Item label="名称" field="name">
                <Input placeholder="示例回显" />
              </Form.Item>
              <Form.Item
                label="脚本绝对路径"
                field="path"
                rules={[{ required: true, message: '请输入路径' }]}
                extra="容器内路径，需为 .py 或 .js 文件"
              >
                <Input placeholder="/srv/gateway/data/scripts/echo/echo.py" />
              </Form.Item>
              <Form.Item label="超时（秒）" field="timeout_sec" initialValue={30}>
                <Input type="number" />
              </Form.Item>
              <Form.Item label="每分钟次数" field="rate_per_min" initialValue={60}>
                <Input type="number" />
              </Form.Item>
              <Form.Item label="并发" field="concurrency" initialValue={2}>
                <Input type="number" />
              </Form.Item>
              <Form.Item label="启用" field="enabled" initialValue={true} triggerPropName="checked">
                <Switch />
              </Form.Item>
              <Button type="primary" long onClick={submitPath}>
                创建
              </Button>
            </Form>
          </Tabs.TabPane>
        </Tabs>
      </Modal>

      {/* 编辑端点 */}
      <Modal
        title={`编辑端点 · ${editRow?.slug || ''}`}
        visible={!!editRow}
        onOk={submitEdit}
        onCancel={() => setEditRow(null)}
        okText="保存"
        cancelText="取消"
        style={{ width: 520 }}
      >
        <Form form={editForm} layout="vertical">
          <Form.Item label="名称" field="name">
            <Input />
          </Form.Item>
          <Form.Item label="超时（秒）" field="timeout_sec">
            <Input type="number" />
          </Form.Item>
          <Form.Item label="每分钟次数" field="rate_per_min">
            <Input type="number" />
          </Form.Item>
          <Form.Item label="并发" field="concurrency">
            <Input type="number" />
          </Form.Item>
          <Form.Item label="HTTP 方法" field="http_methods">
            <Input placeholder="GET,POST" />
          </Form.Item>
          <Form.Item label="IP 白名单" field="ip_allow">
            <Input placeholder="留空不限" />
          </Form.Item>
          <Form.Item label="IP 黑名单" field="ip_deny">
            <Input placeholder="留空不限" />
          </Form.Item>
          <Form.Item label="启用" field="enabled" triggerPropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* 试运行 */}
      <Modal
        title={`试运行 · ${tryRow?.slug || ''}`}
        visible={!!tryRow}
        onCancel={() => setTryRow(null)}
        footer={[
          <Button key="cancel" onClick={() => setTryRow(null)}>
            关闭
          </Button>,
          <Button key="run" type="primary" onClick={runTry}>
            运行
          </Button>,
        ]}
        style={{ width: 620 }}
      >
        <div style={{ marginBottom: 8, fontSize: 13, color: '#86909c' }}>
          请求体 JSON（对应脚本 stdin / API_PAYLOAD）
        </div>
        <Input.TextArea
          rows={6}
          value={tryPayload}
          onChange={setTryPayload}
          className="mono"
          style={{ fontFamily: 'monospace' }}
        />
        {tryResult && (
          <pre
            className="mono"
            style={{
              background: '#f7f8fa',
              padding: 12,
              borderRadius: 6,
              maxHeight: 280,
              overflow: 'auto',
              marginTop: 12,
            }}
          >
            {JSON.stringify(tryResult, null, 2)}
          </pre>
        )}
      </Modal>
    </div>
  )
}
