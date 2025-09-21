import React, { useMemo, useState, useEffect } from 'react'
import { Button, Card, Form, Input, Radio, Space, Upload, message, Select, InputNumber } from 'antd'
import { api } from '../api/http'

const DataImport: React.FC = () => {
  const [filePath, setFilePath] = useState('')
  const [logPath, setLogPath] = useState('')
  const [metrics, setMetrics] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [validating, setValidating] = useState(false)
  const [form] = Form.useForm()
  const [registry, setRegistry] = useState<any>({ llms: [], embeddings: [], rerankers: [] })
  const [regLoading, setRegLoading] = useState(false)
  const [contexts, setContexts] = useState<any>({ inference: {}, evaluation: {} })

  const uploadProps = {
    name: 'file',
    multiple: false,
    customRequest: async (options: any) => {
      try {
        const form = new FormData()
        form.append('file', options.file)
        // 不手动设置 Content-Type，交由浏览器自动附加 boundary
        const r = await api.post('/api/v1/admin/data/upload', form)
        setFilePath(r.data.path)
        message.success('上传成功')
        options.onSuccess(r.data)
      } catch (e: any) {
        message.error('上传失败: ' + (e?.response?.data?.detail || e.message))
        options.onError(e)
      }
    }
  }

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

  const llmOptions = useMemo(() => {
    const map = new Map<string, any>()
    const ensure = (model?: string, label?: string, entry?: any) => {
      const val = (model || '').trim()
      if (!val || map.has(val)) return
      map.set(val, { value: val, label: label || val, _entry: entry })
    }
    (registry.llms || []).forEach((it:any) => ensure(it.model, it.label || it.model, it))
    ensure(contexts?.inference?.llm_model, `推理 · ${contexts?.inference?.llm_model || ''}`)
    ensure(contexts?.evaluation?.llm_model, `评测 · ${contexts?.evaluation?.llm_model || ''}`)
    return Array.from(map.values())
  }, [registry, contexts])

  const handleEmbeddingSelectChange = async (v:any, opt:any) => {
    const entry = opt?._entry
    let base = entry?.base_url
    if (!base) {
      if (contexts?.inference?.embedding_model === v) base = contexts?.inference?.base_url
      else if (contexts?.evaluation?.embedding_model === v) base = contexts?.evaluation?.base_url
    }
    if (base) {
      form.setFieldsValue({ base_url: base })
    }
    if (entry) {
      try {
        const resp = await api.post('/api/v1/admin/data/models/check-model', entry)
        const dim = Number(resp?.data?.dimension || 0)
        if (dim > 0) {
          form.setFieldsValue({ embedding_dim: dim })
          message.success(`已探测向量维度：${dim}`)
        }
      } catch (e:any) {
        // ignore
      }
    }
  }

  const onFinish = async (values: any) => {
    if (!filePath) { message.warning('请先上传CSV'); return }
    const model = (values.embedding_model || '').toLowerCase()
    const base = (values.base_url || '').toLowerCase()
    if (model.includes('qwen') || model.includes('ollama')) {
      if (!base || (!base.includes('11434') && !base.includes('ollama'))) {
        message.error('当前选择的是 Ollama 嵌入模型，但 Base URL 仍指向 SiliconFlow。请填写 http://host.docker.internal:11434/v1 或本机 Ollama 地址。')
        return
      }
    }
    setLoading(true)
    try {
      const r = await api.post('/api/v1/admin/data/import', {
        csv_path: filePath,
        mode: values.mode,
        embedding_model: values.embedding_model || undefined,
        llm_model: values.llm_model || undefined,
        base_url: values.base_url || undefined,
        embedding_dim: values.embedding_dim || undefined,
      })
      setLogPath(r.data.log_path || '')
      setMetrics(r.data.metrics || null)
      if (r.data?.started === false || (typeof r.data?.exit_code === 'number' && r.data.exit_code !== 0)) {
        const tail = (r.data?.error_tail || '').slice(-1000)
        message.error(tail ? `导入失败：\n${tail}` : '导入失败，请查看日志')
      } else {
        message.success('导入完成')
      }
    } catch (e: any) {
      message.error('导入失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const handleValidate = async () => {
    setValidating(true)
    try {
      const r = await api.get('/api/v1/admin/data/validate')
      setMetrics(r.data)
      message.success('校验完成')
    } catch (e: any) {
      message.error('校验失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setValidating(false)
    }
  }

  return (
    <div>
      <div className='page-title'>数据导入与构建</div>
      <Card>
        <Space direction='vertical' style={{ width: '100%' }}>
          <Upload {...uploadProps} showUploadList={false}>
            <Button>选择CSV文件并上传</Button>
          </Upload>
          {filePath && <div className='mono'>已上传: {filePath}</div>}
          <Form form={form} layout='vertical' onFinish={onFinish} initialValues={{ mode: 'clear', embedding_model: '', llm_model: '', base_url: '', embedding_dim: undefined }}>
            <Form.Item name='mode' label='模式'>
              <Radio.Group>
                <Radio value='clear'>清空后加载</Radio>
                <Radio value='add'>追加</Radio>
              </Radio.Group>
            </Form.Item>
            <Form.Item name='embedding_model' label='Embedding 模型'>
              <Select 
                showSearch 
                allowClear 
                placeholder='选择已注册的 Embedding 模型或手动输入'
                options={embeddingOptions}
                loading={regLoading}
                onChange={handleEmbeddingSelectChange}
                filterOption={(input, option)=> (option?.label as string).toLowerCase().includes(input.toLowerCase())}
              />
            </Form.Item>
            <Form.Item name='llm_model' label='LLM 模型'>
              <Select 
                showSearch 
                allowClear 
                placeholder='选择已注册的 LLM 模型或手动输入'
                options={llmOptions}
                loading={regLoading}
                filterOption={(input, option)=> (option?.label as string).toLowerCase().includes(input.toLowerCase())}
              />
            </Form.Item>
            <Form.Item name='base_url' label='Embedding Base URL（可选）'>
              <Input placeholder='https://api.siliconflow.cn/v1 或 http://localhost:11434/v1' />
            </Form.Item>
            <Form.Item name='embedding_dim' label='向量维度（可选）'>
              <InputNumber min={64} max={8192} style={{ width: 260 }} placeholder='不填则自动探测/默认1024' />
            </Form.Item>
            <Space>
              <Button type='primary' htmlType='submit' loading={loading}>开始导入</Button>
              <Button onClick={handleValidate} loading={validating}>刷新校验</Button>
            </Space>
          </Form>
          {logPath && <div className='mono'>日志: {logPath}</div>}
          {metrics && (
            <pre className='mono' style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(metrics, null, 2)}</pre>
          )}
        </Space>
      </Card>
    </div>
  )
}

export default DataImport
