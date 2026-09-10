import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Card, Form, Input, Message } from '@arco-design/web-react'
import { IconLock, IconUser } from '@arco-design/web-react/icon'
import { api } from '../api.js'

export default function Login({ onSuccess }) {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const submit = async () => {
    let values
    try {
      values = await form.validate()
    } catch (e) {
      return
    }
    setLoading(true)
    try {
      const data = await api.login(values.username, values.password)
      Message.success('登录成功')
      onSuccess(data.username)
      navigate('/dashboard', { replace: true })
    } catch (e) {
      Message.error(e.message || '登录失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, #1d2129 0%, #2a313c 100%)',
        padding: 16,
      }}
    >
      <Card style={{ width: 380, maxWidth: '100%' }} title={null}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div
            style={{
              width: 52,
              height: 52,
              margin: '0 auto 12px',
              borderRadius: 14,
              background: 'linear-gradient(135deg, #f53f3f, #ff7d00)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontSize: 22,
              fontWeight: 600,
            }}
          >
            朱
          </div>
          <div style={{ fontSize: 18, fontWeight: 600 }}>朱雀 API 网关</div>
          <div style={{ color: '#86909c', fontSize: 13, marginTop: 4 }}>脚本 API 管理面板</div>
        </div>

        <Form form={form} layout="vertical" size="large" onSubmit={submit}>
          <Form.Item field="username" rules={[{ required: true, message: '请输入用户名' }]}>
            <Input prefix={<IconUser />} placeholder="请输入用户名" onPressEnter={submit} />
          </Form.Item>
          <Form.Item field="password" rules={[{ required: true, message: '请输入密码' }]}>
            <Input.Password prefix={<IconLock />} placeholder="请输入密码" onPressEnter={submit} />
          </Form.Item>
          <Button type="primary" long loading={loading} onClick={submit}>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  )
}
