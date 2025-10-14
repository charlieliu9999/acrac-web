# BGE-Large-ZH + Ollama 集成总结

## 概述

本文档总结了 ACRAC 医疗系统中 BGE-Large-ZH 模型与 Ollama 服务的集成实现，提供了完整的配置、部署和使用指南。

## 1. 技术架构

### 1.1 系统组件

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   前端 (Vue.js)  │    │   后端 (FastAPI)  │    │   Ollama服务    │
│                 │    │                  │    │                 │
│ - 搜索界面      │◄──►│ - 嵌入管理器     │◄──►│ - BGE-Large-ZH  │
│ - 结果展示      │    │ - API接口        │    │ - 本地部署      │
│ - 多语言支持    │    │ - 配置管理       │    │ - 高性能       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   关系数据库      │
                       │                  │
                       │ - PostgreSQL     │
                       │ - pgvector       │
                       │ - 医疗数据       │
                       └──────────────────┘
```

### 1.2 核心特性

- **BGE-Large-ZH 模型**: 1024维中文优化向量化模型
- **Ollama 服务**: 本地部署的模型服务，支持多种模型
- **配置管理**: 灵活的配置系统，支持环境变量和配置文件
- **医疗优化**: 专门针对中文医疗场景的文本预处理
- **高性能**: 本地部署，无网络延迟，支持批处理

## 2. 文件结构

### 2.1 新增文件

```
backend/
├── app/
│   ├── core/
│   │   └── embedding_config.py          # 嵌入模型配置
│   ├── services/
│   │   ├── ollama_embedding_service.py  # Ollama嵌入服务
│   │   └── embedding_manager.py         # 嵌入服务管理器
│   └── api/
│       └── api_v1/
│           └── endpoints/
│               └── medical_vector_search.py  # 医疗向量搜索API
├── scripts/
│   └── test_ollama_embedding.py         # 测试脚本
└── requirements-medical.txt             # 医疗专用依赖

docs/
├── Ollama-BGE配置指南.md                # 配置指南
└── BGE-Large-ZH-Ollama集成总结.md       # 本文档
```

### 2.2 修改文件

```
backend/
├── app/
│   ├── models/
│   │   └── acrac_models.py              # 更新向量维度为1024
│   └── api/
│       └── api_v1/
│           └── api.py                   # 添加医疗向量搜索路由
└── requirements-medical.txt             # 添加新依赖
```

## 3. 配置系统

### 3.1 环境变量配置

```env
# 嵌入模型配置
EMBEDDING_MODEL_TYPE=bge-large-zh
EMBEDDING_MODEL_NAME=BAAI/bge-large-zh-v1.5
EMBEDDING_DIMENSION=1024

# Ollama服务配置
OLLAMA_ENABLED=true
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_NAME=bge-large-zh
OLLAMA_TIMEOUT=300

# 性能配置
BATCH_SIZE=32
MAX_WORKERS=4
CACHE_ENABLED=true
CACHE_TTL=3600

# 医疗特定配置
MEDICAL_PREPROCESSING=true
MEDICAL_TERMS_NORMALIZATION=true
CONTEXT_PREFIX_ENABLED=true
```

### 3.2 支持的模型

| 模型名称 | 维度 | 特点 | 推荐场景 |
|---------|------|------|----------|
| bge-large-zh | 1024 | 中文优化，医疗场景最佳 | 生产环境推荐 |
| bge-base-zh | 768 | 平衡性能和速度 | 开发环境推荐 |
| bge-m3 | 1024 | 多语言支持 | 国际化场景 |
| m3e-base | 768 | 轻量级中文模型 | 资源受限环境 |

## 4. API 接口

### 4.1 医疗向量搜索

```http
POST /api/v1/medical-search/search
Content-Type: application/json

{
  "query": "胸部CT检查",
  "search_types": ["topics", "variants", "procedures"],
  "limit": 10,
  "threshold": 0.7
}
```

### 4.2 相似度计算

```http
GET /api/v1/medical-search/similarity?text1=胸部CT检查&text2=胸部计算机断层扫描
```

### 4.3 服务状态检查

```http
GET /api/v1/medical-search/status
```

### 4.4 数据向量化

```http
POST /api/v1/medical-search/vectorize?batch_size=32
```

### 4.5 创建向量索引

```http
POST /api/v1/medical-search/create-indexes
```

## 5. 部署指南

### 5.1 安装 Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# 下载安装包: https://ollama.ai/download
```

