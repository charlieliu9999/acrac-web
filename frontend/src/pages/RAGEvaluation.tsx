import React, { useState, useEffect } from 'react'
import { Button, Card, Col, Form, InputNumber, Row, Select, Table, Progress, Tag, Typography, message, Space, Divider, Modal, Upload, Tabs, Badge, Statistic } from 'antd'
import { DownloadOutlined, PlayCircleOutlined, PauseCircleOutlined, ReloadOutlined, UploadOutlined, FileExcelOutlined, EyeOutlined, DatabaseOutlined, HistoryOutlined } from '@ant-design/icons'
import { api } from '../api/http'
// 简易格式化秒为 分:秒
const formatSeconds = (s?: number) => {
  if (s === undefined || s === null || isNaN(s as any)) return '-'
  const m = Math.floor((s as number) / 60)
  const ss = Math.round((s as number) % 60)
  return `${m}分${ss}秒`
}

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
  runtime?: { elapsed_seconds?: number; eta_seconds?: number; throughput_cpm?: number }
}

const RAGEvaluation: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [evaluationResults, setEvaluationResults] = useState<EvaluationResult[]>([])
  const [currentProgress, setCurrentProgress] = useState(0)
  const [totalItems, setTotalItems] = useState(0)
  const [isRunning, setIsRunning] = useState(false)
  const [historyVisible, setHistoryVisible] = useState(false)
  const [historyData, setHistoryData] = useState<any[]>([])
  const [historyStats, setHistoryStats] = useState<any | null>(null)
  const [historyDetailVisible, setHistoryDetailVisible] = useState(false)
  const [historyDetailTask, setHistoryDetailTask] = useState<any | null>(null)
  const [historyDetailResults, setHistoryDetailResults] = useState<any[]>([])


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

  // 选择评测数据量
  const [selectedDataCount, setSelectedDataCount] = useState<number>(-1)
  // 处理模式：异步(默认)/同步
  const [ragasAsyncMode, setRagasAsyncMode] = useState<boolean>(true)

  // RAGAS评测状态
  const [ragasTaskId, setRagasTaskId] = useState<string | null>(null)
  const [ragasPolling, setRagasPolling] = useState<number | null>(null)
  const [ragasResults, setRagasResults] = useState<any[]>([])
  const [ragasCompleted, setRagasCompleted] = useState<boolean>(false)

  const [ragasSummary, setRagasSummary] = useState<any | null>(null)

  // 中间过程查看器
  const [traceViewerVisible, setTraceViewerVisible] = useState(false)
  const [traceViewerData, setTraceViewerData] = useState<any>(null)
  const openTraceViewer = (record: any) => {
    const t = (record as any)?.trace ?? (record as any)?.trace_preview ?? null
    setTraceViewerData(t || {})
    setTraceViewerVisible(true)
  }

  // 模拟LLM模型选项
  const llmModels = [
    { value: 'gpt-4', label: 'GPT-4' },
    { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
    { value: 'claude-3', label: 'Claude-3' },
    { value: 'qwen-max', label: 'Qwen Max' },
  ]

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
           const response = await api.post('/api/v1/acrac/rag/query', {
             query: testCase.clinical_query,
             model: values.llm_model,
             question_id: testCase.question_id
           })

           const endTime = Date.now()
           const responseTime = (endTime - startTime) / 1000

           const result: EvaluationResult = {
             question_id: testCase.question_id,
             query: testCase.clinical_query,
             ground_truth: testCase.ground_truth,
             answer: response.data.answer || '',
             response_time: responseTime,
             trace: response.data.trace || {},
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

      const items = response.data?.items || response.data?.tasks || []
      if (items && items.length > 0) {
        // 历史任务列表数据
        const tasks = items.map((t: any) => ({
          task_id: t.task_id,
          task_name: t.task_name,
          model_name: t.model_name || 'unknown',
          total_cases: t.total_cases,
          status: t.status,
          start_time: t.start_time || t.created_at,
          end_time: t.end_time,
          processing_time: t.processing_time,
          created_at: t.created_at,
        }))

        setHistoryData(tasks)
        try {
          const statResp = await api.get('/api/v1/ragas/history/statistics')
          const s = statResp.data || {}
          setHistoryStats({
            total_tasks: s.total_tasks ?? 0,
            status_distribution: s.status_distribution || {},
            model_usage: s.model_usage || {},
            recent_tasks: s.recent_tasks_7days ?? s.recent_tasks ?? 0,
            avg_processing_time_min: s.average_processing_time_minutes ?? s.avg_processing_time_min ?? 0,
          })
        } catch (e) {
          setHistoryStats(null)
        }
        setHistoryVisible(true)
        message.success(`成功加载 ${items.length} 条历史记录`)
      } else {
        setHistoryData([])
        setHistoryVisible(true)
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
  const runRAGASEvaluation = async (testCases: ExcelTestCase[], isAsync: boolean = true) => {
    try {
      message.info('开始RAGAS评估...')

      // 映射为后端期望的字段类型与结构：question_id 统一为字符串，忽略多余字段
      const mappedCases = testCases.map(tc => ({
        question_id: String((tc as any).question_id ?? (tc as any).row_index ?? ''),
        clinical_query: (tc as any).clinical_query,
        ground_truth: (tc as any).ground_truth,
      }))

      const response = await api.post('/api/v1/ragas/evaluate', {
        test_cases: mappedCases,
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
        setRagasCompleted(true)

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
      message.error('RAGAS评估失败：' + (error.response?.data?.detail || error.message))
      throw error
    }
  }

  // RAGAS任务状态轮询
  const startRagasStatusPolling = (taskId: string) => {
    const interval = setInterval(async () => {
      try {
        const response = await api.get(`/api/v1/ragas/evaluate/${taskId}/status`)
        const status = response.data

        // 实时更新进度与最近结果
        setExcelEvaluationStatus(prev => {
          const processed = status.processed_cases ?? ((status.completed_cases || 0) + (status.failed_cases || 0))
          const total = status.total_cases ?? prev.total

          // 合并最近结果，按 question_id 去重
          const incoming: any[] = Array.isArray(status.recent_results) ? status.recent_results : []
          const map = new Map<string, any>((prev.results || []).map((r: any) => [String(r.question_id), r]))
          for (const r of incoming) {
            const key = String(r.question_id)
            const prevVal = map.get(key) || {}
            const mergedVal: any = { ...prevVal, ...r, ragas_evaluated: true }
            // 将后端的 trace 或 trace_preview 合并到前端记录，便于进行中展示中间过程
            if (!mergedVal.trace) {
              mergedVal.trace = (r as any).trace ?? (r as any).trace_preview ?? (prevVal as any).trace
            }
            map.set(key, mergedVal)
          }
          const merged = Array.from(map.values())

          return {
            ...prev,
            progress: processed,
            total,
            current_case: incoming.length > 0 ? String(incoming[0].question_id) : prev.current_case,
            results: merged,
            runtime: {
              elapsed_seconds: status.elapsed_seconds,
              eta_seconds: status.eta_seconds,
              throughput_cpm: status.throughput_cpm,
            },
          }
        })

        if (status.status === 'completed') {
          clearInterval(interval)
          setRagasPolling(null)

          // 获取最终评测结果
          const resultsResponse = await api.get(`/api/v1/ragas/evaluate/${taskId}/results`)
          const finalResults: any[] = resultsResponse.data.results || []
          setRagasResults(finalResults)
          setRagasCompleted(true)

          // 保存汇总信息（若后端提供）
          try { setRagasSummary(resultsResponse.data?.summary ?? null) } catch (e) {}


          message.success('RAGAS评估完成！')

          // 合并最终结果：以最终结果为准，覆盖/补全中间结果；并标记完成状态
          setExcelEvaluationStatus(prevStatus => {
            const map = new Map<string, any>((prevStatus.results || []).map((r: any) => [String(r.question_id), r]))
            for (const r of finalResults) {
              const key = String(r.question_id)
              map.set(key, { ...(map.get(key) || {}), ...r, ragas_evaluated: true, status: 'success' })
            }
            return {
              ...prevStatus,
              is_running: false,
              progress: prevStatus.total,
              results: Array.from(map.values()),
            }
          })
        } else if (status.status === 'failed') {
          clearInterval(interval)
          setRagasPolling(null)
          message.error('RAGAS评估失败：' + (status.error_message || status.error || '未知错误'))
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
        await api.delete(`/api/v1/ragas/evaluate/${ragasTaskId}`)

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

    // 应用“数据量选择”
    const useCount = selectedDataCount && selectedDataCount > 0 ? Math.min(selectedDataCount, excelTestCases.length) : excelTestCases.length
    const casesToEval = excelTestCases.slice(0, useCount)

    try {
      // 走统一的 RAGAS 评测流程（与 RAG助手 保持一致）
      setExcelEvaluationStatus(prev => ({ ...prev, is_running: true, progress: 0, total: casesToEval.length, error: null }))
      setRagasCompleted(false)
      setRagasResults([])
      try { setRagasSummary(null) } catch (e) {}
      await runRAGASEvaluation(casesToEval, ragasAsyncMode)
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      const msg = typeof detail === 'object' ? JSON.stringify(detail) : (detail || error.message || String(error));
      message.error('启动评测失败：' + msg)
      setExcelEvaluationStatus(prev => ({ ...prev, is_running: false }))
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
      title: '过程',
      key: 'trace',
      width: 120,
      render: (_: any, record: any) => (
        <Button size="small" onClick={() => openTraceViewer(record)}>查看</Button>
      )
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

  const exportHistoryRecord = async (task: any) => {
    try {
      const resp = await api.get(`/api/v1/ragas/history/${task.task_id}`)
      const data = resp.data || {}
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `ragas_task_${task.task_id}.json`
      a.click()
      URL.revokeObjectURL(url)
      message.success('导出成功')
    } catch (e: any) {
      message.error('导出失败：' + (e.response?.data?.detail || e.message))
    }
  }

  const deleteHistoryRecord = async (task: any) => {
    Modal.confirm({
      title: '确认删除该历史评测记录？',
      content: `任务ID: ${task.task_id}`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.delete(`/api/v1/ragas/history/${task.task_id}`)
          message.success('删除成功')
          loadHistoryData()
        } catch (e: any) {
          message.error('删除失败：' + (e.response?.data?.detail || e.message))
        }
      }
    })
  }

  // 历史任务列表列定义
  const historyColumns = [
    { title: '任务ID', dataIndex: 'task_id', width: 180, ellipsis: true },
    { title: '任务名称', dataIndex: 'task_name', width: 220, ellipsis: true },
    { title: '模型(推理LLM)', dataIndex: 'model_name', width: 180, ellipsis: true },
    { title: '用例数', dataIndex: 'total_cases', width: 90 },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (s: string) => {
        const m: any = { completed: { color: 'success', text: '已完成' }, processing: { color: 'processing', text: '进行中' }, pending: { color: 'default', text: '待处理' }, failed: { color: 'error', text: '失败' }, cancelled: { color: 'warning', text: '取消' } }
        const c = m[s] || { color: 'default', text: s }
        return <Tag color={c.color}>{c.text}</Tag>
      }
    },
    { title: '开始时间', dataIndex: 'start_time', width: 170, render: (t: string) => t ? new Date(t).toLocaleString() : '-' },
    {
      title: '操作', key: 'action', fixed: 'right' as const, width: 110,
      render: (_: any, record: any) => (
        <Space size="small">
          <Button size="small" onClick={() => openHistoryDetail(record)}>查看详情</Button>
          <Button size="small" onClick={() => exportHistoryRecord(record)}>导出</Button>
          <Button size="small" danger onClick={() => deleteHistoryRecord(record)}>删除</Button>
        </Space>
      )
    }
  ]

  const openHistoryDetail = async (task: any) => {
    try {
      setLoading(true)
      const resp = await api.get(`/api/v1/ragas/history/${task.task_id}`)
      setHistoryDetailTask(resp.data?.task || task)
      setHistoryDetailResults(resp.data?.results || [])
      setHistoryDetailVisible(true)
    } catch (e: any) {
      message.error('加载任务详情失败：' + (e.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

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
      title: '模型',
      dataIndex: 'model',
      key: 'model',
      width: 140,
      render: (m: string) => m || '-',
    },
    {
      title: '耗时(推理/评测)',
      key: 'durations',
      width: 160,
      render: (record: any) => {
        const inf = record.inference_ms != null ? `${record.inference_ms}ms` : '-'
        const eva = record.evaluation_ms != null ? `${record.evaluation_ms}ms` : '-'
        return `${inf} / ${eva}`
      }
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
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <Space>
          <Button icon={<HistoryOutlined />} onClick={loadHistoryData}>
            历史记录
          </Button>
        </Space>
      </div>


      <Card title="RAG+LLM 评测系统" style={{ marginBottom: 16 }}>
        {/* 步骤1: 数据上传 */}
        <Card title="步骤1: 数据上传" style={{ marginBottom: 16 }}>
          <Row gutter={16}>
            <Col span={12}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Upload
                  customRequest={handleExcelUpload}
                  accept=".xlsx,.xls"
                  maxCount={1}
                  fileList={excelFile ? [excelFile] : []}
                  onChange={({ fileList }) => {
                    if (fileList.length === 0) {
                      setExcelFile(null)
                      setExcelTestCases([])
                    }
                  }}
                >
                  <Button icon={<FileExcelOutlined />} size="large">上传Excel文件到数据库</Button>
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
            <Space wrap size={12} style={{ marginBottom: 8 }}>
              <span>评测数据量：</span>
              <Select style={{ width: 180 }} value={selectedDataCount} onChange={(v) => setSelectedDataCount(Number(v))}>
                {dataCountOptions.map(opt => (
                  <Option key={opt.value} value={opt.value}>{opt.label}</Option>
                ))}
              </Select>
              <span>处理模式：</span>
              <Select style={{ width: 180 }} value={ragasAsyncMode ? 'async' : 'sync'} onChange={(v) => setRagasAsyncMode(v === 'async')}>
                <Option value="async">异步（推荐）</Option>
                <Option value="sync">同步</Option>
              </Select>
            </Space>
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
              <Button
                onClick={exportExcelResults}
                disabled={excelEvaluationStatus.results.length === 0}
                icon={<DownloadOutlined />}
              >
                导出结果
              </Button>
              <Button
                icon={<HistoryOutlined />}
                onClick={loadHistoryData}
              >
                历史记录
              </Button>
            </Space>
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
              <div style={{ marginTop: 4 }}>
                <Space size={16}>
                  <Text type="secondary">用时: {formatSeconds(excelEvaluationStatus.runtime?.elapsed_seconds)}</Text>
                  <Text type="secondary">预计剩余: {formatSeconds(excelEvaluationStatus.runtime?.eta_seconds)}</Text>
                  <Text type="secondary">吞吐: {excelEvaluationStatus.runtime?.throughput_cpm ?? '-'} 条/分</Text>
                </Space>
              </div>
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
        {((Array.isArray(excelEvaluationStatus.results) && excelEvaluationStatus.results.length > 0) || (Array.isArray(ragasResults) && ragasResults.length > 0) || ragasCompleted) ? (
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
            {/* 汇总卡片（平均分等） */}
            {(
              ragasSummary || (Array.isArray(excelEvaluationStatus.results) && excelEvaluationStatus.results.some((r:any)=>r?.ragas_scores))
            ) && (
              <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col span={6}>
                  <Card size="small" title="忠实度(均值)">
                    <b>{
                      (ragasSummary?.faithfulness_avg != null)
                        ? Number(ragasSummary.faithfulness_avg).toFixed(3)
                        : (()=>{ const arr=(excelEvaluationStatus.results||[]).map((r:any)=>Number(r?.ragas_scores?.faithfulness)).filter((v:number)=>Number.isFinite(v)); return arr.length? (arr.reduce((a:number,b:number)=>a+b,0)/arr.length).toFixed(3):'-' })()
                    }</b>
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small" title="答案相关性(均值)">
                    <b>{
                      (ragasSummary?.answer_relevancy_avg != null)
                        ? Number(ragasSummary.answer_relevancy_avg).toFixed(3)
                        : (()=>{ const arr=(excelEvaluationStatus.results||[]).map((r:any)=>Number(r?.ragas_scores?.answer_relevancy)).filter((v:number)=>Number.isFinite(v)); return arr.length? (arr.reduce((a:number,b:number)=>a+b,0)/arr.length).toFixed(3):'-' })()
                    }</b>
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small" title="上下文精确度(均值)">
                    <b>{
                      (ragasSummary?.context_precision_avg != null)
                        ? Number(ragasSummary.context_precision_avg).toFixed(3)
                        : (()=>{ const arr=(excelEvaluationStatus.results||[]).map((r:any)=>Number(r?.ragas_scores?.context_precision)).filter((v:number)=>Number.isFinite(v)); return arr.length? (arr.reduce((a:number,b:number)=>a+b,0)/arr.length).toFixed(3):'-' })()
                    }</b>
                  </Card>
                </Col>
                <Col span={6}>
                  <Card size="small" title="上下文召回率(均值)">
                    <b>{
                      (ragasSummary?.context_recall_avg != null)
                        ? Number(ragasSummary.context_recall_avg).toFixed(3)
                        : (()=>{ const arr=(excelEvaluationStatus.results||[]).map((r:any)=>Number(r?.ragas_scores?.context_recall)).filter((v:number)=>Number.isFinite(v)); return arr.length? (arr.reduce((a:number,b:number)=>a+b,0)/arr.length).toFixed(3):'-' })()
                    }</b>
                  </Card>
                </Col>
              </Row>
            )}


            {/* Excel评测结果 */}
            {(((excelEvaluationStatus.results && excelEvaluationStatus.results.length > 0) || (ragasResults && ragasResults.length > 0)) ? (
              <div style={{ marginBottom: 24 }}>
                <Title level={4}>Excel评测结果</Title>
                <Table
                  rowKey="question_id"
                  size="small"
                  dataSource={(excelEvaluationStatus.results && excelEvaluationStatus.results.length > 0) ? excelEvaluationStatus.results : ragasResults}
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
            ) : (
              <div style={{ marginBottom: 24 }}>
                <Title level={4}>Excel评测结果</Title>
                <div style={{ color: '#999' }}>暂无可展示的明细。您可以点击页面右上角“历史记录”查看任务记录与统计。</div>
              </div>
            ))}

          </Card>
        ) : null}
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
        {historyStats && (
          <div style={{ marginBottom: 16 }}>
            <Row gutter={16} style={{ marginBottom: 8 }}>
              <Col span={6}><Statistic title="总任务数" value={historyStats.total_tasks ?? 0} /></Col>
              <Col span={6}><Statistic title="最近7天任务" value={historyStats.recent_tasks ?? 0} /></Col>
              <Col span={6}><Statistic title="平均处理时长(分)" value={historyStats.avg_processing_time_min ?? 0} precision={2} /></Col>
            </Row>
            <Row gutter={16}>
              <Col span={12}>
                <Card size="small" title="状态分布" bordered>
                  <div style={{ fontSize: 12 }}>
                    {['completed','processing','pending','failed','cancelled'].map(k => (

                      <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span>{k}</span>
                        <b>{historyStats.status_distribution?.[k] ?? 0}</b>
                      </div>
                    ))}
                  </div>
                </Card>
              </Col>
              <Col span={12}>
                <Card size="small" title="模型使用Top" bordered>
                  <div>
                    {Object.entries(historyStats.model_usage || {}).slice(0,6).map(([name, cnt]: any, idx: number) => {
                      const total = Object.values(historyStats.model_usage || {}).reduce((a: any,b: any)=> (a as number)+(b as number), 0) || 1
                      const percent = Math.round((Number(cnt) / total) * 100)
                      return (


                        <div key={name} style={{ marginBottom: 6 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                            <span style={{ fontSize: 12 }}>{idx+1}. {name}</span>
                            <span style={{ fontSize: 12 }}>{cnt}（{percent}%）</span>
                          </div>
                          <div style={{ background: '#f0f0f0', height: 8, borderRadius: 4 }}>
                            <div style={{ width: `${percent}%`, height: 8, background: '#1677ff', borderRadius: 4 }} />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </Card>
              </Col>
            </Row>
          </div>
        )}

        <Table
          rowKey={(r:any) => r.task_id || r.question_id}
          size="small"
          dataSource={historyData}
          columns={historyColumns}
          pagination={{
            pageSize: 10,
            showSizeChanger: true
          }}
          scroll={{ x: 1100 }}
        />
      </Modal>
      {/* 历史任务详情模态框 */}
      <Modal
        title={`任务详情 - ${historyDetailTask?.task_name || historyDetailTask?.task_id || ''}`}
        open={historyDetailVisible}
        onCancel={() => setHistoryDetailVisible(false)}
        footer={null}
        width={1200}
      >
        <div style={{ marginBottom: 16 }}>
          <Space size={16} wrap>
            <Statistic title="用例数" value={historyDetailTask?.total_cases ?? '-'} />
            <Statistic title="耗时(秒)" value={historyDetailTask?.processing_time ?? '-'} precision={2} />
            <Statistic title="推理LLM" value={historyDetailTask?.model_name || '-'} />
            <Statistic title="评测LLM" value={(historyDetailResults.find((r: any) => r?.evaluation_metadata?.ragas_llm_model)?.evaluation_metadata?.ragas_llm_model) || '-'} />
          </Space>
        </div>
        <Table
          rowKey={(r:any) => r.question_id || r.id}
          size="small"
          dataSource={historyDetailResults}
          columns={[
            { title: '题号', dataIndex: 'question_id', width: 80 },
            { title: '临床场景', dataIndex: 'clinical_query', width: 320, ellipsis: true },
            { title: '状态', dataIndex: 'status', width: 100, render: (s: string) => <Tag>{s}</Tag> },
            { title: 'RAGAS评分', dataIndex: 'ragas_scores', width: 260, render: (scores: any) => scores ? (
              <Space direction="vertical" size="small">
                {Object.entries(scores).map(([k,v]) => (<Text key={k} style={{ fontSize: 12 }}>{k}: <Text strong>{typeof v === 'number' ? (v as number).toFixed(3) : String(v)}</Text></Text>))}
              </Space>
            ) : <Text type="secondary">-</Text> }
          ]}
          pagination={{ pageSize: 10, showSizeChanger: true }}
          scroll={{ x: 1000, y: 480 }}
        />
      </Modal>

      {/* 中间过程详情模态框 */}
      <Modal
        title="中间过程详情"
        open={traceViewerVisible}
        onCancel={() => setTraceViewerVisible(false)}
        footer={null}
        width={900}
      >
        <div style={{ maxHeight: 480, overflow: 'auto' }}>
          <div style={{ marginBottom: 12 }}>
            <Text strong>召回场景(前3)</Text>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify((traceViewerData as any)?.recall_scenarios ?? (traceViewerData as any)?.recall ?? [], null, 2)}</pre>
          </div>
          <div style={{ marginBottom: 12 }}>
            <Text strong>重排场景(前3)</Text>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify((traceViewerData as any)?.rerank_scenarios ?? (traceViewerData as any)?.rerank ?? [], null, 2)}</pre>
          </div>
          <div style={{ marginBottom: 12 }}>
            <Text strong>最终Prompt</Text>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{(traceViewerData as any)?.final_prompt_preview ?? (traceViewerData as any)?.final_prompt ?? '-'}</pre>
          </div>
          <div>
            <Text strong>LLM解析的推荐</Text>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify((traceViewerData as any)?.llm_recommendations ?? (traceViewerData as any)?.llm_parsed ?? {}, null, 2)}</pre>
          </div>
        </div>
      </Modal>


    </div>
  )
}

export default RAGEvaluation