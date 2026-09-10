import { useEffect, useState } from 'react'
import { Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Message, Modal, Tag } from '@arco-design/web-react'
import {
  IconBook,
  IconCode,
  IconDashboard,
  IconDesktop,
  IconExport,
  IconFile,
  IconFolder,
  IconLock,
  IconMenu,
  IconSettings,
  IconStorage,
  IconTags,
  IconUser,
} from '@arco-design/web-react/icon'
import { api } from '../api.js'
import Dashboard from '../pages/Dashboard.jsx'
import Endpoints from '../pages/Endpoints.jsx'
import Keys from '../pages/Keys.jsx'
import Logs from '../pages/Logs.jsx'
import Docs from '../pages/Docs.jsx'
import EnvVars from '../pages/EnvVars.jsx'
import Packages from '../pages/Packages.jsx'
import Files from '../pages/Files.jsx'
import Terminal from '../pages/Terminal.jsx'
import SystemPage from '../pages/System.jsx'

const MENU = [
  { group: '监控' },
  { path: '/dashboard', label: '仪表盘', icon: <IconDashboard /> },
  { group: '接口服务' },
  { path: '/endpoints', label: '端点管理', icon: <IconCode /> },
  { path: '/keys', label: 'API 密钥', icon: <IconLock /> },
  { path: '/logs', label: '调用日志', icon: <IconFile /> },
  { path: '/docs', label: '调用说明', icon: <IconBook /> },
  { group: '运行环境' },
  { path: '/env', label: '环境变量', icon: <IconTags /> },
  { path: '/packages', label: '依赖管理', icon: <IconStorage /> },
  { path: '/files', label: '文件管理', icon: <IconFolder /> },
  { path: '/terminal', label: '终端', icon: <IconDesktop /> },
  { group: '系统' },
  { path: '/system', label: '系统配置', icon: <IconSettings /> },
]

export default function Layout({ username, onLogout }) {
  const location = useLocation()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  const current = MENU.find((m) => m.path === location.pathname)

  const handleLogout = () => {
    Modal.confirm({
      title: '退出登录',
      content: '确定要退出当前登录状态吗？',
      okText: '退出',
      cancelText: '取消',
      onOk: async () => {
        await api.logout().catch(() => {})
        onLogout()
      },
    })
  }

  return (
    <div className="app-shell">
      <aside
        className={`app-sidebar ${collapsed ? 'collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`}
      >
        <div className="brand">
          <span className="brand-logo">朱</span>
          {!collapsed && <span className="brand-text">朱雀 API 网关</span>}
        </div>
        <nav className="app-menu">
          {MENU.map((item, idx) =>
            item.group ? (
              <div className="menu-group-title" key={`g${idx}`}>
                {collapsed ? '·' : item.group}
              </div>
            ) : (
              <div
                key={item.path}
                className={`menu-item ${location.pathname === item.path ? 'active' : ''}`}
                onClick={() => navigate(item.path)}
                title={item.label}
              >
                <span className="icon">{item.icon}</span>
                {!collapsed && <span>{item.label}</span>}
              </div>
            )
          )}
        </nav>
      </aside>

      {mobileOpen && <div className="sidebar-mask" onClick={() => setMobileOpen(false)} />}

      <div className="app-main">
        <header className="app-topbar">
          <button className="icon-btn" onClick={() => setMobileOpen((v) => !v)} title="菜单">
            <IconMenu />
          </button>
          <span className="title">{current?.label || '朱雀网关'}</span>
          <span className="spacer" />
          <Tag icon={<IconUser />} color="arcoblue">
            {username}
          </Tag>
          <button className="icon-btn" onClick={handleLogout} title="退出登录">
            <IconExport />
          </button>
        </header>

        <main className="app-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/endpoints" element={<Endpoints />} />
            <Route path="/keys" element={<Keys />} />
            <Route path="/logs" element={<Logs />} />
            <Route path="/docs" element={<Docs />} />
            <Route path="/env" element={<EnvVars />} />
            <Route path="/packages" element={<Packages />} />
            <Route path="/files" element={<Files />} />
            <Route path="/terminal" element={<Terminal />} />
            <Route path="/system" element={<SystemPage />} />
            <Route path="*" element={<Dashboard />} />
          </Routes>
        </main>
      </div>
      <Outlet />
    </div>
  )
}
