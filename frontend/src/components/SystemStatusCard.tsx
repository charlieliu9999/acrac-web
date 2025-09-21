import React, { useEffect, useState } from 'react'
import { Card, Row, Col, Badge, Statistic, Progress, Tooltip, Space, Button } from 'antd'
import { ReloadOutlined, DatabaseOutlined, ApiOutlined, RobotOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { api } from '../api/http'

interface SystemStatus {
  api: { status: 'ok' | 'error', version?: string, uptime?: number }
  db: { status: 'ok' | 'error', vector_count?: number, connection_pool?: number }
  embedding: { status: 'ok' | 'error', model?: string, dimension?: number, provider?: string }
  llm: { status: 'ok' | 'error', model?: string, provider?: string, tokens_used?: number }
  cache: { status: 'ok' | 'error', hit_rate?: number, memory_usage?: number }
  performance: { avg_response_time?: number, requests_per_minute?: number }
}

const SystemStatusCard: React.FC = () => {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)

  const loadStatus = async () => {
    try {
      setLoading(true)
      const response = await api.get('/api/v1/admin/data/system/status')
      setStatus(response.data)
      setLastUpdate(new Date())
    } catch (error) {
      console.error('加载系统状态失败:', error)
      // 设置错误状态
      setStatus({
        api: { status: 'error' },
        db: { status: 'error' },
        embedding: { status: 'error' },
        llm: { status: 'error' },
        cache: { status: 'error' },
        performance: {}
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadStatus()
    // 每30秒自动刷新
    const interval = setInterval(loadStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  const getStatusBadge = (status: 'ok' | 'error' | undefined) => {
    if (status === 'ok') return <Badge status="success" text="正常" />
    if (status === 'error') return <Badge status="error" text="异常" />
    return <Badge status="default" text="未知" />
  }

  const getStatusColor = (status: 'ok' | 'error' | undefined) => {
    if (status === 'ok') return '#52c41a'
    if (status === 'error') return '#ff4d4f'
    return '#d9d9d9'
  }

  const formatUptime = (seconds?: number) => {
    if (!seconds) return '未知'
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return `${hours}h ${minutes}m`
  }

  const formatNumber = (num?: number) => {
    if (num === undefined) return '未知'
    if (num > 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num > 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toString()
  }

  if (!status) {
    return (
      <Card title="系统状态总览" loading={loading}>
        <div style={{ textAlign: 'center', padding: '20px' }}>
          加载中...
        </div>
      </Card>
    )
  }

  return (
    <Card 
      title={
        <Space>
          <DatabaseOutlined />
          系统状态总览
          {lastUpdate && (
            <span style={{ fontSize: '12px', color: '#666', fontWeight: 'normal' }}>
              最后更新: {lastUpdate.toLocaleTimeString()}
            </span>
          )}
        </Space>
      }
      extra={
        <Button 
          icon={<ReloadOutlined />} 
          onClick={loadStatus} 
          loading={loading}
          size="small"
        >
          刷新
        </Button>
      }
      style={{ marginBottom: 16 }}
    >
      <Row gutter={[16, 16]}>
        {/* API服务状态 */}
        <Col xs={24} sm={12} md={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <ApiOutlined style={{ fontSize: '24px', color: getStatusColor(status.api?.status) }} />
              {getStatusBadge(status.api?.status)}
              <div style={{ fontSize: '12px', color: '#666' }}>
                <div>版本: {status.api?.version || '未知'}</div>
                <div>运行时间: {formatUptime(status.api?.uptime)}</div>
              </div>
            </Space>
          </Card>
        </Col>

        {/* 数据库状态 */}
        <Col xs={24} sm={12} md={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <DatabaseOutlined style={{ fontSize: '24px', color: getStatusColor(status.db?.status) }} />
              {getStatusBadge(status.db?.status)}
              <div style={{ fontSize: '12px', color: '#666' }}>
                <div>向量数: {formatNumber(status.db?.vector_count)}</div>
                <div>连接池: {status.db?.connection_pool || 0}/20</div>
              </div>
            </Space>
          </Card>
        </Col>

        {/* 向量模型状态 */}
        <Col xs={24} sm={12} md={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <ThunderboltOutlined style={{ fontSize: '24px', color: getStatusColor(status.embedding?.status) }} />
              {getStatusBadge(status.embedding?.status)}
              <div style={{ fontSize: '12px', color: '#666' }}>
                <Tooltip title={status.embedding?.model}>
                  <div>模型: {status.embedding?.provider || '未知'}</div>
                </Tooltip>
                <div>维度: {status.embedding?.dimension || 0}</div>
              </div>
            </Space>
          </Card>
        </Col>

        {/* LLM模型状态 */}
        <Col xs={24} sm={12} md={6}>
          <Card size="small" style={{ textAlign: 'center' }}>
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <RobotOutlined style={{ fontSize: '24px', color: getStatusColor(status.llm?.status) }} />
              {getStatusBadge(status.llm?.status)}
              <div style={{ fontSize: '12px', color: '#666' }}>
                <Tooltip title={status.llm?.model}>
                  <div>提供商: {status.llm?.provider || '未知'}</div>
                </Tooltip>
                <div>Token: {formatNumber(status.llm?.tokens_used)}</div>
              </div>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* 性能指标 */}
      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col xs={24} sm={8}>
          <Statistic
            title="平均响应时间"
            value={status.performance?.avg_response_time || 0}
            precision={2}
            suffix="s"
            valueStyle={{ color: (status.performance?.avg_response_time || 0) < 3 ? '#3f8600' : '#cf1322' }}
          />
        </Col>
        <Col xs={24} sm={8}>
          <Statistic
            title="请求频率"
            value={status.performance?.requests_per_minute || 0}
            suffix="req/min"
            valueStyle={{ color: '#1890ff' }}
          />
        </Col>
        <Col xs={24} sm={8}>
          <div>
            <div style={{ marginBottom: 8 }}>缓存命中率</div>
            <Progress
              percent={Math.round((status.cache?.hit_rate || 0) * 100)}
              status={(status.cache?.hit_rate || 0) > 0.7 ? 'success' : 'normal'}
              strokeColor={(status.cache?.hit_rate || 0) > 0.7 ? '#52c41a' : '#1890ff'}
            />
          </div>
        </Col>
      </Row>
    </Card>
  )
}

export default SystemStatusCard