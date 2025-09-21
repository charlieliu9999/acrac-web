import React, { useEffect, useState } from 'react'
import { Button, Card, Modal, Table, Tag, message } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { api } from '../api/http'

interface RunLogItem {
  id: number
  query_text: string
  success: boolean
  inference_method?: string
  execution_time_ms?: number
  created_at?: string
}

const RunLogs: React.FC = () => {
  const [data, setData] = useState<RunLogItem[]>([])
  const [total, setTotal] = useState<number>(0)
  const [page, setPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(20)
  const [loading, setLoading] = useState<boolean>(false)

  const [detailOpen, setDetailOpen] = useState<boolean>(false)
  const [detail, setDetail] = useState<any>(null)

  const load = async (p = page, ps = pageSize) => {
    try {
      setLoading(true)
      const r = await api.get('/api/v1/acrac/rag-llm/runs', { params: { page: p, page_size: ps } })
      setData(r.data.items || [])
      setTotal(r.data.total || 0)
    } catch (e:any) {
      message.error('加载失败：' + (e?.response?.data?.detail || e.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load(1, pageSize) }, [])

  const openDetail = async (id:number) => {
    try {
      const r = await api.get(`/api/v1/acrac/rag-llm/runs/${id}`)
      setDetail(r.data)
      setDetailOpen(true)
    } catch (e:any) {
      message.error('获取详情失败：' + (e?.response?.data?.detail || e.message))
    }
  }

  const columns: ColumnsType<RunLogItem> = [
    { title: 'ID', dataIndex: 'id', width: 80 },
    { title: '查询', dataIndex: 'query_text', ellipsis: true },
    { title: '方法', dataIndex: 'inference_method', width: 110, render: (v) => <Tag>{v || 'rag'}</Tag> },
    { title: '成功', dataIndex: 'success', width: 90, render: (v:boolean) => v ? <Tag color='green'>是</Tag> : <Tag color='red'>否</Tag> },
    { title: '耗时(ms)', dataIndex: 'execution_time_ms', width: 110 },
    { title: '时间', dataIndex: 'created_at', width: 200 },
    { title: '操作', dataIndex: 'op', width: 120, render: (_, r) => (<Button size='small' onClick={() => openDetail(r.id)}>查看</Button>) },
  ]

  return (
    <div>
      <div className='page-title'>运行历史</div>
      <Card>
        <Table
          rowKey='id'
          size='small'
          loading={loading}
          dataSource={data}
          columns={columns}
          pagination={{
            total,
            current: page,
            pageSize,
            showSizeChanger: true,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); load(p, ps) },
          }}
        />
      </Card>

      <Modal open={detailOpen} width={880} title={`运行详情 #${detail?.id || ''}`} onCancel={() => setDetailOpen(false)} footer={null}>
        {detail ? (
          <div>
            <div>查询：{detail.query_text}</div>
            <div style={{ marginTop: 6 }}>成功：{detail.success ? '是' : '否'}</div>
            <div style={{ marginTop: 6 }}>方法：{detail.inference_method}</div>
            <div style={{ marginTop: 6 }}>耗时：{detail.execution_time_ms} ms</div>
            <div style={{ marginTop: 12 }}>
              <div style={{ fontWeight: 600 }}>完整结果 JSON</div>
              <pre className='mono' style={{ whiteSpace: 'pre-wrap', maxHeight: 420, overflow: 'auto' }}>{JSON.stringify(detail.result || {}, null, 2)}</pre>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}

export default RunLogs