### 5.2 启动服务

```bash
# 启动 Ollama 服务
ollama serve

# 拉取 BGE-Large-ZH 模型
ollama pull bge-large-zh

# 启动后端服务
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5.3 Docker 部署

```yaml
# docker-compose.yml
version: '3.8'
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_NUM_PARALLEL=4
      - OLLAMA_MAX_LOADED_MODELS=2

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
    depends_on:
      - ollama

volumes:
  ollama_data:
```

## 6. 测试验证

### 6.1 运行测试

```bash
# 运行完整测试
python scripts/test_ollama_embedding.py

# 测试特定功能
python -c "from app.services.embedding_manager import embedding_manager; print(embedding_manager.get_service_status())"
```

### 6.2 测试内容

- ✅ Ollama 服务连接测试
- ✅ 嵌入服务状态检查
- ✅ 文本向量化测试
- ✅ 相似度计算测试
- ✅ 医疗术语处理测试
- ✅ API 端点测试

## 7. 性能优化

### 7.1 Ollama 配置优化

```bash
# 设置环境变量
export OLLAMA_NUM_PARALLEL=4
export OLLAMA_MAX_LOADED_MODELS=2
export OLLAMA_FLASH_ATTENTION=1
```

### 7.2 批处理优化

```python
# 调整批处理参数
BATCH_SIZE=64        # 增加批处理大小
MAX_WORKERS=8        # 增加工作线程数
CACHE_TTL=7200       # 增加缓存时间
```

### 7.3 数据库优化

```sql
-- 创建优化的向量索引
CREATE INDEX CONCURRENTLY idx_topics_ollama_embedding 
ON topics USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 200, probes = 20);
```

## 8. 监控和维护

### 8.1 健康检查

```bash
# 检查 Ollama 服务
curl http://localhost:11434/api/tags

# 检查模型状态
curl http://localhost:11434/api/show -d '{"name": "bge-large-zh"}'

# 检查应用状态
curl http://localhost:8000/api/v1/medical-search/status
```

### 8.2 日志监控

```bash
# 查看 Ollama 日志
ollama logs

# 查看应用日志
tail -f logs/acrac.log
```

## 9. 故障排除

### 9.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| Ollama 连接失败 | 服务未启动 | 启动 Ollama 服务 |
| 模型加载失败 | 模型未安装 | 运行 `ollama pull bge-large-zh` |
| 内存不足 | 批处理过大 | 减少 BATCH_SIZE |
| 响应时间过长 | 超时设置过小 | 增加 OLLAMA_TIMEOUT |

### 9.2 性能调优

```python
# 调整模型参数
model_config = {
    "temperature": 0.0,
    "top_p": 0.9,
    "num_predict": 1,
    "num_ctx": 2048,
    "num_batch": 512
}
```

## 10. 扩展功能

### 10.1 多模型支持

```python
# 支持多个模型同时运行
models = {
    "bge-large-zh": "医疗场景",
    "bge-base-zh": "通用场景",
    "m3e-base": "轻量级场景"
}
```

### 10.2 实时更新

```python
# 支持实时向量更新
def update_vector_on_change(record_id: int, new_text: str):
    # 实时更新向量
    pass
```

### 10.3 缓存优化

```python
# 实现智能缓存
cache_config = {
    "enabled": True,
    "ttl": 3600,
    "max_size": 10000,
    "strategy": "LRU"
}
```

## 11. 总结

### 11.1 主要优势

1. **高性能**: 本地部署，无网络延迟
2. **易管理**: 简单的模型管理和更新
3. **可扩展**: 支持多种模型和配置
4. **医疗优化**: 专门针对中文医疗场景优化
5. **成本效益**: 无需云服务费用

### 11.2 技术特点

- **BGE-Large-ZH**: 1024维中文优化向量化模型
- **Ollama 服务**: 本地部署的模型服务
- **配置管理**: 灵活的配置系统
- **医疗优化**: 专门针对中文医疗场景的文本预处理
- **高性能**: 支持批处理和缓存

### 11.3 应用场景

- 医疗知识检索
- 智能搜索推荐
- 语义相似度计算
- 医疗术语标准化
- 多语言支持

通过这个集成方案，ACRAC 医疗系统获得了强大的向量化能力，支持智能搜索、语义匹配和医疗知识检索，为医疗专业人员提供了更好的工具支持。
