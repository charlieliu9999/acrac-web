import React, { useState } from 'react'
import { Card, Form, Input, Button, Space, Select, InputNumber, Switch, Badge, Tooltip, Alert } from 'antd'
import { CheckCircleOutlined, ExclamationCircleOutlined, SettingOutlined } from '@ant-design/icons'

interface ModelProviderCardProps {
  provider: 'ollama' | 'siliconflow' | 'qwen' | 'openai'
  title: string
  description: string
  config: any
  onConfigChange: (config: any) => void
  onTest: (config: any) => Promise<boolean>
  disabled?: boolean
}

const ModelProviderCard: React.FC<ModelProviderCardProps> = ({
  provider,
  title,
  description,
  config,
  onConfigChange,
  onTest,
  disabled = false
}) => {
  const [form] = Form.useForm()
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<'success' | 'error' | null>(null)

  const handleTest = async () => {
    try {
      setTesting(true)
      const values = await form.validateFields()
      const success = await onTest({ ...config, ...values })
      setTestResult(success ? 'success' : 'error')
    } catch (error) {
      setTestResult('error')
    } finally {
      setTesting(false)
    }
  }

  const getStatusBadge = () => {
    if (testing) return <Badge status="processing" text="测试中..." />
    if (testResult === 'success') return <Badge status="success" text="连接正常" />
    if (testResult === 'error') return <Badge status="error" text="连接失败" />
    return <Badge status="default" text="未测试" />
  }

  const getProviderSpecificFields = () => {
    switch (provider) {
      case 'ollama':
        return (
          <>
            <Form.Item name="base_url" label="Ollama服务地址" initialValue="http://localhost:11434/v1">
              <Input placeholder="http://localhost:11434/v1" />
            </Form.Item>
            <Alert 
              message="Ollama本地部署" 
              description="确保Ollama服务正在运行，支持qwen3:4b等本地模型" 
              type="info" 
              showIcon 
              style={{ marginBottom: 16 }}
            />
          </>
        )
      case 'siliconflow':
        return (
          <>
            <Form.Item name="api_key" label="API Key" rules={[{ required: true }]}>
              <Input.Password placeholder="sk-..." />
            </Form.Item>
            <Form.Item name="base_url" label="API地址" initialValue="https://api.siliconflow.cn/v1">
              <Input />
            </Form.Item>
          </>
        )
      case 'qwen':
        return (
          <>
            <Form.Item name="api_key" label="DashScope API Key" rules={[{ required: true }]}>
              <Input.Password placeholder="sk-..." />
            </Form.Item>
            <Form.Item name="base_url" label="API地址" initialValue="https://dashscope.aliyuncs.com/compatible-mode/v1">
              <Input />
            </Form.Item>
          </>
        )
      case 'openai':
        return (
          <>
            <Form.Item name="api_key" label="OpenAI API Key" rules={[{ required: true }]}>
              <Input.Password placeholder="sk-..." />
            </Form.Item>
            <Form.Item name="base_url" label="API地址" initialValue="https://api.openai.com/v1">
              <Input />
            </Form.Item>
          </>
        )
      default:
        return null
    }
  }

  return (
    <Card
      title={
        <Space>
          <SettingOutlined />
          {title}
          {getStatusBadge()}
        </Space>
      }
      extra={
        <Space>
          <Button size="small" onClick={handleTest} loading={testing}>
            测试连接
          </Button>
          <Switch 
            checked={!disabled} 
            onChange={(checked) => onConfigChange({ ...config, enabled: checked })}
            checkedChildren="启用"
            unCheckedChildren="禁用"
          />
        </Space>
      }
      style={{ marginBottom: 16 }}
    >
      <Alert message={description} type="info" showIcon style={{ marginBottom: 16 }} />
      
      <Form
        form={form}
        layout="vertical"
        initialValues={config}
        onValuesChange={(_, allValues) => onConfigChange({ ...config, ...allValues })}
        disabled={disabled}
      >
        {getProviderSpecificFields()}
        
        <Divider orientation="left">模型配置</Divider>
        
        <Row gutter={16}>
          <Col span={8}>
            <Form.Item name="embedding_model" label="Embedding模型">
              <Select
                placeholder="选择embedding模型"
                options={getEmbeddingOptions(provider)}
                showSearch
                allowClear
              />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="llm_model" label="LLM模型">
              <Select
                placeholder="选择LLM模型"
                options={getLLMOptions(provider)}
                showSearch
                allowClear
              />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="rerank_model" label="Rerank模型">
              <Select
                placeholder="选择rerank模型"
                options={getRerankOptions(provider)}
                showSearch
                allowClear
              />
            </Form.Item>
          </Col>
        </Row>

        {provider === 'ollama' && (
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="embedding_dimension" label="向量维度">
                <Select
                  placeholder="选择向量维度"
                  options={[
                    { value: 1024, label: '1024维 (BGE-M3)' },
                    { value: 2560, label: '2560维 (Qwen3-4B)' },
                    { value: 1536, label: '1536维 (OpenAI)' },
                    { value: 768, label: '768维 (BERT)' }
                  ]}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="max_tokens" label="最大Token数">
                <InputNumber min={1} max={32000} placeholder="4096" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
        )}
      </Form>
    </Card>
  )
}

