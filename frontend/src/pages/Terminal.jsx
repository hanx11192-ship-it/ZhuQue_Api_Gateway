import { useCallback, useEffect, useRef, useState } from 'react'
import { Button, Message, Space, Tag } from '@arco-design/web-react'
import { IconDelete, IconRefresh } from '@arco-design/web-react/icon'
import { Terminal as XTerm } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'

// 常用控制键，移动端键盘打不出这些组合键
const KEYS = [
  { label: 'Ctrl+C', seq: '\x03' },
  { label: 'Ctrl+D', seq: '\x04' },
  { label: 'Ctrl+L', seq: '\x0c' },
  { label: 'Tab', seq: '\t' },
  { label: 'Esc', seq: '\x1b' },
  { label: '↑', seq: '\x1b[A' },
  { label: '↓', seq: '\x1b[B' },
  { label: 'Ctrl+Z', seq: '\x1a' },
]

export default function Terminal() {
  const hostRef = useRef(null)
  const inputRef = useRef(null)
  const termRef = useRef(null)
  const fitRef = useRef(null)
  const wsRef = useRef(null)
  const [status, setStatus] = useState('连接中')
  const [input, setInput] = useState('')

  const send = useCallback((text) => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(text)
  }, [])

  const sendResize = useCallback(() => {
    const term = termRef.current
    if (!term) return
    send(`\x1eRESIZE:${term.cols},${term.rows}`)
  }, [send])

  useEffect(() => {
    const term = new XTerm({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Consolas, "Liberation Mono", monospace',
      theme: {
        background: '#0d0f12',
        foreground: '#d7dade',
        cursor: '#f53f3f',
        selectionBackground: '#3a4b66',
      },
      // 移动端不拦截触摸，避免与页面滚动/输入冲突
      scrollback: 3000,
      allowProposedApi: true,
    })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(hostRef.current)
    termRef.current = term
    fitRef.current = fit

    // 让 xterm 在获得焦点时把输入交给下方真实输入框（移动端可靠唤起键盘）
    const el = hostRef.current?.querySelector('.xterm-screen') || hostRef.current
    const handleTap = () => {
      setTimeout(() => inputRef.current?.focus(), 0)
    }
    el?.addEventListener('click', handleTap)
    el?.addEventListener('touchend', handleTap)

    try {
      fit.fit()
    } catch (e) {
      /* 容器尚未布局完成时忽略 */
    }

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${location.host}/admin/ws/term`)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('已连接')
      try {
        fit.fit()
      } catch (e) {
        /* noop */
      }
      sendResize()
      term.focus()
    }
    ws.onmessage = (evt) => {
      if (typeof evt.data === 'string') term.write(evt.data)
      else term.write(new Uint8Array(evt.data))
    }
    ws.onerror = () => setStatus('连接错误')
    ws.onclose = () => {
      setStatus('已断开')
      term.write('\r\n\x1b[31m[连接已断开]\x1b[0m\r\n')
    }

    term.onData((data) => send(data))
    term.onResize(() => sendResize())

    const onWinResize = () => {
      try {
        fit.fit()
        sendResize()
      } catch (e) {
        /* noop */
      }
    }
    window.addEventListener('resize', onWinResize)

    return () => {
      window.removeEventListener('resize', onWinResize)
      el?.removeEventListener('click', handleTap)
      el?.removeEventListener('touchend', handleTap)
      try {
        ws.close()
      } catch (e) {
        /* noop */
      }
      term.dispose()
    }
  }, [send, sendResize])

  // 移动端 / 桌面端通用的输入栏：真实 input，软键盘必定可唤起，且支持中文输入法
  const submitLine = () => {
    const text = input
    if (!text) {
      send('\r')
      return
    }
    send(text)
    if (!text.endsWith('\r')) send('\r')
    setInput('')
    inputRef.current?.focus()
  }

  const sendKey = (seq) => {
    send(seq)
    inputRef.current?.focus()
  }

  const reconnect = () => {
    window.location.reload()
  }

  const clearScreen = () => {
    termRef.current?.clear()
    send('\x0c')
  }

  return (
    <div className="panel">
      <div className="toolbar">
        <Tag color={status === '已连接' ? 'green' : status === '连接中' ? 'orange' : 'red'}>
          {status}
        </Tag>
        <span className="text-weak" style={{ fontSize: 13 }}>
          在浏览器中打开容器 Shell，可执行任意命令，无需独立 SSH
        </span>
        <span style={{ flex: 1 }} />
        <Space>
          <Button size="small" icon={<IconDelete />} onClick={clearScreen}>
            清屏
          </Button>
          <Button size="small" icon={<IconRefresh />} onClick={reconnect}>
            重连
          </Button>
        </Space>
      </div>

      <div className="term-wrap">
        <div className="term-body" ref={hostRef} />
        <div className="term-mobile-bar">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                submitLine()
              }
            }}
            placeholder="在此输入命令后回车发送"
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
          />
          <button className="term-key" onClick={submitLine}>
            发送
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
        {KEYS.map((k) => (
          <button key={k.label} className="term-key" onClick={() => sendKey(k.seq)}>
            {k.label}
          </button>
        ))}
      </div>
    </div>
  )
}
