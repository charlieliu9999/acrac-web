import React, { useState, useEffect } from 'react'
import { Button, Card, Col, Form, InputNumber, Row, Select, Table, Progress, Tag, Typography, message, Space, Divider, Modal, Upload, Tabs, Badge, Statistic, Switch, Input } from 'antd'
import { DownloadOutlined, PlayCircleOutlined, PauseCircleOutlined, ReloadOutlined, UploadOutlined, FileExcelOutlined, EyeOutlined, DatabaseOutlined, HistoryOutlined } from '@ant-design/icons'
import { api } from '../api/http'
import type { UploadProps, UploadFile } from 'antd/es/upload/interface'

const { Text, Title } = Typography
const { Option } = Select

interface EvaluationResult {
  question_id: number
  query: string
  ground_truth: string
  answer?: string
  response_time?: number
  trace: any
  ragas_scores?: any
  timestamp: string
  model?: string
  source?: string
  status: 'pending' | 'running' | 'completed' | 'error'
  error?: string
  error_message?: string
}

interface EvaluationConfig {
  data_count: number
  llm_model: string
  similarity_threshold: number
  top_scenarios: number
  top_recommendations_per_scenario: number
}

interface ExcelTestCase {
  question_id: number
  clinical_query: string
  ground_truth: string
  row_index: number
}

interface ExcelEvaluationStatus {
  is_running: boolean
  progress: number
  total: number
  current_case: string | null
  results: any[]
  error: string | null
}

