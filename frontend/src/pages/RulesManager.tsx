import React, { useEffect, useState } from 'react'
import { Button, Card, Space, message, Tooltip, Input } from 'antd'
import { api } from '../api/http'

const { TextArea } = Input

const RulesManager: React.FC = () => {
  const [content, setContent] = useState<string>('')
  const [loading, setLoading] = useState(false)

  const load = async () => {
    try {
      const r = await api.get('/api/v1/acrac/rag-llm/rules-packs')
      setContent(JSON.stringify(r.data.content, null, 2))
    } catch (e:any) {
      message.error('读取规则失败: ' + (e?.response?.data?.detail || e.message))
    }
  }

  useEffect(() => { load() }, [])

  const save = async () => {
    setLoading(true)
    try {
      const obj = JSON.parse(content || '{}')
      await api.post('/api/v1/acrac/rag-llm/rules-packs', { content: obj })
      message.success('规则已保存并热重载')
    } catch (e:any) {
      message.error('保存失败: ' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  const format = () => {
    try {
      const obj = JSON.parse(content || '{}')
      setContent(JSON.stringify(obj, null, 2))
    } catch {
      message.warning('JSON 无法格式化，请检查语法')
    }
  }

  return (
    <div>
      <div className='page-title'>规则管理</div>
      <Space style={{ marginBottom: 12 }}>
        <Button onClick={load}>刷新</Button>
        <Button onClick={format}>格式化</Button>
        <Tooltip title='保存并热重载'>
          <Button type='primary' onClick={save} loading={loading}>保存</Button>
        </Tooltip>
      </Space>
      <Card>
        <TextArea
          rows={24}
          className='mono'
          value={content}
          onChange={(e)=> setContent(e.target.value)}
          placeholder="请输入 JSON 格式的规则配置..."
        />
      </Card>
    </div>
  )
}

export default RulesManager
