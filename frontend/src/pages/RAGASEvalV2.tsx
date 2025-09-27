import React, { useMemo, useRef, useState } from 'react'
import { api } from '../api/http'
import { Button, Card, Col, Descriptions, Divider, Form, Input, InputNumber, message, Progress, Row, Space, Switch, Tabs, Table, Tag, Upload, Modal, DatePicker, Select, Popconfirm, Spin } from 'antd'
import type { UploadProps } from 'antd'
import type { ColumnsType } from 'antd/es/table'

interface ExcelTestCase {
  question_id?: string | number
  row_index?: number
  clinical_query: string
  ground_truth?: string
}

interface EvalResultItem {
  question_id: string
  clinical_query: string
  ground_truth?: string
  rag_answer?: string
  contexts?: string[]
  ragas_scores?: any
  evaluation_details?: any
  status?: string
}
interface RunLogItem {
  id: number
  query_text: string
  success: boolean
  inference_method?: string
  execution_time_ms?: number
  created_at?: string
}
interface EvalTaskItem {
  task_id: string
  status: string
  created_at?: string
  completed_at?: string
  total_cases?: number
  processed_cases?: number
  model_name?: string
  evaluation_config?: any
}



const RAGASEvalV2: React.FC = () => {
  const [excelFile, setExcelFile] = useState<any>(null)
  const [excelTestCases, setExcelTestCases] = useState<ExcelTestCase[]>([])
  const [runs, setRuns] = useState<RunLogItem[]>([])
  const [runsLoading, setRunsLoading] = useState<boolean>(false)
  const [runsSelectedKeys, setRunsSelectedKeys] = useState<React.Key[]>([])
  const [runStatusFilter, setRunStatusFilter] = useState<string | undefined>(undefined)
  const [runDateRange, setRunDateRange] = useState<any>(null)

  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [inferLoading, setInferLoading] = useState(false)
  const [inferProgress, setInferProgress] = useState({ current: 0, total: 0 })
  // 检索/候选配置，与RAG助手保持一致
  const [topScenarios, setTopScenarios] = useState<number>(Number(localStorage.getItem('rag.topScenarios') || 3))
  const [topRecsPerScenario, setTopRecsPerScenario] = useState<number>(Number(localStorage.getItem('rag.topRecs') || 3))
  const [simThreshold, setSimThreshold] = useState<number>(Number(localStorage.getItem('rag.simThreshold') || 0.6))
  const [evalLoading, setEvalLoading] = useState(false)
  const [evalTasks, setEvalTasks] = useState<EvalTaskItem[]>([])
  const [evalTasksLoading, setEvalTasksLoading] = useState<boolean>(false)
  const [evalTaskDetail, setEvalTaskDetail] = useState<any>(null)
  const [evalTaskDetailOpen, setEvalTaskDetailOpen] = useState<boolean>(false)

  // 推理记录详情
  const [runDetailOpen, setRunDetailOpen] = useState<boolean>(false)
  const [runDetail, setRunDetail] = useState<any>(null)
  const [runDetailId, setRunDetailId] = useState<number | null>(null)
  const [runDetailCache, setRunDetailCache] = useState<Record<number, any>>({})

  const [ragasProgress, setRagasProgress] = useState({ current: 0, total: 0 })
  const [ragasSummary, setRagasSummary] = useState<any>(null)
  const [ragasResults, setRagasResults] = useState<EvalResultItem[]>([])

  // 评测数据处理相关状态
  // 已弃用：评测数据处理预览

  const handleExcelUpload: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options
    try {
      const formData = new FormData()
      formData.append('file', file as File)
      const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      if (response.data.success) {
        const testCases = (response.data.test_cases || []) as ExcelTestCase[]
        setExcelTestCases(testCases)
        setExcelFile({ uid: '1', name: response.data.filename, status: 'done', response: response.data })
        message.success(`成功解析Excel文件，共${response.data.total_cases}个测试案例`)
        onSuccess?.(response.data)
      } else {
        throw new Error(response.data.message || '文件上传失败')
      }
    } catch (error: any) {
      message.error('文件上传失败：' + (error.response?.data?.detail || error.message))
      onError?.(error)
    }
  }

  const runsColumns: ColumnsType<RunLogItem> = [
    { title: 'ID', dataIndex: 'id', width: 80 },
    { title: '查询', dataIndex: 'query_text', ellipsis: true },
    { title: '方法', dataIndex: 'inference_method', width: 110, render: (v) => <Tag>{v || 'rag'}</Tag> },
    { title: '成功', dataIndex: 'success', width: 90, render: (v:boolean) => v ? <Tag color='green'>是</Tag> : <Tag color='red'>否</Tag> },
    { title: '耗时(ms)', dataIndex: 'execution_time_ms', width: 110 },
    { title: '时间', dataIndex: 'created_at', width: 200, render: (v:any) => v ? new Date(v).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '' },
  ]

  const ragasColumns: ColumnsType<EvalResultItem> = [
    { title: 'ID', dataIndex: 'question_id', width: 120 },
    { title: '临床场景', dataIndex: 'clinical_query', ellipsis: true },
    { title: '标准答案', dataIndex: 'ground_truth', width: 240, ellipsis: true },
    { title: '模型', width: 200, render: (_:any, r) => (r as any)?.evaluation_details?.ragas_llm_model 
        || (r as any)?.metadata?.ragas_details?.ragas_llm_model 
        || (r as any)?.metadata?.ragas_llm_model 
        || (r as any)?.evaluation_details?.model 
        || 'unknown' },
    { title: '输出预览', dataIndex: 'rag_answer', width: 240, ellipsis: true },
    { title: 'Faithfulness', dataIndex: ['ragas_scores', 'faithfulness'], width: 130,
      render: (_:any, r) => {
        const v = r?.ragas_scores?.faithfulness
        return typeof v === 'number' ? v.toFixed(3) : (v ?? '')
      }
    },
    { title: 'Answer Relevancy', dataIndex: ['ragas_scores', 'answer_relevancy'], width: 160,
      render: (_:any, r) => {
        const v = r?.ragas_scores?.answer_relevancy
        return typeof v === 'number' ? v.toFixed(3) : (v ?? '')

      }
    },
    { title: 'Context Precision', dataIndex: ['ragas_scores', 'context_precision'], width: 160,
      render: (_:any, r) => {
        const v = r?.ragas_scores?.context_precision
        return typeof v === 'number' ? v.toFixed(3) : (v ?? '')
      }
    },
    { title: 'Context Recall', dataIndex: ['ragas_scores', 'context_recall'], width: 150,
      render: (_:any, r) => {
        const v = r?.ragas_scores?.context_recall
        return typeof v === 'number' ? v.toFixed(3) : (v ?? '')
      }
    },
  ]

  // 离线评测详细渲染（输入/GT/输出/模型/上下文/细节）
  const renderEvalDetail = (r: EvalResultItem) => {
    const details = (r as any)?.evaluation_details || (r as any)?.metadata?.ragas_details || (r as any)?.metadata || {}
    const model = details?.ragas_llm_model || details?.model || 'unknown'
    const embedModel = details?.ragas_embedding_model || details?.embedding_model
    return (
      <div style={{ background: '#fafafa', padding: 12, borderRadius: 6 }}>
        <Descriptions size='small' column={1} bordered>
          <Descriptions.Item label='输入（question）'>
            <div style={{ whiteSpace: 'pre-wrap' }}>{r?.clinical_query || ''}</div>
          </Descriptions.Item>
          <Descriptions.Item label='标准答案（ground_truth）'>
            <div style={{ whiteSpace: 'pre-wrap' }}>{r?.ground_truth || ''}</div>
          </Descriptions.Item>
          <Descriptions.Item label='输出（rag_answer）'>
            <div style={{ whiteSpace: 'pre-wrap' }}>{r?.rag_answer || ''}</div>
          </Descriptions.Item>
          <Descriptions.Item label='使用的模型'>
            <div>{model}{embedModel ? ` · ${embedModel}` : ''}</div>
          </Descriptions.Item>
          <Descriptions.Item label='评测方式'>
            <div>{details?.method || 'ragas_v2'}</div>
          </Descriptions.Item>
        </Descriptions>
        {Array.isArray(r?.contexts) && r.contexts.length > 0 && (
          <div style={{ marginTop: 10 }}>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>上下文（contexts）</div>
            {r.contexts.map((c, i) => (
              <div key={i} style={{ background: '#f5f5f5', padding: 8, borderRadius: 4, marginBottom: 6, fontSize: 12 }}>
                <b>#{i+1}</b> {c}
              </div>
            ))}
          </div>
        )}
        <div style={{ marginTop: 10 }}>
          <div style={{ fontWeight: 600, marginBottom: 6 }}>评分（ragas_scores）</div>
          <pre className='mono' style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(r?.ragas_scores || {}, null, 2)}</pre>
        </div>
        {Object.keys(details).length > 0 && (
          <div style={{ marginTop: 10 }}>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>评测细节（evaluation_details）</div>
            <pre className='mono' style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(details, null, 2)}</pre>
          </div>
        )}
      </div>
    )
  }


  const mappedSelection = useMemo(() => {
    if (!selectedRowKeys.length) return [] as ExcelTestCase[]
    return selectedRowKeys.map((idx) => excelTestCases[Number(idx)])
  }, [selectedRowKeys, excelTestCases])

  const columns: ColumnsType<ExcelTestCase> = [
    { title: '索引', dataIndex: 'row_index', key: 'row_index', width: 80, render: (_: any, __: any, i: number) => i + 1 },
    { title: '临床场景(question)', dataIndex: 'clinical_query', key: 'clinical_query' },
    { title: '标准答案(ground_truth)', dataIndex: 'ground_truth', key: 'ground_truth', width: 260 },
  ]

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[]) => setSelectedRowKeys(keys),
    preserveSelectedRowKeys: true,
  }

  const runsRowSelection = {
    selectedRowKeys: runsSelectedKeys,
    onChange: (keys: React.Key[]) => setRunsSelectedKeys(keys),
    preserveSelectedRowKeys: true,
  }

  // 阶段一：批量推理与记录（仅调用推荐API并上传run日志，不做RAGAS）
  const runBatchInference = async () => {
    const cases = mappedSelection.length ? mappedSelection : excelTestCases
    if (!cases.length) return message.warning('请先上传并选择评测数据')

    setInferLoading(true)
    setInferProgress({ current: 0, total: cases.length })

    for (let i = 0; i < cases.length; i++) {
      const tc = cases[i]
      const q = tc.clinical_query


      const gt = (tc.ground_truth || '').toString()
      try {
        const t0 = Date.now()
        const resp = await api.post('/api/v1/acrac/rag-llm/intelligent-recommendation', {
          clinical_query: q,
          top_scenarios: topScenarios,
          top_recommendations_per_scenario: topRecsPerScenario,
          show_reasoning: true,
          similarity_threshold: simThreshold,
          debug_mode: true,
          include_raw_data: true,
          compute_ragas: false,
          ground_truth: gt,
        })
        const t1 = Date.now()
        // 上传到服务端持久化（与 RAG 助手一致）
        await api.post('/api/v1/acrac/rag-llm/runs/log', {
          query_text: q,
          result: resp.data,
          success: resp?.data?.success !== false,
          execution_time_ms: resp?.data?.processing_time_ms || (t1 - t0),
          inference_method: resp?.data?.is_low_similarity_mode ? 'no-rag' : 'rag',
          error_message: resp?.data?.message || null,
        })
      } catch (e: any) {
        // 不中断全量，继续
      } finally {
        setInferProgress((p) => ({ current: p.current + 1, total: p.total }))
      }
    }

    setInferLoading(false)
    message.success('批量推理完成，已保存到历史记录')
    // 自动刷新最近推理记录，便于立即查看并选择评测
    await loadRunsWithFilters()
  }

  // 阶段二：离线RAGAS评测（当前复用 /api/v1/ragas/evaluate，后端将逐步改为直接使用历史推理数据）

  const loadRunsWithFilters = async () => {
    try {
      setRunsLoading(true)
      const params:any = { page: 1, page_size: 10 }
      if (runStatusFilter) params.status = runStatusFilter
      if (runDateRange && runDateRange.length === 2) {
        params.start = runDateRange[0]?.format ? runDateRange[0].format('YYYY-MM-DD') : undefined
        params.end = runDateRange[1]?.format ? runDateRange[1].format('YYYY-MM-DD') : undefined
      }
      const r = await api.get('/api/v1/acrac/rag-llm/runs', { params })
      setRuns(r.data?.items || [])
    } catch (e:any) {
      message.error('加载推理记录失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setRunsLoading(false)
    }
  }

  const openRunDetail = async (record: RunLogItem) => {
    const id = record?.id
    setRunDetailId(id)
    setRunDetailOpen(true)
    try {
      const r = await api.get(`/api/v1/acrac/rag-llm/runs/${id}`)
      setRunDetail(r.data || r)
      setRunDetailCache((prev) => ({ ...prev, [id]: (r.data || r) }))
    } catch (e:any) {
      // 若后端无详情接口，回退到列表项本身
      setRunDetail(record)
      message.warning('后端未提供推理详情接口，已显示列表项内容')
    }
  }

  const ensureRunDetail = async (record: RunLogItem) => {
    if (!record?.id) return
    if (runDetailCache[record.id]) return
    try {
      const r = await api.get(`/api/v1/acrac/rag-llm/runs/${record.id}`)
      setRunDetailCache((prev) => ({ ...prev, [record.id]: (r.data || r) }))
    } catch (e:any) {
      // 忽略错误，使用列表项信息兜底
      setRunDetailCache((prev) => ({ ...prev, [record.id]: record }))
    }
  }

  // 渲染处理后的评测数据
  // 已弃用：renderProcessedData

  // 渲染推理详情的结构化内容
  const renderRunDetailContent = (detail: any) => {
    if (!detail) return <div>暂无数据</div>

    const result = detail.result || detail
    
    return (
      <div style={{ maxHeight: 500, overflow: 'auto' }}>
        <Descriptions title="基本信息" bordered size="small" column={2}>
          <Descriptions.Item label="查询ID">{detail.id}</Descriptions.Item>
          <Descriptions.Item label="查询文本">{detail.query_text}</Descriptions.Item>
          <Descriptions.Item label="推理方法">{detail.inference_method}</Descriptions.Item>
          <Descriptions.Item label="执行状态">{detail.success ? '成功' : '失败'}</Descriptions.Item>
          <Descriptions.Item label="执行时间">{detail.execution_time_ms}ms</Descriptions.Item>
          <Descriptions.Item label="创建时间">{detail.created_at}</Descriptions.Item>
        </Descriptions>

        {detail.error_message && (
          <div style={{ marginTop: 16 }}>
            <h4>错误信息</h4>
            <div style={{ color: 'red', background: '#fff2f0', padding: 8, borderRadius: 4 }}>
              {detail.error_message}
            </div>
          </div>
        )}

        {result && (
          <div style={{ marginTop: 16 }}>
            <h4>推理结果</h4>
            
            {/* LLM推荐结果 */}
            {result.llm_recommendations && (
              <div style={{ marginBottom: 16 }}>
                <h5>LLM推荐</h5>
                <div style={{ background: '#f6ffed', padding: 12, borderRadius: 4, border: '1px solid #b7eb8f' }}>
                  <div><strong>推荐内容：</strong></div>
                  <div style={{ marginTop: 8, whiteSpace: 'pre-wrap' }}>
                    {typeof result.llm_recommendations === 'string' 
                      ? result.llm_recommendations 
                      : JSON.stringify(result.llm_recommendations, null, 2)}
                  </div>
                </div>
              </div>
            )}

            {/* 检索场景 */}
            {result.scenarios && result.scenarios.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <h5>检索场景 ({result.scenarios.length}个)</h5>
                {result.scenarios.map((scenario: any, idx: number) => (
                  <div key={idx} style={{ 
                    background: '#f0f2f5', 
                    padding: 12, 
                    marginBottom: 8, 
                    borderRadius: 4,
                    border: '1px solid #d9d9d9'
                  }}>
                    <div><strong>场景 {idx + 1}:</strong> {scenario.scenario_name || scenario.name}</div>
                    {scenario.similarity_score && (
                      <div><strong>相似度:</strong> {(scenario.similarity_score * 100).toFixed(2)}%</div>
                    )}
                    {scenario.description && (
                      <div style={{ marginTop: 4 }}>
                        <strong>描述:</strong> {scenario.description}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* 上下文信息 */}
            {result.contexts && result.contexts.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <h5>检索上下文 ({result.contexts.length}个)</h5>
                {result.contexts.map((context: string, idx: number) => (
                  <div key={idx} style={{ 
                    background: '#fff7e6', 
                    padding: 8, 
                    marginBottom: 4, 
                    borderRadius: 4,
                    border: '1px solid #ffd591'
                  }}>
                    <strong>上下文 {idx + 1}:</strong> {context.substring(0, 200)}
                    {context.length > 200 && '...'}
                  </div>
                ))}
              </div>
            )}

            {/* 模型信息 */}
            <div style={{ marginBottom: 16 }}>
              <h5>模型信息</h5>
              <Descriptions size="small" column={1}>
                {result.model_used && <Descriptions.Item label="LLM模型">{result.model_used}</Descriptions.Item>}
                {result.embedding_model_used && <Descriptions.Item label="嵌入模型">{result.embedding_model_used}</Descriptions.Item>}
                {result.reranker_model_used && <Descriptions.Item label="重排模型">{result.reranker_model_used}</Descriptions.Item>}
                {result.similarity_threshold && <Descriptions.Item label="相似度阈值">{result.similarity_threshold}</Descriptions.Item>}
                {result.max_similarity && <Descriptions.Item label="最大相似度">{(result.max_similarity * 100).toFixed(2)}%</Descriptions.Item>}
                {result.processing_time_ms && <Descriptions.Item label="处理时间">{result.processing_time_ms}ms</Descriptions.Item>}
              </Descriptions>
            </div>

            {/* 调试信息 */}
            {result.debug_info && (
              <div style={{ marginBottom: 16 }}>
                <h5>调试信息</h5>
                <pre style={{ 
                  background: '#f5f5f5', 
                  padding: 8, 
                  borderRadius: 4, 
                  fontSize: '12px',
                  maxHeight: 200,
                  overflow: 'auto'
                }}>
                  {JSON.stringify(result.debug_info, null, 2)}
                </pre>
              </div>
            )}

            {/* 原始数据 */}
            <div>
              <h5>完整原始数据</h5>
              <pre style={{ 
                background: '#fafafa', 
                padding: 8, 
                borderRadius: 4, 
                fontSize: '11px',
                maxHeight: 300,
                overflow: 'auto',
                border: '1px solid #e8e8e8'
              }}>
                {JSON.stringify(result, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    )
  }

  const runsColumnsWithOps: ColumnsType<RunLogItem> = useMemo(() => {
    return [
      ...runsColumns,
      { title: '操作', width: 120, render: (_: any, r: RunLogItem) => (
        <Button size='small' onClick={() => openRunDetail(r)}>查看详细</Button>
      )}
    ]
  }, [runsColumns])

  const loadRecentRuns = async () => {
    await loadRunsWithFilters()
  }

  // 评测数据处理函数
  // 已弃用：processEvaluationData

  const offlineEvaluateSelectedRuns = async () => {
    if (!runsSelectedKeys.length) return message.warning('请先选择要评测的推理记录')
    
    try {
      // 构建 run_id -> ground_truth 映射
      const gtMap: Record<number, string> = {}
      const runIdToQuery: Record<number, string> = {}
      runs.filter(r => runsSelectedKeys.includes(r.id)).forEach(r => { runIdToQuery[r.id] = r.query_text })
      excelTestCases.forEach(tc => {
        const match = Object.entries(runIdToQuery).find(([id, q]) => q === tc.clinical_query)
        if (match && tc.ground_truth) gtMap[Number(match[0])] = tc.ground_truth
      })

      // 调用RAGAS离线评测API
      const resp = await api.post('/api/v1/ragas/offline-evaluate', {
        run_ids: runsSelectedKeys,
        ground_truths: gtMap,
        async_mode: false
      })
      
      setRagasResults(resp.data?.results || [])
      setRagasSummary(resp.data?.summary || null)
      message.success(`已完成离线评测，共评测${runsSelectedKeys.length}条记录`)
    } catch (e:any) {
      message.error('离线评测失败：' + (e?.response?.data?.detail || e.message))
    }
  }

  const deleteSelectedRuns = async () => {
    if (!runsSelectedKeys.length) return message.warning('请先勾选要删除的推理记录')
    try {
      await api.delete('/api/v1/acrac/rag-llm/runs', { data: { ids: runsSelectedKeys } })
      message.success('已删除所选推理记录')
      setRunsSelectedKeys([])
      await loadRunsWithFilters()
    } catch (e:any) {
      message.error('删除失败：' + (e?.response?.data?.detail || e.message))
    }
  }

  // 移除loadFullRagasResults函数，因为改为同步模式

  const evalTasksColumns: ColumnsType<EvalTaskItem> = [
    { title: '任务ID', dataIndex: 'task_id', width: 220 },
    { title: '状态', dataIndex: 'status', width: 120, render: (v) => <Tag color={v==='completed'?'green':(v==='failed'?'red':'processing')}>{v}</Tag> },
    { title: '模型', width: 180, render: (_:any, r:EvalTaskItem) => r?.model_name || r?.evaluation_config?.ragas_llm_model || r?.evaluation_config?.model_name || 'unknown' },
    { title: '总数', dataIndex: 'total_cases', width: 90 },
    { title: '已处理', dataIndex: 'processed_cases', width: 100 },
    { title: '创建时间', dataIndex: 'created_at', width: 180, render: (v:any) => v ? new Date(v).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }) : '' },
  ]

  const loadEvalHistory = async () => {
    try {
      setEvalTasksLoading(true)
      const r = await api.get('/api/v1/ragas/history', { params: { page: 1, page_size: 10 } })
      setEvalTasks(r.data?.items || r.data?.tasks || [])
    } catch (e:any) {
      message.error('加载评测历史失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setEvalTasksLoading(false)
    }
  }

  const openEvalTask = async (taskId: string) => {
    try {
      const r = await api.get(`/api/v1/ragas/history/${taskId}`)
      setEvalTaskDetail(r.data)
      setEvalTaskDetailOpen(true)
    } catch (e:any) {
      message.error('加载评测任务详情失败：' + (e?.response?.data?.detail || e.message))
    }
  }

  const startOfflineEvaluation = async () => {
    const cases = mappedSelection.length ? mappedSelection : excelTestCases
    if (!cases.length) return message.warning('请先上传并选择评测数据')

    setEvalLoading(true)
    setRagasResults([])
    setRagasSummary(null)

    try {
      const mappedCases = cases.map(tc => ({
        question_id: String((tc as any).question_id ?? (tc as any).row_index ?? ''),
        clinical_query: (tc as any).clinical_query,
        ground_truth: (tc as any).ground_truth,
      }))
      // 初始化同步评测进度（总数）
      setRagasProgress({ current: 0, total: mappedCases.length })
      // 使用同步的RAGAS评测API
      const response = await api.post('/api/v1/ragas-standalone/evaluate', {
        test_data: mappedCases
      })
      
      if (response.data?.status === 'success') {
        const results = response.data.results
        setRagasResults(results?.detailed_results || [])
        setRagasSummary(results?.summary || {})
        setRagasProgress({ current: mappedCases.length, total: mappedCases.length })
        message.success('RAGAS评测完成！')
      } else {
        message.error(`RAGAS评测失败: ${response.data?.error || '未知错误'}`)
      }
    } catch (e: any) {
      message.error('RAGAS评测失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setEvalLoading(false)
    }
  }

  // 移除轮询函数，因为改为同步模式

  const dataSource = useMemo(() => excelTestCases.map((tc, i) => ({ key: i, ...tc })), [excelTestCases])

  return (
    <div>
      <div className='page-title'>RAGAS 评测（两阶段：批量推理 → 离线评分）</div>
      <Card size='small' style={{ marginBottom: 12 }}>
        <Descriptions column={1} size='small'>
          <Descriptions.Item label='使用说明'>
            1) 阶段一仅执行 RAG+LLM 推理并保存记录；2) 阶段二读取历史推理/或本次数据，按RAGAS规则离线评分。支持选择部分样本分别执行。
          </Descriptions.Item>
          <Descriptions.Item label='数据集'>
            建议上传本地 Excel：影像测试样例-0318-1.xlsx（包含 question/ground_truth）。服务器路径不可直接读取，请在此上传。
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title='步骤1：上传与预览' style={{ marginBottom: 12 }}>
        <Space direction='vertical' style={{ width: '100%' }}>
          <Upload
            customRequest={handleExcelUpload}
            accept='.xlsx,.xls'
            maxCount={1}
            fileList={excelFile ? [excelFile] : []}
            onChange={({ fileList }) => { if (fileList.length === 0) { setExcelFile(null); setExcelTestCases([]); setSelectedRowKeys([]) } }}
          >
            <Button type='primary'>上传Excel文件</Button>
          </Upload>
          <Table
            size='small'
            rowSelection={rowSelection}
            columns={columns}
            dataSource={dataSource}
            pagination={{ pageSize: 8 }}
          />
        </Space>
      </Card>

      <Tabs
        items={[
          {
            key: 'phase1',
            label: '阶段一：批量推理并保存记录',
            children: (
              <Card>
                <Space direction='vertical' style={{ width: '100%' }}>
                  <Space wrap>
                    <InputNumber min={1} max={10} value={topScenarios} onChange={(v)=>{ const n=Number(v||3); setTopScenarios(n); localStorage.setItem('rag.topScenarios', String(n)) }} addonBefore='检索场景数' />
                    <InputNumber min={1} max={10} value={topRecsPerScenario} onChange={(v)=>{ const n=Number(v||3); setTopRecsPerScenario(n); localStorage.setItem('rag.topRecs', String(n)) }} addonBefore='每场景候选数' />
                    <InputNumber min={0} max={1} step={0.05} value={simThreshold} onChange={(v)=>{ const n=Number(v||0.6); setSimThreshold(n); localStorage.setItem('rag.simThreshold', String(n)) }} addonBefore='相似度阈值' />
                    <Button type='primary' onClick={runBatchInference} loading={inferLoading}>
                      开始批量推理（仅推理，不评测）
                    </Button>
                    {inferProgress.total > 0 && (
                      <span>进度：{inferProgress.current}/{inferProgress.total}</span>
                    )}
                  </Space>
                  {inferProgress.total > 0 && (
                    <Progress percent={Math.round((inferProgress.current / Math.max(inferProgress.total, 1)) * 100)} />
                  )}
                </Space>
              </Card>
            )
          },
          {
            key: 'phase2',
            label: '阶段二：离线RAGAS评测（基于历史/本次数据）',
            children: (
              <Card>
                <Space direction='vertical' style={{ width: '100%' }}>
                  <Space>
                    <Button type='primary' onClick={startOfflineEvaluation} loading={evalLoading}>开始离线评测</Button>
                    {ragasProgress.total > 0 && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {evalLoading && <Spin size='small' />}
                        <span>进度：{ragasProgress.current}/{ragasProgress.total}</span>
                      </div>
                    )}
                  </Space>
                  <Divider />
                  <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                    <Space wrap>
                      <Select
                        placeholder='状态筛选'
                        allowClear
                        style={{ width: 140 }}
                        value={runStatusFilter}
                        onChange={(v) => setRunStatusFilter(v)}
                        options={[{ label: '成功', value: 'success' }, { label: '失败', value: 'failed' }]}
                      />
                      <DatePicker.RangePicker value={runDateRange} onChange={(v) => setRunDateRange(v)} />
                      <Button onClick={loadRunsWithFilters} loading={runsLoading}>筛选</Button>
                      <Button onClick={() => { setRunStatusFilter(undefined); setRunDateRange(null); loadRunsWithFilters(); }}>清空筛选</Button>
                    </Space>
                    <Space>
                      <Button onClick={loadRecentRuns} loading={runsLoading}>刷新</Button>
                      <Button type='primary' disabled={!runsSelectedKeys.length} onClick={offlineEvaluateSelectedRuns}>开始离线评测</Button>
                      <Popconfirm title='确认删除选中推理记录？' onConfirm={deleteSelectedRuns}>
                        <Button danger disabled={!runsSelectedKeys.length}>批量删除</Button>
                      </Popconfirm>
                      <a href="/runs" target="_blank" rel="noreferrer">查看全部运行历史</a>
                    </Space>
                  </Space>
                  <Table
                    size='small'
                    rowKey='id'
                    rowSelection={runsRowSelection}
                    columns={runsColumnsWithOps}
                    expandable={{
                      expandedRowRender: (record) => renderRunDetailContent(runDetailCache[(record as any).id] || record),
                      onExpand: (expanded, record) => { if (expanded) ensureRunDetail(record as RunLogItem) }
                    }}
                    dataSource={runs}
                    pagination={{ pageSize: 10 }}
                    style={{ marginTop: 12 }}
                  />

                  {ragasProgress.total > 0 && (
                    <Progress 
                      status={evalLoading ? 'active' : undefined}
                      percent={Math.round((ragasProgress.current / Math.max(ragasProgress.total, 1)) * 100)} 
                      format={(p)=>`${ragasProgress.current}/${ragasProgress.total} · ${p}%`} 
                    />
                  )}
                  {ragasSummary && (
                    <>
                      <Card size='small' title='评测汇总（可视化）' style={{ marginBottom: 8 }}>
                        <Row gutter={12}>
                          <Col span={12}>
                            <div style={{ marginBottom: 8 }}>Faithfulness</div>
                            <Progress percent={Math.round((ragasSummary?.faithfulness || 0) * 100)} />
                            <div style={{ margin: '12px 0 8px' }}>Answer Relevancy</div>
                            <Progress percent={Math.round((ragasSummary?.answer_relevancy || 0) * 100)} />
                          </Col>
                          <Col span={12}>
                            <div style={{ marginBottom: 8 }}>Context Precision</div>
                            <Progress percent={Math.round((ragasSummary?.context_precision || 0) * 100)} />
                            <div style={{ margin: '12px 0 8px' }}>Context Recall</div>
                            <Progress percent={Math.round((ragasSummary?.context_recall || 0) * 100)} />
                          </Col>
                        </Row>
                        <div style={{ marginTop: 8, color: '#999' }}>
                          统计：{ragasSummary?.completed ?? 0}/{ragasSummary?.total ?? 0} 完成 · 失败 {ragasSummary?.failed ?? 0}
                        </div>
                        <div style={{ marginTop: 4 }}>
                          使用模型：{(ragasResults?.[0]?.evaluation_details?.ragas_llm_model) || 'unknown'}
                        </div>
                      </Card>
                      <pre className='mono' style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(ragasSummary, null, 2)}</pre>
                    </>
                  )}
                  <Divider />
                  <Table
                    size='small'
                    rowKey='question_id'
                    columns={ragasColumns}
                    dataSource={ragasResults}
                    expandable={{ expandedRowRender: (r) => renderEvalDetail(r as EvalResultItem) }}
                    pagination={{ pageSize: 10 }}
                    style={{ marginTop: 12 }}
                  />

                </Space>
              </Card>
            )
          }
,
          {
            key: 'history',
            label: '历史：推理与评测',
            children: (
              <Card>
                <Space direction='vertical' style={{ width: '100%' }}>
                  <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                    <Space wrap>
                      <Select
                        placeholder='状态筛选'
                        allowClear
                        style={{ width: 140 }}
                        value={runStatusFilter}
                        onChange={(v) => setRunStatusFilter(v)}
                        options={[{ label: '成功', value: 'success' }, { label: '失败', value: 'failed' }]}
                      />
                      <DatePicker.RangePicker value={runDateRange} onChange={(v) => setRunDateRange(v)} />
                      <Button onClick={loadRunsWithFilters} loading={runsLoading}>筛选</Button>
                      <Button onClick={() => { setRunStatusFilter(undefined); setRunDateRange(null); loadRunsWithFilters(); }}>清空筛选</Button>
                    </Space>
                    <Space>
                      <Button onClick={loadRecentRuns} loading={runsLoading}>刷新推理记录</Button>
                      <Button type='primary' disabled={!runsSelectedKeys.length} onClick={offlineEvaluateSelectedRuns}>开始离线评测</Button>
                      <Popconfirm title='确认删除选中推理记录？' onConfirm={deleteSelectedRuns}>
                        <Button danger disabled={!runsSelectedKeys.length}>批量删除</Button>
                      </Popconfirm>
                      <Button onClick={loadEvalHistory} loading={evalTasksLoading}>刷新评测历史</Button>
                      <a href="/runs" target="_blank" rel="noreferrer">查看全部运行历史</a>
                    </Space>
                  </Space>

                  <Table
                    size='small'
                    rowKey='id'
                    rowSelection={runsRowSelection}
                    columns={runsColumnsWithOps}
                    dataSource={runs}
                    pagination={{ pageSize: 10 }}
                    title={() => '最近推理记录'}
                  />

                  <Table
                    size='small'
                    rowKey='task_id'
                    columns={[
                      ...evalTasksColumns,
                      {
                        title: '操作', width: 200,
                        render: (_: any, r: EvalTaskItem) => (
                          <Space>
                            <Button size='small' onClick={() => openEvalTask(r.task_id)}>查看</Button>
                          </Space>
                        )
                      }
                    ]}
                    dataSource={evalTasks}
                    pagination={{ pageSize: 10 }}
                    title={() => 'RAGAS 评测历史任务'}
                  />

                  <Modal open={evalTaskDetailOpen} width={900} title={`评测任务详情 #${evalTaskDetail?.task_id || ''}`}
                         onCancel={() => setEvalTaskDetailOpen(false)} footer={null}>
                    {evalTaskDetail ? (
                      <div>
                        <div>状态：{evalTaskDetail?.status}</div>
                        <div>模型：{evalTaskDetail?.model_name || evalTaskDetail?.evaluation_config?.ragas_llm_model || evalTaskDetail?.evaluation_config?.model_name}</div>
                        <div>总数/已处理：{evalTaskDetail?.total_cases}/{evalTaskDetail?.processed_cases}</div>
                        {evalTaskDetail?.summary && (
                          <Card size='small' title='汇总可视化' style={{ marginTop: 8 }}>
                            <Row gutter={12}>
                              <Col span={12}>
                                <div style={{ marginBottom: 8 }}>Faithfulness</div>
                                <Progress percent={Math.round((evalTaskDetail.summary?.faithfulness || 0) * 100)} />
                                <div style={{ margin: '12px 0 8px' }}>Answer Relevancy</div>
                                <Progress percent={Math.round((evalTaskDetail.summary?.answer_relevancy || 0) * 100)} />
                              </Col>
                              <Col span={12}>
                                <div style={{ marginBottom: 8 }}>Context Precision</div>
                                <Progress percent={Math.round((evalTaskDetail.summary?.context_precision || 0) * 100)} />
                                <div style={{ margin: '12px 0 8px' }}>Context Recall</div>
                                <Progress percent={Math.round((evalTaskDetail.summary?.context_recall || 0) * 100)} />
                              </Col>
                            </Row>
                          </Card>
                        )}
                        <Divider />
                        <div style={{ fontWeight: 600, marginBottom: 6 }}>评测案例明细</div>
                        <Table
                          size='small'
                          rowKey='question_id'
                          columns={ragasColumns}
                          dataSource={evalTaskDetail?.results || []}
                          expandable={{ expandedRowRender: (r:any) => renderEvalDetail(r as any) }}
                          pagination={{ pageSize: 8 }}
                        />
                      </div>
                    ) : null}
                  </Modal>
                  <Modal
                     title={`推理记录详情 #${runDetailId ?? ''}`}
                     open={runDetailOpen}
                     onCancel={() => setRunDetailOpen(false)}
                     footer={null}
                     width={1000}
                   >
                     {renderRunDetailContent(runDetail)}
                   </Modal>

                  {/* 已移除：评测数据处理功能 */}


                </Space>
              </Card>
            )
          }
        ]}
      />
    </div>
  )
}

export default RAGASEvalV2

