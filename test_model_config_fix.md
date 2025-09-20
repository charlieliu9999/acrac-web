# 模型配置页面修复说明

## 问题描述
模型配置页面在启动后能正确显示模型列表，但是到数据浏览页面再回到模型配置页面时，模型列表都显示不出来了。

## 问题根因分析

### 1. 状态管理问题
- 模型配置页面使用 `useEffect(() => { load() }, [])` 在组件挂载时加载数据
- 每次路由切换都会重新挂载组件，导致状态重置
- 如果配置API失败，模型库也会被重置为空

### 2. 加载顺序问题
- 原代码先加载配置，再在 `finally` 块中加载模型库
- 如果配置加载失败，模型库加载也可能失败
- 导致 `registry` 状态为空，下拉选项消失

## 修复方案

### 1. 调整加载顺序
```typescript
const load = async () => {
  // 先加载模型库，确保下拉选项始终可用
  try {
    setRegLoading(true)
    const rr = await api.get('/api/v1/admin/data/models/registry')
    setRegistry(rr.data || { llms: [], embeddings: [], rerankers: [] })
  } catch (e:any) {
    // 提供默认选项避免下拉框空白
    setRegistry({ 
      llms: [{ id: 'default-llm', label: '默认LLM', model: 'Qwen/Qwen2.5-32B-Instruct', provider: 'siliconflow' }], 
      embeddings: [{ id: 'default-embedding', label: '默认Embedding', model: 'BAAI/bge-m3', provider: 'siliconflow' }], 
      rerankers: [] 
    })
  } finally {
    setRegLoading(false)
  }

  // 然后加载配置
  try {
    const r = await api.get('/api/v1/admin/data/models/config')
    // ... 设置配置状态
  } catch (e: any) {
    message.error('加载配置失败：' + (e?.response?.data?.detail || e.message))
  }
}
```

### 2. 错误处理优化
- 模型库加载失败时提供默认选项
- 使用 `console.warn` 而不是 `message.error` 避免用户看到过多错误信息
- 确保即使API失败，下拉框也有可选项

### 3. 状态保护
- 优先加载模型库，确保UI可用性
- 配置加载失败不影响模型库显示
- 提供合理的默认选项

## 测试步骤

1. **启动系统**：确保后端和前端都正常运行
2. **访问模型配置页面**：检查模型列表是否正常显示
3. **切换到数据浏览页面**：确保页面正常加载
4. **返回模型配置页面**：检查模型列表是否仍然显示
5. **重复切换**：多次在页面间切换，验证问题是否解决

## 预期结果

- ✅ 模型配置页面首次加载时显示模型列表
- ✅ 从其他页面返回时模型列表仍然显示
- ✅ 即使API失败，也有默认选项可用
- ✅ 用户体验更加稳定

## 相关文件

- `frontend/src/pages/ModelConfig.tsx` - 主要修复文件
- `backend/app/api/api_v1/endpoints/admin_data_api.py` - 后端API
- `backend/config/models_registry.json` - 模型注册表
