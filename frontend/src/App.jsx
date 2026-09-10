import { useEffect, useState } from 'react'
import { Spin } from '@arco-design/web-react'
import { api } from './api.js'
import Login from './pages/Login.jsx'
import Layout from './components/Layout.jsx'

export default function App() {
  const [user, setUser] = useState(undefined)

  useEffect(() => {
    api
      .me()
      .then((d) => setUser(d.username))
      .catch(() => setUser(null))
  }, [])

  if (user === undefined) {
    return (
      <div style={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
        <Spin size={32} />
      </div>
    )
  }

  if (user === null) return <Login onSuccess={(name) => setUser(name)} />

  return <Layout username={user} onLogout={() => setUser(null)} />
}
