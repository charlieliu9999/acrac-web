import React, { useEffect, useMemo, useState } from 'react'
import {
  Card,
  Col,
  Input,
  Row,
  Select,
  Table,
  Typography,
  message,
  Statistic,
  Space,
  Tag,
  Tree,
  Spin,
  Divider,
  Tooltip,
  Modal,
  Button,
  Tabs,
  Form,
  Radio,
  Collapse,
  Badge,
  InputNumber,
} from 'antd'
import { EyeOutlined, SearchOutlined, RobotOutlined, FilterOutlined, BarChartOutlined } from '@ant-design/icons'
import type { DataNode, EventDataNode } from 'antd/es/tree'
import { api } from '../api/http'
import EnhancedAnalyticsDashboard from './EnhancedAnalyticsDashboard'

const { Paragraph, Text } = Typography

type PanelItem = { semantic_id: string; name_zh?: string; topics_count?: number; scenarios_count?: number }
type TopicItem = { semantic_id: string; name_zh?: string; scenarios_count?: number }
type ScenarioItem = {
  semantic_id: string
  description_zh?: string
  description_en?: string
  pregnancy_status?: string
  urgency_level?: string
  risk_level?: string
  patient_population?: string
  age_group?: string
  gender?: string
  recs_count?: number
}

type Stats = { panels: number; topics: number; scenarios: number; procedures: number }

// 搜索相关类型
type SearchMode = 'keyword' | 'vector' | 'combined'
type SearchField = 'panels' | 'topics' | 'scenarios' | 'procedures'

interface SearchFilters {
  panels: string[]
  topics: string[]
  scenarios: string[]
  procedures: string[]
  pregnancy?: string
  urgency?: string
  risk?: string
  population?: string
  modality?: string
  ratingMin?: number
  ratingMax?: number
}

interface SearchResult {
  type: SearchField
  id: string
  title: string
  description: string
  metadata: Record<string, any>
  score?: number
}

