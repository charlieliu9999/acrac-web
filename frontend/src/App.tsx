import React, { useEffect, useState } from 'react'
import { Layout, Menu, Switch, theme, message } from 'antd'
import { Link, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import RAGAssistant from './pages/RAGAssistant'
import RulesManager from './pages/RulesManager'
import DataBrowser from './pages/DataBrowser'
import Tools from './pages/Tools'
import DataImport from './pages/DataImport'
import ModelConfig from './pages/ModelConfig'
import RAGEvaluation from './pages/RAGEvaluation'
import { api } from './api/http'

const { Header, Content, Sider, Footer } = Layout

function App() {
  const {
    token: { colorBgContainer },
  } = theme.useToken()
  const location = useLocation()
  const navigate = useNavigate()
  const [enabled, setEnabled] = useState<boolean>(false)
  const [auditOnly, setAuditOnly] = useState<boolean>(true)

  const selectedKey = React.useMemo(() => {
    if (location.pathname.startsWith('/rules')) return 'rules'
    if (location.pathname.startsWith('/data')) return 'data'
    if (location.pathname.startsWith('/tools')) return 'tools'
    if (location.pathname.startsWith('/import')) return 'import'
    if (location.pathname.startsWith('/models')) return 'models'
    if (location.pathname.startsWith('/evaluation')) return 'evaluation'
    return 'assistant'
  }, [location.pathname])

  useEffect(() => {
    api.get('/api/v1/acrac/rag-llm/rules-config').then(res => {
      setEnabled(res.data.enabled)
      setAuditOnly(res.data.audit_only)
    }).catch(() => {})
  }, [])

  const updateRules = async (p: { enabled?: boolean; audit_only?: boolean }) => {
    try {
      const res = await api.post('/api/v1/acrac/rag-llm/rules-config', {
        enabled: p.enabled ?? enabled,
        audit_only: p.audit_only ?? auditOnly,
      })
      if (p.enabled !== undefined) setEnabled(p.enabled)
      if (p.audit_only !== undefined) setAuditOnly(p.audit_only)
      message.success('规则引擎配置已更新')
    } catch (e:any) {
      message.error('更新规则配置失败: ' + (e?.response?.data?.detail || e.message))
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider breakpoint="lg" collapsedWidth="0">
        <div className="logo">ACRAC Admin</div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          onClick={(e) => {
            if (e.key === 'assistant') navigate('/')
            if (e.key === 'rules') navigate('/rules')
            if (e.key === 'data') navigate('/data')
            if (e.key === 'tools') navigate('/tools')
            if (e.key === 'import') navigate('/import')
            if (e.key === 'models') navigate('/models')
            if (e.key === 'evaluation') navigate('/evaluation')
          }}
          items={[
            { key: 'assistant', label: 'RAG 助手' },
            { key: 'evaluation', label: 'RAG 评测' },
            { key: 'rules', label: '规则管理' },
            { key: 'data', label: '数据浏览' },
            { key: 'tools', label: '工具箱' },
            { key: 'import', label: '数据导入' },
            { key: 'models', label: '模型配置' },
          ]}
        />
      </Sider>
      <Layout>
        <Header style={{ background: colorBgContainer, display: 'flex', gap: 16, alignItems: 'center' }}>
          <div style={{ fontWeight: 600 }}>规则引擎：</div>
          <span>启用</span>
          <Switch checked={enabled} onChange={(v)=>updateRules({enabled:v})} />
          <span style={{ marginLeft: 12 }}>仅审计</span>
          <Switch checked={auditOnly} onChange={(v)=>updateRules({audit_only:v})} />
          <div style={{ marginLeft: 'auto' }}>
            <a href="/docs" target="_blank" rel="noreferrer">API Docs</a>
          </div>
        </Header>
        <Content style={{ margin: '16px' }}>
          <div style={{ padding: 16, minHeight: 360, background: colorBgContainer }}>
            <Routes>
              <Route path="/" element={<RAGAssistant />} />
              <Route path="/evaluation" element={<RAGEvaluation />} />
              <Route path="/rules" element={<RulesManager />} />
              <Route path="/data" element={<DataBrowser />} />
              <Route path="/tools" element={<Tools />} />
              <Route path="/import" element={<DataImport />} />
              <Route path="/models" element={<ModelConfig />} />
            </Routes>
          </div>
        </Content>
        <Footer style={{ textAlign: 'center' }}>ACRAC Admin ©2025</Footer>
      </Layout>
    </Layout>
  )
}

export default App

