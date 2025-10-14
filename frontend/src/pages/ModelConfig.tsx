import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../api/http'
import {
  Card,
  Row,
  Col,
  Space,
  Typography,
  Button,
  Alert,
  Form,
  Select,
  Input,
  InputNumber,
  Tabs,
  Table,
  Modal,
  Popconfirm,
  message,
} from 'antd'
import { SettingOutlined } from '@ant-design/icons'

const { Title, Text } = Typography

type Registry = { llms: any[]; embeddings: any[]; rerankers: any[] }

const ModelConfig: React.FC = () => {
  // 上下文与配置
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [reloading, setReloading] = useState(false)
  const [auditLoading, setAuditLoading] = useState(false)
  const [audit, setAudit] = useState<any>(null)
  const [contexts, setContexts] = useState<any>({ inference: {}, evaluation: {} })

  // 模型库
  const [registry, setRegistry] = useState<Registry>({ llms: [], embeddings: [], rerankers: [] })
  const [regLoading, setRegLoading] = useState(false)
  const [editVisible, setEditVisible] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [editForm] = Form.useForm()
  const [newForm] = Form.useForm()

  // 下拉选项（来源于模型库）
  const buildOptions = useMemo(() => {
    const toOpts = (arr: any[]) => (arr || []).map((x) => ({ value: x.model, label: `${x.provider}/${x.model}`, _entry: x }))
    return {
      llm: toOpts(registry.llms),
      embedding: toOpts(registry.embeddings),
    }
  }, [registry])

  // 载入配置
  const loadConfig = async () => {
    try {
      const r = await api.get('/api/v1/admin/data/models/config')
      const ctx = r.data?.contexts || { inference: {}, evaluation: {} }
      setContexts(ctx)
      form.setFieldsValue({
        llm_model: ctx?.inference?.llm_model,
        embedding_model: ctx?.inference?.embedding_model,
        reranker_model: ctx?.inference?.reranker_model,
        rerank_provider: r.data?.rerank_provider || 'auto',
        base_url: ctx?.inference?.base_url,
        ragas_llm_model: ctx?.evaluation?.llm_model,
        ragas_embedding_model: ctx?.evaluation?.embedding_model,
        inf_temperature: ctx?.inference?.temperature ?? null,
        inf_top_p: ctx?.inference?.top_p ?? null,
      })
    } catch (e: any) {
      message.error('加载配置失败：' + (e?.response?.data?.detail || e.message))
    }
  }

  // 载入模型库
  const loadRegistry = async () => {
    try {
      setRegLoading(true)
      const rr = await api.get('/api/v1/admin/data/models/registry')
      setRegistry(rr.data || { llms: [], embeddings: [], rerankers: [] })
    } catch (e: any) {
      message.error('加载模型库失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setRegLoading(false)
    }
  }

  const refreshAll = async () => {
    await Promise.all([loadConfig(), loadRegistry()])
  }

  useEffect(() => {
    refreshAll()
  }, [])

  // 保存上下文配置
  const save = async (v: any) => {
    setLoading(true)
    try {
      const payload = {
        rerank_provider: v.rerank_provider,
        contexts: {
          inference: {
            llm_model: v.llm_model,
            embedding_model: v.embedding_model,
            reranker_model: v.reranker_model,
            base_url: v.base_url,
            temperature: v.inf_temperature ?? undefined,
            top_p: v.inf_top_p ?? undefined,
          },
          evaluation: {
            llm_model: v.ragas_llm_model,
            embedding_model: v.ragas_embedding_model,
          },
        },
      }
      await api.post('/api/v1/admin/data/models/config', payload)
      message.success('已保存配置')
      await loadConfig()
    } catch (e: any) {
      message.error('保存失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  // 重载服务
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

  // 一致性审计
  const runAudit = async () => {
    setAuditLoading(true)
    setAudit(null)
    try {
      const r = await api.get('/api/v1/admin/data/models/audit')
      setAudit(r.data)
    } catch (e: any) {
      message.error('一致性检查失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setAuditLoading(false)
    }
  }

  // 推荐配置：Ollama LLM/Embedding + SiliconFlow Rerank
  const applyRecommended = () => {
    form.setFieldsValue({
      llm_model: 'qwen2.5:32b',
      embedding_model: 'bge-m3:latest',
      reranker_model: 'BAAI/bge-reranker-v2-m3',
      base_url: 'http://host.docker.internal:11434/v1',
      rerank_provider: 'siliconflow',
      ragas_llm_model: 'Qwen/Qwen2.5-32B-Instruct',
      ragas_embedding_model: 'BAAI/bge-m3',
    })
    message.success('已应用推荐配置：Ollama(LLM/Embedding) + SiliconFlow(Rerank)')
  }

  // 选择模型时联动 BaseURL（仅 LLM/Embedding）
  const onPickModel = (field: string, opt: any) => {
    const entry = opt?._entry
    if (!entry) return
    if (field === 'llm_model' || field === 'embedding_model') {
      if (entry.base_url) form.setFieldsValue({ base_url: entry.base_url })
    }
  }

  // 新增模型库条目
  const addRegistry = async (v: any) => {
    try {
      const entry = {
        label: v.label,
        provider: v.provider || 'siliconflow',
        kind: v.kind,
        model: v.model,
        base_url: v.base_url,
        api_key_env: v.api_key_env || '',
        api_key: v.api_key || '',
      }
      const resp = await api.post('/api/v1/admin/data/models/check-model', entry)
      if (resp.data?.status !== 'ok') {
        message.error(`模型连通性测试未通过：${resp.data?.status || 'error'}`)
        return
      }
      await api.post(`/api/v1/admin/data/models/registry/${v.kind}`, entry)
      message.success('已保存到模型库')
      newForm.resetFields()
      loadRegistry()
    } catch (e: any) {
      message.error('保存失败：' + (e?.response?.data?.detail || e.message))
    }
  }

  // 编辑模型库条目保存（全量覆盖）
  const saveEdit = async () => {
    try {
      const v = await editForm.validateFields()
      const testEntry = {
        provider: v.provider || editing.provider,
        kind: editing._kind,
        model: v.model || editing.model,
        base_url: v.base_url || editing.base_url,
        api_key_env: v.api_key_env || editing.api_key_env,
        api_key: v.api_key || undefined,
        label: v.label || editing.label,
      }
      const resp = await api.post('/api/v1/admin/data/models/check-model', testEntry)
      if (resp.data?.status !== 'ok') {
        message.error(`模型连通性测试未通过：${resp.data?.status || 'error'}`)
        return
      }
      const next: Registry = JSON.parse(JSON.stringify(registry))
      const key = editing._kind === 'llm' ? 'llms' : editing._kind === 'embedding' ? 'embeddings' : 'rerankers'
      const arr: any[] = next[key] || []
      const idx = arr.findIndex((x) => x.id === editing.id)
      const updated = {
        ...(arr[idx] || {}),
        id: editing.id,
        label: v.label || editing.label,
        provider: v.provider || editing.provider,
        model: v.model || editing.model,
        base_url: v.base_url || editing.base_url,
        api_key_env: v.api_key_env || editing.api_key_env,
        has_api_key: Boolean(v.api_key) || Boolean(editing.has_api_key),
      }
      if (idx >= 0) arr[idx] = updated
      else arr.push(updated)
      next[key] = arr
      await api.post('/api/v1/admin/data/models/registry', next)
      message.success('已更新')
      setEditVisible(false)
      setEditing(null)
      editForm.resetFields()
      loadRegistry()
    } catch (e: any) {
      if (e?.errorFields) return
      message.error('更新失败：' + (e?.response?.data?.detail || e.message))
    }
  }

  return (
    <div>
      <div className='page-title'>
        <Title level={2}>
          <SettingOutlined /> 模型配置管理
        </Title>
      </div>

      {/* 总览与操作 */}
      <Card title='总览与操作' style={{ marginBottom: 16 }}>
        {contexts && (
          <Row gutter={16}>
            <Col span={12}>
              <Space direction='vertical' style={{ width: '100%' }}>
                <Text strong>当前（inference）</Text>
                <div>LLM: {contexts?.inference?.llm_model || '-'}</div>
                <div>Embedding: {contexts?.inference?.embedding_model || '-'}</div>
                <div>Reranker: {contexts?.inference?.reranker_model || '-'}</div>
                <div>Base URL: {contexts?.inference?.base_url || '-'}</div>
              </Space>
            </Col>
            <Col span={12}>
              <Space direction='vertical' style={{ width: '100%' }}>
                <Space wrap>
                  <Button onClick={runAudit} loading={auditLoading}>一致性检查</Button>
                  <Button onClick={reloadSvc} loading={reloading} type='primary'>重载服务</Button>
                  <Button onClick={applyRecommended}>一键推荐</Button>
                </Space>
                {audit && (
                  <Alert
                    type={audit?.match?.inference && audit?.match?.evaluation ? 'success' : 'warning'}
                    showIcon
                    message='一致性检查结果'
                    description={
                      <pre className='mono' style={{ whiteSpace: 'pre-wrap', maxHeight: 220, overflow: 'auto' }}>
                        {JSON.stringify(audit, null, 2)}
                      </pre>
                    }
                  />
                )}
              </Space>
            </Col>
          </Row>
        )}
      </Card>

      {/* 上下文配置 */}
      <Card title='上下文配置'>
        <Form form={form} layout='vertical' onFinish={save} initialValues={{ rerank_provider: 'auto' }}>
          <Tabs
            items={[
              {
                key: 'inference',
                label: '推理（inference）',
                children: (
                  <>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name='llm_model' label='LLM 模型'>
                          <Select showSearch allowClear options={buildOptions.llm} onChange={(_, opt: any) => onPickModel('llm_model', opt)} />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name='embedding_model' label='Embedding 模型'>
                          <Select showSearch allowClear options={buildOptions.embedding} onChange={(_, opt: any) => onPickModel('embedding_model', opt)} />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name='reranker_model' label='Reranker 模型'>
                          <Input placeholder='BAAI/bge-reranker-v2-m3' />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name='base_url' label='Base URL'>
                          <Input placeholder='http://host.docker.internal:11434/v1' />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name='rerank_provider' label='Rerank 提供方'>
                          <Select options={[{ value: 'auto', label: '自动' }, { value: 'local', label: '本地' }, { value: 'siliconflow', label: 'SiliconFlow' }]} />
                        </Form.Item>
                      </Col>
                      <Col span={6}>
                        <Form.Item name='inf_temperature' label='Temperature'>
                          <InputNumber min={0} max={0.3} step={0.05} style={{ width: '100%' }} />
                        </Form.Item>
                      </Col>
                      <Col span={6}>
                        <Form.Item name='inf_top_p' label='Top-p'>
                          <InputNumber min={0} max={1} step={0.05} style={{ width: '100%' }} />
                        </Form.Item>
                      </Col>
                    </Row>
                    <Alert type='info' showIcon message='说明' description='Base URL 仅用于 LLM/Embedding；Rerank 始终使用 SILICONFLOW_BASE_URL + API Key。' />
                  </>
                ),
              },
              {
                key: 'evaluation',
                label: '评测（RAGAS）',
                children: (
                  <>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Form.Item name='ragas_llm_model' label='RAGAS LLM 模型'>
                          <Select showSearch allowClear options={buildOptions.llm} />
                        </Form.Item>
                      </Col>
                      <Col span={12}>
                        <Form.Item name='ragas_embedding_model' label='RAGAS Embedding 模型'>
                          <Select showSearch allowClear options={buildOptions.embedding} />
                        </Form.Item>
                      </Col>
                    </Row>
                  </>
                ),
              },
            ]}
          />
          <Space>
            <Button type='primary' htmlType='submit' loading={loading}>
              保存配置
            </Button>
            <Button onClick={reloadSvc} loading={reloading}>
              重载服务
            </Button>
            <Button onClick={refreshAll}>刷新</Button>
          </Space>
        </Form>
      </Card>

      {/* 模型库管理 */}
      <Card title='模型库（管理与新增）' style={{ marginTop: 16 }} extra={<Button size='small' onClick={loadRegistry}>刷新模型库</Button>}>
        <Tabs
          items={[
            {
              key: 'llm',
              label: 'LLM',
              children: (
                <Table
                  size='small'
                  loading={regLoading}
                  rowKey={(r: any) => `llm:${r.id}`}
                  dataSource={registry.llms || []}
                  pagination={{ pageSize: 5 }}
                  columns={[
                    { title: '名称', dataIndex: 'label', width: 200 },
                    { title: '模型ID', dataIndex: 'model' },
                    { title: 'Provider', dataIndex: 'provider', width: 140 },
                    { title: 'Base URL', dataIndex: 'base_url' },
                    { title: 'Key/ENV', width: 120, render: (_: any, r: any) => (r.has_api_key || r.api_key_env ? '已配置' : '未配置') },
                    {
                      title: '操作',
                      width: 300,
                      render: (_: any, r: any) => (
                        <Space wrap>
                          <Button
                            size='small'
                            onClick={() => {
                              setEditing({ ...r, _kind: 'llm' })
                              editForm.setFieldsValue({ id: r.id, label: r.label, provider: r.provider, model: r.model, base_url: r.base_url, api_key_env: r.api_key_env, api_key: '' })
                              setEditVisible(true)
                            }}
                          >
                            编辑
                          </Button>
                          <Button
                            size='small'
                            onClick={async () => {
                              try {
                                const resp = await api.post('/api/v1/admin/data/models/check-model', { ...r, kind: 'llm' })
                                message[resp.data?.status === 'ok' ? 'success' : 'warning'](`测试完成: ${resp.data?.status}`)
                              } catch (e: any) {
                                message.error('测试失败：' + (e?.response?.data?.detail || e.message))
                              }
                            }}
                          >
                            测试
                          </Button>
                          <Button size='small' onClick={() => { form.setFieldsValue({ llm_model: r.model, base_url: r.base_url }); message.success('已设为推理 LLM') }}>设为推理</Button>
                          <Button size='small' onClick={() => { form.setFieldsValue({ ragas_llm_model: r.model }); message.success('已设为评测 LLM') }}>设为评测</Button>
                          <Popconfirm
                            title='确认删除？'
                            onConfirm={async () => {
                              try {
                                await api.delete(`/api/v1/admin/data/models/registry/llm/${r.id}`)
                                message.success('已删除')
                                loadRegistry()
                              } catch (e: any) {
                                message.error('删除失败：' + (e?.response?.data?.detail || e.message))
                              }
                            }}
                          >
                            <Button size='small' danger>
                              删除
                            </Button>
                          </Popconfirm>
                        </Space>
                      ),
                    },
                  ]}
                />
              ),
            },
            {
              key: 'embedding',
              label: 'Embedding',
              children: (
                <Table
                  size='small'
                  loading={regLoading}
                  rowKey={(r: any) => `embedding:${r.id}`}
                  dataSource={registry.embeddings || []}
                  pagination={{ pageSize: 5 }}
                  columns={[
                    { title: '名称', dataIndex: 'label', width: 200 },
                    { title: '模型ID', dataIndex: 'model' },
                    { title: 'Provider', dataIndex: 'provider', width: 140 },
                    { title: 'Base URL', dataIndex: 'base_url' },
                    { title: 'Key/ENV', width: 120, render: (_: any, r: any) => (r.has_api_key || r.api_key_env ? '已配置' : '未配置') },
                    {
                      title: '操作',
                      width: 300,
                      render: (_: any, r: any) => (
                        <Space wrap>
                          <Button
                            size='small'
                            onClick={() => {
                              setEditing({ ...r, _kind: 'embedding' })
                              editForm.setFieldsValue({ id: r.id, label: r.label, provider: r.provider, model: r.model, base_url: r.base_url, api_key_env: r.api_key_env, api_key: '' })
                              setEditVisible(true)
                            }}
                          >
                            编辑
                          </Button>
                          <Button
                            size='small'
                            onClick={async () => {
                              try {
                                const resp = await api.post('/api/v1/admin/data/models/check-model', { ...r, kind: 'embedding' })
                                message[resp.data?.status === 'ok' ? 'success' : 'warning'](`测试完成: ${resp.data?.status}`)
                              } catch (e: any) {
                                message.error('测试失败：' + (e?.response?.data?.detail || e.message))
                              }
                            }}
                          >
                            测试
                          </Button>
                          <Button size='small' onClick={() => { form.setFieldsValue({ embedding_model: r.model, base_url: r.base_url }); message.success('已设为推理 Embedding') }}>设为推理</Button>
                          <Button size='small' onClick={() => { form.setFieldsValue({ ragas_embedding_model: r.model }); message.success('已设为评测 Embedding') }}>设为评测</Button>
                          <Popconfirm
                            title='确认删除？'
                            onConfirm={async () => {
                              try {
                                await api.delete(`/api/v1/admin/data/models/registry/embedding/${r.id}`)
                                message.success('已删除')
                                loadRegistry()
                              } catch (e: any) {
                                message.error('删除失败：' + (e?.response?.data?.detail || e.message))
                              }
                            }}
                          >
                            <Button size='small' danger>
                              删除
                            </Button>
                          </Popconfirm>
                        </Space>
                      ),
                    },
                  ]}
                />
              ),
            },
            {
              key: 'reranker',
              label: 'Reranker',
              children: (
                <Table
                  size='small'
                  loading={regLoading}
                  rowKey={(r: any) => `reranker:${r.id}`}
                  dataSource={registry.rerankers || []}
                  pagination={{ pageSize: 5 }}
                  columns={[
                    { title: '名称', dataIndex: 'label', width: 200 },
                    { title: '模型ID', dataIndex: 'model' },
                    { title: 'Provider', dataIndex: 'provider', width: 140 },
                    { title: 'Base URL', dataIndex: 'base_url' },
                    { title: 'Key/ENV', width: 120, render: (_: any, r: any) => (r.has_api_key || r.api_key_env ? '已配置' : '未配置') },
                    {
                      title: '操作',
                      width: 240,
                      render: (_: any, r: any) => (
                        <Space wrap>
                          <Button
                            size='small'
                            onClick={() => {
                              setEditing({ ...r, _kind: 'reranker' })
                              editForm.setFieldsValue({ id: r.id, label: r.label, provider: r.provider, model: r.model, base_url: r.base_url, api_key_env: r.api_key_env, api_key: '' })
                              setEditVisible(true)
                            }}
                          >
                            编辑
                          </Button>
                          <Button
                            size='small'
                            onClick={async () => {
                              try {
                                const resp = await api.post('/api/v1/admin/data/models/check-model', { ...r, kind: 'reranker' })
                                message[resp.data?.status === 'ok' ? 'success' : 'warning'](`测试完成: ${resp.data?.status}`)
                              } catch (e: any) {
                                message.error('测试失败：' + (e?.response?.data?.detail || e.message))
                              }
                            }}
                          >
                            测试
                          </Button>
                          <Button size='small' onClick={() => { form.setFieldsValue({ reranker_model: r.model, rerank_provider: r.provider?.toLowerCase() === 'ollama' ? 'local' : 'siliconflow' }); message.success('已设为推理 Reranker') }}>设为推理</Button>
                          <Popconfirm
                            title='确认删除？'
                            onConfirm={async () => {
                              try {
                                await api.delete(`/api/v1/admin/data/models/registry/reranker/${r.id}`)
                                message.success('已删除')
                                loadRegistry()
                              } catch (e: any) {
                                message.error('删除失败：' + (e?.response?.data?.detail || e.message))
                              }
                            }}
                          >
                            <Button size='small' danger>
                              删除
                            </Button>
                          </Popconfirm>
                        </Space>
                      ),
                    },
                  ]}
                />
              ),
            },
          ]}
        />

        <Alert type='info' showIcon message='新增条目' style={{ marginTop: 12 }} />
        <Form form={newForm} layout='vertical' onFinish={addRegistry}>
          <Row gutter={16}>
            <Col span={6}>
              <Form.Item name='kind' label='类型' rules={[{ required: true }]}>
                <Select options={[{ value: 'llm', label: 'LLM' }, { value: 'embedding', label: 'Embedding' }, { value: 'reranker', label: 'Reranker' }]} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name='label' label='名称' rules={[{ required: true }]}>
                <Input />
              </Form.Item>
            </Col>
            <Col span={10}>
              <Form.Item name='provider' label='Provider' rules={[{ required: true }]}>
                <Select options={[{ value: 'siliconflow', label: 'SiliconFlow' }, { value: 'openai', label: 'OpenAI' }, { value: 'ollama', label: 'Ollama' }, { value: 'dashscope', label: 'DashScope' }]} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name='model' label='模型ID' rules={[{ required: true }]}>
                <Input placeholder='如 Qwen/Qwen2.5-32B-Instruct 或 qwen3:30b' />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name='base_url' label='Base URL'>
                <Input placeholder='https://api.siliconflow.cn/v1 或 http://localhost:11434/v1' />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name='api_key_env' label='API Key ENV（推荐）'>
                <Input placeholder='SILICONFLOW_API_KEY 或 OPENAI_API_KEY' />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={16}>
              <Form.Item name='api_key' label='API Key（可选）'>
                <Input.Password placeholder='直填Key（仅用于本机测试）' />
              </Form.Item>
            </Col>
            <Col span={8} style={{ display: 'flex', alignItems: 'end' }}>
              <Button type='primary' htmlType='submit'>保存到模型库</Button>
            </Col>
          </Row>
        </Form>
      </Card>

      {/* 编辑弹窗 */}
      <Modal
        title={`编辑模型（${editing?._kind?.toUpperCase()}: ${editing?.id || ''}）`}
        open={editVisible}
        onCancel={() => {
          setEditVisible(false)
          setEditing(null)
          editForm.resetFields()
        }}
        onOk={saveEdit}
        okText='保存'
        cancelText='取消'
        destroyOnClose
      >
        <Form form={editForm} layout='vertical'>
          <Form.Item name='id' label='ID'>
            <Input disabled />
          </Form.Item>
          <Form.Item name='label' label='名称' rules={[{ required: true }]}>
            <Input placeholder='显示名称' />
          </Form.Item>
          <Form.Item name='provider' label='Provider' rules={[{ required: true }]}>
            <Select options={[{ value: 'siliconflow', label: 'SiliconFlow' }, { value: 'openai', label: 'OpenAI' }, { value: 'ollama', label: 'Ollama' }, { value: 'dashscope', label: 'DashScope' }]} />
          </Form.Item>
          <Form.Item name='model' label='模型ID' rules={[{ required: true }]}>
            <Input placeholder='如 Qwen/Qwen3-32B 或 qwen3:30b' />
          </Form.Item>
          <Form.Item name='base_url' label='Base URL' extra='Ollama 建议 http://localhost:11434/v1'>
            <Input placeholder='https://api.siliconflow.cn/v1 或 http://localhost:11434/v1' />
          </Form.Item>
          <Form.Item name='api_key_env' label='API Key 环境变量（推荐）'>
            <Input placeholder='SILICONFLOW_API_KEY 或 OPENAI_API_KEY' />
          </Form.Item>
          <Form.Item name='api_key' label='API Key（可选，优先使用ENV）'>
            <Input.Password placeholder='不填则沿用原值' />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default ModelConfig

