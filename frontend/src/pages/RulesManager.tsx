import React, { useEffect, useMemo, useState } from 'react'
import { Button, Card, Space, message, Tooltip, Input, Tabs, Table, Tag, Modal, Form, InputNumber, Switch, Select, Popconfirm, Divider, Radio, Collapse, Typography, Alert } from 'antd'
import { QuestionCircleOutlined, InfoCircleOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { api } from '../api/http'

const { TextArea } = Input

type Rule = {
  id: string
  enabled?: boolean
  priority?: number
  condition?: any
  action?: any
}

type RulePack = {
  id: string
  scope: 'pre' | 'rerank' | 'post_llm' | string
  enabled?: boolean
  priority?: number
  rules?: Rule[]
}

type RulesContent = { packs?: RulePack[] }

const emptyContent: RulesContent = { packs: [] }

const scopes = [
  { label: '检索前(pre)', value: 'pre' },
  { label: '重排(rerank)', value: 'rerank' },
  { label: 'LLM后处理(post_llm)', value: 'post_llm' },
]

const RulesManager: React.FC = () => {
  const [content, setContent] = useState<string>('')
  const [obj, setObj] = useState<RulesContent>(emptyContent)
  const [loading, setLoading] = useState(false)
  const [activeKey, setActiveKey] = useState<string>('visual')
  const [helpOpen, setHelpOpen] = useState<boolean>(false)

  const [selectedPackId, setSelectedPackId] = useState<string>('')
  const selectedPack = useMemo(() => (obj.packs || []).find(p => p.id === selectedPackId), [obj, selectedPackId])

  // modals
  const [packModalOpen, setPackModalOpen] = useState(false)
  const [packEditing, setPackEditing] = useState<RulePack | null>(null)
  const [ruleModalOpen, setRuleModalOpen] = useState(false)
  const [ruleEditing, setRuleEditing] = useState<Rule | null>(null)

  // ---------- load/save ----------
  const load = async () => {
    try {
      const r = await api.get('/api/v1/acrac/rag-llm/rules-packs')
      const data = (r.data?.content || {}) as RulesContent
      const normalized: RulesContent = {
        packs: Array.isArray(data.packs) ? data.packs : []
      }
      setObj(normalized)
      setContent(JSON.stringify(normalized, null, 2))
      if (!selectedPackId && normalized.packs && normalized.packs[0]) {
        setSelectedPackId(normalized.packs[0].id)
      }
    } catch (e:any) {
      message.error('读取规则失败: ' + (e?.response?.data?.detail || e.message))
    }
  }

  useEffect(() => { load() }, [])

  const validateRulesContent = (payload: RulesContent): { ok: boolean; errors: string[] } => {
    const errors: string[] = []
    if (!payload || !Array.isArray(payload.packs)) {
      return { ok: false, errors: ['结构无效：缺少 packs 数组'] }
    }
    const packIds = new Set<string>()
    const allowedScopes = new Set(['pre','rerank','post_llm'])
    const allowedActions = new Set(['warn','boost','filter','fix','override'])
    payload.packs.forEach((p, pi) => {
      if (!p || !p.id || typeof p.id !== 'string') errors.push(`第 ${pi+1} 个 Pack 缺少 id`)
      if (p && p.id) {
        if (packIds.has(p.id)) errors.push(`Pack id 重复：${p.id}`)
        packIds.add(p.id)
      }
      if (!p || !p.scope || !allowedScopes.has(String(p.scope))) errors.push(`Pack ${p?.id || (pi+1)} 的 scope 无效（需为 pre/rerank/post_llm）`)
      if (!Array.isArray(p.rules)) errors.push(`Pack ${p?.id || (pi+1)} 缺少 rules 数组`)
      const ruleIds = new Set<string>()
      ;(p.rules || []).forEach((r, ri) => {
        if (!r || !r.id || typeof r.id !== 'string') errors.push(`Pack ${p?.id}: 第 ${ri+1} 条规则缺少 id`)
        if (r && r.id) {
          if (ruleIds.has(r.id)) errors.push(`Pack ${p?.id} 的规则 id 重复：${r.id}`)
          ruleIds.add(r.id)
        }
        if (!r || typeof r.condition !== 'object') errors.push(`规则 ${r?.id || ri+1} 的 condition 应为对象`)
        if (!r || typeof r.action !== 'object') errors.push(`规则 ${r?.id || ri+1} 的 action 应为对象`)
        const typ = (r?.action as any)?.type
        if (!allowedActions.has(String(typ))) errors.push(`规则 ${r?.id}: action.type 无效（支持 warn/boost/filter/fix/override）`)
        if (typ === 'boost') {
          const by = Number((r?.action as any)?.by)
          if (!Number.isFinite(by)) errors.push(`规则 ${r?.id}: boost 需要数值 by`)
          if (Number.isFinite(by) && (by < -1 || by > 5)) errors.push(`规则 ${r?.id}: boost.by 建议在 [-1, 5] 范围内`)
        }
        if (typ === 'fix') {
          const field = (r?.action as any)?.field
          const strategy = (r?.action as any)?.strategy
          if (field !== 'filter_procedures_by_keywords') errors.push(`规则 ${r?.id}: fix 目前仅支持 field=filter_procedures_by_keywords`)
          if (strategy !== 'deny_if_any_contains') errors.push(`规则 ${r?.id}: fix.strategy 需为 deny_if_any_contains`)
          const kws = (r?.action as any)?.keywords
          if (!Array.isArray(kws) || kws.some((x:any)=>typeof x!=='string')) errors.push(`规则 ${r?.id}: fix.keywords 需为字符串数组`)
        }
        if (typ === 'override') {
          const field = (r?.action as any)?.field
          if (!field || typeof field !== 'string') errors.push(`规则 ${r?.id}: override 需提供 field 字段名`)
        }
      })
    })
    return { ok: errors.length === 0, errors }
  }

  const postSave = async (payload: RulesContent) => {
    const v = validateRulesContent(payload)
    if (!v.ok) {
      Modal.error({
        title: '保存失败：规则配置不合法',
        width: 720,
        content: (
          <div>
            <div style={{ marginBottom: 8 }}>请根据以下错误进行修正：</div>
            <pre className='mono' style={{ whiteSpace:'pre-wrap' }}>{(v.errors || []).map((e,i)=>`• ${e}`).join('\n')}</pre>
          </div>
        )
      })
      return
    }
    setLoading(true)
    try {
      await api.post('/api/v1/acrac/rag-llm/rules-packs', { content: payload })
      message.success('规则已保存并热重载')
      Modal.info({
        title: '规则已生效（已热重载）',
        width: 720,
        icon: <InfoCircleOutlined />,
        content: (
          <div>
            <Typography.Paragraph>
              规则在<b>重排（rerank）</b>与<b>LLM后处理（post_llm）</b>阶段按优先级执行。建议先在“试运行”或“仅审计”模式验证命中与影响，再关闭仅审计。
            </Typography.Paragraph>
            <Typography.Paragraph>
              立即体验：前往“试运行”标签，选择阶段、输入示例 Query 与场景列表，点击“试运行”查看审计日志与输出变化。
            </Typography.Paragraph>
            <Alert type='info' showIcon message='提示' description='可在“模板库”插入常用规则，再按需调整。' />
          </div>
        )
      })
      setObj(payload)
      setContent(JSON.stringify(payload, null, 2))
    } catch (e:any) {
      message.error('保存失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const saveJson = async () => {
    try {
      const parsed = JSON.parse(content || '{}') as RulesContent
      const normalized: RulesContent = {
        packs: Array.isArray(parsed.packs) ? parsed.packs : []
      }
      await postSave(normalized)
    } catch (e:any) {
      message.error('JSON 解析失败: ' + e.message)
    }
  }

  const formatJson = () => {
    try {
      const parsed = JSON.parse(content || '{}')
      setContent(JSON.stringify(parsed, null, 2))
    } catch {
      message.warning('JSON 无法格式化，请检查语法')
    }
  }

  // ---------- visual helpers ----------
  const upsertPack = (pack: RulePack, originalId?: string) => {
    const packs = [...(obj.packs || [])]
    const idx = packs.findIndex(p => p.id === (originalId || pack.id))
    if (idx >= 0) packs[idx] = pack
    else packs.push(pack)
    const next = { packs }
    setObj(next)
    setContent(JSON.stringify(next, null, 2))
    if (!selectedPackId || originalId === selectedPackId) setSelectedPackId(pack.id)
  }

  const deletePack = (id: string) => {
    const packs = (obj.packs || []).filter(p => p.id !== id)
    const next = { packs }
    setObj(next)
    setContent(JSON.stringify(next, null, 2))
    if (selectedPackId === id) setSelectedPackId(packs[0]?.id || '')
  }

  const upsertRule = (rule: Rule, packId: string, originalId?: string) => {
    const packs = [...(obj.packs || [])]
    const pIdx = packs.findIndex(p => p.id === packId)
    if (pIdx < 0) return
    const prules = [...(packs[pIdx].rules || [])]
    const rIdx = prules.findIndex(r => r.id === (originalId || rule.id))
    if (rIdx >= 0) prules[rIdx] = rule
    else prules.push(rule)
    packs[pIdx] = { ...(packs[pIdx] || {}), rules: prules }
    const next = { packs }
    setObj(next)
    setContent(JSON.stringify(next, null, 2))
  }

  const deleteRule = (ruleId: string, packId: string) => {
    const packs = [...(obj.packs || [])]
    const pIdx = packs.findIndex(p => p.id === packId)
    if (pIdx < 0) return
    const prules = (packs[pIdx].rules || []).filter(r => r.id !== ruleId)
    packs[pIdx] = { ...(packs[pIdx] || {}), rules: prules }
    const next = { packs }
    setObj(next)
    setContent(JSON.stringify(next, null, 2))
  }

  // ---------- columns ----------
  const packCols: ColumnsType<RulePack> = [
    { title: 'Pack ID', dataIndex: 'id', key: 'id' },
    { title: 'Scope', dataIndex: 'scope', key: 'scope', render: (v) => <Tag>{v}</Tag> },
    { title: '启用', dataIndex: 'enabled', key: 'enabled', render: (v) => <Tag color={v? 'green':'default'}>{v? '是':'否'}</Tag> },
    { title: '优先级', dataIndex: 'priority', key: 'priority', width: 90 },
    { title: '规则数', key: 'rules', render: (_, r) => (r.rules?.length || 0), width: 90 },
    { title: '操作', key: 'op', width: 220, render: (_, r) => (
      <Space>
        <Button size='small' onClick={() => { setPackEditing(r); setPackModalOpen(true) }}>编辑</Button>
        <Popconfirm title='确认删除该 Pack 及其规则？' onConfirm={() => deletePack(r.id)}>
          <Button danger size='small'>删除</Button>
        </Popconfirm>
        <Button size='small' type={selectedPackId===r.id?'primary':'default'} onClick={() => setSelectedPackId(r.id)}>查看规则</Button>
      </Space>
    )}
  ]

  const ruleCols: ColumnsType<Rule> = [
    { title: 'Rule ID', dataIndex: 'id', key: 'id' },
    { title: '启用', dataIndex: 'enabled', key: 'enabled', render: (v) => <Tag color={v? 'green':'default'}>{v? '是':'否'}</Tag>, width: 90 },
    { title: '优先级', dataIndex: 'priority', key: 'priority', width: 90 },
    { title: '动作', dataIndex: 'action', key: 'action', ellipsis: true, render: (a) => <span className='mono'>{a?.type || '-'}</span> },
    { title: '操作', key: 'op', width: 200, render: (_, r) => (
      <Space>
        <Button size='small' onClick={() => { setRuleEditing(r); setRuleModalOpen(true) }}>编辑</Button>
        <Popconfirm title='确认删除该规则？' onConfirm={() => deleteRule(r.id, selectedPackId)}>
          <Button danger size='small'>删除</Button>
        </Popconfirm>
      </Space>
    )}
  ]

  // ---------- modals content ----------
  const PackForm: React.FC<{ data?: RulePack, onOk: (v: RulePack, originalId?: string)=>void, onCancel: ()=>void }> = ({ data, onOk, onCancel }) => {
    const [form] = Form.useForm<RulePack & { originalId?: string }>()
    useEffect(() => { form.setFieldsValue({ ...data, originalId: data?.id }) }, [data])
    const submit = () => {
      form.validateFields().then(v => {
        const pack: RulePack = {
          id: v.id.trim(),
          scope: v.scope,
          enabled: !!v.enabled,
          priority: v.priority ?? 100,
          rules: data?.rules || [],
        }
        onOk(pack, (v as any).originalId)
      }).catch(() => {})
    }
    return (
      <Form form={form} layout='vertical' initialValues={{ enabled: true, priority: 100, scope: 'rerank' }}>
        <Form.Item name='originalId' hidden><Input /></Form.Item>
        <Form.Item name='id' label={<span>Pack ID <Tooltip title='规则包唯一标识，用于区分不同业务主题或阶段。'><QuestionCircleOutlined /></Tooltip></span>} rules={[{ required: true, message: '请输入 Pack ID' }]}>
          <Input placeholder='唯一ID，如 pregnancy_safety' />
        </Form.Item>
        <Form.Item name='scope' label={<span>作用域 <Tooltip title='规则执行阶段：pre（检索前，主要审计）、rerank（重排加权/过滤）、post_llm（LLM后处理）'><QuestionCircleOutlined /></Tooltip></span>} rules={[{ required: true }]}>
          <Select options={scopes} />
        </Form.Item>
        <Space size='large'>
          <Form.Item name='enabled' label={<span>启用 <Tooltip title='关闭后该 Pack 下所有规则不生效'><QuestionCircleOutlined /></Tooltip></span>} valuePropName='checked'>
            <Switch />
          </Form.Item>
          <Form.Item name='priority' label={<span>优先级 <Tooltip title='同一阶段多个 Pack 的执行顺序，数值越小优先级越高'><QuestionCircleOutlined /></Tooltip></span>}>
            <InputNumber min={0} max={1000} />
          </Form.Item>
        </Space>
        <Divider />
        <Space>
          <Button onClick={onCancel}>取消</Button>
          <Button type='primary' onClick={submit}>确定</Button>
        </Space>
      </Form>
    )
  }

  const RuleForm: React.FC<{ data?: Rule, onOk: (v: Rule, originalId?: string)=>void, onCancel: ()=>void }> = ({ data, onOk, onCancel }) => {
    const [form] = Form.useForm<any>()
    const [condText, setCondText] = useState<string>('')
    const [actText, setActText] = useState<string>('')
    const [condErr, setCondErr] = useState<string>('')
    const [actErr, setActErr] = useState<string>('')
    // quick builders state
    const [groupOp, setGroupOp] = useState<'and'|'or'>('and')
    const [rows, setRows] = useState<Array<{ path: string; op: string; value: string }>>([
      { path: 'query_signals.pregnancy_status', op: 'in', value: '妊娠/围产,妊娠' }
    ])
    const [actionType, setActionType] = useState<string>('warn')
    const [actionPayload, setActionPayload] = useState<{ by?: number; message?: string; keywords?: string; field?: string; strategy?: string; overrideField?: string; overrideValue?: string }>({})
    useEffect(() => {
      form.setFieldsValue({ id: data?.id, enabled: data?.enabled ?? true, priority: data?.priority ?? 100, originalId: data?.id })
      setCondText(data?.condition ? JSON.stringify(data.condition, null, 2) : '{ }')
      setActText(data?.action ? JSON.stringify(data.action, null, 2) : '{ "type": "warn" }')
      setCondErr(''); setActErr('')
      // reset builders to defaults on open
      setGroupOp('and');
      setRows([{ path: 'query_signals.pregnancy_status', op: 'in', value: '妊娠/围产,妊娠' }])
      setActionType('warn')
      setActionPayload({})
    }, [data])
    const submit = () => {
      try {
        const cond = condText ? JSON.parse(condText) : {}
        setCondErr('')
        try {
          const act = actText ? JSON.parse(actText) : {}
          setActErr('')
          form.validateFields().then(v => {
            const rule: Rule = {
              id: (v.id || '').trim(),
              enabled: !!v.enabled,
              priority: v.priority ?? 100,
              condition: cond,
              action: act,
            }
            onOk(rule, v.originalId)
          })
        } catch (e:any) {
          setActErr(e.message || 'action 不是合法 JSON')
        }
      } catch (e:any) {
        setCondErr(e.message || 'condition 不是合法 JSON')
      }
    }
    return (
      <Form form={form} layout='vertical'>
        <Form.Item name='originalId' hidden><Input /></Form.Item>
        <Form.Item name='id' label={<span>Rule ID <Tooltip title='规则唯一标识，便于追踪审计日志'><QuestionCircleOutlined /></Tooltip></span>} rules={[{ required: true, message: '请输入 Rule ID' }]}>
          <Input placeholder='唯一ID，如 avoid_high_radiation_pregnancy' />
        </Form.Item>
        <Space size='large'>
          <Form.Item name='enabled' label={<span>启用 <Tooltip title='关闭后该规则不生效'><QuestionCircleOutlined /></Tooltip></span>} valuePropName='checked'>
            <Switch />
          </Form.Item>
          <Form.Item name='priority' label={<span>优先级 <Tooltip title='同一 Pack 内的执行顺序，数值越小优先'><QuestionCircleOutlined /></Tooltip></span>}>
            <InputNumber min={0} max={1000} />
          </Form.Item>
        </Space>
        <Form.Item label={<span>条件 (condition JSON) <Tooltip title='支持 and/or/not/eq/ne/gt/gte/lt/lte/in/any_in/all_in/contains/exists/regex；使用如 query_signals.pregnancy_status 这样的点路径取值'><QuestionCircleOutlined /></Tooltip></span>}>
          <TextArea rows={6} value={condText} onChange={e => setCondText(e.target.value)} className='mono' />
          {condErr ? <div style={{ color: 'red' }}>{condErr}</div> : null}
        </Form.Item>
        <Collapse size='small' style={{ marginBottom: 8 }} items={[{
          key: 'qb',
          label: '快速构建（可选）',
          children: (
            <div>
              <div style={{ fontWeight: 600, margin: '6px 0' }}>条件构建器</div>
              <Space direction='vertical' style={{ width: '100%' }}>
                <Space>
                  <span>组合方式：</span>
                  <Radio.Group value={groupOp} onChange={(e)=>setGroupOp(e.target.value)}>
                    <Radio.Button value='and'>AND</Radio.Button>
                    <Radio.Button value='or'>OR</Radio.Button>
                  </Radio.Group>
                </Space>
                {rows.map((r, idx) => (
                  <Space key={idx} wrap>
                    <Select
                      value={r.path}
                      style={{ width: 220 }}
                      options={[
                        { label: 'query_signals.pregnancy_status', value: 'query_signals.pregnancy_status' },
                        { label: 'query_signals.keywords', value: 'query_signals.keywords' },
                        { label: 'scenario.semantic_id', value: 'scenario.semantic_id' },
                        { label: 'scenario.modality', value: 'scenario.modality' },
                        { label: 'scenario.risk_level', value: 'scenario.risk_level' },
                      ]}
                      onChange={(v)=>{
                        const next=[...rows]; next[idx] = { ...r, path: v }; setRows(next)
                      }}
                    />
                    <Select
                      value={r.op}
                      style={{ width: 140 }}
                      options={[
                        { label:'eq', value:'eq' },
                        { label:'ne', value:'ne' },
                        { label:'in', value:'in' },
                        { label:'any_in', value:'any_in' },
                        { label:'all_in', value:'all_in' },
                        { label:'contains', value:'contains' },
                        { label:'regex', value:'regex' },
                        { label:'exists', value:'exists' },
                        { label:'gt', value:'gt' },
                        { label:'gte', value:'gte' },
                        { label:'lt', value:'lt' },
                        { label:'lte', value:'lte' },
                      ]}
                      onChange={(v)=>{ const next=[...rows]; next[idx] = { ...r, op: v }; setRows(next) }}
                    />
                    <Input
                      style={{ width: 260 }}
                      placeholder={r.op?.includes('in') ? '多个值用逗号分隔' : '值'}
                      value={r.value}
                      onChange={(e)=>{ const next=[...rows]; next[idx] = { ...r, value: e.target.value }; setRows(next) }}
                    />
                    <Button size='small' danger onClick={()=>{ const next=rows.filter((_,i)=>i!==idx); setRows(next.length?next:[{ path:'query_signals.pregnancy_status', op:'in', value:'妊娠/围产,妊娠' }]) }}>删除</Button>
                  </Space>
                ))}
                <Button size='small' onClick={()=> setRows([...rows, { path: 'query_signals.keywords', op: 'any_in', value: '雷击样,TCH,SAH' }])}>+ 添加条件</Button>
                <div>
                  <Button size='small' type='dashed' onClick={() => {
                    try {
                      const conds = rows.map(r => {
                        const path = r.path || ''
                        const op = r.op || 'eq'
                        if (op === 'exists') return { exists: [path, true] }
                        if (op.includes('in')) {
                          const arr = (r.value || '').split(',').map(s=>s.trim()).filter(Boolean)
                          return { [op]: [path, arr] }
                        }
                        return { [op]: [path, r.value] }
                      })
                      const built = conds.length>1 ? { [groupOp]: conds } : (conds[0] || {})
                      setCondText(JSON.stringify(built, null, 2))
                      message.success('已应用到条件 JSON')
                    } catch(e:any) {
                      message.error('生成条件失败: ' + (e?.message||''))
                    }
                  }}>应用到条件</Button>
                </div>
              </Space>

              <Divider />
              <div style={{ fontWeight: 600, margin: '6px 0' }}>动作构建器</div>
              <Space wrap>
                <Select
                  value={actionType}
                  onChange={(v)=>{ setActionType(v); setActionPayload({}) }}
                  options={[
                    { label:'warn（仅记录）', value:'warn' },
                    { label:'boost（加权）', value:'boost' },
                    { label:'filter（过滤）', value:'filter' },
                    { label:'fix（按关键词过滤）', value:'fix' },
                    { label:'override（覆盖字段）', value:'override' },
                  ]}
                />
                {actionType==='warn' && (
                  <Input style={{ width: 320 }} placeholder='message' value={actionPayload.message} onChange={(e)=>setActionPayload({ ...actionPayload, message: e.target.value })} />
                )}
                {actionType==='boost' && (
                  <InputNumber placeholder='by' value={actionPayload.by} onChange={(v)=>setActionPayload({ ...actionPayload, by: Number(v) })} />
                )}
                {actionType==='fix' && (
                  <>
                    <Select style={{ width: 260 }} value={actionPayload.strategy || 'deny_if_any_contains'} onChange={(v)=>setActionPayload({ ...actionPayload, strategy: v })} options={[{label:'deny_if_any_contains', value:'deny_if_any_contains'}]} />
                    <Input style={{ width: 320 }} placeholder='keywords，逗号分隔，例如 CTA,增强CT,核医学' value={actionPayload.keywords} onChange={(e)=>setActionPayload({ ...actionPayload, keywords: e.target.value })} />
                  </>
                )}
                {actionType==='override' && (
                  <>
                    <Input style={{ width: 240 }} placeholder='field，如 summary' value={actionPayload.overrideField} onChange={(e)=>setActionPayload({ ...actionPayload, overrideField: e.target.value })} />
                    <Input style={{ width: 320 }} placeholder='value（文本）' value={actionPayload.overrideValue} onChange={(e)=>setActionPayload({ ...actionPayload, overrideValue: e.target.value })} />
                  </>
                )}
                <Button size='small' type='dashed' onClick={() => {
                  try {
                    let a: any = { type: actionType }
                    if (actionType==='warn') a.message = actionPayload.message || ''
                    if (actionType==='boost') a.by = Number(actionPayload.by || 0)
                    if (actionType==='fix') { a.field = 'filter_procedures_by_keywords'; a.strategy = actionPayload.strategy || 'deny_if_any_contains'; a.keywords = (actionPayload.keywords||'').split(',').map(s=>s.trim()).filter(Boolean) }
                    if (actionType==='override') { a.field = actionPayload.overrideField || ''; a.value = actionPayload.overrideValue ?? '' }
                    setActText(JSON.stringify(a, null, 2))
                    message.success('已应用到动作 JSON')
                  } catch(e:any) {
                    message.error('生成动作失败: ' + (e?.message||''))
                  }
                }}>应用到动作</Button>
              </Space>
            </div>
          )
        }]} />

        <Form.Item label={<span>动作 (action JSON) <Tooltip title='动作类型：warn（仅记录）、boost（加权）、filter（过滤）、fix（关键词过滤）、override（覆盖字段）'><QuestionCircleOutlined /></Tooltip></span>}>
          <TextArea rows={6} value={actText} onChange={e => setActText(e.target.value)} className='mono' />
          {actErr ? <div style={{ color: 'red' }}>{actErr}</div> : null}
        </Form.Item>
        <Divider />
        <Space>
          <Button onClick={onCancel}>取消</Button>
          <Button type='primary' onClick={submit}>确定</Button>
        </Space>
      </Form>
    )
  }

  // ---------- render ----------
  return (
    <div>
      <div className='page-title'>规则管理</div>
      <Card style={{ marginBottom: 12 }}>
        <Typography.Paragraph>
          <b>概念：</b>规则由<b>规则包 Pack</b>与<b>规则 Rule</b>组成。Pack 绑定到某个<b>作用域 Scope</b>（pre/rerank/post_llm），其中包含多条 Rule；Rule 由<b>条件 condition</b>与<b>动作 action</b>构成。
        </Typography.Paragraph>
        <Typography.Paragraph>
          <b>生效路径：</b>服务启动后会加载配置文件（默认 `backend/config/rules_packs.json`），在<b>重排</b>与<b>LLM后处理</b>阶段按优先级执行。可在页面顶部切换“启用/仅审计”。
        </Typography.Paragraph>
        <Typography.Paragraph>
          <b>使用步骤：</b>（1）新增 Pack 并选择 Scope；（2）为该 Pack 新增 Rule，可通过“快速构建器”生成条件与动作；（3）点击“保存”热重载；（4）在“试运行”中用示例入参验证；（5）观察“仅审计”命中情况，确认后再关闭仅审计。
        </Typography.Paragraph>
        <Alert type='info' showIcon message='提示' description='若你熟悉 JSON，可直接在“JSON 编辑”中批量编辑；可视化编辑会自动同步为 JSON。' />
      </Card>
      <Space style={{ marginBottom: 12 }}>
        <Button onClick={load}>刷新</Button>
        <Tooltip title='保存当前配置到后端并热重载'>
          <Button type='primary' onClick={() => postSave(obj)} loading={loading}>保存</Button>
        </Tooltip>
        <Tooltip title='核心逻辑说明与示例'>
          <Button icon={<QuestionCircleOutlined />} onClick={()=>setHelpOpen(true)}>帮助</Button>
        </Tooltip>
      </Space>
      <Tabs activeKey={activeKey} onChange={setActiveKey} items={[
        {
          key: 'visual',
          label: '可视化编辑',
          children: (
            <div>
              <Card style={{ marginBottom: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>模板库</div>
                <Space wrap>
                  <Button onClick={() => {
                    const tpl: RulePack = {
                      id: 'pregnancy_safety', scope: 'post_llm', enabled: true, priority: 10,
                      rules: [
                        {
                          id: 'warn_pregnancy_case', enabled: true, priority: 10,
                          condition: { in: ['query_signals.pregnancy_status', ['妊娠/围产','妊娠']] },
                          action: { type: 'warn', message: 'Pregnancy case: ensure low radiation' }
                        },
                        {
                          id: 'deny_high_radiation_keywords', enabled: true, priority: 20,
                          condition: { in: ['query_signals.pregnancy_status', ['妊娠/围产','妊娠']] },
                          action: { type: 'fix', field: 'filter_procedures_by_keywords', strategy: 'deny_if_any_contains', keywords: ['CTA','增强CT','核医学'] }
                        }
                      ]
                    }
                    upsertPack(tpl)
                    message.success('已插入模板：pregnancy_safety')
                  }}>妊娠安全（post_llm）</Button>
                  <Button onClick={() => {
                    const tpl: RulePack = {
                      id: 'tch_boost', scope: 'rerank', enabled: true, priority: 20,
                      rules: [
                        {
                          id: 'boost_thunderclap_headache', enabled: true, priority: 10,
                          condition: { any_in: ['query_signals.keywords', ['雷击样','TCH','SAH','蛛网膜下腔出血']] },
                          action: { type: 'boost', by: 0.15 }
                        }
                      ]
                    }
                    upsertPack(tpl)
                    message.success('已插入模板：tch_boost')
                  }}>雷击样头痛加权（rerank）</Button>
                </Space>
              </Card>
              <Card style={{ marginBottom: 12 }}>
                <Space style={{ marginBottom: 8 }}>
                  <Button type='dashed' onClick={() => { setPackEditing({ id: '', scope: 'rerank', enabled: true, priority: 100, rules: [] }); setPackModalOpen(true) }}>新增 Pack</Button>
                </Space>
                <Table
                  rowKey='id'
                  columns={packCols}
                  dataSource={obj.packs || []}
                  pagination={false}
                  size='middle'
                />
              </Card>
              <Card>
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                  <div style={{ fontWeight: 600, flex: 1 }}>规则列表 {selectedPack ? `（${selectedPack.id}）` : ''}</div>
                  <Space>
                    <Button disabled={!selectedPack} onClick={() => { if (!selectedPack) return; setRuleEditing({ id: '', enabled: true, priority: 100, condition: {}, action: { type: 'warn' } }); setRuleModalOpen(true) }}>新增规则</Button>
                  </Space>
                </div>
                {selectedPack ? (
                  <Table
                    rowKey='id'
                    columns={ruleCols}
                    dataSource={selectedPack.rules || []}
                    pagination={false}
                    size='middle'
                  />
                ) : (
                  <div>请先在上方选择或创建一个 Pack。</div>
                )}
              </Card>

              <Modal title={packEditing?.id ? '编辑 Pack' : '新增 Pack'} open={packModalOpen} onCancel={() => setPackModalOpen(false)} footer={null} destroyOnClose>
                <PackForm
                  data={packEditing || undefined}
                  onOk={(v, originalId) => { upsertPack(v, originalId); setPackModalOpen(false) }}
                  onCancel={() => setPackModalOpen(false)}
                />
              </Modal>

              <Modal title={ruleEditing?.id ? '编辑规则' : '新增规则'} open={ruleModalOpen} onCancel={() => setRuleModalOpen(false)} footer={null} destroyOnClose>
                <RuleForm
                  data={ruleEditing || undefined}
                  onOk={(v, originalId) => { if (selectedPack) { upsertRule(v, selectedPack.id, originalId); } setRuleModalOpen(false) }}
                  onCancel={() => setRuleModalOpen(false)}
                />
              </Modal>
            </div>
          )
        },
        {
          key: 'simulate',
          label: '试运行',
          children: (
            <div>
              <Card>
                <SimulatePanel />
              </Card>
            </div>
          )
        },
        {
          key: 'json',
          label: 'JSON 编辑',
          children: (
            <div>
              <Space style={{ marginBottom: 12 }}>
                <Button onClick={formatJson}>格式化</Button>
                <Tooltip title='保存并热重载'>
                  <Button type='primary' onClick={saveJson} loading={loading}>保存 JSON</Button>
                </Tooltip>
              </Space>
              <Card>
                <TextArea
                  rows={24}
                  className='mono'
                  value={content}
                  onChange={(e)=> setContent(e.target.value)}
                  placeholder='请输入 JSON 格式的规则配置...'
                />
              </Card>
            </div>
          )
        }
      ]} />
      <Modal title='核心逻辑与示例' open={helpOpen} onCancel={()=>setHelpOpen(false)} footer={null} width={820}>
        <Typography.Paragraph>
          <b>执行流程：</b>系统在检索后进行<b>重排（rerank）</b>，可按规则对候选场景加权/过滤；随后进入<b>LLM 后处理（post_llm）</b>，可对 LLM 结构化输出进行告警/修复/覆盖。
        </Typography.Paragraph>
        <Typography.Paragraph>
          <b>常见用法：</b>
          <br/>— <b>妊娠安全</b>（post_llm）：当 <code>query_signals.pregnancy_status ∈ [妊娠/围产, 妊娠]</code> 时，记录告警，并按关键词（CTA/增强CT/核医学）过滤不合规的推荐项。
          <br/>— <b>雷击样头痛加权</b>（rerank）：当 <code>query_signals.keywords</code> 中出现 “雷击样/TCH/SAH” 时，为相关场景增加 <code>_rule_bonus</code>，从而提高排序。
        </Typography.Paragraph>
        <Alert type='success' showIcon message='关于 query_signals' description='query_signals 由后端根据 query 文本按配置自动提取，具备否定词护栏，默认配置位于 backend/config/query_signals.sample.json，可复制为 query_signals.json 并按需调整（无需改代码）。' style={{ marginBottom: 12 }} />
        <Alert type='info' showIcon message='如何验证与发布' description='建议先在“仅审计”模式观察命中情况，并使用“试运行”输入示例数据验证效果；待确认后关闭仅审计正式生效。' />
      </Modal>
    </div>
  )
}

export default RulesManager

// ---- Simulate Panel ----
const SimulatePanel: React.FC = () => {
  const [stage, setStage] = useState<'rerank'|'post_llm'>('rerank')
  const [query, setQuery] = useState<string>('妊娠期 胸痛，考虑肺栓塞')
  const [scenarios, setScenarios] = useState<string>(JSON.stringify([
    { semantic_id: 'S0001', description_zh: '妊娠相关胸痛', modality: 'CT', similarity: 0.6 }
  ], null, 2))
  const [parsed, setParsed] = useState<string>(JSON.stringify({
    recommendations: [ { procedure_name: 'CT 胸部平扫', modality: 'CT', appropriateness_rating: '7/9', recommendation_reason: '疑似肺栓塞' } ],
    summary: ''
  }, null, 2))
  const [resp, setResp] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const run = async () => {
    try {
      setLoading(true)
      const payload: any = { stage, query }
      if (stage==='rerank') payload.scenarios = JSON.parse(scenarios || '[]')
      else { payload.scenarios = JSON.parse(scenarios || '[]'); payload.llm_parsed = JSON.parse(parsed || '{}') }
      const r = await api.post('/api/v1/acrac/rag-llm/rules-simulate', payload)
      setResp(r.data)
    } catch (e:any) {
      message.error('试运行失败: ' + (e?.response?.data?.detail || e.message))
    } finally { setLoading(false) }
  }
  return (
    <div>
      <Space direction='vertical' style={{ width: '100%' }}>
        <Space>
          <span>阶段：</span>
          <Radio.Group value={stage} onChange={(e)=>setStage(e.target.value)}>
            <Radio.Button value='rerank'>rerank</Radio.Button>
            <Radio.Button value='post_llm'>post_llm</Radio.Button>
          </Radio.Group>
        </Space>
        <Input placeholder='query' value={query} onChange={(e)=>setQuery(e.target.value)} />
        <Space align='start' wrap>
          <div style={{ flex: 1, minWidth: 320 }}>
            <div style={{ fontWeight: 600, marginBottom: 6 }}>scenarios（用于 rerank / post_llm）</div>
            <TextArea rows={10} className='mono' value={scenarios} onChange={(e)=>setScenarios(e.target.value)} />
          </div>
          {stage==='post_llm' && (
            <div style={{ flex: 1, minWidth: 320 }}>
              <div style={{ fontWeight: 600, marginBottom: 6 }}>llm_parsed（用于 post_llm）</div>
              <TextArea rows={10} className='mono' value={parsed} onChange={(e)=>setParsed(e.target.value)} />
            </div>
          )}
        </Space>
        <Button type='primary' onClick={run} loading={loading}>试运行</Button>
        {resp && (
          <div>
            <Divider />
            <div style={{ fontWeight: 600, marginBottom: 6 }}>审计日志</div>
            <pre className='mono' style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(resp.audit_logs || [], null, 2)}</pre>
            {resp.scenarios && (
              <>
                <div style={{ fontWeight: 600, margin: '10px 0 6px' }}>rerank 输出</div>
                <pre className='mono' style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(resp.scenarios, null, 2)}</pre>
              </>
            )}
            {resp.parsed && (
              <>
                <div style={{ fontWeight: 600, margin: '10px 0 6px' }}>post_llm 输出</div>
                <pre className='mono' style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(resp.parsed, null, 2)}</pre>
              </>
            )}
          </div>
        )}
      </Space>
    </div>
  )
}