const DataBrowser: React.FC = () => {
  // Global stats
  const [stats, setStats] = useState<Stats | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)

  // Hierarchy caches
  const [panels, setPanels] = useState<PanelItem[]>([])
  const [topicsMap, setTopicsMap] = useState<Record<string, TopicItem[]>>({})
  const [topicToPanel, setTopicToPanel] = useState<Record<string, string>>({})
  const [scenariosMap, setScenariosMap] = useState<Record<string, ScenarioItem[]>>({})
  const [treeLoadingKeys, setTreeLoadingKeys] = useState<string[]>([])

  // Selection & data
  const [selectedScenario, setSelectedScenario] = useState<ScenarioItem | null>(null)
  const [recs, setRecs] = useState<any[]>([])
  const [recsLoading, setRecsLoading] = useState(false)

  // Filters
  const [keyword, setKeyword] = useState<string>('')
  const [pregnancy, setPregnancy] = useState<string | undefined>()
  const [urgency, setUrgency] = useState<string | undefined>()
  const [risk, setRisk] = useState<string | undefined>()
  const [population, setPopulation] = useState<string | undefined>()

  // Modal for detailed reasoning
  const [reasoningModal, setReasoningModal] = useState<{
    visible: boolean
    title: string
    content: string
  }>({ visible: false, title: '', content: '' })

  // 新的搜索状态
  const [searchMode, setSearchMode] = useState<SearchMode>('keyword')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [searchFields, setSearchFields] = useState<SearchField[]>(['scenarios'])
  const [searchFilters, setSearchFilters] = useState<SearchFilters>({
    panels: [],
    topics: [],
    scenarios: [],
    procedures: [],
  })
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [activeTab, setActiveTab] = useState<string>('hierarchy')
  const [similarityThreshold, setSimilarityThreshold] = useState<number>(0.3)

  // 获取所有场景数据（用于搜索结果详情查看）
  const allScenarios = useMemo(() => {
    const scenarios: ScenarioItem[] = []
    Object.values(scenariosMap).forEach(arr => scenarios.push(...arr))
    return scenarios
  }, [scenariosMap])

  const normList = (data: any, preferKey?: string) => {
    if (Array.isArray(data)) return data
    if (preferKey && Array.isArray(data?.[preferKey])) return data[preferKey]
    if (Array.isArray(data?.items)) return data.items
    return []
  }

  // Load stats
  const loadStats = async () => {
    try {
      setStatsLoading(true)
      const r = await api.get('/api/v1/data/import-stats')
      const c = r.data?.current_counts
      if (c) setStats({ panels: c.panels, topics: c.topics, scenarios: c.scenarios, procedures: c.procedures })
    } catch (e: any) {
      message.warning('统计数据不可用：' + (e?.response?.data?.detail || e.message))
    } finally {
      setStatsLoading(false)
    }
  }

  // Load root panels
  const loadPanels = async () => {
    try {
      const r = await api.get('/api/v1/acrac/data/panels')
      setPanels(normList(r.data))
    } catch (e: any) {
      message.error('加载科室失败: ' + (e?.response?.data?.detail || e.message))
    }
  }

  // Lazy-load topics under a panel
  const ensureTopics = async (panelId: string) => {
    if (topicsMap[panelId]) return
    setTreeLoadingKeys((ks) => [...new Set([...ks, `panel:${panelId}`])])
    try {
      const r = await api.get('/api/v1/acrac/data/topics/by-panel', { params: { panel_id: panelId } })
      const list: TopicItem[] = normList(r.data)
      setTopicsMap((m) => ({ ...m, [panelId]: list }))
      setTopicToPanel((m) => ({
        ...m,
        ...Object.fromEntries(list.map((t) => [t.semantic_id, panelId])),
      }))
    } catch (e: any) {
      message.error('加载主题失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setTreeLoadingKeys((ks) => ks.filter((k) => k !== `panel:${panelId}`))
    }
  }

  // Lazy-load scenarios under a topic
  const ensureScenarios = async (topicId: string) => {
    if (scenariosMap[topicId]) return
    setTreeLoadingKeys((ks) => [...new Set([...ks, `topic:${topicId}`])])
    try {
      const r = await api.get('/api/v1/acrac/data/scenarios/by-topic', { params: { topic_id: topicId } })
      const list: ScenarioItem[] = normList(r.data)
      setScenariosMap((m) => ({ ...m, [topicId]: list }))
    } catch (e: any) {
      message.error('加载场景失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setTreeLoadingKeys((ks) => ks.filter((k) => k !== `topic:${topicId}`))
    }
  }

  // Recommendations for a scenario
  const loadRecs = async (sid: string) => {
    try {
      setRecsLoading(true)
      const r = await api.get('/api/v1/acrac/data/recommendations', { params: { scenario_id: sid, page: 1, size: 100 } })
      setRecs(r.data.items || [])
    } catch (e: any) {
      message.error('加载推荐失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setRecsLoading(false)
    }
  }

  // Show detailed reasoning modal
  const showReasoningDetail = (procedureName: string, reasoning: string) => {
    setReasoningModal({
      visible: true,
      title: `推荐理由 - ${procedureName}`,
      content: reasoning || '暂无详细理由'
    })
  }

  // 智能合并搜索结果
  const mergeSearchResults = (keywordResults: SearchResult[], vectorResults: SearchResult[]): SearchResult[] => {
    const mergedMap = new Map<string, SearchResult>()
    
    // 处理关键词搜索结果
    keywordResults.forEach(item => {
      const key = `${item.type}-${item.id}`
      const existing = mergedMap.get(key)
      
      if (!existing) {
        // 新项目，添加关键词标记
        mergedMap.set(key, {
          ...item,
          metadata: {
            ...item.metadata,
            searchSource: 'keyword',
            keywordScore: item.score || 1.0
          }
        })
      } else {
        // 已存在，更新关键词分数
        existing.metadata = {
          ...existing.metadata,
          searchSource: 'both',
          keywordScore: item.score || 1.0
        }
      }
    })
    
    // 处理向量搜索结果
    vectorResults.forEach(item => {
      const key = `${item.type}-${item.id}`
      const existing = mergedMap.get(key)
      
      if (!existing) {
        // 新项目，添加向量标记
        mergedMap.set(key, {
          ...item,
          metadata: {
            ...item.metadata,
            searchSource: 'vector',
            vectorScore: item.score || 0
          }
        })
      } else {
        // 已存在，更新向量分数和搜索源
        existing.metadata = {
          ...existing.metadata,
          searchSource: 'both',
          vectorScore: item.score || 0
        }
        // 更新综合分数（向量分数优先，因为更准确）
        existing.score = Math.max(existing.score || 0, item.score || 0)
      }
    })
    
    // 转换为数组并排序
    const results = Array.from(mergedMap.values())
    
    // 综合排序：优先显示同时匹配关键词和向量的结果
    results.sort((a, b) => {
      const aSource = a.metadata?.searchSource || 'unknown'
      const bSource = b.metadata?.searchSource || 'unknown'
      
      // 同时匹配的结果优先
      if (aSource === 'both' && bSource !== 'both') return -1
      if (bSource === 'both' && aSource !== 'both') return 1
      
      // 按分数排序
      return (b.score || 0) - (a.score || 0)
    })
    
    return results
  }

  // 执行搜索
  const performSearch = async () => {
    if (!searchQuery.trim()) {
      message.warning('请输入搜索关键词')
      return
    }

    try {
      setSearchLoading(true)
      let results: SearchResult[] = []

      if (searchMode === 'keyword') {
        // 关键词搜索
        results = await performKeywordSearch()
      } else if (searchMode === 'vector') {
        // 向量搜索
        results = await performVectorSearch()
      } else if (searchMode === 'combined') {
        // 组合搜索：并行执行关键词和向量搜索
        const [keywordResults, vectorResults] = await Promise.all([
          performKeywordSearch(),
          performVectorSearch()
        ])
        
        // 智能去重和合并
        results = mergeSearchResults(keywordResults, vectorResults)
      }

      setSearchResults(results)
      message.success(`找到 ${results.length} 个结果`)
    } catch (error: any) {
      message.error('搜索失败: ' + (error?.response?.data?.detail || error.message))
    } finally {
      setSearchLoading(false)
    }
  }

  // 关键词搜索
  const performKeywordSearch = async (): Promise<SearchResult[]> => {
    const results: SearchResult[] = []
    
    for (const field of searchFields) {
      try {
        let endpoint = ''
        let params: any = { q: searchQuery, page: 1, size: 50 }
        
        switch (field) {
          case 'panels':
            endpoint = '/api/v1/acrac/data/panels'
            break
          case 'topics':
            endpoint = '/api/v1/acrac/data/topics'
            break
          case 'scenarios':
            endpoint = '/api/v1/acrac/data/scenarios'
            break
          case 'procedures':
            endpoint = '/api/v1/acrac/data/procedures'
            break
        }

        const response = await api.get(endpoint, { params })
        const items = normList(response.data)
        
        items.forEach((item: any) => {
          results.push({
            type: field,
            id: item.semantic_id || item.id,
            title: item.name_zh || item.description_zh || item.title,
            description: item.description_zh || item.description_en || item.description,
            metadata: item,
            score: 1.0 // 关键词搜索默认分数
          })
        })
      } catch (error) {
        console.warn(`搜索 ${field} 失败:`, error)
      }
    }
    
    return results
  }

  // 向量搜索 - 使用成熟的综合向量搜索API
  const performVectorSearch = async (): Promise<SearchResult[]> => {
    try {
      const response = await api.post('/api/v1/acrac/rag-services/search/comprehensive', {
        query: searchQuery,
        top_k: 20,
        similarity_threshold: similarityThreshold
      })

      const results: SearchResult[] = []
      const data = response.data

      // 处理科室结果
      if (data.panels && data.panels.length > 0) {
        data.panels.forEach((item: any) => {
          results.push({
            type: 'panels',
            id: item.semantic_id,
            title: item.name_zh,
            description: item.description || '',
            metadata: item,
            score: item.similarity_score || 0
          })
        })
      }

      // 处理主题结果
      if (data.topics && data.topics.length > 0) {
        data.topics.forEach((item: any) => {
          results.push({
            type: 'topics',
            id: item.semantic_id,
            title: item.name_zh,
            description: item.description || '',
            metadata: item,
            score: item.similarity_score || 0
          })
        })
      }

      // 处理场景结果
      if (data.scenarios && data.scenarios.length > 0) {
        data.scenarios.forEach((item: any) => {
          results.push({
            type: 'scenarios',
            id: item.semantic_id,
            title: item.description_zh || item.description_en,
            description: item.description_en || item.description_zh || '',
            metadata: item,
            score: item.similarity_score || 0
          })
        })
      }

      // 处理检查项目结果
      if (data.procedures && data.procedures.length > 0) {
        data.procedures.forEach((item: any) => {
          results.push({
            type: 'procedures',
            id: item.semantic_id,
            title: item.name_zh,
            description: item.description_zh || item.description_en || '',
            metadata: item,
            score: item.similarity_score || 0
          })
        })
      }

      // 处理推荐结果（如果有）
      if (data.recommendations && data.recommendations.length > 0) {
        data.recommendations.forEach((item: any) => {
          results.push({
            type: 'procedures',
            id: item.procedure_id || item.semantic_id,
            title: item.procedure_name_zh || item.procedure_name,
            description: item.reasoning_zh || item.reasoning || '',
            metadata: item,
            score: item.similarity_score || 0
          })
        })
      }

      // 按相似度排序
      results.sort((a, b) => (b.score || 0) - (a.score || 0))

      return results
    } catch (error) {
      console.error('向量搜索失败:', error)
      message.error('向量搜索失败，请检查网络连接或稍后重试')
      return []
    }
  }

  useEffect(() => {
    loadStats()
    loadPanels()
  }, [])

  // Build tree data on the fly with filters applied to scenarios
  const treeData: DataNode[] = useMemo(() => {
    const matchScenario = (s: ScenarioItem) => {
      const kw = keyword?.trim()
      if (kw && !((s.description_zh || s.description_en || '').toLowerCase().includes(kw.toLowerCase()) || s.semantic_id.toLowerCase().includes(kw.toLowerCase()))) return false
      if (pregnancy && s.pregnancy_status !== pregnancy) return false
      if (urgency && s.urgency_level !== urgency) return false
      if (risk && s.risk_level !== risk) return false
      if (population && s.patient_population !== population) return false
      return true
    }
    return panels.map((p) => {
      const pKey = `panel:${p.semantic_id}`
      const topics = topicsMap[p.semantic_id] || []
      const topicNodes: DataNode[] = topics.map((t) => {
        const tKey = `topic:${t.semantic_id}`
        const scenarios = (scenariosMap[t.semantic_id] || []).filter(matchScenario)
        const scenarioNodes: DataNode[] = scenarios.map((s) => ({
          key: `scenario:${s.semantic_id}`,
          title: (
            <Space size={8}>
              <span>{s.semantic_id}</span>
              <span style={{ color: '#555' }}>{s.description_zh || s.description_en}</span>
              {s.pregnancy_status && <Tag color='purple'>{s.pregnancy_status}</Tag>}
              {s.urgency_level && <Tag color='red'>{s.urgency_level}</Tag>}
              {typeof s.recs_count === 'number' && <Tag>检查 {s.recs_count}</Tag>}
            </Space>
          ),
          isLeaf: true,
        }))
        return {
          key: tKey,
          title: (
            <Space>
              <span>{t.semantic_id}</span>
              <span style={{ color: '#555' }}>{t.name_zh}</span>
              {typeof t.scenarios_count === 'number' && <Tag color='geekblue'>场景 {t.scenarios_count}</Tag>}
            </Space>
          ),
          children: scenarioNodes.length ? scenarioNodes : undefined,
        } as DataNode
      })
      return {
        key: pKey,
        title: (
          <Space>
            <span>{p.semantic_id}</span>
            <span style={{ color: '#555' }}>{p.name_zh}</span>
            {typeof p.topics_count === 'number' && <Tag color='blue'>主题 {p.topics_count}</Tag>}
            {typeof p.scenarios_count === 'number' && <Tag>场景 {p.scenarios_count}</Tag>}
          </Space>
        ),
        children: topicNodes.length ? topicNodes : undefined,
      } as DataNode
    })
  }, [panels, topicsMap, scenariosMap, keyword, pregnancy, urgency, risk, population])

  const onLoadData = async (node: EventDataNode) => {
    const key = String(node.key)
    if (key.startsWith('panel:')) {
      const id = key.substring('panel:'.length)
      await ensureTopics(id)
    } else if (key.startsWith('topic:')) {
      const id = key.substring('topic:'.length)
      await ensureScenarios(id)
    }
  }

  const onSelect = async (keys: React.Key[]) => {
    const key = String(keys[0] || '')
    if (!key.startsWith('scenario:')) return
    const sid = key.substring('scenario:'.length)
    // Find scenario in cache
    let found: ScenarioItem | null = null
    let selTid: string | null = null
    for (const tid of Object.keys(scenariosMap)) {
      const arr = scenariosMap[tid]
      const s = arr?.find((x) => x.semantic_id === sid)
      if (s) {
        found = s
        selTid = tid
        break
      }
    }
    setSelectedScenario(found ? { ...found } : { semantic_id: sid })
    await loadRecs(sid)
    // Optionally scroll or show path; path can be derived using topicToPanel
    if (selTid) {
      const pid = topicToPanel[selTid]
      if (pid) {
        // no-op for now; kept for future breadcrumb/path display
      }
    }
  }

  // Dynamic filter options gathered from loaded scenarios
  const filterOptions = useMemo(() => {
    const all: ScenarioItem[] = Object.values(scenariosMap).flat()
    const uniq = (vals: (string | undefined)[]) => Array.from(new Set(vals.filter(Boolean) as string[])).map((v) => ({ label: v, value: v }))
    return {
      pregnancy: uniq(all.map((s) => s.pregnancy_status)),
      urgency: uniq(all.map((s) => s.urgency_level)),
      risk: uniq(all.map((s) => s.risk_level)),
      population: uniq(all.map((s) => s.patient_population)),
    }
  }, [scenariosMap])

  // 搜索结果显示组件
  const renderSearchResults = () => {
    if (searchResults.length === 0) {
      return (
        <Card>
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Text type="secondary">暂无搜索结果</Text>
          </div>
        </Card>
      )
    }

    // 根据相似度阈值过滤结果
    const filteredResults = searchResults.filter(result => 
      (result.score || 0) >= similarityThreshold
    )

    if (filteredResults.length === 0) {
      return (
        <Card>
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Text type="secondary">相似度阈值 {similarityThreshold.toFixed(2)} 下暂无结果</Text>
            <br />
            <Text type="secondary">请降低相似度阈值或调整搜索条件</Text>
          </div>
        </Card>
      )
    }

    // 按类型分组结果
    const groupedResults = filteredResults.reduce((acc, result) => {
      if (!acc[result.type]) acc[result.type] = []
      acc[result.type].push(result)
      return acc
    }, {} as Record<SearchField, SearchResult[]>)

    return (
      <div>
        {Object.entries(groupedResults).map(([type, results]) => (
          <Card key={type} size="small" style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 12 }}>
              <Badge count={results.length} showZero>
                <Text strong>
                  {type === 'panels' && '科室'}
                  {type === 'topics' && '主题'}
                  {type === 'scenarios' && '临床场景'}
                  {type === 'procedures' && '检查项目'}
                </Text>
              </Badge>
            </div>
            <Table
              size="small"
              dataSource={results}
              pagination={{ pageSize: 5 }}
              columns={[
                {
                  title: '相似度',
                  dataIndex: 'score',
                  width: 100,
                  render: (score: number, record: SearchResult) => {
                    const source = record.metadata?.searchSource
                    const color = score > 0.7 ? 'green' : score > 0.5 ? 'orange' : 'red'
                    const text = score ? `${(score * 100).toFixed(1)}%` : '-'
                    
                    return (
                      <Space direction="vertical" size="small">
                        <Tag color={color}>{text}</Tag>
                        {source === 'both' && <Tag color="blue" size="small">组合</Tag>}
                        {source === 'keyword' && <Tag color="purple" size="small">关键词</Tag>}
                        {source === 'vector' && <Tag color="cyan" size="small">向量</Tag>}
                      </Space>
                    )
                  }
                },
                {
                  title: '标题',
                  dataIndex: 'title',
                  ellipsis: true,
                  render: (title: string, record: SearchResult) => (
                    <Button
                      type="link"
                      onClick={() => {
                        if (record.type === 'scenarios') {
                          const scenario = allScenarios.find(s => s.semantic_id === record.id)
                          if (scenario) {
                            setSelectedScenario(scenario)
                            loadRecs(record.id)
                            setActiveTab('hierarchy')
                          }
                        }
                      }}
                    >
                      {title}
                    </Button>
                  )
                },
                {
                  title: 'ID',
                  dataIndex: 'id',
                  width: 120,
                  render: (id: string) => <Text code>{id}</Text>
                },
                {
                  title: '描述',
                  dataIndex: 'description',
                  ellipsis: true,
                  width: 300,
                  render: (description: string, record: SearchResult) => (
                    <div>
                      <div>{description || '暂无描述'}</div>
                      {record.metadata?.name_en && (
                        <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                          <Text type="secondary">EN: {record.metadata.name_en}</Text>
                        </div>
                      )}
                      {record.metadata?.description_en && record.metadata.description_en !== description && (
                        <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                          <Text type="secondary">EN: {record.metadata.description_en}</Text>
                        </div>
                      )}
                    </div>
                  )
                },
                {
                  title: '操作',
                  key: 'action',
                  width: 120,
                  render: (_, record: SearchResult) => (
                    <Space>
                      <Button 
                        size="small" 
                        type="link"
                        onClick={() => {
                          if (record.type === 'scenarios') {
                            const scenario = allScenarios.find(s => s.semantic_id === record.id)
                            if (scenario) {
                              setSelectedScenario(scenario)
                              loadRecs(record.id)
                              setActiveTab('hierarchy')
                            }
                          }
                        }}
                      >
                        查看详情
                      </Button>
                    </Space>
                  )
                }
              ]}
            />
          </Card>
        ))}
      </div>
    )
  }

  return (
    <div>
      <div className='page-title'>ACR-AC 数据浏览与检索系统</div>

      {/* Stats Dashboard */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size='small' loading={statsLoading}>
            <Statistic title='科室数' value={stats?.panels ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size='small' loading={statsLoading}>
            <Statistic title='主题数' value={stats?.topics ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size='small' loading={statsLoading}>
            <Statistic title='临床场景数' value={stats?.scenarios ?? 0} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size='small' loading={statsLoading}>
            <Statistic title='检查项目数' value={stats?.procedures ?? 0} />
          </Card>
        </Col>
      </Row>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'hierarchy',
            label: '层次浏览',
            children: (
              <div>
                <Divider />
                <Row gutter={12}>
        {/* Left: Filters + Tree */}
        <Col span={10}>
          <Card size='small' title='筛选与搜索'>
            <Space wrap style={{ width: '100%' }}>
              <Input.Search
                allowClear
                placeholder='按场景ID或描述关键词筛选'
                onChange={(e) => setKeyword(e.target.value)}
                style={{ width: 280 }}
              />
              <Select
                allowClear
                placeholder='妊娠状态'
                style={{ width: 140 }}
                options={filterOptions.pregnancy}
                value={pregnancy}
                onChange={(v) => setPregnancy(v)}
              />
              <Select
                allowClear
                placeholder='急诊程度'
                style={{ width: 140 }}
                options={filterOptions.urgency}
                value={urgency}
                onChange={(v) => setUrgency(v)}
              />
              <Select
                allowClear
                placeholder='风险等级'
                style={{ width: 140 }}
                options={filterOptions.risk}
                value={risk}
                onChange={(v) => setRisk(v)}
              />
              <Select
                allowClear
                placeholder='人群'
                style={{ width: 140 }}
                options={filterOptions.population}
                value={population}
                onChange={(v) => setPopulation(v)}
              />
            </Space>
          </Card>
          <Card size='small' title='科室 / 主题 / 临床场景' style={{ marginTop: 12 }}>
            <Spin spinning={treeLoadingKeys.length > 0}>
              <Tree
                blockNode
                loadData={onLoadData}
                treeData={treeData}
                onSelect={onSelect}
                showLine
                showIcon={false}
              />
            </Spin>
            {panels.length === 0 && (
              <Paragraph type='secondary' style={{ marginTop: 8 }}>未加载到数据。请先在“数据导入”页面完成导入。</Paragraph>
            )}
          </Card>
        </Col>

        {/* Right: Details and Recommendations */}
        <Col span={14}>
          <Card size='small' title={
            <Space>
              <span>推荐与理由</span>
              {selectedScenario?.semantic_id && <Text type='secondary'>({selectedScenario.semantic_id})</Text>}
            </Space>
          }>
            {selectedScenario && (
              <Paragraph type='secondary' style={{ marginBottom: 12 }}>
                {selectedScenario.description_zh || selectedScenario.description_en}
                {' '}
                {selectedScenario.pregnancy_status && <Tag color='purple'>妊娠: {selectedScenario.pregnancy_status}</Tag>}
                {selectedScenario.urgency_level && <Tag color='red'>急诊: {selectedScenario.urgency_level}</Tag>}
                {selectedScenario.risk_level && <Tag color='orange'>风险: {selectedScenario.risk_level}</Tag>}
                {selectedScenario.patient_population && <Tag>人群: {selectedScenario.patient_population}</Tag>}
              </Paragraph>
            )}
            <Table
              rowKey='semantic_id'
              size='small'
              loading={recsLoading}
              dataSource={recs}
              pagination={{ pageSize: 10 }}
              columns={[
                { 
                  title: '分值', 
                  dataIndex: 'appropriateness_rating', 
                  width: 80,
                  sorter: (a: any, b: any) => (b.appropriateness_rating || 0) - (a.appropriateness_rating || 0),
                  defaultSortOrder: 'descend' as const,
                  render: (value: number) => value ? <Text strong style={{ color: value >= 7 ? '#52c41a' : value >= 4 ? '#faad14' : '#ff4d4f' }}>{value}</Text> : '-'
                },
                { title: '类别', dataIndex: 'appropriateness_category_zh', width: 160 },
                { title: '检查项目', dataIndex: 'procedure_name_zh', width: 300, ellipsis: true },
                { title: '模态', dataIndex: 'modality', width: 100 },
                { title: '成人RRL', dataIndex: 'adult_radiation_dose', width: 100 },
                { title: '儿童RRL', dataIndex: 'pediatric_radiation_dose', width: 100 },
                { title: '证据', dataIndex: 'evidence_level', width: 120 },
                {
                  title: '操作',
                  key: 'action',
                  width: 100,
                  render: (_, record: any) => (
                    <Button
                      type="link"
                      size="small"
                      icon={<EyeOutlined />}
                      onClick={() => showReasoningDetail(
                        record.procedure_name_zh || '未知项目', 
                        record.reasoning_zh || '暂无详细理由'
                      )}
                    >
                      理由
                    </Button>
                  )
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
              </div>
            )
          },
          {
            key: 'search',
            label: '智能检索',
            children: (
              <div>
                {/* 搜索配置 */}
                <Card size="small" style={{ marginBottom: 16 }}>
                  <Form layout="inline">
                    <Form.Item label="搜索模式">
                      <Radio.Group value={searchMode} onChange={(e) => setSearchMode(e.target.value)}>
                        <Radio.Button value="keyword">
                          <SearchOutlined /> 关键词
                        </Radio.Button>
                        <Radio.Button value="vector">
                          <RobotOutlined /> 向量
                        </Radio.Button>
                        <Radio.Button value="combined">
                          <FilterOutlined /> 组合
                        </Radio.Button>
                      </Radio.Group>
                    </Form.Item>
                    <Form.Item label="搜索字段">
                      <Select
                        mode="multiple"
                        value={searchFields}
                        onChange={setSearchFields}
                        style={{ width: 300 }}
                        options={[
                          { label: '科室', value: 'panels' },
                          { label: '主题', value: 'topics' },
                          { label: '临床场景', value: 'scenarios' },
                          { label: '检查项目', value: 'procedures' }
                        ]}
                      />
                    </Form.Item>
                    {searchMode === 'vector' || searchMode === 'combined' ? (
                      <Form.Item label="相似度阈值">
                        <Space>
                          <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.05"
                            value={similarityThreshold}
                            onChange={(e) => setSimilarityThreshold(parseFloat(e.target.value))}
                            style={{ width: 150 }}
                            title={`相似度阈值: ${similarityThreshold.toFixed(2)}`}
                            aria-label="相似度阈值调整"
                          />
                          <Text strong>{similarityThreshold.toFixed(2)}</Text>
                          <Button 
                            size="small" 
                            onClick={() => setSimilarityThreshold(0.3)}
                          >
                            重置
                          </Button>
                        </Space>
                      </Form.Item>
                    ) : null}
                  </Form>
                  
                  {/* 搜索模式说明 */}
                  <Collapse size="small" style={{ marginTop: 12 }}>
                    <Collapse.Panel header="搜索模式说明" key="help">
                      <div style={{ padding: '8px 0' }}>
                        <Space direction="vertical" size="small" style={{ width: '100%' }}>
                          <div>
                            <Text strong>🔍 关键词搜索：</Text>
                            <Text type="secondary">基于文本匹配的传统搜索，支持精确匹配和模糊搜索</Text>
                          </div>
                          <div>
                            <Text strong>🤖 向量搜索：</Text>
                            <Text type="secondary">基于AI语义理解的智能搜索，能理解同义词和语义相似性</Text>
                          </div>
                          <div>
                            <Text strong>🔄 组合搜索：</Text>
                            <Text type="secondary">同时执行关键词和向量搜索，去重合并结果，提供最全面的搜索结果</Text>
                          </div>
                          <Divider style={{ margin: '8px 0' }} />
                          <div>
                            <Text strong>💡 多关键字组合查询方法：</Text>
                            <ul style={{ margin: '4px 0', paddingLeft: '20px' }}>
                              <li><Text code>空格分隔</Text>：多个关键词用空格分隔，如"胸痛 呼吸困难"</li>
                              <li><Text code>引号精确匹配</Text>：用引号包围精确短语，如"急性心肌梗死"</li>
                              <li><Text code>布尔操作符</Text>：使用 AND、OR、NOT 进行逻辑组合</li>
                              <li><Text code>通配符</Text>：使用 * 进行模糊匹配，如"CT*"匹配所有CT相关项目</li>
                              <li><Text code>字段限定</Text>：指定搜索特定字段，如"科室:心内科"</li>
                            </ul>
                          </div>
                          <div>
                            <Text strong>📊 相似度评分：</Text>
                            <Text type="secondary">向量搜索结果显示相似度百分比，绿色(&gt;70%)、橙色(50-70%)、红色(&lt;50%)</Text>
                          </div>
                        </Space>
                      </div>
                    </Collapse.Panel>
                  </Collapse>
                  
                  <Divider />
                  <Space.Compact style={{ width: '100%' }}>
                    <Input
                      placeholder="输入搜索关键词，支持多关键字组合查询..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onPressEnter={performSearch}
                      style={{ flex: 1 }}
                    />
                    <Button 
                      type="primary" 
                      icon={<SearchOutlined />}
                      loading={searchLoading}
                      onClick={performSearch}
                    >
                      搜索
                    </Button>
                  </Space.Compact>
                </Card>

                {/* 搜索统计 */}
                {searchResults.length > 0 && (
                  <Card size="small" style={{ marginBottom: 16 }}>
                    <Space wrap>
                      <Text strong>搜索结果统计：</Text>
                      <Tag color="blue">总计 {searchResults.length} 条</Tag>
                      {searchMode === 'vector' || searchMode === 'combined' ? (
                        <Tag color="orange">相似度≥{similarityThreshold.toFixed(2)}: {searchResults.filter(r => (r.score || 0) >= similarityThreshold).length} 条</Tag>
                      ) : null}
                      {searchMode === 'combined' && (
                        <>
                          <Tag color="purple">关键词 {searchResults.filter(r => r.metadata?.searchSource === 'keyword').length} 条</Tag>
                          <Tag color="cyan">向量 {searchResults.filter(r => r.metadata?.searchSource === 'vector').length} 条</Tag>
                          <Tag color="green">组合 {searchResults.filter(r => r.metadata?.searchSource === 'both').length} 条</Tag>
                        </>
                      )}
                    </Space>
                  </Card>
                )}

                {/* 搜索结果 */}
                {renderSearchResults()}
              </div>
            )
          },
          {
            key: 'analytics',
            label: (
              <span>
                <BarChartOutlined />
                数据关系看板
              </span>
            ),
            children: <EnhancedAnalyticsDashboard />
          }
        ]}
      />

      {/* 推荐理由详细Modal */}
      <Modal
        title={reasoningModal.title}
        open={reasoningModal.visible}
        onCancel={() => setReasoningModal({ visible: false, title: '', content: '' })}
        footer={[
          <Button key="close" onClick={() => setReasoningModal({ visible: false, title: '', content: '' })}>
            关闭
          </Button>
        ]}
        width={800}
      >
        <div style={{ 
          maxHeight: '60vh', 
          overflowY: 'auto',
          padding: '16px',
          backgroundColor: '#fafafa',
          borderRadius: '6px',
          whiteSpace: 'pre-wrap',
          lineHeight: '1.6'
        }}>
          {reasoningModal.content}
        </div>
      </Modal>
    </div>
  )
}

export default DataBrowser
