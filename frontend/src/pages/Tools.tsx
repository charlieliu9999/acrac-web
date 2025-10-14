import React, { useMemo, useState, useEffect } from 'react'
import { Button, Card, Col, Form, Input, InputNumber, Row, Space, Table, Typography, message, Statistic, Alert, Collapse, Upload, Select, Radio } from 'antd'
import type { UploadProps } from 'antd'
import { api } from '../api/http'

const { Paragraph } = Typography
const { Panel } = Collapse

const Tools: React.FC = () => {
  const [vsForm] = Form.useForm()
  const [vrForm] = Form.useForm()
  const [vsOut, setVsOut] = useState<any>(null)
  const [vrOut, setVrOut] = useState<any>(null)
  const [parseText, setParseText] = useState('')
  const [scenariosJson, setScenariosJson] = useState<string>('[]')
  const [parseOut, setParseOut] = useState<any>(null)
  const [ragasForm] = Form.useForm()
  const [ragasOut, setRagasOut] = useState<any>(null)
  const [ragasSchema, setRagasSchema] = useState<any>(null)
  const [vectorStatus, setVectorStatus] = useState<any>(null)
  const [loadingStatus, setLoadingStatus] = useState(false)
  const [importing, setImporting] = useState(false)
  const [csvPath, setCsvPath] = useState<string>('')
  const [importForm] = Form.useForm()
  const [registry, setRegistry] = useState<any>({ llms: [], embeddings: [], rerankers: [] })
  const [regLoading, setRegLoading] = useState(false)
  const [contexts, setContexts] = useState<any>({ inference: {}, evaluation: {} })

  // LLM输出解析示例
  const exampleLLMOutput = `{
  "recommendations": [
    {
      "rank": 1,
      "procedure_name": "CT颅脑(平扫)",
      "modality": "CT",
      "appropriateness_rating": "9/9",
      "recommendation_reason": "头部CT平扫在雷击样头痛（TCH）评估中具有重要价值，因其对颅内出血检测的高敏感性。",
      "clinical_considerations": "患者突发剧烈头痛，无神经系统体征，需迅速排除颅内出血等紧急情况。"
    },
    {
      "rank": 2,
      "procedure_name": "CT颅内动脉血管成像(CTA)",
      "modality": "CT",
      "appropriateness_rating": "8/9",
      "recommendation_reason": "CTA可用于检测动脉瘤等血管病变，是TCH评估的重要组成部分。",
      "clinical_considerations": "在CT平扫阴性后，CTA有助于发现血管源性病变。"
    }
  ]
}`

  const doVector = async (v:any) => {
    const payload = { query: v.query, top_k: v.top_k }
    const r = await api.post('/api/v1/acrac/rag-services/search-scenarios-by-text', payload)
    setVsOut({ scenarios: r.data })
    const arr = (Array.isArray(r.data) ? r.data : []).map((s:any)=> ({ semantic_id: s.semantic_id, description_zh: s.description_zh, panel_name: s.panel_name, topic_name: s.topic_name, similarity: s.similarity_score || s.similarity }))
    setScenariosJson(JSON.stringify(arr, null, 2))
  }

  const doRerank = async (v:any) => {
    try {
      const scenarios = JSON.parse(scenariosJson || '[]')
      const r = await api.post('/api/v1/acrac/rag-services/rerank', { query: v.query, scenarios })
      setVrOut(r.data)
    } catch (e:any) {
      setVrOut(null)
      message.error('场景JSON解析失败，请检查格式')
    }
  }

  const doParse = async () => {
    const r = await api.post('/api/v1/acrac/rag-services/parse', { llm_response: parseText })
    setParseOut(r.data)
  }

  const loadExample = () => {
    setParseText(exampleLLMOutput)
  }

  const doRagas = async (v: any) => {
    try {
      // 兼容将文本contexts解析为字符串数组
      let payload: any = { ...v }
      const raw = v?.contexts
      if (typeof raw === 'string') {
        const trimmed = raw.trim()
        if (!trimmed) {
          payload.contexts = []
        } else if (trimmed.startsWith('[')) {
          try {
            const arr = JSON.parse(trimmed)
            if (Array.isArray(arr)) {
              payload.contexts = arr
            } else {
              throw new Error('contexts需为字符串数组')
            }
          } catch (e:any) {
            message.error('contexts应为JSON数组，例如 ["片段1", "片段2"]')
            return
          }
        } else {
          // 非JSON时，按换行分割
          payload.contexts = trimmed.split('\n').map(s=>s.trim()).filter(Boolean)
        }
      }
      const r = await api.post('/api/v1/acrac/rag-services/ragas', payload)
      setRagasOut(r.data)
    } catch (e: any) {
      message.error('RAGAS评测失败: ' + (e?.response?.data?.detail || e.message))
    }
  }

  const loadRagasSchema = async () => {
    try {
      const r = await api.get('/api/v1/acrac/rag-services/ragas/schema')
      setRagasSchema(r.data)
    } catch (e: any) {
      message.error('获取RAGAS方案失败: ' + (e?.response?.data?.detail || e.message))
    }
  }

  const loadVectorStatus = async () => {
    setLoadingStatus(true)
    try {
      const r = await api.get('/api/v1/admin/data/validate')
      setVectorStatus(r.data)
    } catch (e: any) {
      message.error('获取向量状态失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoadingStatus(false)
    }
  }

  // 加载模型库（用于导入面板 Embedding 下拉）
  const loadRegistry = async () => {
    try {
      setRegLoading(true)
      const r = await api.get('/api/v1/admin/data/models/registry')
      setRegistry(r.data || { llms: [], embeddings: [], rerankers: [] })
    } catch (e:any) {
      message.error('加载模型库失败：' + (e?.response?.data?.detail || e.message))
      setRegistry({ llms: [], embeddings: [], rerankers: [] })
    } finally {
      setRegLoading(false)
    }
  }

  useEffect(() => { loadRegistry() }, [])
  useEffect(() => {
    const loadCtx = async () => {
      try {
        const res = await api.get('/api/v1/admin/data/models/config')
        setContexts(res.data?.contexts || { inference: {}, evaluation: {} })
      } catch (e:any) {
        message.error('加载模型配置失败：' + (e?.response?.data?.detail || e.message))
      }
    }
    loadCtx()
  }, [])

  const embeddingOptions = useMemo(() => {
    const map = new Map<string, any>()
    const ensure = (model?: string, label?: string, entry?: any) => {
      const val = (model || '').trim()
      if (!val || map.has(val)) return
      map.set(val, { value: val, label: label || val, _entry: entry })
    }
    (registry.embeddings || []).forEach((it:any) => ensure(it.model, it.label || it.model, it))
    ensure(contexts?.inference?.embedding_model, `推理 · ${contexts?.inference?.embedding_model || ''}`)
    ensure(contexts?.evaluation?.embedding_model, `评测 · ${contexts?.evaluation?.embedding_model || ''}`)
    return Array.from(map.values())
  }, [registry, contexts])

  const handleEmbeddingSelectChange = async (v: any, opt: any) => {
    const entry = opt?._entry
    let base = entry?.base_url
    if (!base) {
      if (contexts?.inference?.embedding_model === v) base = contexts?.inference?.base_url
      else if (contexts?.evaluation?.embedding_model === v) base = contexts?.evaluation?.base_url
    }
    if (base) {
      importForm.setFieldsValue({ base_url: base })
    }
    if (entry) {
      try {
        const resp = await api.post('/api/v1/admin/data/models/check-model', entry)
        const dim = Number(resp?.data?.dimension || 0)
        if (dim > 0) {
          importForm.setFieldsValue({ embedding_dim: dim })
          message.success(`已探测向量维度：${dim}`)
        }
      } catch (e:any) {
        // ignore
      }
    }
  }

  // ---- 数据导入/重建 ----
  const uploadProps: UploadProps = {
    name: 'file',
    multiple: false,
    showUploadList: false,
    customRequest: async (opt) => {
      try {
        const fd = new FormData()
        fd.append('file', opt.file as any)
        const r = await api.post('/api/v1/admin/data/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
        const p = r.data?.path || ''
        setCsvPath(p)
        message.success('上传成功')
        opt.onSuccess && opt.onSuccess(r.data as any)
      } catch (e: any) {
        message.error('上传失败：' + (e?.response?.data?.detail || e.message))
        opt.onError && opt.onError(e)
      }
    }
  }

  const doImport = async (v: any) => {
    if (!csvPath && !v.csv_path) {
      message.warning('请先上传CSV或填入服务器路径')
      return
    }
    const model = (v.embedding_model || '').toLowerCase()
    const base = (v.base_url || '').toLowerCase()
    if (model.includes('qwen') || model.includes('ollama')) {
      if (!base || (!base.includes('11434') && !base.includes('ollama'))) {
        message.error('当前选择的是 Ollama 嵌入模型，但 Base URL 仍指向 SiliconFlow。请填写 http://host.docker.internal:11434/v1 或本机 Ollama 地址。')
        return
      }
    }
    setImporting(true)
    try {
      const payload = {
        csv_path: v.csv_path || csvPath,
        mode: v.mode || 'clear',
        embedding_model: v.embedding_model || undefined,
        embedding_dim: v.embedding_dim || undefined,
        base_url: v.base_url || undefined,
      }
      const r = await api.post('/api/v1/admin/data/import', payload)
      if (r.data?.started === false || (typeof r.data?.exit_code === 'number' && r.data.exit_code !== 0)) {
        const tail = (r.data?.error_tail || '').slice(-1000)
        message.error(tail ? `导入失败：\n${tail}` : '导入失败，请查看日志')
      } else {
        message.success('已触发导入/重建，详见日志：' + (r.data?.log_path || ''))
      }
    } catch (e:any) {
      message.error('导入失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setImporting(false)
    }
  }

  const copyStatusToClipboard = () => {
    if (vectorStatus) {
      navigator.clipboard.writeText(JSON.stringify(vectorStatus, null, 2))
      message.success('状态已复制到剪贴板')
    }
  }

  useEffect(() => {
    loadVectorStatus()
  }, [])

  return (
    <div>
      <div className='page-title'>工具箱</div>
      
      <Collapse defaultActiveKey={['vector-status', 'vector-search', 'llm-parse', 'ragas-eval']} size="large">
        {/* 向量状态监控 */}
        <Panel header="向量状态监控" key="vector-status">
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space>
              <Button onClick={loadVectorStatus} loading={loadingStatus}>刷新状态</Button>
              <Button onClick={copyStatusToClipboard} disabled={!vectorStatus}>复制状态</Button>
            </Space>
            
            {vectorStatus && (
              <Row gutter={16}>
                <Col span={6}>
                  <Statistic title="Panels" value={vectorStatus.tables?.panels || 0} />
                </Col>
                <Col span={6}>
                  <Statistic title="Topics" value={vectorStatus.tables?.topics || 0} />
                </Col>
                <Col span={6}>
                  <Statistic title="Scenarios" value={vectorStatus.tables?.clinical_scenarios || 0} />
                </Col>
                <Col span={6}>
                  <Statistic title="Recommendations" value={vectorStatus.tables?.clinical_recommendations || 0} />
                </Col>
              </Row>
            )}
            
            {vectorStatus && (
              <Row gutter={16}>
                <Col span={12}>
                  <Card size="small" title="向量覆盖情况">
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <div>Panels: {vectorStatus.embedding_coverage?.panels || 0}/{vectorStatus.tables?.panels || 0}</div>
                      <div>Topics: {vectorStatus.embedding_coverage?.topics || 0}/{vectorStatus.tables?.topics || 0}</div>
                      <div>Scenarios: {vectorStatus.embedding_coverage?.clinical_scenarios || 0}/{vectorStatus.tables?.clinical_scenarios || 0}</div>
                      <div>Recommendations: {vectorStatus.embedding_coverage?.clinical_recommendations || 0}/{vectorStatus.tables?.clinical_recommendations || 0}</div>
                    </Space>
                  </Card>
                </Col>
                <Col span={12}>
                  <Card size="small" title="数据质量检查">
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <div>孤儿推荐: {vectorStatus.orphan_recommendations || 0}</div>
                      {(vectorStatus.orphan_recommendations || 0) > 0 && (
                        <Alert message="发现孤儿推荐记录" type="warning" showIcon />
                      )}
                      {(vectorStatus.orphan_recommendations || 0) === 0 && (
                        <Alert message="数据关联正常" type="success" showIcon />
                      )}
                    </Space>
                  </Card>
                </Col>
              </Row>
            )}
          </Space>
        </Panel>

        {/* 向量检索 */}
        <Panel header="向量检索" key="vector-search">
          <Row gutter={12}>
            <Col span={12}>
              <Card title='向量检索'>
                <Form form={vsForm} layout='vertical' initialValues={{ query:'雷击样头痛', top_k: 5 }} onFinish={doVector}>
                  <Form.Item label='查询' name='query' rules={[{required:true}]}><Input/></Form.Item>
                  <Form.Item label='TopK' name='top_k'><InputNumber min={1} max={20}/></Form.Item>
                  <Button type='primary' htmlType='submit'>检索</Button>
                </Form>
                <Paragraph className='mono' style={{ whiteSpace:'pre-wrap' }}>{JSON.stringify(vsOut, null, 2)}</Paragraph>
              </Card>
            </Col>
            <Col span={12}>
              <Card title='重排打分'>
                <Form form={vrForm} layout='vertical' initialValues={{ query:'雷击样头痛' }} onFinish={doRerank}>
                  <Form.Item label='查询' name='query' rules={[{required:true}]}><Input/></Form.Item>
                  <div style={{ marginBottom: 8 }}>场景（可编辑）JSON</div>
                  <Input.TextArea rows={8} className='mono' value={scenariosJson} onChange={(e)=> setScenariosJson(e.target.value)} />
                  <Button type='primary' htmlType='submit'>重排</Button>
                </Form>
                <Paragraph className='mono' style={{ whiteSpace:'pre-wrap' }}>{JSON.stringify(vrOut, null, 2)}</Paragraph>
              </Card>
            </Col>
          </Row>
        </Panel>

        {/* LLM 输出解析 */}
        <Panel header="LLM 输出解析" key="llm-parse">
          <Card title='LLM 输出解析'>
            <Space direction='vertical' style={{ width: '100%' }}>
              <Space>
                <Button onClick={loadExample}>加载示例</Button>
                <Button onClick={doParse} type="primary">解析</Button>
              </Space>
              <Input.TextArea 
                rows={8} 
                value={parseText} 
                onChange={(e)=>setParseText(e.target.value)} 
                placeholder='粘贴LLM输出（JSON或文本）' 
              />
              <Paragraph className='mono' style={{ whiteSpace:'pre-wrap' }}>{JSON.stringify(parseOut, null, 2)}</Paragraph>
            </Space>
          </Card>
        </Panel>

        {/* RAGAS 评测 */}
        <Panel header="RAGAS 评测" key="ragas-eval">
          <Card title='RAGAS 评测'>
            <Space direction='vertical' style={{ width: '100%' }}>
              <Space>
                <Button onClick={loadRagasSchema}>查看方案</Button>
                <Button onClick={() => ragasForm.submit()} type="primary">开始评测</Button>
              </Space>
              
              {ragasSchema && (
                <Alert 
                  message="RAGAS 评测方案" 
                  description={
                    <div>
                      <div><strong>输入格式：</strong></div>
                      <div>• user_input: 用户原始问题（必填）</div>
                      <div>• answer: 模型输出答案（必填）</div>
                      <div>• contexts: 上下文片段列表（可选）</div>
                      <div>• reference: 参考答案（可选）</div>
                      <div><strong>评测指标：</strong> {ragasSchema.metrics?.join(', ')}</div>
                      <div><strong>说明：</strong> {ragasSchema.notes}</div>
                    </div>
                  } 
                  type="info" 
                  showIcon 
                />
              )}

              <Form form={ragasForm} layout='vertical' onFinish={doRagas} initialValues={{
                user_input: '雷击样头痛的影像学检查推荐',
                answer: '对于雷击样头痛患者，推荐进行CT颅脑平扫作为首选检查，因为其对颅内出血检测具有高敏感性。',
                contexts: '["雷击样头痛是突发剧烈头痛的医学术语", "CT平扫对颅内出血检测敏感性高"]',
                reference: 'ACR适宜性标准'
              }}>
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item name='user_input' label='用户问题' rules={[{required: true}]}>
                      <Input.TextArea rows={2} placeholder='用户原始问题' />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item name='answer' label='模型答案' rules={[{required: true}]}>
                      <Input.TextArea rows={2} placeholder='模型输出的答案' />
                    </Form.Item>
                  </Col>
                </Row>
                
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item name='contexts' label='上下文片段'>
                      <Input.TextArea rows={3} placeholder='JSON格式的上下文列表' />
                    </Form.Item>
                  </Col>
                  <Col span={12}>
                    <Form.Item name='reference' label='参考答案'>
                      <Input placeholder='标准答案或参考术语' />
                    </Form.Item>
                  </Col>
                </Row>
              </Form>

              {ragasOut && (
                <Card size="small" title="评测结果">
                  <Paragraph className='mono' style={{ whiteSpace:'pre-wrap' }}>
                    {JSON.stringify(ragasOut, null, 2)}
                  </Paragraph>
                </Card>
              )}
            </Space>
          </Card>
        </Panel>
      </Collapse>

      <Collapse defaultActiveKey={[]} style={{ marginTop: 16 }}>
        <Panel header="数据导入 / 重建（Admin）" key="import">
          <Alert 
            type='warning' 
            showIcon 
            message='说明'
            description={(
              <div>
                <div>· 支持从CSV重建数据库（清空重建）或追加导入。</div>
                <div>· 可选设置 Embedding 模型与 Base URL（SiliconFlow 或本地 Ollama）。若使用 Ollama，请确保 Base URL 形如 http://localhost:11434/v1。</div>
                <div>· 当模型维度非 1024（例如 qwen3-embed-4b 为 2560）时，请填写“向量维度”。</div>
              </div>
            )}
            style={{ marginBottom: 12 }}
          />
          <Form form={importForm} layout='vertical' onFinish={doImport} initialValues={{ mode: 'clear', embedding_model: '', embedding_dim: undefined, base_url: '' }}>
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item label='上传CSV'>
                  <Space>
                    <Upload {...uploadProps}><Button>选择CSV文件并上传</Button></Upload>
                    <Input placeholder='或直接填服务器CSV路径' value={csvPath} onChange={(e)=> setCsvPath(e.target.value)} style={{ width: 320 }} />
                  </Space>
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name='csv_path' label='服务器CSV路径（可选）'>
                  <Input placeholder='/absolute/path/to/ACR_final.csv' />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={16}>
              <Col span={6}>
                <Form.Item name='mode' label='导入模式'>
                  <Select options={[{ value:'clear', label:'清空重建' }, { value:'add', label:'追加导入' }]} />
                </Form.Item>
              </Col>
              <Col span={9}>
                <Form.Item name='embedding_model' label='Embedding 模型（可选）'>
                  <Select
                    showSearch
                    allowClear
                    placeholder='选择模型库中的 Embedding 或手动输入'
                    options={embeddingOptions}
                    loading={regLoading}
                    onChange={handleEmbeddingSelectChange}
                    filterOption={(input, option)=> (option?.label as string).toLowerCase().includes(input.toLowerCase())}
                  />
                </Form.Item>
              </Col>
              <Col span={9}>
                <Form.Item name='base_url' label='Embedding Base URL（可选）'>
                  <Input placeholder='https://api.siliconflow.cn/v1 或 http://localhost:11434/v1' />
                </Form.Item>
              </Col>
            </Row>
            <Row gutter={16}>
              <Col span={6}>
                <Form.Item name='embedding_dim' label='向量维度（可选）'>
                  <InputNumber min={64} max={8192} style={{ width: '100%' }} placeholder='不填则自动探测/默认1024' />
                </Form.Item>
              </Col>
            </Row>
            <Button type='primary' htmlType='submit' loading={importing}>开始导入/重建</Button>
          </Form>
        </Panel>
      </Collapse>
    </div>
  )
}

export default Tools
