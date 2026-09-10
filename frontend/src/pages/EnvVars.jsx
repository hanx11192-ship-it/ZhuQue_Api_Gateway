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
  Tag,
  Tooltip,
  Typography,
} from '@arco-design/web-react'
import { IconPlus, IconRefresh, IconSearch } from '@arco-design/web-react/icon'
import { api, formatTime } from '../api.js'

export default function EnvVars() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [visible, setVisible] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form] = Form.useForm()
  const timerRef = useRef(null)

  const load = useCallback(async (kw) => {
    setLoading(true)
    try {
      setRows(await api.listEnv(kw))
    } catch (e) {
      Message.error(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(keyword)
  }, [keyword, load])

  const onSearch = (v) => {
    setKeyword(v)
    clearTimeout(timerRef.current)
    // 输入即搜，本地过滤保证输入流畅；结果为空时再由后端兜底
  }

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ enabled: true })
    setVisible(true)
  }

  const openEdit = (row) => {
    setEditing(row)
    form.setFieldsValue({
      name: row.name,
      value: row.value,
      remark: row.remark,
      enabled: row.enabled,
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
        await api.updateEnv(editing.id, values)
        Message.success('已保存')
      } else {
        await api.createEnv(values)
        Message.success('已添加')
      }
      setVisible(false)
      load(keyword)
    } catch (e) {
      Message.error(e.message)
    }
  }

  const toggle = async (row) => {
    try {
      await api.toggleEnv(row.id)
      load(keyword)
    } catch (e) {
      Message.error(e.message)
    }
  }

  const remove = async (row) => {
    try {
      await api.deleteEnv(row.id)
      Message.success('已删除')
      load(keyword)
    } catch (e) {
      Message.error(e.message)
    }
  }

  return (
    <div className="panel">
      <div className="toolbar">
        <Button type="primary" icon={<IconPlus />} onClick={openCreate}>
          新增变量
        </Button>
        <span style={{ flex: 1 }} />
        <Input
          allowClear
          prefix={<IconSearch />}
          placeholder="搜索变量名 / 变量值 / 备注"
          style={{ width: 280 }}
          value={keyword}
          onChange={onSearch}
        />
        <Button icon={<IconRefresh />} onClick={() => load(keyword)} loading={loading}>
          刷新
        </Button>
      </div>

      <div style={{ marginBottom: 10 }}>
        <Tag>共 {rows.length} 条</Tag>
        <Tag color="green">启用 {rows.filter((r) => r.enabled).length}</Tag>
        <Tag color="gray">暂停 {rows.filter((r) => !r.enabled).length}</Tag>
      </div>

      <Table
        rowKey="id"
        loading={loading}
        data={rows}
        pagination={{ pageSize: 15, showTotal: true }}
        scroll={{ x: 1000 }}
        noDataElement={keyword ? '没有匹配的变量' : '暂无环境变量'}
        columns={[
          {
            title: '变量名',
            dataIndex: 'name',
            width: 200,
            render: (v) => <span className="mono">{v}</span>,
          },
          {
            title: '变量值',
            dataIndex: 'value',
            ellipsis: true,
            render: (v) =>
              v ? (
                <Tooltip content={v}>
                  <Typography.Text copyable={{ text: v }} className="mono" style={{ maxWidth: 260 }}>
                    {v.length > 40 ? `${v.slice(0, 40)}…` : v}
                  </Typography.Text>
                </Tooltip>
              ) : (
                <span className="text-weak">空</span>
              ),
          },
          {
            title: '备注',
            dataIndex: 'remark',
            ellipsis: true,
            render: (v) => v || <span className="text-weak">-</span>,
          },
          {
            title: '状态',
            dataIndex: 'enabled',
            width: 110,
            render: (v, r) => (
              <Switch size="small" checked={!!v} onChange={() => toggle(r)} />
            ),
          },
          {
            title: '创建时间',
            dataIndex: 'created_at',
            width: 170,
            render: (v) => <span className="text-weak">{formatTime(v)}</span>,
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
                <Popconfirm title={`确认删除变量 ${r.name}？`} onOk={() => remove(r)}>
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
        title={editing ? '编辑环境变量' : '新增环境变量'}
        visible={visible}
        onOk={submit}
        onCancel={() => setVisible(false)}
        okText="保存"
        cancelText="取消"
        style={{ width: 520 }}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="变量名"
            field="name"
            rules={[{ required: true, message: '请输入变量名' }]}
            extra="字母、数字、下划线，不能以数字开头"
          >
            <Input placeholder="API_TOKEN" className="mono" />
          </Form.Item>
          <Form.Item label="变量值" field="value">
            <Input.TextArea rows={3} placeholder="变量值" className="mono" />
          </Form.Item>
          <Form.Item label="备注" field="remark">
            <Input placeholder="用途说明，便于搜索" />
          </Form.Item>
          <Form.Item label="状态" field="enabled" triggerPropName="checked">
            <Switch checkedText="启用" uncheckedText="暂停" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
