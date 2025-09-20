import React, { useEffect, useMemo, useState } from 'react'
import { Card, Form, Input, Button, Space, message, Alert, Row, Col, Typography, Divider, Tabs, Select, Table, Popconfirm, Tag, Modal } from 'antd'
import { api } from '../api/http'
import { API_BASE } from '../config'

const { Text } = Typography

const ModelConfig: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [reloading, setReloading] = useState(false)
  const [config, setConfig] = useState<any>(null)
  const [contexts, setContexts] = useState<any>({ inference: {}, evaluation: {} })
  const [overrides, setOverrides] = useState<any[]>([])
  const [checking, setChecking] = useState(false)
  const [checkResult, setCheckResult] = useState<any>(null)
  const [ragasChecking, setRagasChecking] = useState(false)
  const [ragasCheckResult, setRagasCheckResult] = useState<any>(null)
  const [registry, setRegistry] = useState<any>({ llms: [], embeddings: [], rerankers: [] })
  const [regLoading, setRegLoading] = useState(false)
  const [newForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [editVisible, setEditVisible] = useState(false)
  const [editing, setEditing] = useState<any>(null)

  const inferenceCtx = useMemo(() => contexts?.inference || {}, [contexts])
  const evaluationCtx = useMemo(() => contexts?.evaluation || {}, [contexts])

  const buildOptions = useMemo(() => {
    const ensureOption = (map: Map<string, any>, value?: string, labelPrefix?: string, entry?: any) => {
      const val = (value || '').trim()
      if (!val || map.has(val)) return
      const label = labelPrefix ? `${labelPrefix} · ${val}` : val
      map.set(val, entry ? { value: val, label, _entry: entry } : { value: val, label })
    }

    const llmMap = new Map<string, any>()
    const embMap = new Map<string, any>()

    ;(registry.llms || []).forEach((item: any) => {
      ensureOption(llmMap, item.model, item.label || item.model, item)
    })
    ;(registry.embeddings || []).forEach((item: any) => {
      ensureOption(embMap, item.model, item.label || item.model, item)
    })

    const tagCurrent = (label: string) => label

    ensureOption(llmMap, config?.llm_model, tagCurrent('当前推理'))
    ensureOption(embMap, config?.embedding_model, tagCurrent('当前推理'))
    ensureOption(llmMap, inferenceCtx?.llm_model, tagCurrent('推理默认'))
    ensureOption(embMap, inferenceCtx?.embedding_model, tagCurrent('推理默认'))
    ensureOption(llmMap, evaluationCtx?.llm_model, tagCurrent('评测默认'))
    ensureOption(embMap, evaluationCtx?.embedding_model, tagCurrent('评测默认'))

    overrides.forEach((ov) => {
      if (ov?.inference) {
        ensureOption(llmMap, ov.inference.llm_model, `覆盖-${ov.scope_id}`)
        ensureOption(embMap, ov.inference.embedding_model, `覆盖-${ov.scope_id}`)
      }
      if (ov?.evaluation) {
        ensureOption(llmMap, ov.evaluation.llm_model, `覆盖-${ov.scope_id}`)
        ensureOption(embMap, ov.evaluation.embedding_model, `覆盖-${ov.scope_id}`)
      }
    })

    return {
      llm: Array.from(llmMap.values()),
      embedding: Array.from(embMap.values()),
    }
  }, [registry, config, inferenceCtx, evaluationCtx, overrides])

  const load = async () => {
    // 先加载模型库，确保下拉选项始终可用
    try {
      setRegLoading(true)
      const rr = await api.get('/api/v1/admin/data/models/registry')
      setRegistry(rr.data || { llms: [], embeddings: [], rerankers: [] })
    } catch (e:any) {
      console.warn('加载模型库失败：' + (e?.response?.data?.detail || e.message))
      // 模型库加载失败时，提供默认选项避免下拉框空白
      setRegistry({ 
        llms: [
          { id: 'default-llm', label: '默认LLM', model: 'Qwen/Qwen2.5-32B-Instruct', provider: 'siliconflow' }
        ], 
        embeddings: [
          { id: 'default-embedding', label: '默认Embedding', model: 'BAAI/bge-m3', provider: 'siliconflow' }
        ], 
        rerankers: [] 
      })
    } finally {
      setRegLoading(false)
    }

    // 然后加载配置
    try {
      const r = await api.get('/api/v1/admin/data/models/config')
      setConfig(r.data)
      setContexts(r.data.contexts || { inference: {}, evaluation: {} })
      setOverrides(r.data.scenario_overrides || [])
      form.setFieldsValue({
        embedding_model: r.data.embedding_model,
        llm_model: r.data.llm_model,
        reranker_model: r.data.reranker_model,
        base_url: r.data.base_url,
        rerank_provider: r.data.rerank_provider || 'auto',
        ragas_llm_model: r.data.ragas_defaults?.llm_model || '',
        ragas_embedding_model: r.data.ragas_defaults?.embedding_model || '',
        siliconflow_api_key: '',
        openai_api_key: '',
      })
    } catch (e: any) {
      message.error('加载配置失败：' + (e?.response?.data?.detail || e.message))
    }
  }

  useEffect(() => { 
    load()
  }, [])

  const loadConfigOnly = async () => {
    try {
      const r = await api.get('/api/v1/admin/data/models/config')
      setConfig(r.data)
      setContexts(r.data.contexts || { inference: {}, evaluation: {} })
      setOverrides(r.data.scenario_overrides || [])
      form.setFieldsValue({
        embedding_model: r.data.embedding_model,
        llm_model: r.data.llm_model,
        reranker_model: r.data.reranker_model,
        base_url: r.data.base_url,
        rerank_provider: r.data.rerank_provider || 'auto',
        ragas_llm_model: r.data.ragas_defaults?.llm_model || '',
        ragas_embedding_model: r.data.ragas_defaults?.embedding_model || '',
        siliconflow_api_key: '',
        openai_api_key: '',
      })
    } catch (e: any) {
      message.error('加载配置失败：' + (e?.response?.data?.detail || e.message))
    }
  }
  // 自动自检：加载配置后，静默检查推理/评测上下文的连通性
  useEffect(() => {
    if (config) {
      checkConnectivity('inference', true)
      checkRagasConnectivity(true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config?.llm_model, config?.embedding_model, config?.base_url])

  const save = async (v: any) => {
    setLoading(true)
    try {
      // 统一 payload：contexts + overrides + 兼容旧字段
      const payload: any = {
        // API keys（可选）
        siliconflow_api_key: v.siliconflow_api_key || undefined,
        openai_api_key: v.openai_api_key || undefined,
        rerank_provider: v.rerank_provider || undefined,
        // 兼容旧字段（服务端仍会写入 .env）
        embedding_model: v.embedding_model,
        llm_model: v.llm_model,
        reranker_model: v.reranker_model,
        base_url: v.base_url,
        ragas_llm_model: v.ragas_llm_model,
        ragas_embedding_model: v.ragas_embedding_model,
        // 新结构
        contexts: {
          ...(contexts || {}),
          inference: {
            ...(contexts?.inference || {}),
            llm_model: v.llm_model,
            embedding_model: v.embedding_model,
            reranker_model: v.reranker_model,
            base_url: v.base_url,
          },
          evaluation: {
            ...(contexts?.evaluation || {}),
            llm_model: v.ragas_llm_model || (contexts?.evaluation?.llm_model ?? ''),
            embedding_model: v.ragas_embedding_model || (contexts?.evaluation?.embedding_model ?? ''),
            base_url: contexts?.evaluation?.base_url,
            reranker_model: contexts?.evaluation?.reranker_model,
          }
        },
        scenario_overrides: overrides || [],
      }
      const r = await api.post('/api/v1/admin/data/models/config', payload)
      message.success('已保存（部分配置需重启生效）')
      if (r.data.requires_restart) {
        message.warning('建议重启后端服务以完全生效')
      }
      load() // 重新加载配置
    } catch (e: any) {
      message.error('保存失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const reloadSvc = async () => {
    setReloading(true)
    try {
      await api.post('/api/v1/admin/data/models/reload')
      message.success('已重载服务实例')
    } catch (e: any) {
      message.error('重载失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setReloading(false)
    }
  }

  const checkConnectivity = async (ctxName?: string, silent?: boolean) => {
    setChecking(true)
    setCheckResult(null)
    try {
      const r = await api.get('/api/v1/admin/data/models/check', { params: ctxName ? { context: ctxName } : {} })
      setCheckResult(r.data)
      const ok = (r.data?.llm?.status === 'ok') && (r.data?.embedding?.status === 'ok')
      if (!silent) message[ok ? 'success' : 'warning']('连通性检查完成')
    } catch (e:any) {
      if (!silent) message.error('连通性检查失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setChecking(false)
    }
  }

  const checkRagasConnectivity = async (silent?: boolean) => {
    setRagasChecking(true)
    setRagasCheckResult(null)
    try {
      const r = await api.get('/api/v1/admin/data/models/check', { params: { context: 'evaluation' } })
      setRagasCheckResult(r.data)
      const ok = (r.data?.llm?.status === 'ok') && (r.data?.embedding?.status === 'ok')
      if (!silent) message[ok ? 'success' : 'warning']('RAGAS 连接测试完成')
    } catch (e:any) {
      if (!silent) message.error('RAGAS 连接测试失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setRagasChecking(false)
    }
  }

  const columnsOverrides = [
    { title: '范围', dataIndex: 'scope_type', width: 120, render: (v:string)=> <Tag>{v}</Tag> },
    { title: 'ID', dataIndex: 'scope_id', width: 180 },
    { title: '名称', dataIndex: 'scope_label', width: 200 },
    { title: '推理覆盖', dataIndex: 'inference', render: (c:any)=> c? `${c.llm_model||'-'} | ${c.embedding_model||'-'}`:'-' },
    { title: '评测覆盖', dataIndex: 'evaluation', render: (c:any)=> c? `${c.llm_model||'-'} | ${c.embedding_model||'-'}`:'-' },
    { title: '操作', width: 120, render: (_:any, r:any, idx:number)=> (
      <Space>
        <Popconfirm title='确认删除此覆盖？' onConfirm={()=>{
          const next = overrides.filter((_,i)=> i!==idx)
          setOverrides(next)
          message.success('已从列表移除（记得保存配置）')
        }}>
          <Button size='small' danger>删除</Button>
        </Popconfirm>
      </Space>
    )}
  ]

  return (
    <div>
      <div className='page-title'>模型配置</div>
      <Alert
        type='info'
        showIcon
        style={{ marginBottom: 16 }}
        message='使用说明'
        description={(
          <div>
            <div>· “保存配置” 会写入后端 `config/model_contexts.json` 与 `.env`，随后新请求立即使用该配置。</div>
            <div>· “重载服务” 可在不重启进程的情况下刷新 RAG 推理实例；如调整模型密钥或基地址，建议重载一次。</div>
            <div>· 首次修改后，建议点击对应上下文的“连接测试”确保模型与密钥可用。</div>
          </div>
        )}
      />
      
      <Card title="当前配置状态" style={{ marginBottom: 16 }}>
        {config && (
          <Row gutter={16}>
            <Col span={12}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <div><Text strong>API Keys 状态：</Text></div>
                <div>
                  <Text type={config.keys?.siliconflow_api_key ? 'success' : 'danger'}>
                    SiliconFlow API Key: {config.keys?.siliconflow_api_key ? '已配置' : '未配置'}
                  </Text>
                </div>
                <div>
                  <Text type={config.keys?.openai_api_key ? 'success' : 'warning'}>
                    OpenAI API Key: {config.keys?.openai_api_key ? '已配置' : '未配置'}
                  </Text>
                </div>
              </Space>
            </Col>
            <Col span={12}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <div><Text strong>当前模型：</Text></div>
                <div>Embedding: {config.embedding_model || '未设置'}</div>
                <div>LLM: {config.llm_model || '未设置'}</div>
                <div>Reranker: {config.reranker_model || '未设置'}</div>
                <div>Reranker Provider: {config.rerank_provider || 'auto'}</div>
                <div>Base URL: {config.base_url || '未设置'}</div>
              </Space>
            </Col>
          </Row>
        )}
      </Card>

      <Card title="前端运行环境" style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={12}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>页面地址: <Text code>{window.location.origin}</Text></div>
              <div>Axios BaseURL: <Text code>{API_BASE || '(未设置，使用相对路径)'}</Text></div>
              <div>
                建议：
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  <li>Docker/Nginx 模式可留空（使用相对路径 /api/... 由网关代理）。</li>
                  <li>本机直连开发请设置 VITE_API_BASE，例如 <Text code>http://localhost:8001/api/v1</Text>。</li>
                </ul>
              </div>
            </Space>
          </Col>
          <Col span={12}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>后端健康检查: <Text code>{(API_BASE || '/api/v1') + '/acrac/health'}</Text></div>
              <div>模型配置接口: <Text code>{(API_BASE || '/api/v1') + '/admin/data/models/config'}</Text></div>
            </Space>
          </Col>
        </Row>
      </Card>

      <Card title="模型库（管理与新增）" style={{ marginTop: 16 }}>
        <Alert message='在此查看/新增 LLM、Embedding、Reranker。上方下拉框会显示已注册模型。优先使用环境变量名（推荐）。' type='info' showIcon style={{ marginBottom: 12 }} />

        <Table
          loading={regLoading}
          rowKey={(r:any)=> `${r._kind}:${r.id}`}
          dataSource={[...(registry.llms||[]).map((x:any)=>({ ...x, _kind:'llm'})), ...(registry.embeddings||[]).map((x:any)=>({ ...x, _kind:'embedding'})), ...(registry.rerankers||[]).map((x:any)=>({ ...x, _kind:'reranker'}))]}
          columns={[
            { title:'类型', dataIndex:'_kind', width:100 },
            { title:'名称', dataIndex:'label', width:200 },
            { title:'模型ID', dataIndex:'model' },
            { title:'Provider', dataIndex:'provider', width:140 },
            { title:'Base URL', dataIndex:'base_url' },
            { title:'Key/ENV', width:140, render: (_:any, r:any)=> (r.has_api_key || r.api_key_env)? '已配置' : '未配置' },
            { title:'操作', width:200, render: (_:any, r:any)=> (
              <Space>
                <Button size='small' onClick={()=>{
                  setEditing(r)
                  editForm.setFieldsValue({
                    id: r.id,
                    label: r.label,
                    model: r.model,
                    base_url: r.base_url,
                    api_key_env: r.api_key_env,
                    api_key: '',
                  })
                  setEditVisible(true)
                }}>编辑</Button>
                <Button size='small' onClick={async()=>{
                  try {
                    const resp = await api.post('/api/v1/admin/data/models/check-model', r)
                    message[resp.data?.status === 'ok' ? 'success':'warning'](`测试完成: ${resp.data?.status}`)
                  } catch (e:any) { message.error('测试失败: '+(e?.response?.data?.detail||e.message)) }
                }}>测试</Button>
                <Popconfirm title='确认删除该条目？' onConfirm={async()=>{
                  try {
                    await api.delete(`/api/v1/admin/data/models/registry/${r._kind}/${r.id}`)
                    message.success('已删除'); load();
                  } catch (e:any) { message.error('删除失败: '+(e?.response?.data?.detail||e.message)) }
                }}>
                  <Button size='small' danger>删除</Button>
                </Popconfirm>
              </Space>
            ) }
          ]}
          pagination={{ pageSize: 5 }}
          style={{ marginBottom: 16 }}
        />

        <Modal
          title={`编辑模型（${editing?._kind?.toUpperCase()}: ${editing?.id||''}）`}
          open={editVisible}
          onCancel={()=>{ setEditVisible(false); setEditing(null); editForm.resetFields() }}
          onOk={async ()=>{
            try {
              const v = await editForm.validateFields()
              // 先进行模型连通性测试，失败则禁止保存
              const testEntry = {
                provider: editing?.provider,
                kind: editing?._kind,
                model: v.model || editing?.model,
                base_url: v.base_url || editing?.base_url,
                api_key_env: v.api_key_env || editing?.api_key_env,
                api_key: v.api_key || undefined,
                label: v.label || editing?.label,
              }
              try {
                const resp = await api.post('/api/v1/admin/data/models/check-model', testEntry)
                const status = resp.data?.status
                if (status !== 'ok') {
                  message.error(`模型连通性测试未通过：${status || 'error'}`)
                  return
                }
              } catch (e:any) {
                message.error('模型连通性测试失败：' + (e?.response?.data?.detail || e.message))
                return
              }

              const payload: any = {}
              ;['label','model','base_url','api_key_env','api_key'].forEach((k)=>{
                if (v[k] !== undefined && v[k] !== (editing?.[k]||'')) {
                  if (k === 'api_key' && !v[k]) return // 空的key不覆盖
                  payload[k] = v[k]
                }
              })
              if (Object.keys(payload).length === 0) {
                setEditVisible(false); setEditing(null); editForm.resetFields(); return
              }
              await api.patch(`/api/v1/admin/data/models/registry/${editing._kind}/${editing.id}`, payload)
              message.success('已更新')
              setEditVisible(false); setEditing(null); editForm.resetFields();
              load()
            } catch (e:any) {
              if (e?.errorFields) return; // 表单校验
              message.error('更新失败：' + (e?.response?.data?.detail || e.message))
            }
          }}
          okText='保存'
          cancelText='取消'
          destroyOnClose
        >
          <Form form={editForm} layout='vertical'>
            <Form.Item name='id' label='ID'>
              <Input disabled />
            </Form.Item>
            <Form.Item name='label' label='名称' rules={[{ required: true, message: '请输入名称' }]}> 
              <Input placeholder='显示名称' />
            </Form.Item>
            <Form.Item name='model' label='模型ID' rules={[{ required: true, message: '请输入模型ID' }]}> 
              <Input placeholder='如 Qwen/Qwen3-32B 或 qwen3:30b' />
            </Form.Item>
            <Form.Item name='base_url' label='Base URL' extra='Ollama 建议 http://localhost:11434/v1'>
              <Input id='edit_base_url' placeholder='如 https://api.siliconflow.cn/v1 或 http://localhost:11434/v1' />
            </Form.Item>
            <Form.Item name='api_key_env' label='API Key 环境变量（推荐）'>
              <Input placeholder='如 SILICONFLOW_API_KEY 或 OPENAI_API_KEY' />
            </Form.Item>
            <Form.Item name='api_key' label='API Key（可选，优先使用ENV）'>
              <Input.Password placeholder='不填则沿用原值' />
            </Form.Item>
          </Form>
        </Modal>

        <Divider orientation='left'>新增条目</Divider>
        <Form form={newForm} layout='vertical' onFinish={async (v:any)=>{
          try {
            const entry = {
              label: v.label,
              provider: v.provider||'siliconflow',
              kind: v.kind,
              model: v.model,
              base_url: v.base_url,
              api_key_env: v.api_key_env||'',
              api_key: v.api_key||''
            }
            // 先测试连通性，未通过则拒绝保存
            try {
              const resp = await api.post('/api/v1/admin/data/models/check-model', entry)
              if (resp.data?.status !== 'ok') {
                message.error(`模型连通性测试未通过：${resp.data?.status || 'error'}`)
                return
              }
            } catch (e:any) {
              message.error('模型连通性测试失败：' + (e?.response?.data?.detail || e.message))
              return
            }

            await api.post(`/api/v1/admin/data/models/registry/${v.kind}`, entry)
            message.success('已保存到模型库'); newForm.resetFields(); load()
          } catch (e:any) {
            message.error('保存失败：' + (e?.response?.data?.detail || e.message))
          }
        }}>
          <Row gutter={16}>
            <Col span={6}><Form.Item name='kind' label='类型' rules={[{required:true}]}><Select options={[{value:'llm',label:'LLM'},{value:'embedding',label:'Embedding'},{value:'reranker',label:'Reranker'}]} /></Form.Item></Col>
            <Col span={9}><Form.Item name='label' label='名称' rules={[{required:true}]}><Input placeholder='显示名称（随意命名，用于展示）' /></Form.Item></Col>
            <Col span={9}><Form.Item name='provider' label='Provider'><Select options={[{value:'siliconflow',label:'SiliconFlow'},{value:'openai',label:'OpenAI'},{value:'ollama',label:'Ollama'},{value:'dashscope',label:'DashScope'}]} /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}><Form.Item name='model' label='模型ID' rules={[{required:true}]}><Input placeholder='LLM: Qwen/Qwen2.5-32B-Instruct 或 qwen3:30b; Embedding: BAAI/bge-m3; Reranker: BAAI/bge-reranker-v2-m3' /></Form.Item></Col>
            <Col span={8}><Form.Item name='base_url' label='Base URL'><Input id='registry_base_url' placeholder='https://api.siliconflow.cn/v1 或 http://localhost:11434/v1' /></Form.Item></Col>
            <Col span={8}><Form.Item name='api_key_env' label='API Key ENV（推荐）'><Input placeholder='SILICONFLOW_API_KEY 或 OPENAI_API_KEY' /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={16}><Form.Item name='api_key' label='API Key（可选）'><Input.Password placeholder='直填Key（仅用于本机测试）' /></Form.Item></Col>
            <Col span={8} style={{ display:'flex', alignItems:'end' }}><Button type='primary' htmlType='submit'>保存到模型库</Button></Col>
          </Row>
        </Form>
      </Card>

      <Card title="模型配置">
        <Form form={form} layout='vertical' onFinish={save} initialValues={{
          embedding_model: '',
          llm_model: '',
          reranker_model: '',
          base_url: '',
          rerank_provider: 'auto',
          siliconflow_api_key: '',
          openai_api_key: '',
          ragas_llm_model: '',
          ragas_embedding_model: ''
        }}>
          <Tabs items={[
            {
              key: 'inference',
              label: '推理上下文（inference）',
              children: (
                <>
                  <Alert
                    type='info'
                    showIcon
                    style={{ marginBottom: 12 }}
                    message='应用范围'
                    description={(
                      <div>
                        <div>· 作用于 RAG 智能推荐 API、RAG 助手页面、工具箱实时调试等“推理”场景。</div>
                        <div>· 下拉选项来自模型库，若手动输入自定义模型，请填写完整的模型 ID 与 Base URL。</div>
                        <div>· 保存后即可生效，必要时通过“重载服务”刷新后端实例。</div>
                      </div>
                    )}
                  />
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name='llm_model' label='LLM 模型'>
                        <Select
                          showSearch
                          allowClear
                          placeholder='选择已注册的 LLM 模型'
                          options={buildOptions.llm}
                          filterOption={(i,o)=> (o?.label as string).toLowerCase().includes(i.toLowerCase())}
                          onChange={(v, opt:any)=>{ const entry = opt?._entry; if (entry?.base_url) form.setFieldsValue({ base_url: entry.base_url }) }}
                        />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item name='embedding_model' label='Embedding 模型'>
                        <Select
                          showSearch
                          allowClear
                          placeholder='选择已注册的 Embedding 模型'
                          options={buildOptions.embedding}
                          filterOption={(i,o)=> (o?.label as string).toLowerCase().includes(i.toLowerCase())}
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name='reranker_model' label='重排模型'>
                        <Input placeholder='BAAI/bge-reranker-v2-m3' />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item name='base_url' label='Base URL'>
                        <Input id='inference_base_url' placeholder='https://api.siliconflow.cn/v1' />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name='rerank_provider' label='Reranker 提供方'>
                        <Select
                          options={[
                            { value: 'auto', label: '自动（Ollama→本地 Transformers；否则 SiliconFlow）' },
                            { value: 'local', label: '本地 Transformers（CrossEncoder）' },
                            { value: 'siliconflow', label: 'SiliconFlow /rerank 接口' }
                          ]}
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Space>
                    <Button onClick={()=>checkConnectivity('inference')} loading={checking}>连接测试（推理）</Button>
                    <Text type='secondary'>当前：{contexts?.inference?.llm_model || '-'} | {contexts?.inference?.embedding_model || '-'}</Text>
                  </Space>
                </>
              )
            },
            {
              key: 'evaluation',
              label: '评测上下文（evaluation / RAGAS）',
              children: (
                <>
                  <Alert
                    type='info'
                    showIcon
                    style={{ marginBottom: 12 }}
                    message='应用范围'
                    description={(
                      <div>
                        <div>· 用于 RAG 评测面板与 `/api/v1/acrac/tools/ragas/*` 相关接口。</div>
                        <div>· 通常选择与推理不同的轻量模型以降低评测成本，或指定专用的评测专线。</div>
                        <div>· 若留空，将继承推理上下文的同名配置项。</div>
                      </div>
                    )}
                  />
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name='ragas_llm_model' label='评测 LLM 模型'>
                        <Select
                          showSearch
                          allowClear
                          placeholder='选择已注册的 LLM 模型'
                          options={buildOptions.llm}
                        />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item name='ragas_embedding_model' label='评测 Embedding 模型'>
                        <Select
                          showSearch
                          allowClear
                          placeholder='选择已注册的 Embedding 模型'
                          options={buildOptions.embedding}
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Space>
                    <Button onClick={checkRagasConnectivity} loading={ragasChecking}>连接测试（评测）</Button>
                    <Text type='secondary'>当前：{contexts?.evaluation?.llm_model || '-'} | {contexts?.evaluation?.embedding_model || '-'}</Text>
                  </Space>
                </>
              )
            },
            {
              key: 'overrides',
              label: '场景覆盖（按科室/主题/场景/自定义）',
              children: (
                <>
                  <Alert
                    type='info'
                    showIcon
                    style={{ marginBottom: 12 }}
                    message='覆盖规则'
                    description={(
                      <div>
                        <div>· 优先级：场景 &gt; 主题 &gt; 科室 &gt; 自定义标签；命中后会覆盖对应上下文的模型、基地址与重排器。</div>
                        <div>· Scope ID 使用语义化编号（如 `P0001`、`T0042`、`S0138`）。自定义类型可与业务标签对齐。</div>
                        <div>· 添加后需点击“保存配置”写入后端，再通过“重载服务”确保新覆盖生效。</div>
                      </div>
                    )}
                  />
                  <Form layout='vertical' onFinish={(v:any)=>{
                    const next = [
                      ...overrides,
                      {
                        scope_type: v.scope_type,
                        scope_id: v.scope_id,
                        scope_label: v.scope_label,
                        inference: v.inf_llm_model || v.inf_embedding_model || v.inf_reranker_model || v.inf_base_url ? {
                          llm_model: v.inf_llm_model || undefined,
                          embedding_model: v.inf_embedding_model || undefined,
                          reranker_model: v.inf_reranker_model || undefined,
                          base_url: v.inf_base_url || undefined,
                        } : undefined,
                        evaluation: v.ev_llm_model || v.ev_embedding_model || v.ev_reranker_model || v.ev_base_url ? {
                          llm_model: v.ev_llm_model || undefined,
                          embedding_model: v.ev_embedding_model || undefined,
                          reranker_model: v.ev_reranker_model || undefined,
                          base_url: v.ev_base_url || undefined,
                        } : undefined,
                      }
                    ]
                    setOverrides(next)
                    message.success('已加入覆盖列表（记得保存配置）')
                  }}>
                    <Row gutter={12}>
                      <Col span={6}><Form.Item name='scope_type' label='范围类型' rules={[{required:true}]}>
                        <Select options={[{value:'panel',label:'科室(panel)'},{value:'topic',label:'主题(topic)'},{value:'scenario',label:'场景(scenario)'},{value:'custom',label:'自定义'}]} />
                      </Form.Item></Col>
                      <Col span={6}><Form.Item name='scope_id' label='范围ID' rules={[{required:true}]}>
                        <Input placeholder='如 P001 / T001 / S001 / 任意ID' />
                      </Form.Item></Col>
                      <Col span={6}><Form.Item name='scope_label' label='显示名称'>
                        <Input placeholder='可选，便于识别' />
                      </Form.Item></Col>
                      <Col span={6} style={{display:'flex',alignItems:'end'}}>
                        <Button htmlType='submit' type='primary'>添加覆盖</Button>
                      </Col>
                    </Row>
                    <Divider orientation='left'>推理覆盖</Divider>
                    <Row gutter={12}>
                      <Col span={6}><Form.Item name='inf_llm_model' label='LLM'>
                        <Select showSearch allowClear options={buildOptions.llm} />
                      </Form.Item></Col>
                      <Col span={6}><Form.Item name='inf_embedding_model' label='Embedding'>
                        <Select showSearch allowClear options={buildOptions.embedding} />
                      </Form.Item></Col>
                      <Col span={6}><Form.Item name='inf_reranker_model' label='Reranker'><Input placeholder='可选'/></Form.Item></Col>
                      <Col span={6}><Form.Item name='inf_base_url' label='Base URL'><Input placeholder='可选'/></Form.Item></Col>
                    </Row>
                    <Divider orientation='left'>评测覆盖</Divider>
                    <Row gutter={12}>
                      <Col span={6}><Form.Item name='ev_llm_model' label='LLM'>
                        <Select showSearch allowClear options={buildOptions.llm} />
                      </Form.Item></Col>
                      <Col span={6}><Form.Item name='ev_embedding_model' label='Embedding'>
                        <Select showSearch allowClear options={buildOptions.embedding} />
                      </Form.Item></Col>
                      <Col span={6}><Form.Item name='ev_reranker_model' label='Reranker'><Input placeholder='可选'/></Form.Item></Col>
                      <Col span={6}><Form.Item name='ev_base_url' label='Base URL'><Input placeholder='可选'/></Form.Item></Col>
                    </Row>
                  </Form>
                  <Divider />
                  <Table rowKey={(r:any,idx)=> `${r.scope_type}:${r.scope_id}:${idx}`}
                         dataSource={overrides}
                         columns={columnsOverrides}
                         pagination={{ pageSize: 5 }} />
                </>
              )
            },
            {
              key: 'keys',
              label: 'API Keys',
              children: (
                <>
                  <Divider orientation="left">API Key 配置</Divider>
                  <Alert
                    message="安全与生效方式"
                    description={(
                      <div>
                        <div>· API Key 是敏感信息，输入后将被安全存储在后端，仅用于调用对应模型服务。</div>
                        <div>· 为空表示不更新原值；如需替换 Key，请填入新值并保存。</div>
                        <div>· 修改 Key 或 Base URL 后建议点击“重载服务”，以便后端客户端即时更新。</div>
                      </div>
                    )}
                    type="warning"
                    showIcon
                    style={{ marginBottom: 16 }}
                  />
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        name='siliconflow_api_key'
                        label='SiliconFlow API Key'
                        extra="用于访问 SiliconFlow 模型服务"
                      >
                        <Input.Password placeholder='输入 SiliconFlow API Key' />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name='openai_api_key'
                        label='OpenAI API Key（可选）'
                        extra="用于访问 OpenAI 模型服务"
                      >
                        <Input.Password placeholder='输入 OpenAI API Key（可选）' />
                      </Form.Item>
                    </Col>
                  </Row>
                </>
              )
            }
          ]} />

          <Alert
            message="配置说明"
            description="修改配置后建议重启后端服务以确保所有配置完全生效。重载服务按钮可以应用部分配置（如Base URL、模型名等）而无需重启。API Key 配置会立即生效。"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />

          <Space>
            <Button type='primary' htmlType='submit' loading={loading}>保存配置</Button>
            <Button onClick={reloadSvc} loading={reloading}>重载服务</Button>
            <Button onClick={load}>刷新状态</Button>
          </Space>
        </Form>
      </Card>

      {checkResult && (
        <Card title="连通性结果" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={8}>
              <Alert
                message={`LLM（${checkResult?.env?.llm_model || '未设置'}）`}
                description={checkResult?.llm?.status === 'ok' ? `正常 · ${checkResult?.llm?.latency_ms} ms` : (checkResult?.llm?.error || '未知错误')}
                type={checkResult?.llm?.status === 'ok' ? 'success' : (checkResult?.llm?.status === 'warning' ? 'warning' : 'error')}
                showIcon
              />
            </Col>
            <Col span={8}>
              <Alert
                message={`Embedding（${checkResult?.env?.embedding_model || '未设置'}）`}
                description={checkResult?.embedding?.status === 'ok' ? `正常 · 维度 ${checkResult?.embedding?.dimension}` : (checkResult?.embedding?.error || '未知错误')}
                type={checkResult?.embedding?.status === 'ok' ? 'success' : (checkResult?.embedding?.status === 'warning' ? 'warning' : 'error')}
                showIcon
              />
            </Col>
            <Col span={8}>
              <Alert
                message={`Reranker（${checkResult?.env?.reranker_model || '未设置'}）`}
                description={checkResult?.reranker?.status === 'ok' ? `正常 · HTTP ${checkResult?.reranker?.http_status}` : (checkResult?.reranker?.error || '未检测')}
                type={checkResult?.reranker?.status === 'ok' ? 'success' : (checkResult?.reranker?.status === 'warning' ? 'warning' : 'error')}
                showIcon
              />
            </Col>
          </Row>
        </Card>
      )}

      {ragasCheckResult && (
        <Card title="RAGAS 连接结果" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Alert
                message={`LLM（${ragasCheckResult?.env?.llm_model || '未设置'}）`}
                description={ragasCheckResult?.llm?.status === 'ok' ? `正常 · ${ragasCheckResult?.llm?.latency_ms} ms` : (ragasCheckResult?.llm?.error || '未知错误')}
                type={ragasCheckResult?.llm?.status === 'ok' ? 'success' : (ragasCheckResult?.llm?.status === 'warning' ? 'warning' : 'error')}
                showIcon
              />
            </Col>
            <Col span={12}>
              <Alert
                message={`Embedding（${ragasCheckResult?.env?.embedding_model || '未设置'}）`}
                description={ragasCheckResult?.embedding?.status === 'ok' ? `正常 · 维度 ${ragasCheckResult?.embedding?.dimension}` : (ragasCheckResult?.embedding?.error || '未知错误')}
                type={ragasCheckResult?.embedding?.status === 'ok' ? 'success' : (ragasCheckResult?.embedding?.status === 'warning' ? 'warning' : 'error')}
                showIcon
              />
            </Col>
          </Row>
        </Card>
      )}
    </div>
  )
}

export default ModelConfig
