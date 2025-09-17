import React, { useMemo, useState } from 'react'
import { Button, Card, Col, Collapse, Form, Input, InputNumber, Row, Switch, Table, Tag, Tooltip, Typography } from 'antd'
import { api } from '../api/http'

const { Text, Paragraph } = Typography

const RAGAssistant: React.FC = () => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  const onFinish = async (values: any) => {
    setLoading(true)
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
      const r = await api.post('/api/v1/acrac/rag-llm/intelligent-recommendation', payload)
      setResult(r.data)
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
        <Button type='primary' htmlType='submit' loading={loading}>运行推荐</Button>
      </Form>

      {result && (
        <div style={{ marginTop: 16 }}>
          {/* 改为上下布局，提升“推荐理由”显示宽度 */}
          <Card title='最终推荐'>
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
              </Card>
            </Col>
          </Row>
        </div>
      )}
    </div>
  )
}

export default RAGAssistant
