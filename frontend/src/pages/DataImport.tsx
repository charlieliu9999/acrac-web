import React, { useState } from 'react'
import { Button, Card, Form, Input, Radio, Space, Upload, message } from 'antd'
import { api } from '../api/http'

const DataImport: React.FC = () => {
  const [filePath, setFilePath] = useState('')
  const [logPath, setLogPath] = useState('')
  const [metrics, setMetrics] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [validating, setValidating] = useState(false)

  const uploadProps = {
    name: 'file',
    multiple: false,
    customRequest: async (options: any) => {
      try {
        const form = new FormData()
        form.append('file', options.file)
        const r = await api.post('/api/v1/admin/data/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } })
        setFilePath(r.data.path)
        message.success('上传成功')
        options.onSuccess(r.data)
      } catch (e: any) {
        message.error('上传失败: ' + (e?.response?.data?.detail || e.message))
        options.onError(e)
      }
    }
  }

  const onFinish = async (values: any) => {
    if (!filePath) { message.warning('请先上传CSV'); return }
    setLoading(true)
    try {
      const r = await api.post('/api/v1/admin/data/import', {
        csv_path: filePath,
        mode: values.mode,
        embedding_model: values.embedding_model || undefined,
        llm_model: values.llm_model || undefined,
      })
      setLogPath(r.data.log_path || '')
      setMetrics(r.data.metrics || null)
      message.success('导入完成')
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
          <Form layout='vertical' onFinish={onFinish} initialValues={{ mode: 'clear', embedding_model: 'BAAI/bge-m3', llm_model: 'Qwen/Qwen2.5-32B-Instruct' }}>
            <Form.Item name='mode' label='模式'>
              <Radio.Group>
                <Radio value='clear'>清空后加载</Radio>
                <Radio value='add'>追加</Radio>
              </Radio.Group>
            </Form.Item>
            <Form.Item name='embedding_model' label='Embedding 模型'>
              <Input placeholder='BAAI/bge-m3' />
            </Form.Item>
            <Form.Item name='llm_model' label='LLM 模型'>
              <Input placeholder='Qwen/Qwen2.5-32B-Instruct' />
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
