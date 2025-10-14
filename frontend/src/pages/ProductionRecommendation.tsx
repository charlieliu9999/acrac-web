import React, { useMemo, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Collapse,
  Divider,
  Form,
  Input,
  InputNumber,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { UploadFile, UploadProps } from 'antd/es/upload/interface'
import { UploadOutlined } from '@ant-design/icons'
import { api } from '../api/http'

const { Paragraph, Text } = Typography
const { Panel } = Collapse

interface ScenarioSummary {
  id?: string
  description?: string
  panel?: string
  topic?: string
  similarity?: number
  risk_level?: string
  patient_population?: string
}

interface RecommendationItem {
  rank: number
  procedure_name: string
  modality?: string
  appropriateness_rating?: number
  appropriateness_category?: string
  similarity: number
  scenario: ScenarioSummary
}

interface ProductionRecommendationResponse {
  query: string
  recommendations: RecommendationItem[]
  processing_time_ms: number
  top_k: number
  similarity_threshold: number
  max_similarity?: number
  mode?: string
  source: string
  scenarios: ScenarioSummary[]
}

interface BatchRecommendationResult extends ProductionRecommendationResponse {
  index: number
}

interface BatchRecommendationResponse {
  total: number
  succeeded: number
  failed: number
  results: BatchRecommendationResult[]
  errors: { index: number; query: string; error: string }[]
}

const ProductionRecommendation: React.FC = () => {
  const [singleForm] = Form.useForm()
  const [batchForm] = Form.useForm()
  const [singleLoading, setSingleLoading] = useState(false)
  const [singleResult, setSingleResult] = useState<ProductionRecommendationResponse | null>(null)
  const [batchLoading, setBatchLoading] = useState(false)
  const [batchResult, setBatchResult] = useState<BatchRecommendationResponse | null>(null)
  const [fileList, setFileList] = useState<UploadFile[]>([])

  const recommendationColumns: ColumnsType<RecommendationItem> = useMemo(() => [
    { title: '#', dataIndex: 'rank', width: 60 },
    { title: '检查项目', dataIndex: 'procedure_name', ellipsis: true },
    {
      title: '模态',
      dataIndex: 'modality',
      width: 120,
      render: (value: string | undefined) => value ? <Tag color='blue'>{value}</Tag> : '-',
    },
    {
      title: '评分',
      dataIndex: 'appropriateness_rating',
      width: 100,
      render: (value: number | undefined) =>
        typeof value === 'number' ? <Tag color='green'>{value.toFixed(1)}</Tag> : '-',
    },
    {
      title: '相似度',
      dataIndex: 'similarity',
      width: 110,
      render: (value: number) => value?.toFixed(3),
    },
    {
      title: '临床场景',
      dataIndex: 'scenario',
      ellipsis: true,
      render: (scenario: ScenarioSummary) => {
        if (!scenario) return '-'
        return (
          <div>
            <div>{scenario.description || '-'}</div>
            <div style={{ fontSize: 12, color: '#888' }}>
              {[scenario.panel, scenario.topic].filter(Boolean).join(' / ') || ''}
            </div>
          </div>
        )
      },
    },
  ], [])

  const scenarioColumns: ColumnsType<ScenarioSummary> = useMemo(() => [
    { title: '#', dataIndex: 'id', width: 80, render: (_, __, index) => index + 1 },
    { title: '场景描述', dataIndex: 'description', ellipsis: true },
    {
      title: '科室 / 主题',
      dataIndex: 'panel',
      width: 200,
      render: (_, record) => [record.panel, record.topic].filter(Boolean).join(' / ') || '-',
    },
    {
      title: '相似度',
      dataIndex: 'similarity',
      width: 120,
      render: (value: number | undefined) => (value !== undefined ? value.toFixed(3) : '-'),
    },
  ], [])

  const uploadProps: UploadProps = {
    beforeUpload: (file) => {
      setFileList([file])
      return false
    },
    onRemove: () => {
      setFileList([])
    },
    fileList,
    maxCount: 1,
  }

  const handleSingleSubmit = async () => {
    try {
      const values = await singleForm.validateFields()
      setSingleLoading(true)
      const payload: { clinical_query: string; top_k?: number } = {
        clinical_query: values.clinical_query,
      }
      if (values.top_k) payload.top_k = values.top_k
      const res = await api.post<ProductionRecommendationResponse>(
        '/api/v1/acrac/production/recommendation',
        payload,
      )
      setSingleResult(res.data)
      message.success('推荐已生成')
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || '请求失败'
      message.error(`推荐失败：${detail}`)
    } finally {
      setSingleLoading(false)
    }
  }

  const handleBatchSubmit = async () => {
    if (fileList.length === 0 || !fileList[0]?.originFileObj) {
      message.warning('请先选择一个文件')
      return
    }
    try {
      const values = await batchForm.validateFields()
      setBatchLoading(true)
      const formData = new FormData()
      const fileObj = fileList[0].originFileObj as File
      formData.append('file', fileObj, fileList[0].name)
      const topK = values.top_k
      const url = topK
        ? `/api/v1/acrac/production/recommendation/upload?top_k=${topK}`
        : '/api/v1/acrac/production/recommendation/upload'
      const res = await api.post<BatchRecommendationResponse>(url, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setBatchResult(res.data)
      message.success('批量推荐已完成')
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || '上传失败'
      message.error(`批量推荐失败：${detail}`)
    } finally {
      setBatchLoading(false)
    }
  }

  const renderRecommendations = (data: RecommendationItem[]) => (
    <Table
      size='small'
      rowKey={(row) => `${row.rank}-${row.procedure_name}`}
      columns={recommendationColumns}
      dataSource={data}
      pagination={false}
    />
  )

  return (
    <Space direction='vertical' size='large' style={{ width: '100%' }}>
      <Card title='生产环境快速推荐'>
        <Form form={singleForm} layout='vertical' initialValues={{ top_k: 3 }}>
          <Form.Item
            label='临床描述'
            name='clinical_query'
            rules={[{ required: true, message: '请输入临床描述' }, { min: 3, message: '至少3个字符' }]}
          >
            <Input.TextArea rows={4} placeholder='例如：65岁男性，持续胸痛伴随呼吸困难，需要判断肺部病变' />
          </Form.Item>
          <Form.Item label='返回数量 (Top K)' name='top_k'>
            <InputNumber min={1} max={10} style={{ width: 160 }} />
          </Form.Item>
          <Space>
            <Button type='primary' onClick={handleSingleSubmit} loading={singleLoading}>
              生成推荐
            </Button>
            {singleResult && (
              <Text type='secondary'>耗时：{singleResult.processing_time_ms} ms</Text>
            )}
          </Space>
        </Form>
        {singleResult && (
          <div style={{ marginTop: 24 }}>
            <Paragraph>
              <Text strong>查询：</Text>{singleResult.query}
            </Paragraph>
            <Paragraph type='secondary'>来源：{singleResult.source}，相似度阈值 {singleResult.similarity_threshold}</Paragraph>
            {typeof singleResult.max_similarity === 'number' && (
              <Paragraph type='secondary'>
                最大相似度：{singleResult.max_similarity.toFixed(3)}（模式：{singleResult.mode || 'hybrid-rag'}）
              </Paragraph>
            )}
            {singleResult.scenarios?.length ? (
              <div style={{ marginBottom: 16 }}>
                <Table
                  size='small'
                  rowKey='id'
                  columns={scenarioColumns}
                  dataSource={singleResult.scenarios}
                  pagination={false}
                />
              </div>
            ) : null}
            {renderRecommendations(singleResult.recommendations)}
          </div>
        )}
      </Card>

      <Card title='批量推荐（上传文件）'>
        <Form form={batchForm} layout='inline' initialValues={{ top_k: 3 }}>
          <Form.Item label='返回数量 (Top K)' name='top_k'>
            <InputNumber min={1} max={10} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item>
            <Upload {...uploadProps} accept='.csv,.xlsx,.xls,.json'>
              <Button icon={<UploadOutlined />}>选择文件</Button>
            </Upload>
          </Form.Item>
          <Form.Item>
            <Button type='primary' onClick={handleBatchSubmit} loading={batchLoading}>
              开始批量推荐
            </Button>
          </Form.Item>
        </Form>
        <Paragraph type='secondary' style={{ marginTop: 12 }}>
          支持 CSV / Excel / JSON。文件需包含 query 或 clinical_query 列。
        </Paragraph>

        {batchResult && (
          <div style={{ marginTop: 24 }}>
            <Alert
              type='info'
              showIcon
              message={
                <Space>
                  <span>总计 {batchResult.total} 条</span>
                  <span>成功 {batchResult.succeeded} 条</span>
                  <span>失败 {batchResult.failed} 条</span>
                </Space>
              }
            />
            {batchResult.errors.length > 0 && (
              <Card size='small' title='失败记录' style={{ marginTop: 16 }}>
                {batchResult.errors.map((err) => (
                  <Paragraph key={err.index}>
                    <Text strong>#{err.index + 1}</Text>{' '}
                    <Text>{err.query || '(空)'}</Text>{' '}
                    <Text type='danger'>— {err.error}</Text>
                  </Paragraph>
                ))}
              </Card>
            )}
            <Divider />
            <Collapse accordion>
              {batchResult.results.map((item) => (
                <Panel
                  header={`#${item.index + 1} ${item.query}`}
                  key={item.index}
                  extra={<Text type='secondary'>{item.processing_time_ms} ms</Text>}
                >
                  {renderRecommendations(item.recommendations)}
                </Panel>
              ))}
            </Collapse>
          </div>
        )}
      </Card>
    </Space>
  )
}

export default ProductionRecommendation
