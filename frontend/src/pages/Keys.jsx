import { useCallback, useEffect, useState } from 'react'
import {
  Button,
  Form,
  Input,
  Message,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
} from '@arco-design/web-react'
import { IconCopy, IconPlus, IconRefresh } from '@arco-design/web-react/icon'
import { api } from '../api.js'

export default function Keys() {
  const [rows, setRows] = useState([])
  const [endpoints, setEndpoints] = useState([])
  const [loading, setLoading] = useState(false)
  const [visible, setVisible] = useState(false)
  const [editing, setEditing] = useState(null)
  const [secret, setSecret] = useState('')
  const [form] = Form.useForm()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRows(await api.listKeys())
    } catch (e) {
      Message.error(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    api.listEndpoints().then(setEndpoints).catch(() => {})
  }, [load])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ enabled: true, rate_per_min: 120, endpoint_slugs: [] })
    setVisible(true)
  }

  const openEdit = (row) => {
    setEditing(row)
    form.setFieldsValue({
      name: row.name,
      enabled: row.enabled,
      rate_per_min: row.rate_per_min,
      endpoint_slugs: row.endpoint_slugs || [],
      ip_allow: row.ip_allow || '',
    })
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
      if (editing) {
        await api.updateKey(editing.id, values)
        Message.success('已保存')
        setVisible(false)
      } else {
        const data = await api.createKey(values)
        setSecret(data.secret)
        Message.success('密钥已创建，请立即保存')
        setVisible(false)
      }
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  const remove = async (row) => {
    try {
      await api.deleteKey(row.id)
      Message.success('已删除')
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  const toggle = async (row, checked) => {
    try {
      await api.updateKey(row.id, { enabled: checked })
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  return (
    <div className="panel">
      <div className="toolbar">
        <Button type="primary" icon={<IconPlus />} onClick={openCreate}>
          新建密钥
        </Button>
        <span style={{ flex: 1 }} />
        <Button icon={<IconRefresh />} onClick={load} loading={loading}>
          刷新
        </Button>
      </div>

      {secret && (
        <div
          style={{
            marginBottom: 12,
            padding: 12,
            background: '#fff7e8',
            border: '1px solid #ffd591',
            borderRadius: 6,
          }}
        >
          <div style={{ marginBottom: 6, fontWeight: 600 }}>新密钥（仅显示一次）</div>
          <Space>
            <Typography.Text copyable={{ text: secret }} className="mono">
              {secret}
            </Typography.Text>
            <Button size="mini" onClick={() => setSecret('')}>
              我已保存
            </Button>
          </Space>
        </div>
      )}

      <Table
        rowKey="id"
        loading={loading}
        data={rows}
        scroll={{ x: 1000 }}
        pagination={{ pageSize: 10 }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: '名称', dataIndex: 'name', width: 140 },
          { title: '前缀', dataIndex: 'key_prefix', width: 120, render: (v) => <span className="mono">{v}</span> },
          {
            title: '状态',
            dataIndex: 'enabled',
            width: 100,
            render: (v, r) => (
              <Switch size="small" checked={v} onChange={(c) => toggle(r, c)} />
            ),
          },
          { title: '频率/分', dataIndex: 'rate_per_min', width: 100 },
          {
            title: '绑定端点',
            dataIndex: 'endpoint_slugs',
            render: (v) =>
              (v && v.length
                ? v.map((s) => <Tag key={s}>{s}</Tag>)
                : <span className="text-weak">全部</span>),
          },
          {
            title: '操作',
            width: 120,
            fixed: 'right',
            render: (_, r) => (
              <div className="row-actions">
                <Button size="mini" onClick={() => openEdit(r)}>
                  编辑
                </Button>
                <Popconfirm title="确认删除该密钥？" onOk={() => remove(r)}>
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
        title={editing ? '编辑密钥' : '新建密钥'}
        visible={visible}
        onOk={submit}
        onCancel={() => setVisible(false)}
        okText="保存"
        cancelText="取消"
        style={{ width: 520 }}
      >
        <Form form={form} layout="vertical">
          <Form.Item label="名称" field="name" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="例如：前端调用" />
          </Form.Item>
          <Form.Item label="每分钟次数" field="rate_per_min">
            <Input type="number" placeholder="120" />
          </Form.Item>
          <Form.Item label="绑定端点（留空表示全部）" field="endpoint_slugs">
            <Select
              mode="multiple"
              allowClear
              placeholder="选择允许的端点"
              options={endpoints.map((e) => ({ label: e.slug, value: e.slug }))}
            />
          </Form.Item>
          <Form.Item label="IP 白名单（逗号分隔，留空不限）" field="ip_allow">
            <Input placeholder="1.2.3.4,10.0.0.0/8" />
          </Form.Item>
          <Form.Item label="启用" field="enabled" triggerPropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
