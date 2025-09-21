import React, { useMemo, useState, useRef } from 'react'
import { Button, Card, Col, Collapse, Form, Input, InputNumber, Row, Switch, Table, Tag, Tooltip, Typography, Space, message, Steps } from 'antd'
import { api } from '../api/http'

const { Text, Paragraph } = Typography

const RAGAssistant: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [currentStep, setCurrentStep] = useState<number>(0)
  const [stepsVisible, setStepsVisible] = useState<boolean>(false)

  const [ragasTaskId, setRagasTaskId] = useState<string | null>(null)
  const [ragasStatus, setRagasStatus] = useState<string | null>(null)
  const [ragasData, setRagasData] = useState<any>(null)
  const ragasTimerRef = useRef<number | null>(null)

  const onFinish = async (values: any) => {
    setLoading(true)
    setStepsVisible(true)
    setCurrentStep(0)
    message.loading({ content: '准备请求', key: 'rag-flow', duration: 0 })
    try {
      const payload = {
        clinical_query: values.query,
        top_scenarios: values.top_scenarios,
        top_recommendations_per_scenario: values.top_recs,
        show_reasoning: values.show_reasoning,
        similarity_threshold: values.threshold,
        debug_mode: true,
        include_raw_data: true,
        compute_ragas: values.compute_ragas || false,
        ground_truth: values.ground_truth || undefined
      }
      setCurrentStep(1)
      message.loading({ content: '已发送请求，等待后端…', key: 'rag-flow', duration: 0 })
      const r = await api.post('/api/v1/acrac/rag-llm/intelligent-recommendation', payload)
      // 收到响应：若包含评测，则将进度切到“评价中”，由异步任务完成后再切到“渲染结果”
      if (payload.compute_ragas) setCurrentStep(2)
      message.loading({ content: payload.compute_ragas ? '评价中…' : '已收到响应，渲染中…', key: 'rag-flow', duration: 0 })
      setResult(r.data)
      // 自动上传到服务端持久化
      try { await uploadToServer() } catch {}
      if (payload.compute_ragas) {
        // 异步发起评测并轮询
        startRagasEvaluation(values, r.data)
        message.success({ content: '推荐已完成，已启动评测', key: 'rag-flow' })
      } else {
        setCurrentStep(3)
        message.success({ content: '推荐已完成', key: 'rag-flow' })
      }
      // 轻量刷新：强制表格重绘，确保视图更新
      setTimeout(() => {
        const el = document.querySelector('#final-recs')
        if (el && 'scrollIntoView' in el) (el as any).scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 50)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || '请求失败'
      message.error({ content: `推荐失败：${detail}`, key: 'rag-flow' })
    } finally {
      setLoading(false)
    }
  }

  const recColumns = useMemo(()=>[
    { title:'#', dataIndex:'rank', width:60 },
    { title:'检查项目', dataIndex:'procedure_name' },
    { title:'模态', dataIndex:'modality', width:100, render:(v:string)=> v ? <Tag color='blue'>{v}</Tag> : '-' },
    { title:'评分', dataIndex:'appropriateness_rating', width:100, render:(v:string)=> v ? <Tag color='green'>{v}</Tag> : '-' },
  ],[])

  const recallColumns = useMemo(()=>[
    { title:'ID', dataIndex:'semantic_id', width:120 },
    { title:'相似度', dataIndex:'similarity', width:100, render:(v:number)=> (v||0).toFixed(3) },
    { title:'描述', dataIndex:'description_zh' },
  ],[])

  const rerankColumns = useMemo(()=>[
    { title:'ID', dataIndex:'id', width:120 },
    { title:'相似度', dataIndex:'similarity', width:100, render:(v:number)=> (v||0).toFixed(3) },
    { title:'重排分', dataIndex:'_rerank_score', width:100, render:(v:number)=> (v||0).toFixed(3) },
    { title:'主题', dataIndex:'topic', width:120 },
    { title:'科室', dataIndex:'panel', width:120 },
  ],[])

  const trace = result?.trace || {}

  const exportJSON = () => {
    if (!result) return
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `rag_result_${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }
  const copyTrace = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(result?.trace || {}, null, 2))
      message.success('Trace 已复制到剪贴板')
    } catch (e) {
      message.error('复制失败')
    }
  }
  const saveLocal = () => {
    try {
      const key = `rag-run:${Date.now()}`
      localStorage.setItem(key, JSON.stringify(result || {}))
      message.success(`已保存到本地（键：${key}）`)
    } catch (e) {
      message.error('保存失败')
    }
  }
  const clearRagasTimer = () => {
    if (ragasTimerRef.current) {
      window.clearInterval(ragasTimerRef.current)
      ragasTimerRef.current = null
    }
  }

  const startRagasEvaluation = async (values: any, respData: any) => {
    try {
      const testCase = {
        clinical_query: values.query,
        ground_truth: values.ground_truth || ''
      }
      const modelName = respData?.model_used || respData?.trace?.models?.llm_model || 'unknown'
      const req = {
        test_cases: [testCase],
        model_name: modelName,
        async_mode: true
      }
      const r = await api.post('/api/v1/ragas/evaluate', req)
      const tid = r.data?.task_id
      if (!tid) {
        throw new Error('未返回任务ID')
      }
      setRagasTaskId(tid)
      setRagasStatus('processing')
      // 轮询任务状态
      clearRagasTimer()
      ragasTimerRef.current = window.setInterval(async () => {
        try {
          const st = await api.get(`/api/v1/ragas/evaluate/${tid}/status`)
          const status = st.data?.status || st.data?.status?.toLowerCase?.()
          if (status) setRagasStatus(status)
          if (status === 'completed' || status === 'failed' || status === 'cancelled') {
            clearRagasTimer()
            if (status === 'completed') {
              const detail = await api.get(`/api/v1/ragas/evaluate/${tid}/results`)
              setRagasData(detail.data)
              message.success('评测已完成')
            } else if (status === 'failed') {
              message.error('评测失败')
            } else {
              message.info('评测已取消')
            }
            setCurrentStep(3)
          }
        } catch (e:any) {
          // 轮询错误不终止，短暂提示
          console.warn('poll ragas status error', e?.message)
        }
      }, 1500)
    } catch (e:any) {
      message.error('创建评测任务失败：' + (e?.response?.data?.detail || e.message))
    }
  }

  const cancelRagas = async () => {
    if (!ragasTaskId) return
    try {
      await api.delete(`/api/v1/ragas/evaluate/${ragasTaskId}`)
      clearRagasTimer()
      setRagasStatus('cancelled')
      message.success('已取消评测')
    } catch (e:any) {
      message.error('取消失败：' + (e?.response?.data?.detail || e.message))
    }
  }



  const resetSession = () => {
    // 清理评测轮询
    clearRagasTimer()
    setRagasTaskId(null)
    setRagasStatus(null)
    setRagasData(null)
    // 清理推荐展示
    setResult(null)
    setStepsVisible(false)
    setCurrentStep(0)
    message.info('已开始新的会话，状态已清空')
  }


  const uploadToServer = async () => {
    if (!result) return
    try {
      const payload = {
        query_text: result?.query || form.getFieldValue('query') || '',
        result,
        success: result?.success !== false,
        execution_time_ms: result?.processing_time_ms || result?.trace?.timing?.total_ms || 0,
        inference_method: result?.is_low_similarity_mode ? 'no-rag' : 'rag',
        error_message: result?.message || null,
      }
      await api.post('/api/v1/acrac/rag-llm/runs/log', payload)
      message.success('已上传到服务端')
    } catch (e:any) {
      message.error('上传失败：' + (e?.response?.data?.detail || e.message))
    }
  }

  const getReason = (r:any) => (r?.recommendation_reason || r?.reason_zh || r?.reason || r?.justification || '') as string

  return (
    <div>
      <div className='page-title'>RAG 智能推荐助手</div>
      <Form form={form} layout='vertical' initialValues={{ top_scenarios: 3, top_recs: 3, show_reasoning: true, threshold: 0.6, compute_ragas: false, ground_truth: '' }} onFinish={onFinish}>
        <Form.Item name='query' label='临床查询' rules={[{ required: true, message: '请输入临床查询' }]}>
          <Input.TextArea rows={3} placeholder='例如：32岁男性，10分钟前突发雷击样头痛，无神经系统体征。' />
        </Form.Item>
        <Row gutter={12}>
          <Col span={6}><Form.Item name='top_scenarios' label='场景数量'><InputNumber min={1} max={10} style={{width:'100%'}}/></Form.Item></Col>
          <Col span={6}><Form.Item name='top_recs' label='每场景推荐数'><InputNumber min={1} max={10} style={{width:'100%'}}/></Form.Item></Col>
          <Col span={6}><Form.Item name='threshold' label='相似度阈值'><InputNumber min={0.1} max={0.9} step={0.05} style={{width:'100%'}}/></Form.Item></Col>
          <Col span={6}><Form.Item name='show_reasoning' label='显示理由' valuePropName='checked'><Switch/></Form.Item></Col>
        </Row>
        <Row gutter={12}>
          <Col span={6}>
            <Form.Item name='compute_ragas' label='RAGAS评估' valuePropName='checked'>
              <Switch />
            </Form.Item>
          </Col>
          <Col span={18}>
            <Form.Item
              noStyle
              shouldUpdate={(prevValues, currentValues) => prevValues.compute_ragas !== currentValues.compute_ragas}
            >
              {({ getFieldValue }) => {
                return getFieldValue('compute_ragas') ? (
                  <Form.Item name='ground_truth' label='参考答案/标准术语（可选，用于评测）'>
                    <Input placeholder='例如：CT颅脑(平扫) 或 标准术语' />
                  </Form.Item>
                ) : null;
              }}
            </Form.Item>
          </Col>
        </Row>
        <Space>
          <Button type='primary' htmlType='submit' loading={loading}>运行推荐</Button>
          <Button onClick={resetSession} disabled={loading}>开始新的会话</Button>
        </Space>
      </Form>

      {(loading || stepsVisible) && (
        <Card title='执行状态' size='small' style={{ marginTop: 12 }}>
          <Steps size='small' current={currentStep} items={[
            { title: '准备请求' },
            { title: '推理中' },
            { title: '评价中' },
            { title: '渲染结果' },
          ]} />
          {ragasTaskId && (
            <div style={{ marginTop: 8 }}>
              <Space>
                <Text type='secondary'>  评估任务：</Text>
                <Tag color={ragasStatus==='completed'?'green':ragasStatus==='failed'?'red':ragasStatus==='cancelled'?'orange':'blue'}>
                  {ragasStatus || 'processing'}
                </Tag>
                {ragasStatus==='processing' && (
                  <Button size='small' danger onClick={cancelRagas}>停止评测</Button>
                )}
              </Space>
            </div>
          )}

        </Card>
      )}

      {result && (
        <div style={{ marginTop: 16 }}>
          {/* 改为上下布局，提升“推荐理由”显示宽度 */}
          <Card id='final-recs' title='最终推荐'>
            <Table
              rowKey={(r:any)=>r.rank}
              size='small'
              dataSource={result.llm_recommendations?.recommendations || []}
              columns={recColumns}
              pagination={false}

              expandable={{
                expandedRowRender: (r:any) => (
                  <div style={{ whiteSpace:'pre-wrap' }}>
                    {getReason(r) || <em>无推荐理由</em>}
                  </div>
                ),
                rowExpandable: (r:any) => !!getReason(r),
              }}
            />
          </Card>

          <Card title='流程详情' style={{ marginTop: 12 }}>
            <div>模式：{result.is_low_similarity_mode ? 'no-RAG' : 'RAG'}</div>
            <div style={{ marginTop: 6 }}>
              <Text type='secondary'>模型：</Text>
              <Space size={16} style={{ marginLeft: 6 }}>
                <span>LLM: <Tag color='blue'>{result.model_used || '-'}</Tag></span>
                <span>Embedding: <Tag color='geekblue'>{result.embedding_model_used || '-'}</Tag></span>
                <span>Reranker: <Tag color='purple'>{result.reranker_model_used || '-'}</Tag></span>
              </Space>
            </div>
            <Collapse bordered={false} style={{ marginTop: 8 }} items={[
              {
                key: 'recall', label: '① 召回场景（Top8）', children: (
                  <Table rowKey='semantic_id' size='small' pagination={false} dataSource={(result.scenarios||[]).slice(0,8)} columns={recallColumns} />
                )
              },
              {
                key: 'recall_recs', label: '② 召回的检查项目（按场景）', children: (
                  <div>
                    {(result.scenarios_with_recommendations||[]).slice(0,3).map((sc:any)=> (
                      <div key={sc.scenario_id} style={{ marginBottom: 8 }}>
                        <div style={{ fontWeight:600 }}>{sc.scenario_id} - {sc.scenario_description}</div>
                        <Table
                          rowKey={(r:any)=>`${sc.scenario_id}:${r?.procedure_id || r?.procedure_name_zh || r?.procedure_name || ''}:${r?.appropriateness_rating || ''}`}
                          size='small'
                          pagination={false}
                          dataSource={(sc.recommendations||[]).slice(0,5)}
                          columns={[
                            { title:'类别', dataIndex:'appropriateness_category_zh', width:160 },
                            { title:'分值', dataIndex:'appropriateness_rating', width:80 },
                            { title:'检查项目', dataIndex:'procedure_name_zh', width:240 },
                            { title:'理由', dataIndex:'reasoning_zh', render:(v:string)=> (<span style={{whiteSpace:'pre-wrap'}}>{v}</span>) },
                          ]}
                        />
                      </div>
                    ))}
                  </div>
                )
              },
              {
                key: 'rerank', label: '③ 重排结果', children: (
                  <Table rowKey='id' size='small' pagination={false} dataSource={trace.rerank_scenarios || []} columns={rerankColumns} />
                )
              },
              {
                key: 'prompt', label: '④ 提示词（Prompt）', children: (
                  <pre className='mono' style={{ whiteSpace:'pre-wrap' }}>{trace.final_prompt || '(调试模式下可显示)'}</pre>
                )
              }
            ]} />
          </Card>

          <Card title='执行耗时与保存' style={{ marginTop: 12 }}>
            <div>总耗时：{result.processing_time_ms ?? result.trace?.timing?.total_ms} ms</div>
            <div style={{ marginTop: 6 }}>
              <Text type='secondary'>分步耗时：</Text>
              <pre className='mono' style={{ whiteSpace:'pre-wrap' }}>{JSON.stringify(result.trace?.timing || {}, null, 2)}</pre>
            </div>
            <div style={{ marginTop: 8 }}>
              <Space>
                <Button onClick={exportJSON}>导出结果JSON</Button>
                <Button onClick={copyTrace}>复制 Trace</Button>
                <Button onClick={saveLocal}>保存到本地</Button>
                <Button type='primary' onClick={uploadToServer}>上传到服务端</Button>
              </Space>
            </div>
          </Card>

          <Row gutter={12} style={{ marginTop: 12 }}>
            <Col span={12}>
              <Card title='规则审计'>
                <div style={{ fontWeight: 600 }}>Rerank</div>
                <pre className='mono' style={{ whiteSpace:'pre-wrap' }}>{JSON.stringify(result.debug_info?.rules_audit?.rerank || [], null, 2)}</pre>
                <div style={{ fontWeight: 600, marginTop: 8 }}>Post-LLM</div>
                <pre className='mono' style={{ whiteSpace:'pre-wrap' }}>{JSON.stringify(result.debug_info?.rules_audit?.post || [], null, 2)}</pre>
              </Card>
            </Col>
            <Col span={12}>
              <Card title='LLM 解析与Prompt'>
                <div>Prompt长度（预估）：{result.debug_info?.step_6_prompt_length}</div>
                <div className='mono' style={{ marginTop: 8 }}>
                  <details>
                    <summary>查看解析JSON</summary>
                    <pre style={{ whiteSpace:'pre-wrap' }}>{JSON.stringify(result.llm_recommendations, null, 2)}</pre>
                  </details>
                </div>
              </Card>
            </Col>
          </Row>
          <Row gutter={12} style={{ marginTop: 12 }}>
            <Col span={24}>
              <Card title='RAGAS 评估'>
                {ragasData ? (
                  <pre className='mono' style={{ whiteSpace:'pre-wrap' }}>
                    {JSON.stringify(ragasData, null, 2)}
                  </pre>
                ) : (
                  <>
                    <div>上下文片段数：{trace.ragas_contexts_count ?? 0}</div>
                    {trace.ragas_scores ? (
                      <pre className='mono' style={{ whiteSpace:'pre-wrap' }}>
                        {JSON.stringify(trace.ragas_scores, null, 2)}
                      </pre>
                    ) : (
                      <div style={{ marginTop: 8 }}>
                        {form.getFieldValue('compute_ragas') ? (
                          <span>{trace.ragas_error ? `评测错误：${trace.ragas_error}` : '未返回评分（可能缺少参考答案或服务未启用）'}</span>
                        ) : (
                          <span>未启用RAGAS评测</span>
                        )}
                      </div>
                    )}
                  </>
                )}
              </Card>
            </Col>
          </Row>
        </div>
      )}
    </div>
  )
}

export default RAGAssistant
