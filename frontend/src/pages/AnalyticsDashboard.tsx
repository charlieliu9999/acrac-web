import React, { useEffect, useMemo, useState } from 'react'
import {
  Card,
  Col,
  Row,
  Statistic,
  Space,
  Select,
  InputNumber,
  Button,
  Typography,
  Table,
  Tag,
  Form,
  message,
  Divider,
} from 'antd'
import { api } from '../api/http'

const { Text } = Typography

type KPIResp = {
  panels: number
  topics: number
  scenarios: number
  procedures: number
  recommendations: number
}

type SankeyNode = { id: string; type: 'panel'|'topic'|'scenario'|'procedure'; label?: string; count?: number }
type SankeyLink = { source: string; target: string; value: number }
type SankeyResp = { nodes: SankeyNode[]; links: SankeyLink[]; meta?: any }

type HeatmapResp = {
  x_labels: string[] // scenarios
  y_labels: string[] // procedures
  z: number[][] // y by x
  metric: 'rating_mean' | 'count'
}

type TopicHeatmapResp = {
  topic_id: string
  x_labels: string[]
  y_labels: string[]
  scenarios: { id: string; desc: string }[]
  procedures: { id: string; name: string; modality?: string }[]
  ratings: (number|null)[][] // y by x
  procedure_stats: { procedure_id: string; name: string; modality?: string; high: number; mid: number; low: number; coverage: number; avg_rating: number }[]
  thresholds: { high_min: number; low_max: number }
}

type PanelItem = { semantic_id: string; name_zh?: string }
type TopicItem = { semantic_id: string; name_zh?: string }

const gradient = (v: number, min: number, max: number) => {
  if (!isFinite(v)) return '#f0f0f0'
  const t = (v - min) / (max - min || 1)
  const h = 210 - 210 * t // blue to light
  const s = 70
  const l = 90 - 50 * t
  return `hsl(${h}, ${s}%, ${l}%)`
}

