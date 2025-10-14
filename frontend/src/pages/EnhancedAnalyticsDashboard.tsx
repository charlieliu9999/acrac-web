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
  Tabs,
} from 'antd'
import ReactECharts from 'echarts-for-react'
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
type SankeyLink = { source: string; target: string; value: number; max_rating?: number; avg_rating?: number }
type SankeyResp = { nodes: SankeyNode[]; links: SankeyLink[]; meta?: any }

type HeatmapResp = {
  x_labels: string[] // scenarios
  y_labels: string[] // procedures
  x_label_names?: Record<string, string> // scenario ID到名称的映射
  y_label_names?: Record<string, string> // procedure ID到名称的映射
  z: (number | null)[][] // y by x（后端按 [procedure][scenario] 返回；缺失为 null）
  metric: 'rating_mean' | 'count'
}

type PanelItem = { semantic_id: string; name_zh?: string }
type TopicItem = { semantic_id: string; name_zh?: string }

// 工具函数定义
const getNodeColor = (type: string) => {
  const colors = {
    panel: '#5470c6',
    topic: '#91cc75',
    scenario: '#fac858',
    procedure: '#ee6666'
  }
  return colors[type as keyof typeof colors] || '#999'
}

const EnhancedAnalyticsDashboard: React.FC = () => {
  const [kpi, setKpi] = useState<KPIResp | null>(null)
  const [loadingKpi, setLoadingKpi] = useState(false)
  const [sankey, setSankey] = useState<SankeyResp | null>(null)
  const [loadingSankey, setLoadingSankey] = useState(false)
  const [heatmap, setHeatmap] = useState<HeatmapResp | null>(null)
  const [loadingHeatmap, setLoadingHeatmap] = useState(false)
  const [panels, setPanels] = useState<PanelItem[]>([])
  const [topics, setTopics] = useState<TopicItem[]>([])

  // Filters
  const [panelId, setPanelId] = useState<string | undefined>()
  const [topicIds, setTopicIds] = useState<string[] | undefined>(undefined)
  const [pregnancy, setPregnancy] = useState<string | undefined>()
  const [urgency, setUrgency] = useState<string | undefined>()
  const [risk, setRisk] = useState<string | undefined>()
  const [population, setPopulation] = useState<string | undefined>()
  const [modality, setModality] = useState<string | undefined>()
  const [ratingRange, setRatingRange] = useState<[number, number] | undefined>([1, 9])
  const [showTopN, setShowTopN] = useState<boolean>(false)
  const [topN, setTopN] = useState<number>(150)
  
  // Sankey图控制
  const [showScenarios, setShowScenarios] = useState<boolean>(true)
  const [procedureRatingFilter, setProcedureRatingFilter] = useState<{high: boolean, mid: boolean, low: boolean}>({
    high: true,
    mid: true,
    low: true
  })

  const queryParams = useMemo(() => {
    const p: any = {}
    if (panelId) p.panel_id = panelId
    if (topicIds?.length) p.topic_ids = topicIds.join(',')
    if (pregnancy) p.pregnancy = pregnancy
    if (urgency) p.urgency = urgency
    if (risk) p.risk = risk
    if (population) p.population = population
    if (modality) p.modality = modality
    
    // 根据评分筛选按钮状态调整评分范围
    // 如果没有任何筛选按钮选中，使用原始范围
    if (!procedureRatingFilter.high && !procedureRatingFilter.mid && !procedureRatingFilter.low) {
      if (ratingRange) {
        p.rating_min = ratingRange[0]
        p.rating_max = ratingRange[1]
      }
    } else {
      // 使用离散筛选：只选择选中的评分区间
      const selectedRanges: [number, number][] = []
      if (procedureRatingFilter.high) selectedRanges.push([7, 9])
      if (procedureRatingFilter.mid) selectedRanges.push([4, 6])
      if (procedureRatingFilter.low) selectedRanges.push([1, 3])
      
      if (selectedRanges.length > 0) {
        // 对于多个区间，我们使用第一个区间的范围
        // 更好的方案是后端支持多个区间，但这里先简化处理
        const [minRating, maxRating] = selectedRanges[0]
        p.rating_min = minRating
        p.rating_max = maxRating
      }
    }
    if (showTopN && topN) p.topN = topN
    return p
  }, [panelId, topicIds, pregnancy, urgency, risk, population, modality, ratingRange, showTopN, topN, procedureRatingFilter])

  const loadKPIs = async () => {
    try {
      setLoadingKpi(true)
      const r = await api.get('/api/v1/acrac/analytics/kpis')
      setKpi(r.data)
    } catch (e: any) {
      message.error('加载KPI失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoadingKpi(false)
    }
  }

  const loadPanels = async () => {
    try {
      const r = await api.get('/api/v1/acrac/data/panels')
      setPanels(r.data)
    } catch (e: any) {
      message.error('加载科室失败: ' + (e?.response?.data?.detail || e.message))
    }
  }

  const loadTopics = async (panelId: string) => {
    try {
      const r = await api.get('/api/v1/acrac/data/topics/by-panel', { params: { panel_id: panelId } })
      setTopics(r.data)
    } catch (e: any) {
      message.error('加载主题失败: ' + (e?.response?.data?.detail || e.message))
    }
  }

  const loadSankey = async () => {
    try {
      setLoadingSankey(true)
      const r = await api.get('/api/v1/acrac/analytics/sankey', { params: queryParams })
      setSankey(r.data)
    } catch (e: any) {
      message.error('加载Sankey数据失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoadingSankey(false)
    }
  }

  const loadHeatmap = async () => {
    try {
      setLoadingHeatmap(true)
      const r = await api.get('/api/v1/acrac/analytics/heatmap', { params: queryParams })
      setHeatmap(r.data)
    } catch (e: any) {
      message.error('加载热力图数据失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoadingHeatmap(false)
    }
  }

  const refreshAll = () => {
    loadSankey()
    loadHeatmap()
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
    loadSankey()
    loadHeatmap()
  }, [queryParams])

  // ECharts配置
  const sankeyOption = useMemo(() => {
    if (!sankey?.nodes?.length || !sankey?.links?.length) {
      return {
        title: { text: '暂无数据', left: 'center', top: 'middle' },
        graphic: { type: 'text', left: 'center', top: 'middle', style: { text: '请调整筛选条件后刷新', fontSize: 14, fill: '#999' } }
      }
    }

    // 根据控制条件过滤节点和链接
    let filteredNodes = [...sankey.nodes]
    let filteredLinks = [...sankey.links]

    // 评分筛选通过API参数控制，这里不需要额外处理

    // 如果不显示scenario层，需要重新构建连接
    if (!showScenarios) {
      // 保留非scenario节点
      filteredNodes = filteredNodes.filter(n => n.type !== 'scenario')
      
      // 构建topic到procedure的直接连接
      const topicToProcedureLinks = new Map<string, Map<string, number>>()
      
      // 第一步：找出所有 topic -> scenario 的连接
      const topicToScenarioMap = new Map<string, Set<string>>()
      sankey.links.forEach(link => {
        if (link.source.startsWith('topic:') && link.target.startsWith('scenario:')) {
          if (!topicToScenarioMap.has(link.source)) {
            topicToScenarioMap.set(link.source, new Set())
          }
          topicToScenarioMap.get(link.source)!.add(link.target)
        }
      })
      
      // 第二步：找出所有 scenario -> procedure 的连接
      const scenarioToProcedureMap = new Map<string, Array<{target: string, value: number}>>()
      sankey.links.forEach(link => {
        if (link.source.startsWith('scenario:') && link.target.startsWith('procedure:')) {
          if (!scenarioToProcedureMap.has(link.source)) {
            scenarioToProcedureMap.set(link.source, [])
          }
          scenarioToProcedureMap.get(link.source)!.push({target: link.target, value: link.value})
        }
      })
      
      // 第三步：聚合 topic -> procedure 的连接
      topicToScenarioMap.forEach((scenarios, topic) => {
        scenarios.forEach(scenario => {
          const procedures = scenarioToProcedureMap.get(scenario) || []
          procedures.forEach(proc => {
            if (!topicToProcedureLinks.has(topic)) {
              topicToProcedureLinks.set(topic, new Map())
            }
            const procMap = topicToProcedureLinks.get(topic)!
            procMap.set(proc.target, (procMap.get(proc.target) || 0) + proc.value)
          })
        })
      })
      
      // 过滤链接：保留panel->topic和新构建的topic->procedure
      filteredLinks = sankey.links.filter(l => 
        l.source.startsWith('panel:') && l.target.startsWith('topic:')
      )
      
      // 添加聚合后的topic->procedure连接
      topicToProcedureLinks.forEach((procedures, topic) => {
        procedures.forEach((value, procedure) => {
          filteredLinks.push({source: topic, target: procedure, value})
        })
      })
    }

    // 为节点分配固定的层级（depth）
    const nodeDepthMap = new Map<string, number>()
    filteredNodes.forEach(node => {
      let depth = 0
      if (node.type === 'panel') depth = 0
      else if (node.type === 'topic') depth = 1
      else if (node.type === 'scenario') depth = 2
      else if (node.type === 'procedure') depth = 3
      nodeDepthMap.set(node.id, depth)
    })

    return {
      title: {
        text: 'ACR-AC 数据关系图',
        subtext: showScenarios ? 'Panel → Topic → Scenario → Procedure' : 'Panel → Topic → Procedure',
        left: 'center'
      },
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            const node = sankey.nodes.find(n => n.id === params.name)
            const label = node?.label || params.name
            const typeLabelMap: any = { panel: '科室', topic: '主题', scenario: '场景', procedure: '检查项目' }
            const typeKey = node?.type || params?.data?.type
            const typeLabel = typeLabelMap[typeKey] || '未知'
            const qty = (params?.data?.value ?? 0)
            return `${label}<br/>类型: ${typeLabel}<br/>数量: ${qty}`
          } else {
            // 连接线显示评分信息
            const link = sankey.links.find(l => l.source === params.data.source && l.target === params.data.target)
            let tooltip = `${params.data.source} → ${params.data.target}<br/>推荐数: ${params.data.value}`
            // 优先展示“评分”（取最大评分），便于判断应否推荐
            if (link?.max_rating !== undefined && link?.max_rating !== null) {
              tooltip += `<br/>评分: ${link.max_rating.toFixed(1)}`
            }
            // 备用展示平均评分
            if (link?.avg_rating !== undefined && link?.avg_rating !== null) {
              tooltip += `<br/>平均评分: ${link.avg_rating.toFixed(1)}`
            }
            return tooltip
          }
        }
      },
      grid: {
        left: '5%',
        right: '20%',
        top: '10%',
        bottom: '5%',
        containLabel: true
      },
      series: [{
        type: 'sankey',
        layout: 'none',
        layoutIterations: 0,
        nodeGap: 5,
        nodeWidth: 15,
        orient: 'horizontal',
        draggable: false,
        emphasis: {
          focus: 'adjacency'
        },
        data: filteredNodes.map(node => ({
          name: node.id,
          value: node.count ?? 1,
          depth: nodeDepthMap.get(node.id),
          type: node.type,
          itemStyle: {
            color: getNodeColor(node.type),
            borderColor: '#333',
            borderWidth: 1
          },
          label: {
            formatter: (params: any) => {
              const node = sankey.nodes.find(n => n.id === params.name)
              if (node?.type === 'procedure') {
                const count = (node as any)?.count
                const label = node?.label || params.name
                return typeof count === 'number' ? `${label} (${count})` : label
              }
              return node?.label || params.name
            },
            fontSize: 10,
            color: '#333'
          }
        })),
        links: filteredLinks.map(link => ({
          source: link.source,
          target: link.target,
          value: link.value
        })),
        lineStyle: {
          color: 'gradient',
          curveness: 0.5,
          opacity: 0.3
        }
      }]
    }
  }, [sankey, showScenarios])

  const heatmapOption = useMemo(() => {
    if (!heatmap?.x_labels?.length || !heatmap?.y_labels?.length) {
      return {
        title: { text: '暂无数据', left: 'center', top: 'middle' },
        graphic: { type: 'text', left: 'center', top: 'middle', style: { text: '请调整筛选条件后刷新', fontSize: 14, fill: '#999' } }
      }
    }

    const data = []
    // 后端返回 z[y=procedure][x=scenario]
    // ECharts需要 [x, y, value] 其中x是procedure索引，y是scenario索引
    for (let y = 0; y < heatmap.y_labels.length; y++) {
      for (let x = 0; x < heatmap.x_labels.length; x++) {
        const value = heatmap.z[y]?.[x]
        if (value !== null && value !== undefined) {
          data.push([y, x, value])
        }
      }
    }

    return {
      title: {
        text: '评分热力图 (Procedure × Scenario)',
        subtext: '颜色越深表示评分越高；鼠标悬停查看完整内容',
        left: 'center'
      },
      tooltip: {
        position: 'top',
        formatter: (params: any) => {
          const procedureId = heatmap.y_labels[params.data[0]]
          const scenarioId = heatmap.x_labels[params.data[1]]
          const procedureName = heatmap.y_label_names?.[procedureId] || procedureId
          const scenarioName = heatmap.x_label_names?.[scenarioId] || scenarioId
          return `检查项目: ${procedureName}<br/>场景: ${scenarioName}<br/>评分: ${params.data[2].toFixed(2)}`
        }
      },
      grid: {
        height: '50%',
        top: '12%',
        left: '10%',
        right: '5%'
      },
      xAxis: {
        type: 'category',
        data: heatmap.y_labels,
        splitArea: {
          show: true
        },
        axisLabel: {
          rotate: 45,
          fontSize: 10,
          interval: 0,
          formatter: (value: string) => value // 只显示ID
        },
        name: 'Procedure ID',
        nameLocation: 'middle',
        nameGap: 60,
        nameTextStyle: {
          fontSize: 12,
          fontWeight: 'bold'
        }
      },
      yAxis: {
        type: 'category',
        data: heatmap.x_labels,
        splitArea: {
          show: true
        },
        axisLabel: {
          fontSize: 10,
          interval: 0,
          formatter: (value: string) => value // 只显示ID
        },
        name: 'Scenario ID',
        nameLocation: 'middle',
        nameGap: 60,
        nameTextStyle: {
          fontSize: 12,
          fontWeight: 'bold'
        }
      },
      visualMap: {
        min: 1,
        max: 9,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: '5%',
        text: ['高分(9)', '低分(1)'],
        inRange: {
          // 从浅色到深色的渐变：浅蓝 -> 深蓝 -> 深红
          color: [
            '#f0f9ff', // 1分 - 极浅蓝
            '#d0e8f5', // 2分 - 浅蓝
            '#a8d5e8', // 3分 - 较浅蓝
            '#7ec1db', // 4分 - 蓝色
            '#4da6c7', // 5分 - 较深蓝
            '#2b8cae', // 6分 - 深蓝
            '#ff9933', // 7分 - 橙色
            '#ff6633', // 8分 - 深橙
            '#cc0000'  // 9分 - 深红
          ]
        }
      },
      series: [{
        name: '评分',
        type: 'heatmap',
        data: data,
        label: {
          show: data.length < 100, // 减少显示标签的条件
          fontSize: 8,
          formatter: (params: any) => {
            const value = params.data[2]
            return value > 0 ? value.toFixed(1) : ''
          }
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }]
    }
  }, [heatmap])


  // 分布分析图表
  const distributionOption = useMemo(() => {
    if (!kpi) return null

    return {
      title: {
        text: '数据分布概览',
        left: 'center'
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'shadow'
        }
      },
      legend: {
        data: ['数量'],
        top: 'bottom'
      },
      xAxis: {
        type: 'category',
        data: ['科室', '主题', '临床场景', '检查项目', '推荐关系'],
        axisLabel: {
          rotate: 45
        }
      },
      yAxis: {
        type: 'value'
      },
      series: [{
        name: '数量',
        type: 'bar',
        data: [kpi.panels, kpi.topics, kpi.scenarios, kpi.procedures, kpi.recommendations],
        itemStyle: {
          color: '#5470c6'
        },
        emphasis: {
          itemStyle: {
            color: '#3b4d8a'
          }
        }
      }]
    }
  }, [kpi])

  return (
    <div>
      <div className='page-title'>数据关系看板</div>
      
      {/* KPI统计 */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={4}><Card size='small' loading={loadingKpi}><Statistic title='科室' value={kpi?.panels ?? 0} /></Card></Col>
        <Col span={4}><Card size='small' loading={loadingKpi}><Statistic title='主题' value={kpi?.topics ?? 0} /></Card></Col>
        <Col span={4}><Card size='small' loading={loadingKpi}><Statistic title='临床场景' value={kpi?.scenarios ?? 0} /></Card></Col>
        <Col span={4}><Card size='small' loading={loadingKpi}><Statistic title='检查项目' value={kpi?.procedures ?? 0} /></Card></Col>
        <Col span={8}><Card size='small' loading={loadingKpi}><Statistic title='推荐关系' value={kpi?.recommendations ?? 0} /></Card></Col>
      </Row>

      {/* 筛选器 */}
      <Card size='small' title='筛选条件' style={{ marginBottom: 16 }}>
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
          <Form.Item label='评分区间' style={{ marginBottom: 0 }}>
            <InputNumber 
              min={1} max={9} 
              value={ratingRange?.[0]} 
              onChange={(v)=>setRatingRange([v||1, ratingRange?.[1]||9])} 
              style={{ width: 80 }} 
              placeholder='最小'
            />
            <span style={{ margin: '0 8px' }}>-</span>
            <InputNumber 
              min={1} max={9} 
              value={ratingRange?.[1]} 
              onChange={(v)=>setRatingRange([ratingRange?.[0]||1, v||9])} 
              style={{ width: 80 }} 
              placeholder='最大'
            />
          </Form.Item>
          <Form.Item label='TopN限制' style={{ marginBottom: 0 }}>
            <Button 
              size='small' 
              type={showTopN ? 'primary' : 'default'} 
              onClick={() => setShowTopN(!showTopN)}
            >
              {showTopN ? '开启' : '关闭'}
            </Button>
            {showTopN && (
              <InputNumber 
                min={20} max={500} 
                value={topN} 
                onChange={(v)=>setTopN(v||150)} 
                style={{ width: 100, marginLeft: 8 }} 
              />
            )}
          </Form.Item>
          <Button type='primary' onClick={refreshAll}>刷新</Button>
        </Space>
      </Card>

      {/* 图表展示 */}
      <Tabs
        items={[
          {
            key: 'overview',
            label: '概览分析',
            children: (
              <Row gutter={16}>
                <Col span={24}>
                  <Card title="数据分布概览" style={{ marginBottom: 16 }}>
                    {distributionOption && (
                      <ReactECharts 
                        option={distributionOption} 
                        style={{ height: '400px' }}
                        opts={{ renderer: 'canvas' }}
                      />
                    )}
                  </Card>
                </Col>
              </Row>
            )
          },
          {
            key: 'sankey',
            label: '关系流程图',
            children: (
              <Card 
                title="ACR-AC 数据关系图" 
                loading={loadingSankey}
                extra={
                  <Space>
                    <Space>
                      <Text>显示Scenario层:</Text>
                      <Button 
                        size="small"
                        type={showScenarios ? 'primary' : 'default'}
                        onClick={() => setShowScenarios(!showScenarios)}
                      >
                        {showScenarios ? '开' : '关'}
                      </Button>
                    </Space>
                    <Divider type="vertical" />
                    <Text>评分筛选:</Text>
                    <Button 
                      size="small" 
                      type={procedureRatingFilter.high && procedureRatingFilter.mid && procedureRatingFilter.low ? 'primary' : 'default'}
                      onClick={() => {
                        const allSelected = procedureRatingFilter.high && procedureRatingFilter.mid && procedureRatingFilter.low
                        setProcedureRatingFilter({
                          high: !allSelected,
                          mid: !allSelected,
                          low: !allSelected
                        })
                      }}
                    >
                      全部
                    </Button>
                    <Button 
                      size="small" 
                      type={procedureRatingFilter.high ? 'primary' : 'default'}
                      onClick={() => {
                        setProcedureRatingFilter({...procedureRatingFilter, high: !procedureRatingFilter.high})
                      }}
                    >
                      高分(7-9)
                    </Button>
                    <Button 
                      size="small"
                      type={procedureRatingFilter.mid ? 'primary' : 'default'}
                      onClick={() => {
                        setProcedureRatingFilter({...procedureRatingFilter, mid: !procedureRatingFilter.mid})
                      }}
                    >
                      中分(4-6)
                    </Button>
                    <Button 
                      size="small"
                      type={procedureRatingFilter.low ? 'primary' : 'default'}
                      onClick={() => {
                        setProcedureRatingFilter({...procedureRatingFilter, low: !procedureRatingFilter.low})
                      }}
                    >
                      低分(1-3)
                    </Button>
                  </Space>
                }
              >
                <ReactECharts 
                  option={sankeyOption} 
                  style={{ height: '600px' }}
                  opts={{ renderer: 'canvas' }}
                />
              </Card>
            )
          },
          {
            key: 'heatmap',
            label: '评分热力图',
            children: (
              <div>
                <Card title="评分热力图 (Procedure × Scenario)" loading={loadingHeatmap}>
                  <ReactECharts 
                    option={heatmapOption} 
                    style={{ height: '600px' }}
                    opts={{ renderer: 'canvas' }}
                  />
                </Card>
                
                {/* 独立图例 */}
                {heatmap && (
                  <Row gutter={16} style={{ marginTop: 16 }}>
                    <Col span={12}>
                      <Card size="small" title="场景列表" style={{ height: '300px', overflow: 'auto' }}>
                        <div style={{ maxHeight: '250px', overflow: 'auto' }}>
                          {heatmap.x_labels.map((scenarioId, index) => (
                            <div key={scenarioId} style={{ marginBottom: 4, fontSize: '12px' }}>
                              <Tag color="blue" style={{ marginRight: 8 }}>
                                {index + 1}
                              </Tag>
                              <Text style={{ fontSize: '11px' }}>
                                {heatmap.x_label_names?.[scenarioId] || scenarioId}
                              </Text>
                            </div>
                          ))}
                        </div>
                      </Card>
                    </Col>
                    <Col span={12}>
                      <Card size="small" title="检查项目列表" style={{ height: '300px', overflow: 'auto' }}>
                        <div style={{ maxHeight: '250px', overflow: 'auto' }}>
                          {heatmap.y_labels.map((procedureId, index) => (
                            <div key={procedureId} style={{ marginBottom: 4, fontSize: '12px' }}>
                              <Tag color="green" style={{ marginRight: 8 }}>
                                {index + 1}
                              </Tag>
                              <Text style={{ fontSize: '11px' }}>
                                {heatmap.y_label_names?.[procedureId] || procedureId}
                              </Text>
                            </div>
                          ))}
                        </div>
                      </Card>
                    </Col>
                  </Row>
                )}
              </div>
            )
          }
        ]}
      />

      <Divider />
      <Space>
        <Tag>提示</Tag>
        <Text type='secondary'>使用筛选条件可以动态调整图表显示内容，支持多维度数据分析和可视化展示。</Text>
      </Space>
    </div>
  )
}

export default EnhancedAnalyticsDashboard
