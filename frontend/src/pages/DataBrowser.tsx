import React, { useEffect, useState } from 'react'
import { Card, Col, Input, Row, Select, Table, Typography, message } from 'antd'
import { api } from '../api/http'

const { Paragraph } = Typography

const DataBrowser: React.FC = () => {
  const [panels, setPanels] = useState<any[]>([])
  const [topics, setTopics] = useState<any[]>([])
  const [scenarios, setScenarios] = useState<any[]>([])
  const [recs, setRecs] = useState<any[]>([])
  const [panel, setPanel] = useState<string>('')
  const [topic, setTopic] = useState<string>('')
  const [scenario, setScenario] = useState<string>('')
  const [q, setQ] = useState('')

  const loadPanels = async () => {
    try {
      const r = await api.get('/api/v1/acrac/data/panels')
      setPanels(r.data)
    } catch (e:any) {
      message.error('加载科室失败: '+(e?.response?.data?.detail || e.message))
    }
  }
  const loadTopics = async (pid: string) => {
    try {
      const r = await api.get('/api/v1/acrac/data/topics/by-panel', { params: { panel_id: pid }})
      setTopics(r.data)
    } catch (e:any) {
      message.error('加载主题失败: '+(e?.response?.data?.detail || e.message))
    }
  }
  const loadScenarios = async (tid: string) => {
    try {
      const r = await api.get('/api/v1/acrac/data/scenarios/by-topic', { params: { topic_id: tid }})
      setScenarios(r.data)
    } catch (e:any) {
      message.error('加载场景失败: '+(e?.response?.data?.detail || e.message))
    }
  }
  const loadRecs = async (sid: string) => {
    try {
      const r = await api.get('/api/v1/acrac/data/recommendations', { params: { scenario_id: sid, page: 1, size: 50 }})
      setRecs(r.data.items || [])
    } catch (e:any) {
      message.error('加载推荐失败: '+(e?.response?.data?.detail || e.message))
    }
  }

  useEffect(()=>{ loadPanels() }, [])

  return (
    <div>
      <div className='page-title'>分层浏览（科室 → 主题 → 临床场景 → 推荐与理由）</div>
      <Row gutter={12}>
        <Col span={6}>
          <Card title='科室' size='small'>
            <Select
              value={panel||undefined}
              onChange={(v)=>{ setPanel(v); setTopic(''); setScenario(''); setScenarios([]); setRecs([]); loadTopics(v) }}
              options={panels.map(p=> ({ value: p.semantic_id, label: `${p.semantic_id} ${p.name_zh} (${p.topics_count})` }))}
              style={{ width: '100%' }}
              placeholder='选择科室'
            />
            <Paragraph type='secondary' style={{ marginTop: 8 }}>共 {panels.length} 个科室</Paragraph>
          </Card>
        </Col>
        <Col span={6}>
          <Card title='主题' size='small'>
            <Select
              value={topic||undefined}
              onChange={(v)=>{ setTopic(v); setScenario(''); setRecs([]); loadScenarios(v) }}
              options={topics.map(t=> ({ value: t.semantic_id, label: `${t.semantic_id} ${t.name_zh} (${t.scenarios_count})` }))}
              style={{ width: '100%' }}
              placeholder='选择主题'
              disabled={!panel}
            />
            <Paragraph type='secondary' style={{ marginTop: 8 }}>共 {topics.length} 个主题</Paragraph>
          </Card>
        </Col>
        <Col span={12}>
          <Card title='临床场景' size='small'>
            <Input.Search placeholder='搜索当前主题中的场景' allowClear onSearch={(v)=>setQ(v)} style={{ marginBottom: 8 }} />
            <Table
              rowKey='semantic_id'
              size='small'
              dataSource={scenarios.filter(s=>!q || (s.description_zh||'').includes(q))}
              onRow={(r)=>({ onClick:()=>{ setScenario(r.semantic_id); loadRecs(r.semantic_id) } })}
              pagination={{ pageSize: 8 }}
              columns={[
                { title:'ID', dataIndex:'semantic_id', width:100 },
                { title:'描述', dataIndex:'description_zh' },
                { title:'检查数量', dataIndex:'recs_count', width:100 },
                { title:'妊娠', dataIndex:'pregnancy_status', width:120 },
                { title:'急诊', dataIndex:'urgency_level', width:120 },
              ]}
            />
          </Card>
        </Col>
      </Row>
      <Row gutter={12} style={{ marginTop: 12 }}>
        <Col span={24}>
          <Card title={`推荐与理由 ${scenario ? '('+scenario+')' : ''}`} size='small'>
              <Table
                rowKey='semantic_id'
                size='small'
                dataSource={recs}
                pagination={{ pageSize: 10 }}
                columns={[
                { title:'类别', dataIndex:'appropriateness_category_zh', width:160 },
                { title:'分值', dataIndex:'appropriateness_rating', width:80 },
                { title:'检查项目', dataIndex:'procedure_name_zh', width:260 },
                { title:'理由', dataIndex:'reasoning_zh' },
                { title:'成人RRL', dataIndex:'adult_radiation_dose', width:100 },
                { title:'儿童RRL', dataIndex:'pediatric_radiation_dose', width:100 },
                { title:'证据', dataIndex:'evidence_level', width:120 },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default DataBrowser
