import { Component } from 'react'
import { Button, Result } from '@arco-design/web-react'

/**
 * 页面级错误边界：避免任意子组件在渲染期抛错时整页白屏。
 * 捕获错误后展示可读的错误卡片与「重试」按钮，而不是留给用户一片空白。
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // 保留到控制台，便于排查
    console.error('[ErrorBoundary] 页面渲染出错：', error, info)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="panel">
        <Result
          status="error"
          title="页面出错了"
          subTitle={
            <span>
              {String(error?.message || error)}
              <div style={{ marginTop: 6, fontSize: 12, color: '#86909c' }}>
                已阻止页面白屏。可点击重试，或切换到其他页面。
              </div>
            </span>
          }
          extra={[
            <Button key="retry" type="primary" onClick={() => this.setState({ error: null })}>
              重试
            </Button>,
            <Button key="reload" onClick={() => window.location.reload()}>
              刷新页面
            </Button>,
          ]}
        />
      </div>
    )
  }
}