const getEmbeddingOptions = (provider: string) => {
  const options = {
    ollama: [
      { value: 'bge-m3:latest', label: 'BGE-M3 (1024维)' },
      { value: 'qwen3:4b', label: 'Qwen3-4B (2560维)' },
      { value: 'nomic-embed-text', label: 'Nomic Embed Text' }
    ],
    siliconflow: [
      { value: 'BAAI/bge-m3', label: 'BGE-M3' },
      { value: 'BAAI/bge-large-zh-v1.5', label: 'BGE-Large-ZH' },
      { value: 'sentence-transformers/all-MiniLM-L6-v2', label: 'MiniLM-L6-v2' }
    ],
    qwen: [
      { value: 'text-embedding-v1', label: 'Text Embedding V1' },
      { value: 'text-embedding-v2', label: 'Text Embedding V2' }
    ],
    openai: [
      { value: 'text-embedding-3-large', label: 'Text Embedding 3 Large' },
      { value: 'text-embedding-3-small', label: 'Text Embedding 3 Small' },
      { value: 'text-embedding-ada-002', label: 'Ada 002' }
    ]
  }
  return options[provider as keyof typeof options] || []
}

const getLLMOptions = (provider: string) => {
  const options = {
    ollama: [
      { value: 'qwen3:30b', label: 'Qwen3-30B' },
      { value: 'qwen3:4b', label: 'Qwen3-4B' },
      { value: 'llama3:8b', label: 'Llama3-8B' },
      { value: 'mistral:7b', label: 'Mistral-7B' }
    ],
    siliconflow: [
      { value: 'Qwen/Qwen2.5-32B-Instruct', label: 'Qwen2.5-32B-Instruct' },
      { value: 'Qwen/Qwen2.5-14B-Instruct', label: 'Qwen2.5-14B-Instruct' },
      { value: 'meta-llama/Meta-Llama-3.1-8B-Instruct', label: 'Llama-3.1-8B-Instruct' }
    ],
    qwen: [
      { value: 'qwen-max', label: 'Qwen Max' },
      { value: 'qwen-plus', label: 'Qwen Plus' },
      { value: 'qwen-turbo', label: 'Qwen Turbo' }
    ],
    openai: [
      { value: 'gpt-4o', label: 'GPT-4o' },
      { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
      { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' }
    ]
  }
  return options[provider as keyof typeof options] || []
}

const getRerankOptions = (provider: string) => {
  const options = {
    ollama: [
      { value: 'bge-reranker-v2-m3', label: 'BGE Reranker V2 M3' }
    ],
    siliconflow: [
      { value: 'BAAI/bge-reranker-v2-m3', label: 'BGE Reranker V2 M3' },
      { value: 'BAAI/bge-reranker-large', label: 'BGE Reranker Large' }
    ],
    qwen: [
      { value: 'gte-rerank', label: 'GTE Rerank' }
    ],
    openai: []
  }
  return options[provider as keyof typeof options] || []
}

export default ModelProviderCard