const RAGEvaluation: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [evaluationResults, setEvaluationResults] = useState<EvaluationResult[]>([])
  const [currentProgress, setCurrentProgress] = useState(0)
  const [totalItems, setTotalItems] = useState(0)
  const [isRunning, setIsRunning] = useState(false)
  const [historyVisible, setHistoryVisible] = useState(false)
  const [historyData, setHistoryData] = useState<EvaluationResult[]>([])

  // Excel相关状态
  const [activeTab, setActiveTab] = useState('database')
  const [excelFile, setExcelFile] = useState<UploadFile | null>(null)
  const [excelTestCases, setExcelTestCases] = useState<ExcelTestCase[]>([])
  const [excelPreviewVisible, setExcelPreviewVisible] = useState(false)
  const [excelEvaluationStatus, setExcelEvaluationStatus] = useState<ExcelEvaluationStatus>({
    is_running: false,
    progress: 0,
    total: 0,
    current_case: null,
    results: [],
    error: null
  })
  const [excelStatusPolling, setExcelStatusPolling] = useState<number | null>(null)

  // RAGAS评测状态
  const [ragasTaskId, setRagasTaskId] = useState<string | null>(null)
  const [ragasPolling, setRagasPolling] = useState<number | null>(null)
  const [ragasResults, setRagasResults] = useState<any[]>([])
  const [outputFilename, setOutputFilename] = useState<string | null>(null)
  const [selectedLLM, setSelectedLLM] = useState<string>('')
  const [selectedEmbedding, setSelectedEmbedding] = useState<string | undefined>(undefined)
  const [dataCount, setDataCount] = useState<number | undefined>(undefined)
  // 新增：RAGAS进度（用于异步实时进度展示，及同步模式的占位进度）
  const [ragasSyncInProgress, setRagasSyncInProgress] = useState<boolean>(false)
  const [ragasSyncProgress, setRagasSyncProgress] = useState<number>(0)
  const [ragasStatus, setRagasStatus] = useState<{progress?: number; completed_cases?: number; failed_cases?: number; total?: number; status?: string} | null>(null)

  // 合并RAGAS结果（优先同步ragasResults，其次Excel评测结果）
  const getCombinedRagasItems = () => {
    const items = (ragasResults && ragasResults.length > 0) ? ragasResults : (excelEvaluationStatus.results || [])
    return Array.isArray(items) ? items.filter((it:any) => !!it && !!it.ragas_scores) : []
  }

  const metricValues = (key: 'faithfulness'|'answer_relevancy'|'context_precision'|'context_recall') => {
    const items = getCombinedRagasItems()
    return items.map((it:any) => Number(it?.ragas_scores?.[key] ?? 0)).filter((v:number) => Number.isFinite(v))
  }

  const metricAvg = (vals: number[]) => vals.length ? (vals.reduce((a,b)=>a+b,0)/vals.length) : 0

  const renderTinyBars = (vals: number[]) => {
    if (!vals || vals.length === 0) return <span style={{ color: '#999' }}>无数据</span>
    const maxH = 60
    return (
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: maxH }}>
        {vals.slice(0, 40).map((v, idx) => (
          <div key={idx} title={v.toFixed(3)} style={{ width: 6, height: Math.max(2, Math.round(v * maxH)), background: '#1677ff', borderRadius: 2 }} />
        ))}
      </div>
    )
  }

  const downloadRagasResults = (format: 'json'|'excel') => {
    const items = getCombinedRagasItems()
    if (!items.length) {
      message.warning('暂无可导出的RAGAS结果')
      return
    }
    if (format === 'json') {
      const dataStr = JSON.stringify(items, null, 2)
      const blob = new Blob([dataStr], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `ragas_results_${new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')}.json`
      a.click()
      URL.revokeObjectURL(url)
      message.success('已导出 JSON')
      return
    }
    // 简易Excel导出：使用CSV，Excel可直接打开
    if (format === 'excel') {
      const headers = ['question_id','clinical_query','ground_truth','faithfulness','answer_relevancy','context_precision','context_recall']
      const rows = items.map((it:any) => [
        it.question_id ?? '',
        (it.clinical_query ?? '').toString().replace(/\n/g,' '),
        (it.ground_truth ?? '').toString().replace(/\n/g,' '),
        (it.ragas_scores?.faithfulness ?? 0),
        (it.ragas_scores?.answer_relevancy ?? 0),
        (it.ragas_scores?.context_precision ?? 0),
        (it.ragas_scores?.context_recall ?? 0),
      ])
      const csv = [headers.join(','), ...rows.map(r => r.map(v => (typeof v === 'string' && (v.includes(',')||v.includes('"')))?`"${v.replace(/"/g,'""')}"`:v).join(','))].join('\n')
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `ragas_results_${new Date().toISOString().slice(0,19).replace(/[:T]/g,'-')}.csv`
      a.click()
      URL.revokeObjectURL(url)
      message.success('已导出 Excel(CSV)')
      return
    }
  }

  const [ragasAsync, setRagasAsync] = useState<boolean>(true)

  // 模拟LLM模型选项
  const [ragasLLMOptions, setRagasLLMOptions] = useState<{value:string,label:string,_entry?:any}[]>([])
  const [ragasEmbOptions, setRagasEmbOptions] = useState<{value:string,label:string,_entry?:any}[]>([])
  useEffect(() => {
    (async ()=>{
      try {
        const reg = await api.get('/api/v1/admin/data/models/registry')
        const data = reg.data || {}
        setRagasLLMOptions((data.llms||[]).map((m:any)=>({ value: m.model, label: (m.label||m.model)+' · '+m.model, _entry: m })))
        setRagasEmbOptions((data.embeddings||[]).map((m:any)=>({ value: m.model, label: (m.label||m.model)+' · '+m.model, _entry: m })))
      } catch(e) {}
      try {
        const cfg = await api.get('/api/v1/admin/data/models/config')
        const ragas = cfg.data?.ragas_defaults || {}
        if (ragas.llm_model) setSelectedLLM(ragas.llm_model)
        if (ragas.embedding_model) setSelectedEmbedding(ragas.embedding_model)
      } catch(e) {}
    })()
  }, [])

  useEffect(() => {
    if (!ragasSyncInProgress) {
      setRagasSyncProgress(0)
      return
    }

    setRagasSyncProgress(prev => (prev > 0 ? prev : 5))
    const timer = setInterval(() => {
      setRagasSyncProgress(prev => {
        const next = Math.min(95, prev + Math.max(1, Math.round((95 - prev) / 5)))
        setRagasStatus(current => {
          if (current && current.status === 'processing') {
            return { ...current, progress: next }
          }
          return current
        })
        return next
      })
    }, 800)

    return () => clearInterval(timer)
  }, [ragasSyncInProgress])
  const llmModels = ragasLLMOptions.length ? ragasLLMOptions : [ { value: 'Qwen/Qwen2.5-32B-Instruct', label: 'Qwen/Qwen2.5-32B-Instruct (SiliconFlow)' } ]

  const dataCountOptions = [
    { value: 5, label: '前5条数据' },
    { value: 10, label: '前10条数据' },
    { value: 20, label: '前20条数据' },
    { value: -1, label: '全部数据' },
  ]

  const onFinish = async (values: EvaluationConfig) => {
    // 检查是否有可用的测试数据
    const availableTestCases = excelTestCases.length > 0 ? excelTestCases : []

    if (availableTestCases.length === 0) {
      message.warning('请先上传Excel文件或加载数据库中的测试数据')
      return
    }

    setLoading(true)
    setIsRunning(true)
    setEvaluationResults([])
    setCurrentProgress(0)
    setTotalItems(availableTestCases.length)

    try {
      message.info(`开始评测，共${availableTestCases.length}条数据，使用模型：${values.llm_model}`)

      // 使用Excel数据进行批量评测
      const results: EvaluationResult[] = []

      for (let i = 0; i < availableTestCases.length; i++) {
        if (!isRunning) break // 支持暂停

        const testCase = availableTestCases[i]

         try {
           const startTime = Date.now()
           // 调用后端 RAG+LLM 主接口，获取推荐与trace
           const response = await api.post('/api/v1/acrac/rag-llm/intelligent-recommendation', {
             clinical_query: testCase.clinical_query,
             include_raw_data: true,
             debug_mode: true,
             top_scenarios: 3,
             top_recommendations_per_scenario: 3,
           })

           const endTime = Date.now()
           const responseTime = (endTime - startTime) / 1000

           // 将推荐拼接为可读答案文本（用于预览/导出，不影响RAGAS流程）
           const llm = response.data?.llm_recommendations || {}
           const recs = Array.isArray(llm?.recommendations) ? llm.recommendations : []
           const answerText = recs && recs.length
             ? `推荐的影像学检查:\n` + recs.slice(0,3).map((r:any)=>`- ${r.procedure_name||r.name||r.recommendation||''} (${r.modality||''})`).join('\n')
             : ''

           const result: EvaluationResult = {
             question_id: testCase.question_id,
             query: testCase.clinical_query,
             ground_truth: testCase.ground_truth,
             answer: answerText,
             response_time: responseTime,
             trace: response.data.trace || response.data.debug_info || {},
             timestamp: new Date().toISOString(),
             model: values.llm_model,
             source: 'excel',
             status: 'completed'
           }

           results.push(result)
         } catch (error) {
           const errorResult: EvaluationResult = {
             question_id: testCase.question_id,
             query: testCase.clinical_query,
             ground_truth: testCase.ground_truth,
             answer: '',
             error: error instanceof Error ? error.message : '未知错误',
             response_time: 0,
             trace: {},
             timestamp: new Date().toISOString(),
             model: values.llm_model,
             source: 'excel',
             status: 'error'
           }

           results.push(errorResult)
         }

         setCurrentProgress(i + 1)
         setEvaluationResults([...results])

         // 添加小延迟避免请求过于频繁
         await new Promise(resolve => setTimeout(resolve, 100))
      }

      message.success(`评测完成！共处理 ${results.length} 条数据`)

    } catch (error: any) {
      message.error('评测失败：' + (error.message || '未知错误'))
    } finally {
      setLoading(false)
      setIsRunning(false)
    }
  }

  const pauseEvaluation = () => {
    setIsRunning(false)
    setLoading(false)
    message.info('评测已暂停')
  }

  const resetEvaluation = () => {
    setEvaluationResults([])
    setCurrentProgress(0)
    setTotalItems(0)
    setIsRunning(false)
    setLoading(false)
    message.info('评测已重置')
  }

  const exportResults = () => {
    // 合并数据库评测结果和Excel评测结果
    const allResults = {
      database_results: evaluationResults,
      excel_results: excelEvaluationStatus.results,
      export_time: new Date().toISOString(),
      total_count: evaluationResults.length + excelEvaluationStatus.results.length,
      summary: {
        database_count: evaluationResults.length,
        excel_count: excelEvaluationStatus.results.length,
        avg_database_scores: evaluationResults.length > 0 ? {
          faithfulness: evaluationResults.reduce((sum, r) => sum + (r.ragas_scores?.faithfulness || 0), 0) / evaluationResults.length,
          answer_relevancy: evaluationResults.reduce((sum, r) => sum + (r.ragas_scores?.answer_relevancy || 0), 0) / evaluationResults.length
        } : null,
        avg_excel_scores: excelEvaluationStatus.results.length > 0 ? {
          faithfulness: excelEvaluationStatus.results.reduce((sum, r) => sum + (r.ragas_scores?.faithfulness || 0), 0) / excelEvaluationStatus.results.length,
          answer_relevancy: excelEvaluationStatus.results.reduce((sum, r) => sum + (r.ragas_scores?.answer_relevancy || 0), 0) / excelEvaluationStatus.results.length
        } : null
      }
    }

    const dataStr = JSON.stringify(allResults, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `rag_evaluation_results_${new Date().toISOString().split('T')[0]}.json`
    link.click()
    URL.revokeObjectURL(url)
    message.success(`结果已导出，共${allResults.total_count}条记录`)
  }

  // 从数据库加载测试数据
  const fetchTestCases = async () => {
    try {
      setLoading(true)
      const response = await api.get('/api/v1/acrac/test-cases')

      if (response.data && response.data.length > 0) {
        // 转换数据格式以匹配ExcelTestCase接口
        const testCases: ExcelTestCase[] = response.data.map((item: any, index: number) => ({
          question_id: item.question_id || index + 1,
          clinical_query: item.clinical_query || item.query || '',
          ground_truth: item.ground_truth || item.answer || '',
          row_index: index + 1
        }))

        setExcelTestCases(testCases)
        message.success(`成功从数据库加载 ${testCases.length} 条测试数据`)
      } else {
        message.warning('数据库中暂无测试数据')
      }
    } catch (error: any) {
      message.error('从数据库加载数据失败：' + (error.message || '未知错误'))
    } finally {
      setLoading(false)
    }
  }

  const loadHistoryData = async () => {
    try {
      setLoading(true)
      const response = await api.get('/api/v1/ragas/history', {
        params: {
          page: 1,
          page_size: 50
        }
      })

      if (response.data && response.data.tasks) {
        // 转换历史数据格式
        const historyResults: EvaluationResult[] = response.data.tasks.map((task: any) => ({
          question_id: task.task_id,
          query: task.task_name || '历史评测任务',
          ground_truth: '',
          answer: '',
          response_time: 0,
          trace: {},
          timestamp: task.created_at,
          model: task.model_name || 'unknown',
          source: 'history',
          ragas_scores: task.summary || {},
          ragas_evaluated: task.status === 'completed'
        }))

        setHistoryData(historyResults)
        message.success(`成功加载 ${historyResults.length} 条历史记录`)
      } else {
        setHistoryData([])
        message.info('暂无历史评测记录')
      }
    } catch (error: any) {
      console.error('加载历史数据失败:', error)
      message.error('加载历史数据失败：' + (error.response?.data?.detail || error.message))
      // 设置模拟历史数据作为备选方案
      const mockHistory: EvaluationResult[] = [
        {
          question_id: 1,
          query: '历史查询1',
          ground_truth: '历史答案1',
          trace: { ragas_scores: { faithfulness: 0.85, answer_relevancy: 0.78 } },
          ragas_scores: { faithfulness: 0.85, answer_relevancy: 0.78 },
          timestamp: '2024-01-15T10:30:00Z',
          status: 'completed'
        },
        {
          question_id: 2,
          query: '历史查询2',
          ground_truth: '历史答案2',
          trace: { ragas_scores: { faithfulness: 0.92, answer_relevancy: 0.88 } },
          ragas_scores: { faithfulness: 0.92, answer_relevancy: 0.88 },
          timestamp: '2024-01-14T15:20:00Z',
          status: 'completed'
        }
      ]
      setHistoryData(mockHistory)

      setHistoryVisible(true)
    }
  }

  // Excel文件处理函数
  const handleExcelUpload: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options

    try {
      const formData = new FormData()
      formData.append('file', file as File)

      const response = await api.post('/api/v1/acrac/excel-evaluation/upload-excel', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })

      if (response.data.success) {
        const testCases = response.data.test_cases

        // 验证数据
        const validation = validateExcelData(testCases)
        const isValid = showValidationResult(validation)

        if (isValid) {
          setExcelTestCases(testCases)
          setExcelFile({
            uid: '1',
            name: response.data.filename,
            status: 'done',
            response: response.data
          })
          message.success(`成功解析Excel文件，共${response.data.total_cases}个测试案例`)

          onSuccess?.(response.data)
        } else {
          // 数据验证失败，不设置测试案例
          onError?.(new Error('数据验证失败'))
        }
      } else {
        throw new Error(response.data.message || '文件上传失败')
      }
    } catch (error: any) {
      message.error('文件上传失败：' + (error.response?.data?.detail || error.message))
      onError?.(error)
    }
  }

  // RAGAS评估函数
  const runRAGASEvaluation = async (testCases: ExcelTestCase[], isAsync: boolean = true, params?: { model_name?: string; embedding_model?: string; data_count?: number }) => {
    let sanitizedCases: { question_id: string; clinical_query: string; ground_truth: string }[] = []
    try {
      message.info('开始RAGAS评估...')
      setRagasStatus(null)
      setRagasSyncInProgress(!isAsync)

      // 统一清洗/强制转为字符串，避免 Pydantic 提示“Input should be a valid string”
      sanitizedCases = (testCases || []).map((tc: any) => ({
        question_id: String(tc?.question_id ?? ''),
        clinical_query: typeof tc?.clinical_query === 'string' ? tc.clinical_query : String(tc?.clinical_query ?? ''),
        ground_truth: typeof tc?.ground_truth === 'string' ? tc.ground_truth : String(tc?.ground_truth ?? ''),
      })).filter((tc) => tc.clinical_query.trim().length > 0 && tc.ground_truth.trim().length > 0)

      if (sanitizedCases.length === 0) {
        message.error('RAGAS评估失败：无有效用例（临床场景/标准答案为空）')
        throw new Error('no valid cases')
      }
      if (sanitizedCases.length !== testCases.length) {
        message.warning(`已过滤 ${testCases.length - sanitizedCases.length} 条无效用例（非字符串或为空）`)
      }

      if (!isAsync) {
        setRagasStatus({
          status: 'processing',
          progress: 0,
          completed_cases: 0,
          failed_cases: 0,
          total: sanitizedCases.length,
        })
        setRagasSyncProgress(5)
      }

      const response = await api.post('/api/v1/ragas/evaluate', {
        test_cases: sanitizedCases,
        model_name: params?.model_name || 'gpt-3.5-turbo',
        embedding_model: params?.embedding_model,
        data_count: params?.data_count,
        async_mode: isAsync
      })

  

      if (isAsync && response.data.task_id) {
        // 异步模式：开始轮询任务状态
        setRagasTaskId(response.data.task_id)
        message.success('RAGAS评估任务已启动，正在后台处理...')
        startRagasStatusPolling(response.data.task_id)
        return response.data
      } else if (response.data.status === 'success') {
        // 同步模式：直接处理结果
        message.success('RAGAS评估完成')
        console.log('RAGAS评估结果:', response.data)
        setRagasResults(response.data.results || [])
        if (!isAsync) {
          const completedCount = Array.isArray(response.data.results) ? response.data.results.length : sanitizedCases.length
          setRagasStatus({
            status: 'completed',
            progress: 100,
            completed_cases: completedCount,
            failed_cases: 0,
            total: sanitizedCases.length,
          })
          setRagasSyncProgress(100)
        }
        if (response.data.output_filename) {
          setOutputFilename(response.data.output_filename)
          message.success(`结果文件已保存: ${response.data.output_filename}`)
        }

        // 更新Excel评测结果，合并RAGAS评分
        setExcelEvaluationStatus(prevStatus => ({
          ...prevStatus,
          results: prevStatus.results.map(result => {
            const ragasResult = response.data.results.find((r: any) => r.question_id === result.question_id)
            if (ragasResult) {
              return {
                ...result,
                ragas_scores: ragasResult.ragas_scores,
                ragas_evaluated: true
              }
            }
            return result
          })
        }))

        return response.data
      } else {
        throw new Error(response.data.error || 'RAGAS评估失败')
      }
    } catch (error: any) {
      console.error('RAGAS评估失败:', error)
      const detail = error?.response?.data?.detail ?? error?.response?.data ?? error?.message ?? error
      let msg: string
      if (typeof detail === 'string') {
        msg = detail
      } else if (Array.isArray(detail)) {
        msg = detail.map((d) => (typeof d === 'string' ? d : (d?.msg || d?.error || JSON.stringify(d)))).join('; ')
      } else if (detail && typeof detail === 'object') {
        msg = detail?.error || detail?.message || JSON.stringify(detail)
      } else {
        msg = String(detail)
      }
      message.error('RAGAS评估失败：' + msg)
      if (!isAsync) {
        setRagasStatus({
          status: 'failed',
          progress: 100,
          completed_cases: 0,
          failed_cases: sanitizedCases.length,
          total: sanitizedCases.length,
        })
        setRagasSyncProgress(100)
      }
      throw new Error(msg)
    } finally {
      setRagasSyncInProgress(false)
    }
  }

  // RAGAS任务状态轮询
  const startRagasStatusPolling = (taskId: string) => {
    const interval = setInterval(async () => {
      try {
        const response = await api.get(`/api/v1/ragas/evaluate/${taskId}/status`)
        const status = response.data

        // 同步到前端进度状态
        setRagasStatus(prev => ({
          progress: typeof status.progress === 'number' ? Math.round(status.progress) : prev?.progress,
          completed_cases: status.completed_cases,
          failed_cases: status.failed_cases,
          status: status.status,
          total: prev?.total ?? (typeof status.completed_cases === 'number' && typeof status.failed_cases === 'number'
            ? status.completed_cases + status.failed_cases
            : undefined),
        }))

        if (status.status === 'completed') {
          clearInterval(interval)
          setRagasPolling(null)

          // 获取评测结果
          const resultsResponse = await api.get(`/api/v1/ragas/evaluate/${taskId}/results`)
          setRagasResults(resultsResponse.data.results || [])

          message.success('RAGAS评估完成！')

          // 更新Excel评测结果，合并RAGAS评分
          setExcelEvaluationStatus(prevStatus => ({
            ...prevStatus,
            results: prevStatus.results.map(result => {
              const ragasResult = resultsResponse.data.results.find((r: any) => r.question_id === result.question_id)
              if (ragasResult) {
                return {
                  ...result,
                  ragas_scores: ragasResult.ragas_scores,
                  ragas_evaluated: true
                }
              }
              return result
            })
          }))
        } else if (status.status === 'failed') {
          clearInterval(interval)
          setRagasPolling(null)
          message.error('RAGAS评估失败：' + (status.error || '未知错误'))
        } else {
          // 任务仍在进行中，显示进度
          console.log('RAGAS评估进度:', status)
        }
      } catch (error: any) {
        console.error('获取RAGAS任务状态失败：', error)
      }
    }, 3000)

    setRagasPolling(interval)
  }

  // 停止RAGAS评估
  const stopRagasEvaluation = async () => {
    if (ragasTaskId) {
      try {
        await api.post(`/api/v1/ragas/evaluate/${ragasTaskId}/stop`)

        if (ragasPolling) {
          clearInterval(ragasPolling)
          setRagasPolling(null)
        }

        setRagasTaskId(null)
        message.info('RAGAS评估已停止')
      } catch (error: any) {
        message.error('停止RAGAS评估失败：' + (error.response?.data?.detail || error.message))
      }
    }
  }

  const startExcelEvaluation = async () => {
    if (excelTestCases.length === 0) {
      message.error('请先上传Excel文件')
      return
    }

    try {
      // 后端 fastapi 接口定义为 test_cases: List[Dict[str, Any]] (body) + filename: str (query)
      // 因此请求体必须是“数组”，filename 作为查询参数传递
      const response = await api.post(
        '/api/v1/acrac/excel-evaluation/start-evaluation',
        excelTestCases,
        { params: { filename: excelFile?.name || '' } }
      )

      if (response.data?.success) {
        message.success('开始Excel评测')
        // 开始轮询状态
        startExcelStatusPolling()
      }
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      const msg = typeof detail === 'object' ? JSON.stringify(detail) : (detail || error.message || String(error));
      message.error('启动评测失败：' + msg)
    }
  }

  const startExcelStatusPolling = () => {
    const interval = setInterval(async () => {
      try {
        const response = await api.get('/api/v1/acrac/excel-evaluation/evaluation-status')
        const status = response.data

        setExcelEvaluationStatus(status)

        if (!status.is_running) {
          clearInterval(interval)
          setExcelStatusPolling(null)

          if (status.error) {
            message.error('评测出错：' + status.error)
          } else if (status.progress === status.total) {
            message.success(`Excel评测完成！共处理${status.total}个案例`)
          }
        }
      } catch (error: any) {
        console.error('获取评测状态失败：', error)
      }
    }, 2000)

    setExcelStatusPolling(interval)
  }

  const stopExcelEvaluation = async () => {
    try {
      await api.post('/api/v1/acrac/excel-evaluation/stop-evaluation')

      if (excelStatusPolling) {
        clearInterval(excelStatusPolling)
        setExcelStatusPolling(null)
      }

      message.info('Excel评测已停止')
    } catch (error: any) {
      message.error('停止评测失败：' + (error.response?.data?.detail || error.message))
    }
  }

  const exportExcelResults = async () => {
    try {
      const response = await api.post('/api/v1/acrac/excel-evaluation/export-results')

      if (response.data.success) {
        message.success('Excel评测结果导出成功')
      }
    } catch (error: any) {
      message.error('导出失败：' + (error.response?.data?.detail || error.message))
    }
  }

  const previewExcelData = () => {
    setExcelPreviewVisible(true)
  }

  // 数据验证函数
  const validateExcelData = (testCases: ExcelTestCase[]) => {
    const errors: string[] = []
    const warnings: string[] = []

    if (testCases.length === 0) {
      errors.push('Excel文件中没有有效数据')
      return { isValid: false, errors, warnings }
    }

    testCases.forEach((testCase, index) => {
      const rowNum = index + 1

      // 检查必需字段
      if (!testCase.question_id) {
        errors.push(`第${rowNum}行：缺少题号`)
      }

      if (!testCase.clinical_query || testCase.clinical_query.trim().length === 0) {
        errors.push(`第${rowNum}行：临床场景不能为空`)
      } else if (testCase.clinical_query.length < 10) {
        warnings.push(`第${rowNum}行：临床场景过短，可能影响评测效果`)
      }

      if (!testCase.ground_truth || testCase.ground_truth.trim().length === 0) {
        errors.push(`第${rowNum}行：标准答案不能为空`)
      }

      // 检查数据质量
      if (testCase.clinical_query && testCase.clinical_query.length > 1000) {
        warnings.push(`第${rowNum}行：临床场景过长，建议控制在1000字符以内`)
      }

      if (testCase.ground_truth && testCase.ground_truth.length > 500) {
        warnings.push(`第${rowNum}行：标准答案过长，建议控制在500字符以内`)
      }
    })

    return {
      isValid: errors.length === 0,
      errors,
      warnings,
      totalCount: testCases.length,
      validCount: testCases.filter(tc => tc.question_id && tc.clinical_query && tc.ground_truth).length
    }
  }

  // 显示数据验证结果
  const showValidationResult = (validation: any) => {
    const { isValid, errors, warnings, totalCount, validCount } = validation

    if (isValid) {
      message.success(`数据验证通过！共${totalCount}条有效数据`)
      if (warnings.length > 0) {
        Modal.warning({
          title: '数据质量提醒',
          content: (
            <div>
              <p>发现以下质量问题，建议优化：</p>
              <ul>
                {warnings.map((warning: string, index: number) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            </div>
          ),
        })
      }
    } else {
      Modal.warning({
        title: '数据验证结果',
        content: (
          <div>
            <div style={{ marginBottom: 16, padding: 12, backgroundColor: '#fff2e8', border: '1px solid #ffbb96', borderRadius: 6 }}>
              <Text strong>数据质量检查：</Text>
              <Text style={{ marginLeft: 8 }}>有效数据 {validCount}/{totalCount} 条</Text>
            </div>
            {errors.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <Text strong style={{ color: '#ff4d4f' }}>发现的问题：</Text>
                <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                  {errors.map((error: string, index: number) => (
                    <li key={index} style={{ color: '#ff4d4f', marginBottom: 4 }}>{error}</li>
                  ))}
                </ul>
              </div>
            )}
            {warnings && warnings.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <Text strong style={{ color: '#faad14' }}>质量提醒：</Text>
                <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                  {warnings.map((warning: string, index: number) => (
                    <li key={index} style={{ color: '#faad14', marginBottom: 4 }}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}
            <div style={{ padding: 12, backgroundColor: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 6 }}>
              <Text strong style={{ color: '#52c41a' }}>建议：</Text>
              <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                <li style={{ color: '#52c41a', marginBottom: 4 }}>检查Excel文件格式，确保包含必需的列</li>
                <li style={{ color: '#52c41a', marginBottom: 4 }}>验证数据完整性，填写所有必需字段</li>
                <li style={{ color: '#52c41a', marginBottom: 4 }}>优化文本长度，提高评测效果</li>
              </ul>
            </div>
          </div>
        ),
        width: 600,
      })
    }

    return isValid
  }

  // 清理轮询
  useEffect(() => {
    return () => {
      if (excelStatusPolling) {
        clearInterval(excelStatusPolling)
      }
    }
  }, [excelStatusPolling])

  const resultColumns = [
    {
      title: '题号',
      dataIndex: 'question_id',
      width: 80,
      fixed: 'left' as const
    },
    {
      title: '查询内容',
      dataIndex: 'query',
      width: 200,
      ellipsis: true
    },
    {
      title: '标准答案',
      dataIndex: 'ground_truth',
      width: 150,
      ellipsis: true
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (status: string) => {
        const statusConfig = {
          pending: { color: 'default', text: '待处理' },
          running: { color: 'processing', text: '运行中' },
          completed: { color: 'success', text: '已完成' },
          error: { color: 'error', text: '错误' }
        }
        const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.pending
        return <Tag color={config.color}>{config.text}</Tag>
      }
    },
    {
      title: 'RAGAS评分',
      dataIndex: 'ragas_scores',
      width: 200,
      render: (scores: any) => {
        if (!scores) return <Text type="secondary">未评分</Text>
        return (
          <Space direction="vertical" size="small">
            {Object.entries(scores).map(([key, value]) => (
              <Text key={key} style={{ fontSize: '12px' }}>
                {key}: <Text strong>{typeof value === 'number' ? value.toFixed(3) : String(value)}</Text>
              </Text>
            ))}
          </Space>
        )
      }
    },
    {
      title: '时间',
      dataIndex: 'timestamp',
      width: 150,
      render: (timestamp: string) => new Date(timestamp).toLocaleString()
    }
  ]

  const excelPreviewColumns = [
    {
      title: '题号',
      dataIndex: 'question_id',
      width: 80
    },
    {
      title: '临床场景',
      dataIndex: 'clinical_query',
      width: 300,
      ellipsis: true
    },
    {
      title: '标准答案',
      dataIndex: 'ground_truth',
      width: 200,
      ellipsis: true
    }
  ]

  const normalizeRecommendations = (candidate: any): any[] => {
    if (!candidate) return []
    if (Array.isArray(candidate)) return candidate
    if (Array.isArray(candidate?.recommendations)) return candidate.recommendations
    return []
  }

  const extractRecommendationList = (record: any): any[] => {
    const candidates = [
      record?.trace?.llm_parsed?.recommendations,
      record?.llm_recommendations,
      record?.metadata?.rag_result?.llm_recommendations,
      record?.metadata?.rag_result?.trace?.llm_parsed?.recommendations,
      record?.metadata?.trace?.llm_parsed?.recommendations,
      record?.metadata?.rag_result?.llm_parsed?.recommendations,
    ]
    for (const item of candidates) {
      const normalized = normalizeRecommendations(item)
      if (normalized.length) {
        return normalized
      }
    }
    return []
  }

  const resolveAnswerText = (record: any): string => {
    const sources = [
      record?.rag_answer,
      record?.answer,
      record?.metadata?.rag_answer,
      record?.metadata?.rag_result?.rag_answer,
    ]
    for (const src of sources) {
      if (typeof src === 'string' && src.trim().length > 0) {
        return src
      }
    }
    return ''
  }

  const resolveScenarioText = (scenario: any): string => {
    if (!scenario) return ''
    const full = scenario.clinical_scenario || scenario.description_zh || scenario.scenario_description || scenario.description
    if (full && typeof full === 'string' && full.trim()) {
      return full.trim()
    }
    const panelTopic = [scenario.panel, scenario.topic].filter(Boolean).join('/')
    return panelTopic || '未知临床场景'
  }

  const ragasResultColumns = [
    { title: '题号', dataIndex: 'question_id', key: 'question_id', width: 80 },
    { title: '临床场景', dataIndex: 'clinical_query', key: 'clinical_query', width: 300, ellipsis: true },
    { title: '标准答案', dataIndex: 'ground_truth', key: 'ground_truth', width: 200, ellipsis: true },
    {
      title: '推荐检查(用于评分)', key: 'rag_answer', width: 300, ellipsis: true,
      render: (record: any) => {
        // 优先从 trace.llm_parsed.recommendations 读取TOP3，回退到 rag_answer 文本
        const recs = extractRecommendationList(record)
        if (recs.length) {
          return (
            <div style={{ fontSize: 12 }}>
              {recs.slice(0, 3).map((rec: any, idx: number) => {
                const title = rec?.procedure_name || rec?.name || rec?.recommendation || rec?.procedure || rec?.procedure_name_zh || '未知检查'
                const modality = rec?.modality ? ` (${rec.modality})` : ''
                const rating = rec?.appropriateness_rating ? ` · 适宜性: ${rec.appropriateness_rating}` : ''
                return <div key={idx}>- {title}{modality}{rating}</div>
              })}
            </div>
          )
        }
        const txt = resolveAnswerText(record)
        return txt ? <span style={{ whiteSpace: 'pre-wrap' }}>{txt}</span> : <span style={{ color: '#999' }}>无</span>
      }
    },
    {
      title: 'RAGAS评分', dataIndex: 'ragas_scores', key: 'ragas_scores', width: 300,
      render: (scores: any) => scores ? (
        <div style={{ fontSize: '12px' }}>
          <div>忠实度: <b>{(scores.faithfulness || 0).toFixed(3)}</b></div>
          <div>答案相关性: <b>{(scores.answer_relevancy || 0).toFixed(3)}</b></div>
          <div>上下文精确度: <b>{(scores.context_precision || 0).toFixed(3)}</b></div>
          <div>上下文召回率: <b>{(scores.context_recall || 0).toFixed(3)}</b></div>
        </div>
      ) : <span style={{ color: '#999' }}>无</span>
    },
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 160, render: (t: number) => new Date(t * 1000).toLocaleString() }
  ]

  const excelResultColumns = [
    {
      title: '题号',
      dataIndex: 'question_id',
      key: 'question_id',
      width: 80,
    },
    {
      title: '临床场景',
      dataIndex: 'clinical_query',
      key: 'clinical_query',
      width: 300,
      ellipsis: true,
    },
    {
      title: '标准答案',
      dataIndex: 'ground_truth',
      key: 'ground_truth',
      width: 200,
      ellipsis: true,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const statusMap = {
          success: { color: 'green', text: '成功' },
          error: { color: 'red', text: '失败' },
          running: { color: 'blue', text: '运行中' }
        }
        const config = statusMap[status as keyof typeof statusMap] || { color: 'default', text: status }
        return <Tag color={config.color}>{config.text}</Tag>
      }
    },
    {
      title: '模式',
      dataIndex: 'mode',
      key: 'mode',
      width: 100,
      render: (mode: string) => (
        <Tag color={mode === 'RAG' ? 'blue' : 'orange'}>
          {mode}
        </Tag>
      ),
    },
    {
      title: 'LLM推荐',
      dataIndex: 'llm_recommendations',
      key: 'llm_recommendations',
      width: 200,
      ellipsis: true,
      render: (recommendations: any[]) => {
        if (!recommendations || recommendations.length === 0) {
          return <span style={{ color: '#999' }}>无推荐</span>;
        }
        return (
          <div>
            {recommendations.slice(0, 3).map((rec, index) => {
              const title = rec?.procedure_name || rec?.name || rec?.recommendation || rec?.procedure || rec?.procedure_name_zh || '未知推荐'
              const modality = rec?.modality ? ` (${rec.modality})` : ''
              const rating = rec?.appropriateness_rating ? ` · 适宜性: ${rec.appropriateness_rating}` : ''
              return (
                <div key={index} style={{ fontSize: '12px' }}>
                  {title}{modality}{rating}
                </div>
              )
            })}
          </div>
        );
      },
    },
    {
      title: 'RAGAS评分',
      key: 'ragas_scores',
      width: 300,
      render: (record: any) => {
        const scores = record.ragas_scores;
        const isEvaluated = record.ragas_evaluated;

        if (!scores || !isEvaluated) {
          return (
            <span style={{ color: '#999' }}>
              {record.status === 'success' ? '待RAGAS评估' : '评测失败'}
            </span>
          );
        }

        return (
          <div style={{ fontSize: '12px' }}>
            <div>忠实度: <span style={{ fontWeight: 'bold', color: scores.faithfulness > 0.7 ? '#52c41a' : scores.faithfulness > 0.5 ? '#faad14' : '#ff4d4f' }}>{(scores.faithfulness || 0).toFixed(3)}</span></div>
            <div>答案相关性: <span style={{ fontWeight: 'bold', color: scores.answer_relevancy > 0.7 ? '#52c41a' : scores.answer_relevancy > 0.5 ? '#faad14' : '#ff4d4f' }}>{(scores.answer_relevancy || 0).toFixed(3)}</span></div>
            <div>上下文精确度: <span style={{ fontWeight: 'bold', color: scores.context_precision > 0.7 ? '#52c41a' : scores.context_precision > 0.5 ? '#faad14' : '#ff4d4f' }}>{(scores.context_precision || 0).toFixed(3)}</span></div>
            <div>上下文召回率: <span style={{ fontWeight: 'bold', color: scores.context_recall > 0.7 ? '#52c41a' : scores.context_recall > 0.5 ? '#faad14' : '#ff4d4f' }}>{(scores.context_recall || 0).toFixed(3)}</span></div>
          </div>
        );
      },
    },
    {
      title: '召回/重排',
      key: 'recall_rerank',
      width: 120,
      render: (record: any) => (
        <div style={{ fontSize: '12px' }}>
          <div>召回: {record.recall_count || 0}</div>
          <div>重排: {record.rerank_count || 0}</div>
          <div>Prompt: {record.prompt_length || 0}字符</div>
        </div>
      ),
    },
    {
      title: '处理时间',
      dataIndex: 'processing_time',
      key: 'processing_time',
      width: 120,
      render: (time: number) => `${(time || 0).toFixed(2)}s`,
    },
  ]

  return (
    <div>
      <div className='page-title'>RAG+LLM 评测系统</div>

      <Card title="RAG+LLM 评测系统" style={{ marginBottom: 16 }}>
        {/* 步骤1: 数据上传 */}
        <Card title="步骤1: 数据上传" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Upload
                  customRequest={handleExcelUpload}
                  openFileDialogOnClick={true}
                  accept=".xlsx,.xls"
                  maxCount={1}
                  showUploadList={false}
                  fileList={excelFile ? [excelFile] : []}
                  onChange={({ fileList }) => {
                    if (fileList.length === 0) {
                      setExcelFile(null)
                      setExcelTestCases([])
                    }
                  }}
                >
                  <Button htmlType="button" icon={<FileExcelOutlined />} size="large">上传Excel文件到数据库</Button>
                </Upload>
                <div style={{ marginTop: 8, color: '#666' }}>
                  支持.xlsx和.xls格式，需包含：题号、临床场景、首选检查项目（标准化）列
                </div>


              </Space>
            </Col>
            <Col span={12}>
              <Space>
                <Button
                  onClick={previewExcelData}
                  disabled={excelTestCases.length === 0}
                  icon={<EyeOutlined />}
                >
                  预览数据
                </Button>
              </Space>
            </Col>
          </Row>

          {/* 数据质量指示器 */}
          {excelFile && excelTestCases.length > 0 && (
            <div style={{ marginTop: 16, padding: 12, backgroundColor: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 6 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 8 }}>
                <Badge
                  status="success"
                  text={`数据已加载: ${excelTestCases.length} 条`}
                />
                <Badge
                  status={excelTestCases.filter(tc => tc.question_id && tc.clinical_query && tc.ground_truth).length === excelTestCases.length ? "success" : "warning"}
                  text={`有效数据: ${excelTestCases.filter(tc => tc.question_id && tc.clinical_query && tc.ground_truth).length} 条`}
                />
              </div>
              <Row gutter={8}>
                <Col span={8}>
                  <Statistic
                    title="平均场景长度"
                    value={Math.round(excelTestCases.reduce((sum, tc) => sum + (tc.clinical_query?.length || 0), 0) / excelTestCases.length)}
                    suffix="字符"
                    valueStyle={{ fontSize: '14px' }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="平均答案长度"
                    value={Math.round(excelTestCases.reduce((sum, tc) => sum + (tc.ground_truth?.length || 0), 0) / excelTestCases.length)}
                    suffix="字符"
                    valueStyle={{ fontSize: '14px' }}
                  />
                </Col>
                <Col span={8}>
                  <Statistic
                    title="数据完整率"
                    value={Math.round((excelTestCases.filter(tc => tc.question_id && tc.clinical_query && tc.ground_truth).length / excelTestCases.length) * 100)}
                    suffix="%"
                    valueStyle={{ fontSize: '14px', color: excelTestCases.filter(tc => tc.question_id && tc.clinical_query && tc.ground_truth).length === excelTestCases.length ? '#52c41a' : '#faad14' }}
                  />
                </Col>
              </Row>
            </div>
          )}

          {excelFile && (
            <div style={{ marginTop: 16 }}>
              <Text strong>已上传文件: </Text>
              <Text>{excelFile.name}</Text>
              <Text type="secondary" style={{ marginLeft: 16 }}>共{excelTestCases.length}个测试案例</Text>
            </div>
          )}
        </Card>

        {/* 操作区：仅保留必要按钮 */}
        {excelTestCases.length > 0 && (
          <Card title="步骤2: 开始评测" style={{ marginBottom: 16 }}>
            <Space>
              <Button
                type='primary'
                onClick={() => startExcelEvaluation()}
                loading={excelEvaluationStatus.is_running}
                disabled={excelTestCases.length === 0 || excelEvaluationStatus.is_running}
                icon={<PlayCircleOutlined />}
                size="large"
              >
                开始评测
              </Button>
              <Button
                onClick={stopExcelEvaluation}
                disabled={!excelEvaluationStatus.is_running}
                icon={<PauseCircleOutlined />}
              >
                停止评测
              </Button>
            </Space>
          </Card>
        )}

          {/* 步骤2B: RAGAS 评分参数与启动 */}
        {excelTestCases.length > 0 && (
            <Card title="步骤2B: RAGAS 评分参数与启动" style={{ marginBottom: 16 }}>
              <Row gutter={16} align="middle">
                <Col span={8}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text strong>LLM 模型</Text>
                    <Select
                      showSearch
                      allowClear
                      placeholder="如 gpt-3.5-turbo / deepseek-chat / qwen2.5-32b-instruct"
                      options={llmModels}
                      value={selectedLLM}
                      onChange={(v) => setSelectedLLM(v)}
                      onSearch={(v) => setSelectedLLM(v)}
                      filterOption={(input, option) => (option?.label as string).toLowerCase().includes(input.toLowerCase())}
                    />
                  </Space>
                </Col>
                <Col span={8}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text strong>Embedding 模型（可选）</Text>
                    <Select
                      showSearch
                      allowClear
                      placeholder="如 BAAI/bge-large-zh-v1.5 / BAAI/bge-m3"
                      options={[
                        { value: 'BAAI/bge-large-zh-v1.5', label: 'BAAI/bge-large-zh-v1.5' },
                        { value: 'BAAI/bge-m3', label: 'BAAI/bge-m3' },
                      ]}
                      value={selectedEmbedding}
                      onChange={(v) => setSelectedEmbedding(v)}
                      onSearch={(v) => setSelectedEmbedding(v)}
                      filterOption={(input, option) => (option?.label as string).toLowerCase().includes(input.toLowerCase())}
                    />
                  </Space>
                </Col>
                <Col span={8}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text strong>评测数量（任意整数，-1 表示全部）</Text>
                    <InputNumber
                      style={{ width: '100%' }}
                      placeholder="如 5 / 10 / 20 / -1"
                      value={dataCount}
                      onChange={(v) => setDataCount(typeof v === 'number' ? v : undefined)}
                    />
                  </Space>
                </Col>
              </Row>
              <Row gutter={16} style={{ marginTop: 16 }}>
                <Col span={8}>
                  <Space>
                    <Text strong>异步模式</Text>
                    <Switch checked={ragasAsync} onChange={setRagasAsync} />
                    <Text type="secondary">同步模式可直接返回评分并给出导出文件名</Text>
                  </Space>
                </Col>
                <Col span={16}>
                  <Space>
                    <Button
                      type="primary"
                      icon={<PlayCircleOutlined />}
                      onClick={async () => {
                        try {
                          const resp = await runRAGASEvaluation(excelTestCases, ragasAsync, {
                            model_name: selectedLLM,
                            embedding_model: selectedEmbedding,
                            data_count: dataCount,
                          })
                          if (!ragasAsync && resp?.output_filename) {
                            setOutputFilename(resp.output_filename)
                          }
                        } catch (e) {}
                      }}
                      disabled={excelTestCases.length === 0}
                    >
                      开始 RAGAS 评分
                    </Button>
                    {outputFilename && (
                      <Badge status="success" text={`已保存文件: ${outputFilename}`} />
                    )}
                  </Space>
                </Col>
              </Row>
            </Card>
          )}
        {/* RAGAS 评分进度（异步真实进度 + 同步占位进度） */}
        {(ragasSyncInProgress || (ragasStatus && ['processing', 'failed'].includes(ragasStatus.status || ''))) && (
          <Card title="RAGAS 评分进度" style={{ marginBottom: 16 }}>
            {ragasSyncInProgress && (
              <div style={{ marginBottom: 8 }}>
                <Text type="secondary">同步模式：正在计算评分，请稍候…</Text>
              </div>
            )}
            <Progress
              percent={typeof ragasStatus?.progress === 'number' ? ragasStatus.progress : ragasSyncProgress}
              status="active"
            />
            <div style={{ marginTop: 8 }}>
              <Text>
                已完成: {ragasStatus?.completed_cases ?? '-'}
                {typeof ragasStatus?.total === 'number' ? ` / ${ragasStatus.total}` : ''}，失败: {ragasStatus?.failed_cases ?? '-'}
              </Text>
              {ragasStatus?.status === 'failed' && (
                <div style={{ marginTop: 4 }}>
                  <Text type="danger">同步RAGAS评分失败，请查看控制台或后端日志。</Text>
                </div>
              )}
            </div>
          </Card>
        )}


        {/* 步骤3: 评测进度显示 */}
        {excelEvaluationStatus.is_running && (
          <Card title="步骤3: 评测进度" style={{ marginBottom: 16 }}>
            <Text strong>Excel评测进度:</Text>
            <Progress
              percent={excelEvaluationStatus.total > 0 ? Math.round((excelEvaluationStatus.progress / excelEvaluationStatus.total) * 100) : 0}
              status="active"
              format={() => `${excelEvaluationStatus.progress}/${excelEvaluationStatus.total}`}
            />
            <div style={{ marginTop: 8 }}>
              <Text>当前进度: {excelEvaluationStatus.progress}/{excelEvaluationStatus.total}</Text>
              {excelEvaluationStatus.current_case && (
                <div style={{ marginTop: 4 }}>
                  <Text type="secondary">当前处理: {excelEvaluationStatus.current_case}</Text>
                </div>
              )}
            </div>


            {/* 中间实时结果展示（最近10条） */}
            {Array.isArray(excelEvaluationStatus.results) && excelEvaluationStatus.results.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <Text strong>实时结果（最近10条）:</Text>
                <Table
                  size="small"
                  rowKey={(r) => String((r as any).question_id ?? Math.random())}
                  dataSource={excelEvaluationStatus.results.slice(-10)}
                  columns={excelResultColumns}
                  pagination={false}
                  scroll={{ x: 1000 }}
                />
              </div>
            )}
          </Card>
        )}

        {/* 步骤5: 评测结果 */}
        {excelEvaluationStatus.results.length > 0 && (
          <Card
            title="步骤4: 评测结果"
            extra={
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                onClick={exportExcelResults}
              >
                保存结果(导出)
              </Button>
            }
          >

            {/* Excel评测结果 */}
            {excelEvaluationStatus.results.length > 0 && (
              <div style={{ marginBottom: 24 }}>
                <Title level={4}>Excel评测结果</Title>
                <Table
                  rowKey="question_id"
                  size="small"
                  dataSource={excelEvaluationStatus.results}
                  columns={excelResultColumns}
                  pagination={{
                    pageSize: 10,
                    showSizeChanger: true,
                    showQuickJumper: true,
                    showTotal: (total) => `共 ${total} 条记录`
                  }}
                  scroll={{ x: 1000 }}
                  expandable={{
                    expandedRowRender: (record) => (
                      <div>
                        <Title level={5}>详细信息</Title>
                        <Row gutter={16}>
                          <Col span={12}>
                            <Text strong>临床场景:</Text>
                            <div style={{ marginBottom: 8, padding: 8, background: '#f5f5f5', borderRadius: 4 }}>
                              {record.clinical_query}
                            </div>
                            <Text strong>标准答案:</Text>
                            <div style={{ marginBottom: 8, padding: 8, background: '#f5f5f5', borderRadius: 4 }}>
                              {record.ground_truth}
                            </div>
                          </Col>
                          <Col span={12}>
                            <Text strong>RAGAS详细评分:</Text>
                            <pre style={{ background: '#f5f5f5', padding: 8, borderRadius: 4, fontSize: '12px' }}>
                              {JSON.stringify(record.ragas_scores || {}, null, 2)}
                            </pre>
                            {record.error && (
                              <div>
                                <Text strong type="danger">错误信息:</Text>
                                <div style={{ color: 'red', marginTop: 4 }}>{record.error}</div>
                              </div>
                            )}
                          </Col>
                        </Row>
                      </div>
                    ),
                    rowExpandable: () => true
                  }}
                />
              </div>
            )}

          </Card>
        )}

        {/* RAGAS 同步结果展示（不依赖 Excel 运行结果） */}
        {(ragasResults.length > 0 || getCombinedRagasItems().length > 0) && (
          <Card
            title="RAGAS 评分结果（可视化）"
            style={{ marginBottom: 16 }}
            extra={
              <Space>
                {outputFilename ? <Text>结果文件: {outputFilename}</Text> : null}
                <Button size="small" icon={<DownloadOutlined />} onClick={() => downloadRagasResults('json')}>下载JSON</Button>
                <Button size="small" icon={<FileExcelOutlined />} onClick={() => downloadRagasResults('excel')}>下载Excel</Button>
              </Space>
            }
          >
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}>
                <Card size="small" title="忠实度（分布）" bordered>
                  <div style={{ marginBottom: 8 }}>
                    <Text type="secondary">平均值: {metricAvg(metricValues('faithfulness')).toFixed(3)}</Text>
                  </div>
                  {renderTinyBars(metricValues('faithfulness'))}
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small" title="答案相关性（分布）" bordered>
                  <div style={{ marginBottom: 8 }}>
                    <Text type="secondary">平均值: {metricAvg(metricValues('answer_relevancy')).toFixed(3)}</Text>
                  </div>
                  {renderTinyBars(metricValues('answer_relevancy'))}
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small" title="上下文精确度（分布）" bordered>
                  <div style={{ marginBottom: 8 }}>
                    <Text type="secondary">平均值: {metricAvg(metricValues('context_precision')).toFixed(3)}</Text>
                  </div>
                  {renderTinyBars(metricValues('context_precision'))}
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small" title="上下文召回率（分布）" bordered>
                  <div style={{ marginBottom: 8 }}>
                    <Text type="secondary">平均值: {metricAvg(metricValues('context_recall')).toFixed(3)}</Text>
                  </div>
                  {renderTinyBars(metricValues('context_recall'))}
                </Card>
              </Col>
            </Row>

            <Table
              rowKey={(r:any) => String(r.question_id)}
              size="small"
              dataSource={ragasResults && ragasResults.length > 0 ? ragasResults : getCombinedRagasItems()}
              columns={ragasResultColumns}
              pagination={{ pageSize: 10 }}
              scroll={{ x: 1000 }}
              expandable={{
                expandedRowRender: (record: any) => {
                  const trace = (record?.trace || record?.metadata?.rag_result?.trace) || null
                  return (
                    <div>
                      <Title level={5}>检索/排序追踪</Title>
                      {trace ? (
                        <div>
                          <Text strong>Recall:</Text>
                          <div style={{ fontSize: 12, marginBottom: 8 }}>
                            {Array.isArray(trace.recall_scenarios) && trace.recall_scenarios.length > 0 ? (
                              trace.recall_scenarios.slice(0, 8).map((s: any, idx: number) => (
                                <div key={idx}>
                                  #{idx+1} {s.id} · {resolveScenarioText(s)} · sim={typeof s.similarity === 'number' ? s.similarity.toFixed(3) : s.similarity}
                                </div>
                              ))
                            ) : (
                              <span style={{ color: '#999' }}>无</span>
                            )}
                          </div>
                          <Text strong>Rerank:</Text>
                          <div style={{ fontSize: 12 }}>
                            {Array.isArray(trace.rerank_scenarios) && trace.rerank_scenarios.length > 0 ? (
                              trace.rerank_scenarios.slice(0, 8).map((s: any, idx: number) => (
                                <div key={idx}>
                                  #{idx+1} {s.id} · {resolveScenarioText(s)} · score={typeof s._rerank_score === 'number' ? s._rerank_score.toFixed(3) : s._rerank_score}
                                </div>
                              ))
                            ) : (
                              <span style={{ color: '#999' }}>无</span>
                            )}
                          </div>
                        </div>
                      ) : (
                        <span style={{ color: '#999' }}>无 trace（结果中未包含追踪数据）</span>
                      )}
                    </div>
                  )
                },
                rowExpandable: () => true
              }}
            />
          </Card>
        )}

      </Card>


      {/* 数据预览模态框 */}
      <Modal
        title="Excel数据预览"
        open={excelPreviewVisible}
        onCancel={() => setExcelPreviewVisible(false)}
        footer={[
          <Button key="validate" type="primary" onClick={() => {
            const validation = validateExcelData(excelTestCases);
            showValidationResult(validation);
          }}>
            重新验证数据
          </Button>,
          <Button key="close" onClick={() => setExcelPreviewVisible(false)}>
            关闭
          </Button>,
        ]}
        width={1200}
      >
        <div style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={6}>
              <Statistic title="总数据量" value={excelTestCases.length} />
            </Col>
            <Col span={6}>
              <Statistic
                title="有效数据"
                value={excelTestCases.filter(tc => tc.question_id && tc.clinical_query && tc.ground_truth).length}
                valueStyle={{ color: '#3f8600' }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="平均场景长度"
                value={Math.round(excelTestCases.reduce((sum, tc) => sum + (tc.clinical_query?.length || 0), 0) / excelTestCases.length)}
                suffix="字符"
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="预览数据"
                value={Math.min(10, excelTestCases.length)}
                suffix={`/ ${excelTestCases.length}`}
              />
            </Col>
          </Row>
        </div>
        <Table
          rowKey="question_id"
          size="small"
          dataSource={excelTestCases}
          columns={excelPreviewColumns}
          pagination={{ pageSize: 20, showSizeChanger: true }}
          scroll={{ x: 600, y: 400 }}
        />
      </Modal>

      {/* 历史记录模态框 */}
      <Modal
        title="历史评测记录"
        open={historyVisible}
        onCancel={() => setHistoryVisible(false)}
        footer={null}
        width={1200}
      >
        <Table
          rowKey="question_id"
          size="small"
          dataSource={historyData}
          columns={resultColumns}
          pagination={{
            pageSize: 5,
            showSizeChanger: true
          }}
          scroll={{ x: 1000 }}
        />
      </Modal>
    </div>
  )
}

export default RAGEvaluation