const AnalyticsDashboard: React.FC = () => {
  const [kpi, setKpi] = useState<KPIResp | null>(null)
  const [loadingKpi, setLoadingKpi] = useState(false)
  const [sankey, setSankey] = useState<SankeyResp | null>(null)
  const [loadingSankey, setLoadingSankey] = useState(false)
  const [heatmap, setHeatmap] = useState<HeatmapResp | null>(null)
  const [loadingHeatmap, setLoadingHeatmap] = useState(false)
  const [topicHeatmap, setTopicHeatmap] = useState<TopicHeatmapResp | null>(null)
  const [loadingTopicHeatmap, setLoadingTopicHeatmap] = useState(false)
  // Search compare (MVP)
  const [cmpQuery, setCmpQuery] = useState<string>('')
  const [cmpTopK, setCmpTopK] = useState<number>(10)
  const [cmpThreshold, setCmpThreshold] = useState<number>(0)
  const [cmpLoading, setCmpLoading] = useState<boolean>(false)
  const [cmpResult, setCmpResult] = useState<any | null>(null)

  const [panels, setPanels] = useState<PanelItem[]>([])
  const [topics, setTopics] = useState<TopicItem[]>([])

  // Filters (MVP)
  const [panelId, setPanelId] = useState<string | undefined>()
  const [topicIds, setTopicIds] = useState<string[] | undefined>(undefined)
  const [pregnancy, setPregnancy] = useState<string | undefined>()
  const [urgency, setUrgency] = useState<string | undefined>()
  const [risk, setRisk] = useState<string | undefined>()
  const [population, setPopulation] = useState<string | undefined>()
  const [modality, setModality] = useState<string | undefined>()
  const [ratingRange, setRatingRange] = useState<[number, number] | undefined>([1, 9])
  const [topN, setTopN] = useState<number>(150)

  const queryParams = useMemo(() => {
    const p: any = { topN }
    if (panelId) p.panel_id = panelId
    if (topicIds?.length) p.topic_ids = topicIds.join(',')
    if (pregnancy) p.pregnancy = pregnancy
    if (urgency) p.urgency = urgency
    if (risk) p.risk = risk
    if (population) p.population = population
    if (modality) p.modality = modality
    if (ratingRange) { p.rating_min = ratingRange[0]; p.rating_max = ratingRange[1] }
    return p
  }, [panelId, topicIds, pregnancy, urgency, risk, population, modality, ratingRange, topN])

  const loadKPIs = async () => {
    try {
      setLoadingKpi(true)
      const r = await api.get('/api/v1/acrac/analytics/kpis')
      setKpi(r.data)
    } catch (e: any) {
      message.error('加载KPI失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoadingKpi(false)
    }
  }
  const loadPanels = async () => {
    try {
      const r = await api.get('/api/v1/acrac/data/panels')
      setPanels(Array.isArray(r.data) ? r.data : [])
    } catch (e:any) {
      // ignore
    }
  }
  const loadTopics = async (pid: string) => {
    try {
      const r = await api.get('/api/v1/acrac/data/topics/by-panel', { params: { panel_id: pid }})
      setTopics(Array.isArray(r.data) ? r.data : [])
    } catch (e:any) {
      setTopics([])
    }
  }
  const loadSankey = async () => {
    try {
      setLoadingSankey(true)
      const r = await api.get('/api/v1/acrac/analytics/sankey', { params: queryParams })
      setSankey(r.data)
    } catch (e:any) {
      message.error('加载关系数据失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoadingSankey(false)
    }
  }
  const loadHeatmap = async () => {
    try {
      setLoadingHeatmap(true)
      const r = await api.get('/api/v1/acrac/analytics/heatmap', { params: { ...queryParams, metric: 'rating_mean' } })
      setHeatmap(r.data)
    } catch (e:any) {
      message.error('加载热力图失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoadingHeatmap(false)
    }
  }

  const loadTopicHeatmap = async () => {
    if (!topicIds || topicIds.length !== 1) {
      setTopicHeatmap(null)
      return
    }
    try {
      setLoadingTopicHeatmap(true)
      const r = await api.get('/api/v1/acrac/analytics/topic-heatmap', { params: { topic_id: topicIds[0] } })
      setTopicHeatmap(r.data)
    } catch (e:any) {
      message.error('加载Topic矩阵失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoadingTopicHeatmap(false)
    }
  }

  const refreshAll = () => {
    loadKPIs()
    loadSankey()
    loadHeatmap()
    loadTopicHeatmap()
  }

  const runCompare = async () => {
    if (!cmpQuery || !cmpQuery.trim()) {
      message.warning('请输入查询')
      return
    }
    try {
      setCmpLoading(true)
      const r = await api.post('/api/v1/acrac/analytics/search-compare', {
        query: cmpQuery,
        top_k: cmpTopK,
        sim_threshold: cmpThreshold,
        scope: 'scenario',
      })
      setCmpResult(r.data)
    } catch (e:any) {
      message.error('对比失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setCmpLoading(false)
    }
  }

  useEffect(() => {
    loadKPIs()
    loadPanels()
  }, [])

  useEffect(() => {
    if (panelId) loadTopics(panelId)
    else setTopics([])
  }, [panelId])

  useEffect(() => {
    // auto refresh topic heatmap when topic changes and filters exist
    if (topicIds && topicIds.length === 1) {
      loadTopicHeatmap()
    } else {
      setTopicHeatmap(null)
    }
  }, [topicIds])

  // Derive layer-specific link views for simple tabular preview
  const panelTopicLinks = useMemo(() => (sankey?.links || []).filter(l => l.source.startsWith('panel:') && l.target.startsWith('topic:')), [sankey])
  const topicScenarioLinks = useMemo(() => (sankey?.links || []).filter(l => l.source.startsWith('topic:') && l.target.startsWith('scenario:')), [sankey])
  const scenarioProcedureLinks = useMemo(() => (sankey?.links || []).filter(l => l.source.startsWith('scenario:') && l.target.startsWith('procedure:')), [sankey])

  const nodeLabel = (id: string) => sankey?.nodes.find(n => n.id === id)?.label || id

  // Heatmap min/max for color
  const heatMinMax = useMemo(() => {
    if (!heatmap?.z?.length) return { min: 0, max: 1 }
    let min = Infinity, max = -Infinity
    for (const row of heatmap.z) {
      for (const v of row) {
        if (Number.isFinite(v)) { if (v < min) min = v; if (v > max) max = v }
      }
    }
    if (!Number.isFinite(min)) min = 0
    if (!Number.isFinite(max)) max = 1
    return { min, max }
  }, [heatmap])

  const topicCellColor = (v: number | null, th: { high_min: number; low_max: number }) => {
    if (v === null || v === undefined) return '#fafafa'
    if (v >= th.high_min) {
      const t = Math.min(1, (v - th.high_min) / (9 - th.high_min || 1))
      const h = 120 // green
      const s = 65
      const l = 92 - 45 * t
      return `hsl(${h}, ${s}%, ${l}%)`
    }
    if (v <= th.low_max) {
      const t = Math.min(1, (th.low_max - v) / (th.low_max - 1 || 1))
      const h = 0 // red
      const s = 70
      const l = 92 - 45 * t
      return `hsl(${h}, ${s}%, ${l}%)`
    }
    // mid range: amber
    const t = (v - th.low_max) / (th.high_min - th.low_max || 1)
    const h = 38 // amber/orange
    const s = 85
    const l = 92 - 40 * t
    return `hsl(${h}, ${s}%, ${l}%)`
  }

  return (
    <div>
      <div className='page-title'>数据关系看板（MVP）</div>
      <Row gutter={12}>
        <Col span={4}><Card size='small' loading={loadingKpi}><Statistic title='科室' value={kpi?.panels ?? 0} /></Card></Col>
        <Col span={4}><Card size='small' loading={loadingKpi}><Statistic title='主题' value={kpi?.topics ?? 0} /></Card></Col>
        <Col span={4}><Card size='small' loading={loadingKpi}><Statistic title='临床场景' value={kpi?.scenarios ?? 0} /></Card></Col>
        <Col span={4}><Card size='small' loading={loadingKpi}><Statistic title='检查项目' value={kpi?.procedures ?? 0} /></Card></Col>
        <Col span={8}><Card size='small' loading={loadingKpi}><Statistic title='推荐关系' value={kpi?.recommendations ?? 0} /></Card></Col>
      </Row>

      <Card size='small' title='筛选' style={{ marginTop: 12 }}>
        <Space wrap>
          <Select
            allowClear
            placeholder='科室'
            style={{ width: 220 }}
            value={panelId}
            onChange={setPanelId}
            options={panels.map(p => ({ label: `${p.semantic_id} ${p.name_zh || ''}`, value: p.semantic_id }))}
          />
          <Select
            mode='multiple'
            allowClear
            placeholder='主题（选科室后可选）'
            style={{ width: 280 }}
            value={topicIds}
            onChange={setTopicIds}
            options={topics.map(t => ({ label: `${t.semantic_id} ${t.name_zh || ''}`, value: t.semantic_id }))}
            disabled={!panelId}
          />
          <Select allowClear placeholder='妊娠' style={{ width: 120 }} value={pregnancy} onChange={setPregnancy} options={[{value:'pregnant',label:'怀孕'},{value:'non-pregnant',label:'非孕'}]} />
          <Select allowClear placeholder='急诊' style={{ width: 120 }} value={urgency} onChange={setUrgency} options={[{value:'emergency',label:'急诊'},{value:'elective',label:'择期'}]} />
          <Select allowClear placeholder='风险' style={{ width: 120 }} value={risk} onChange={setRisk} options={[{value:'low',label:'低'},{value:'medium',label:'中'},{value:'high',label:'高'}]} />
          <Select allowClear placeholder='人群' style={{ width: 160 }} value={population} onChange={setPopulation} options={[{value:'adult',label:'成人'},{value:'pediatric',label:'儿童'}]} />
          <Select allowClear placeholder='模态' style={{ width: 140 }} value={modality} onChange={setModality} options={[{value:'CT',label:'CT'},{value:'MR',label:'MRI'},{value:'US',label:'超声'},{value:'XR',label:'X光'},{value:'NM',label:'核医学'}]} />
          <Form.Item label='TopN' style={{ marginBottom: 0 }}>
            <InputNumber min={20} max={500} value={topN} onChange={(v)=>setTopN(v||150)} style={{ width: 100 }} />
          </Form.Item>
          <Button type='primary' onClick={refreshAll}>刷新</Button>
        </Space>
      </Card>

      {topicIds && topicIds.length === 1 && (
        <Card size='small' title={`Topic 全量矩阵（${topicIds[0]}）`} style={{ marginTop: 12 }} extra={<Text type='secondary'>绿色高分(≥7)，红色低分(≤3)</Text>}>
          {topicHeatmap && topicHeatmap.x_labels.length && topicHeatmap.y_labels.length ? (
            <>
              <Row gutter={12} style={{ marginBottom: 12 }}>
                <Col span={6}><Statistic title='检查项目数' value={topicHeatmap.y_labels.length} /></Col>
                <Col span={6}><Statistic title='场景数' value={topicHeatmap.x_labels.length} /></Col>
              </Row>
              <div style={{ overflowX: 'auto', maxHeight: 520, overflowY: 'auto', border: '1px solid #eee', borderRadius: 6 }}>
                <table style={{ borderCollapse: 'collapse', width: '100%' }}>
                  <thead>
                    <tr>
                      <th style={{ position: 'sticky', left: 0, background: '#fff', zIndex: 2, padding: 6, border: '1px solid #eee', minWidth: 220, textAlign:'left' }}>Procedure</th>
                      {topicHeatmap.scenarios.map((s) => (
                        <th key={s.id} title={s.desc} style={{ padding: 6, border: '1px solid #eee', whiteSpace: 'nowrap' }}>{s.id}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {topicHeatmap.procedures.map((p, yi) => (
                      <tr key={p.id}>
                        <td style={{ position: 'sticky', left: 0, background: '#fff', zIndex: 1, padding: 6, border: '1px solid #eee', whiteSpace: 'nowrap' }}>
                          <Space size={8}>
                            <span>{p.id}</span>
                            <span style={{ color:'#555' }}>{p.name}</span>
                            {p.modality && <Tag color='blue'>{p.modality}</Tag>}
                          </Space>
                        </td>
                        {topicHeatmap.x_labels.map((_, xi) => {
                          const v = topicHeatmap.ratings[yi]?.[xi] ?? null
                          const bg = topicCellColor(v, topicHeatmap.thresholds)
                          return (
                            <td key={xi} style={{ padding: 6, border: '1px solid #eee', background: bg, textAlign: 'center' }}>
                              <span style={{ fontSize: 12 }}>{typeof v === 'number' ? v.toFixed(1) : ''}</span>
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Row gutter={12} style={{ marginTop: 12 }}>
                <Col span={12}>
                  <Card size='small' title='最多选择的检查（高分覆盖 Top 10）'>
                    <Table
                      size='small'
                      rowKey='procedure_id'
                      dataSource={[...topicHeatmap.procedure_stats].sort((a,b)=> b.high - a.high).slice(0,10)}
                      pagination={false}
                      columns={[
                        { title: 'Procedure', dataIndex: 'procedure_id', width: 140 },
                        { title: '名称', dataIndex: 'name' },
                        { title: '模态', dataIndex: 'modality', width: 90 },
                        { title: '高分次数', dataIndex: 'high', width: 100 },
                        { title: '覆盖率', dataIndex: 'coverage', width: 100, render: (v:any)=> (v? (v*100).toFixed(1)+'%':'0%') },
                        { title: '均分', dataIndex: 'avg_rating', width: 90, render: (v:any)=> (typeof v==='number'? v.toFixed(2):'-') },
                      ]}
                    />
                  </Card>
                </Col>
                <Col span={12}>
                  <Card size='small' title='不应选择的检查（低分覆盖 Top 10）'>
                    <Table
                      size='small'
                      rowKey='procedure_id'
                      dataSource={[...topicHeatmap.procedure_stats].sort((a,b)=> b.low - a.low).slice(0,10)}
                      pagination={false}
                      columns={[
                        { title: 'Procedure', dataIndex: 'procedure_id', width: 140 },
                        { title: '名称', dataIndex: 'name' },
                        { title: '模态', dataIndex: 'modality', width: 90 },
                        { title: '低分次数', dataIndex: 'low', width: 100 },
                        { title: '覆盖率', dataIndex: 'coverage', width: 100, render: (v:any)=> (v? (v*100).toFixed(1)+'%':'0%') },
                        { title: '均分', dataIndex: 'avg_rating', width: 90, render: (v:any)=> (typeof v==='number'? v.toFixed(2):'-') },
                      ]}
                    />
                  </Card>
                </Col>
              </Row>
            </>
          ) : (
            <Text type='secondary'>{loadingTopicHeatmap ? '加载中…' : '请选择单一Topic后查看完整矩阵'}</Text>
          )}
        </Card>
      )}

      <Card size='small' title='层级关系（Sankey 数据预览）' style={{ marginTop: 12 }} extra={<Text type='secondary'>暂用表格展示，后续替换为图表</Text>}>
        <Row gutter={12}>
          <Col span={8}>
            <Table
              size='small'
              rowKey={(r) => r.source + '>' + r.target}
              loading={loadingSankey}
              dataSource={panelTopicLinks}
              pagination={{ pageSize: 8 }}
              columns={[
                { title: 'Panel', dataIndex: 'source', render: (v) => nodeLabel(v) },
                { title: 'Topic', dataIndex: 'target', render: (v) => nodeLabel(v) },
                { title: '数量', dataIndex: 'value', width: 100 },
              ]}
            />
          </Col>
          <Col span={8}>
            <Table
              size='small'
              rowKey={(r) => r.source + '>' + r.target}
              loading={loadingSankey}
              dataSource={topicScenarioLinks}
              pagination={{ pageSize: 8 }}
              columns={[
                { title: 'Topic', dataIndex: 'source', render: (v) => nodeLabel(v) },
                { title: 'Scenario', dataIndex: 'target', render: (v) => nodeLabel(v) },
                { title: '推荐数', dataIndex: 'value', width: 100 },
              ]}
            />
          </Col>
          <Col span={8}>
            <Table
              size='small'
              rowKey={(r) => r.source + '>' + r.target}
              loading={loadingSankey}
              dataSource={scenarioProcedureLinks}
              pagination={{ pageSize: 8 }}
              columns={[
                { title: 'Scenario', dataIndex: 'source', render: (v) => nodeLabel(v) },
                { title: 'Procedure', dataIndex: 'target', render: (v) => nodeLabel(v) },
                { title: '推荐数', dataIndex: 'value', width: 100 },
              ]}
            />
          </Col>
        </Row>
      </Card>

      <Card size='small' title='搜索对比（关键词 vs 向量，Scenario）' style={{ marginTop: 12 }}>
        <Space wrap>
          <Select
            disabled
            value={'scenario'}
            options={[{ value: 'scenario', label: 'Scenario' }]}
            style={{ width: 120 }}
          />
          <Form.Item label='TopK' style={{ marginBottom: 0 }}>
            <InputNumber min={1} max={100} value={cmpTopK} onChange={(v)=>setCmpTopK(v||10)} style={{ width: 100 }} />
          </Form.Item>
          <Form.Item label='相似度阈值' style={{ marginBottom: 0 }}>
            <InputNumber min={0} max={1} step={0.01} value={cmpThreshold} onChange={(v)=>setCmpThreshold(v||0)} style={{ width: 140 }} />
          </Form.Item>
          <Form.Item label='查询' style={{ marginBottom: 0 }}>
            <input
              value={cmpQuery}
              onChange={(e)=>setCmpQuery(e.target.value)}
              placeholder='输入自然语言查询（中文或英文）'
              style={{ width: 360, padding: '6px 8px', border: '1px solid #d9d9d9', borderRadius: 6 }}
            />
          </Form.Item>
          <Button type='primary' loading={cmpLoading} onClick={runCompare}>对比</Button>
        </Space>
        {cmpResult && (
          <div style={{ marginTop: 12 }}>
            <Space size={20} wrap>
              <Statistic title='关键词TopK' value={cmpResult.keyword?.ids?.length || 0} />
              <Statistic title='向量TopK' value={cmpResult.vector?.ids?.length || 0} />
              <Statistic title='重叠数' value={cmpResult.overlap?.count || 0} />
              <Statistic title='Jaccard' value={Number(cmpResult.overlap?.jaccard||0).toFixed(3)} />
              <Statistic title='相似度P50' value={Number(cmpResult.vector?.similarity_stats?.p50||0).toFixed(3)} />
              <Statistic title='相似度P90' value={Number(cmpResult.vector?.similarity_stats?.p90||0).toFixed(3)} />
            </Space>
            <Row gutter={12} style={{ marginTop: 12 }}>
              <Col span={12}>
                <Card size='small' title='向量结果'>
                  <Table
                    size='small'
                    rowKey='id'
                    dataSource={cmpResult.vector?.items || []}
                    pagination={{ pageSize: 8 }}
                    columns={[
                      { title:'Scenario', dataIndex:'id', width: 140 },
                      { title:'描述', dataIndex:'description' },
                      { title:'相似度', dataIndex:'similarity', width: 120, render: (v:any)=> (typeof v === 'number'? Number(v).toFixed(3) : '-') },
                    ]}
                  />
                </Card>
              </Col>
              <Col span={12}>
                <Card size='small' title='关键词结果'>
                  <Table
                    size='small'
                    rowKey='id'
                    dataSource={(cmpResult.keyword?.items || []).map((it:any)=>({ ...it, similarity: undefined }))}
                    pagination={{ pageSize: 8 }}
                    columns={[
                      { title:'Scenario', dataIndex:'id', width: 140 },
                      { title:'描述', dataIndex:'description' },
                    ]}
                  />
                </Card>
              </Col>
            </Row>
          </div>
        )}
      </Card>

      <Card size='small' title='评分热力图（Procedure × Scenario）' style={{ marginTop: 12 }} extra={<Text type='secondary'>显示均值；颜色越深表示值越高</Text>}>
        <div style={{ overflowX: 'auto' }}>
          {heatmap && heatmap.x_labels.length && heatmap.y_labels.length ? (
            <table style={{ borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ position: 'sticky', left: 0, background: '#fff', zIndex: 1, padding: 6, border: '1px solid #eee' }}></th>
                  {heatmap.y_labels.map((y) => (
                    <th key={y} style={{ padding: 6, border: '1px solid #eee', whiteSpace: 'nowrap' }}>{y}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {heatmap.x_labels.map((x, xi) => (
                  <tr key={x}>
                    <td style={{ position: 'sticky', left: 0, background: '#fff', zIndex: 1, padding: 6, border: '1px solid #eee', whiteSpace: 'nowrap' }}>{x}</td>
                    {heatmap.y_labels.map((_, yi) => {
                      const v = heatmap.z[yi]?.[xi]
                      const bg = gradient(v ?? 0, heatMinMax.min, heatMinMax.max)
                      return (
                        <td key={yi} title={String(v ?? '')} style={{ padding: 6, border: '1px solid #eee', background: bg, textAlign: 'center' }}>
                          <span style={{ fontSize: 12 }}>{typeof v === 'number' ? v.toFixed(2) : '-'}</span>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <Text type='secondary'>暂无数据，请调整筛选后刷新。</Text>
          )}
        </div>
      </Card>

      <Divider />
      <Space>
        <Tag>提示</Tag>
        <Text type='secondary'>当前为MVP：后续将替换为可交互的Sankey/Graph/Heatmap图表，并新增对比、分享与导出功能。</Text>
      </Space>
    </div>
  )
}

export default AnalyticsDashboard
