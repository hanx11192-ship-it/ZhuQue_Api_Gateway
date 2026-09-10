import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Breadcrumb,
  Button,
  Input,
  Message,
  Modal,
  Popconfirm,
  Table,
  Tag,
} from '@arco-design/web-react'
import {
  IconFile,
  IconFolder,
  IconHome,
  IconPlus,
  IconRefresh,
  IconUpload,
} from '@arco-design/web-react/icon'
import { api, formatBytes } from '../api.js'

export default function Files() {
  const [cwd, setCwd] = useState('')
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)
  const [editor, setEditor] = useState(null) // {path, content, isNew}
  const [newName, setNewName] = useState('')
  const [newKind, setNewKind] = useState('file')
  const [newVisible, setNewVisible] = useState(false)
  const uploadRef = useRef(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.fsList(cwd)
      setCwd(data.cwd)
      setEntries(data.entries)
    } catch (e) {
      Message.error(e.message)
    } finally {
      setLoading(false)
    }
  }, [cwd])

  useEffect(() => {
    load()
  }, [load])

  const openFile = async (row) => {
    try {
      const data = await api.fsRead(row.path)
      setEditor({ path: row.path, content: data.content, isNew: false })
    } catch (e) {
      Message.error(e.message)
    }
  }

  const saveFile = async () => {
    try {
      await api.fsWrite({ path: editor.path, content: editor.content, overwrite: true })
      Message.success('已保存')
      setEditor(null)
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  const createEntry = async () => {
    const name = newName.trim()
    if (!name) {
      Message.warning('请输入名称')
      return
    }
    const path = cwd ? `${cwd}/${name}` : name
    try {
      if (newKind === 'dir') {
        await api.fsMkdir({ path })
        Message.success('已创建')
      } else {
        await api.fsWrite({ path, content: '' })
        setNewVisible(false)
        setNewName('')
        setEditor({ path, content: '', isNew: true })
        load()
        return
      }
      setNewVisible(false)
      setNewName('')
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  const remove = async (row) => {
    try {
      await api.fsDelete(row.path)
      Message.success('已删除')
      load()
    } catch (e) {
      Message.error(e.message)
    }
  }

  const onUpload = async (e) => {
    const f = e.target.files?.[0]
    e.target.value = ''
    if (!f) return
    const fd = new FormData()
    fd.append('dir', cwd)
    fd.append('file', f)
    try {
      await api.fsUpload(fd)
      Message.success('上传成功')
      load()
    } catch (err) {
      Message.error(err.message)
    }
  }

  const parts = cwd ? cwd.split('/').filter(Boolean) : []

  return (
    <div className="panel">
      <div className="toolbar">
        <Button
          icon={<IconHome />}
          onClick={() => setCwd('')}
          disabled={!cwd}
        >
          根目录
        </Button>
        <Button
          icon={<IconPlus />}
          onClick={() => {
            setNewKind('file')
            setNewName('')
            setNewVisible(true)
          }}
        >
          新建
        </Button>
        <Button icon={<IconUpload />} onClick={() => uploadRef.current?.click()}>
          上传
        </Button>
        <span style={{ flex: 1 }} />
        <Button icon={<IconRefresh />} onClick={load} loading={loading}>
          刷新
        </Button>
      </div>

      <input ref={uploadRef} type="file" style={{ display: 'none' }} onChange={onUpload} />

      <Breadcrumb style={{ marginBottom: 12 }}>
        <Breadcrumb.Item onClick={() => setCwd('')}>data</Breadcrumb.Item>
        {parts.map((p, i) => (
          <Breadcrumb.Item
            key={i}
            onClick={() => setCwd(parts.slice(0, i + 1).join('/'))}
            style={{ cursor: 'pointer' }}
          >
            {p}
          </Breadcrumb.Item>
        ))}
      </Breadcrumb>

      <Table
        rowKey="path"
        loading={loading}
        data={entries}
        pagination={false}
        scroll={{ x: 800 }}
        columns={[
          {
            title: '名称',
            dataIndex: 'name',
            render: (v, r) => (
              <span
                style={{ cursor: r.is_dir ? 'pointer' : 'default' }}
                onClick={() => (r.is_dir ? setCwd(r.path) : openFile(r))}
              >
                {r.is_dir ? <IconFolder style={{ color: '#ff9a2e' }} /> : <IconFile />}{' '}
                {v}
              </span>
            ),
          },
          {
            title: '类型',
            dataIndex: 'is_dir',
            width: 90,
            render: (v) => (v ? <Tag color="orange">文件夹</Tag> : <Tag>文件</Tag>),
          },
          {
            title: '大小',
            dataIndex: 'size',
            width: 110,
            render: (v, r) => (r.is_dir ? '-' : formatBytes(v)),
          },
          {
            title: '修改时间',
            dataIndex: 'mtime',
            width: 180,
            render: (v) => new Date(v * 1000).toLocaleString(),
          },
          {
            title: '操作',
            width: 140,
            render: (_, r) => (
              <div className="row-actions">
                {!r.is_dir && (
                  <Button size="mini" onClick={() => openFile(r)}>
                    编辑
                  </Button>
                )}
                <Popconfirm
                  title={r.is_dir ? '将递归删除该目录下所有内容，不可恢复' : '文件将被永久删除'}
                  onOk={() => remove(r)}
                >
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
        title="新建"
        visible={newVisible}
        onOk={createEntry}
        onCancel={() => setNewVisible(false)}
        okText="创建"
        cancelText="取消"
      >
        <div style={{ marginBottom: 12 }}>
          <Button.Group>
            <Button
              type={newKind === 'file' ? 'primary' : 'secondary'}
              size="small"
              onClick={() => setNewKind('file')}
            >
              文件
            </Button>
            <Button
              type={newKind === 'dir' ? 'primary' : 'secondary'}
              size="small"
              onClick={() => setNewKind('dir')}
            >
              文件夹
            </Button>
          </Button.Group>
        </div>
        <Input
          value={newName}
          onChange={setNewName}
          placeholder={newKind === 'file' ? '文件名（含扩展名，如 test.py）' : '文件夹名称'}
        />
      </Modal>

      <Modal
        title={`编辑文件 · ${editor?.path || ''}`}
        visible={!!editor}
        onOk={saveFile}
        onCancel={() => setEditor(null)}
        okText="保存"
        cancelText="取消"
        style={{ width: 760 }}
      >
        <Input.TextArea
          rows={18}
          value={editor?.content || ''}
          onChange={(v) => setEditor((e) => ({ ...e, content: v }))}
          style={{ fontFamily: 'monospace', fontSize: 13 }}
        />
      </Modal>
    </div>
  )
}
