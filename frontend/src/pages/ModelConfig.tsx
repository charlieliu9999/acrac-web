import React, { useEffect, useState } from 'react'
import { Card, Form, Input, Button, Space, message, Alert, Row, Col, Switch, Typography, Divider, Tabs, Select, Table, Popconfirm } from 'antd'
import { api } from '../api/http'

const { Text } = Typography

const ModelConfig: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [reloading, setReloading] = useState(false)
  const [config, setConfig] = useState<any>(null)
  const [checking, setChecking] = useState(false)
  const [checkResult, setCheckResult] = useState<any>(null)
  const [ragasChecking, setRagasChecking] = useState(false)
  const [ragasCheckResult, setRagasCheckResult] = useState<any>(null)
  const [registry, setRegistry] = useState<any>({ llms: [], embeddings: [], rerankers: [] })
  const [regLoading, setRegLoading] = useState(false)
  const [newForm] = Form.useForm()

  const load = async () => {
    try {
      const r = await api.get('/api/v1/admin/data/models/config')
      setConfig(r.data)
      form.setFieldsValue({
        embedding_model: r.data.embedding_model,
        llm_model: r.data.llm_model,
        reranker_model: r.data.reranker_model,
        base_url: r.data.base_url,
        ragas_llm_model: r.data.ragas_defaults?.llm_model || '',
        ragas_embedding_model: r.data.ragas_defaults?.embedding_model || '',
        siliconflow_api_key: '',
        openai_api_key: '',
      })
      // 加载模型库
      try {
        setRegLoading(true)
        const rr = await api.get('/api/v1/admin/data/models/registry')
        setRegistry(rr.data || { llms: [], embeddings: [], rerankers: [] })
      } catch {} finally { setRegLoading(false) }
    } catch (e: any) {
      message.error('加载失败：' + (e?.response?.data?.detail || e.message))
    }
  }

  useEffect(() => { load() }, [])

  const save = async (v: any) => {
    setLoading(true)
    try {
      const r = await api.post('/api/v1/admin/data/models/config', v)
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

  const checkConnectivity = async () => {
    setChecking(true)
    setCheckResult(null)
    try {
      const r = await api.get('/api/v1/admin/data/models/check')
      setCheckResult(r.data)
      const ok = (r.data?.llm?.status === 'ok') && (r.data?.embedding?.status === 'ok')
      message[ok ? 'success' : 'warning']('连通性检查完成')
    } catch (e:any) {
      message.error('连通性检查失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setChecking(false)
    }
  }

  const checkRagasConnectivity = async () => {
    setRagasChecking(true)
    setRagasCheckResult(null)
    try {
      const r = await api.get('/api/v1/admin/data/models/check', { params: { context: 'ragas' } })
      setRagasCheckResult(r.data)
      const ok = (r.data?.llm?.status === 'ok') && (r.data?.embedding?.status === 'ok')
      message[ok ? 'success' : 'warning']('RAGAS 连接测试完成')
    } catch (e:any) {
      message.error('RAGAS 连接测试失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setRagasChecking(false)
    }
  }

  return (
    <div>
      <div className='page-title'>模型配置</div>
      
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
                <div>Base URL: {config.base_url || '未设置'}</div>
              </Space>
            </Col>
          </Row>
        )}
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
            { title:'Key/ENV', width:140, render: (_:any, r:any)=> (r.has_api_key || r.api_key_env)? (r.api_key_env||'已配置') : '未配置' },
            { title:'操作', width:200, render: (_:any, r:any)=> (
              <Space>
                <Button size='small' onClick={async()=>{
                  try {
                    const resp = await api.post('/api/v1/admin/data/models/check-model', r)
                    message[resp.data?.status === 'ok' ? 'success':'warning'](`测试完成: ${resp.data?.status}`)
                  } catch (e:any) { message.error('测试失败: '+(e?.response?.data?.detail||e.message)) }
                }}>测试</Button>
                <Popconfirm title='确认删除该条目？' onConfirm={async()=>{
                  try { const rr = await api.get('/api/v1/admin/data/models/registry');
                    const data = rr.data || { llms:[], embeddings:[], rerankers:[] };
                    const key = r._kind==='llm'? 'llms': r._kind==='embedding'? 'embeddings':'rerankers';
                    const filtered = (data[key]||[]).filter((x:any)=> x.id !== r.id);
                    const payload = { ...data, [key]: filtered };
                    await api.post('/api/v1/admin/data/models/registry', payload);
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

        <Divider orientation='left'>新增条目</Divider>
        <Form form={newForm} layout='vertical' onFinish={async (v:any)=>{
          try {
            const rr = await api.get('/api/v1/admin/data/models/registry');
            const data = rr.data || { llms: [], embeddings: [], rerankers: [] }
            const target = v.kind==='llm'? 'llms' : v.kind==='embedding'? 'embeddings' : 'rerankers'
            const entry = { label: v.label, provider: v.provider||'siliconflow', kind: v.kind, model: v.model, base_url: v.base_url, api_key_env: v.api_key_env||'', api_key: v.api_key||'' }
            const keyFn = (x:any)=> `${x.provider}-${x.kind}-${x.model}`
            const filtered = (data[target]||[]).filter((x:any)=> keyFn(x) !== keyFn(entry))
            const payload = { ...data, [target]: [...filtered, entry] }
            await api.post('/api/v1/admin/data/models/registry', payload)
            message.success('已保存到模型库'); newForm.resetFields(); load()
          } catch (e:any) {
            message.error('保存失败：' + (e?.response?.data?.detail || e.message))
          }
        }}>
          <Row gutter={16}>
            <Col span={6}><Form.Item name='kind' label='类型' rules={[{required:true}]}><Select options={[{value:'llm',label:'LLM'},{value:'embedding',label:'Embedding'},{value:'reranker',label:'Reranker'}]} /></Form.Item></Col>
            <Col span={6}><Form.Item name='id' label='ID' rules={[{required:true}]}><Input placeholder='唯一ID，如 sf-qwen-32b' /></Form.Item></Col>
            <Col span={6}><Form.Item name='label' label='名称' rules={[{required:true}]}><Input placeholder='显示名称' /></Form.Item></Col>
            <Col span={6}><Form.Item name='provider' label='Provider'><Select options={[{value:'siliconflow',label:'SiliconFlow'},{value:'openai',label:'OpenAI'},{value:'ollama',label:'Ollama'},{value:'dashscope',label:'DashScope'}]} /></Form.Item></Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}><Form.Item name='model' label='模型ID' rules={[{required:true}]}><Input placeholder='如 Qwen/Qwen2.5-32B-Instruct / BAAI/bge-m3' /></Form.Item></Col>
            <Col span={8}><Form.Item name='base_url' label='Base URL'><Input placeholder='https://api.siliconflow.cn/v1 或 http://localhost:11434/v1' /></Form.Item></Col>
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
          siliconflow_api_key: '',
          openai_api_key: '',
          ragas_llm_model: '',
          ragas_embedding_model: ''
        }}>
          <Tabs items={[
            {
              key: 'ragllm',
              label: 'RAG+LLM 上下文',
              children: (
                <>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name='llm_model' label='LLM 模型'>
                        <Select
                          showSearch
                          allowClear
                          placeholder='选择已注册的 LLM 模型'
                          options={(registry.llms||[]).map((m:any)=>({ value: m.model, label: `${m.label} · ${m.model}`, _entry: m }))}
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
                          options={(registry.embeddings||[]).map((m:any)=>({ value: m.model, label: `${m.label} · ${m.model}`, _entry: m }))}
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
                        <Input placeholder='https://api.siliconflow.cn/v1' />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Button onClick={checkConnectivity} loading={checking}>连接测试（RAG+LLM）</Button>
                </>
              )
            },
            {
              key: 'ragas',
              label: 'RAGAS 默认上下文',
              children: (
                <>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item name='ragas_llm_model' label='RAGAS LLM 模型（默认）'>
                        <Select
                          showSearch
                          allowClear
                          placeholder='选择已注册的 LLM 模型'
                          options={(registry.llms||[]).map((m:any)=>({ value: m.model, label: `${m.label} · ${m.model}`, _entry: m }))}
                        />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item name='ragas_embedding_model' label='RAGAS Embedding 模型（默认）'>
                        <Select
                          showSearch
                          allowClear
                          placeholder='选择已注册的 Embedding 模型'
                          options={(registry.embeddings||[]).map((m:any)=>({ value: m.model, label: `${m.label} · ${m.model}`, _entry: m }))}
                        />
                      </Form.Item>
                    </Col>
                  </Row>
                  <Button onClick={checkRagasConnectivity} loading={ragasChecking}>连接测试（RAGAS）</Button>
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
                    message="安全提示"
                    description="API Key 是敏感信息，请妥善保管。输入的 API Key 将被安全存储在服务器端，不会在前端明文显示。"
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
