# Ollama + BGE-Large-ZH 配置指南

## 概述

本指南介绍如何配置和使用 Ollama 服务与 BGE-Large-ZH 模型来实现医疗向量化功能。

## 1. 系统架构

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

## 2. 安装和配置

### 2.1 安装 Ollama

#### macOS
```bash
# 使用 Homebrew 安装
brew install ollama

# 或者下载安装包
# https://ollama.ai/download
```

#### Linux
```bash
# 安装 Ollama
curl -fsSL https://ollama.ai/install.sh | sh
```

#### Windows
```bash
# 下载并安装 Ollama
# https://ollama.ai/download
```

### 2.2 启动 Ollama 服务

```bash
# 启动 Ollama 服务
ollama serve

# 在另一个终端中拉取 BGE-Large-ZH 模型
ollama pull bge-large-zh
```

### 2.3 配置环境变量

创建 `.env` 文件：

```env
# 数据库配置
DATABASE_URL=postgresql://username:password@localhost:5432/acrac_db
REDIS_URL=redis://localhost:6379/0

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

# 其他配置
DEBUG=true
LOG_LEVEL=INFO
```

## 3. 模型配置

### 3.1 支持的模型

| 模型名称 | 维度 | 特点 | 推荐场景 |
|---------|------|------|----------|
| bge-large-zh | 1024 | 中文优化，医疗场景最佳 | 生产环境推荐 |
| bge-base-zh | 768 | 平衡性能和速度 | 开发环境推荐 |
| bge-m3 | 1024 | 多语言支持 | 国际化场景 |
| m3e-base | 768 | 轻量级中文模型 | 资源受限环境 |

### 3.2 模型切换

```python
# 在 .env 文件中修改
EMBEDDING_MODEL_TYPE=bge-base-zh  # 切换到 BGE-Base-ZH
EMBEDDING_DIMENSION=768           # 更新维度

# 重启服务
python -m uvicorn app.main:app --reload
```

## 4. API 使用

### 4.1 医疗向量搜索

```bash
# 搜索医疗术语
curl -X POST "http://localhost:8000/api/v1/medical-search/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "胸部CT检查",
    "search_types": ["topics", "variants", "procedures"],
    "limit": 10,
    "threshold": 0.7
  }'
```

### 4.2 相似度计算

```bash
# 计算两个文本的相似度
curl -X GET "http://localhost:8000/api/v1/medical-search/similarity?text1=胸部CT检查&text2=胸部计算机断层扫描"
```

### 4.3 服务状态检查

```bash
# 检查服务状态
curl -X GET "http://localhost:8000/api/v1/medical-search/status"
```

### 4.4 数据向量化

```bash
# 为数据库数据生成向量
curl -X POST "http://localhost:8000/api/v1/medical-search/vectorize?batch_size=32"
```

## 5. 性能优化

### 5.1 Ollama 配置优化

```bash
# 设置 Ollama 环境变量
export OLLAMA_NUM_PARALLEL=4
export OLLAMA_MAX_LOADED_MODELS=2
export OLLAMA_FLASH_ATTENTION=1
```

### 5.2 批处理优化

```python
# 在 .env 文件中调整
BATCH_SIZE=64        # 增加批处理大小
MAX_WORKERS=8        # 增加工作线程数
CACHE_TTL=7200       # 增加缓存时间
```

### 5.3 数据库优化

```sql
-- 创建优化的向量索引
CREATE INDEX CONCURRENTLY idx_topics_ollama_embedding 
ON topics USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 200, probes = 20);

CREATE INDEX CONCURRENTLY idx_variants_ollama_embedding 
ON variants USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 200, probes = 20);

CREATE INDEX CONCURRENTLY idx_procedures_ollama_embedding 
ON procedures USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 200, probes = 20);
```

## 6. 监控和维护

### 6.1 健康检查

```bash
# 检查 Ollama 服务
curl http://localhost:11434/api/tags

# 检查模型状态
curl http://localhost:11434/api/show -d '{"name": "bge-large-zh"}'
```

### 6.2 日志监控

```bash
# 查看 Ollama 日志
ollama logs

# 查看应用日志
tail -f logs/acrac.log
```

### 6.3 性能监控

```python
# 在代码中添加性能监控
import time
import logging

def monitor_embedding_performance(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logging.info(f"Embedding operation took {end_time - start_time:.2f} seconds")
        return result
    return wrapper
```

## 7. 故障排除

### 7.1 常见问题

#### 问题1: Ollama 服务连接失败
```bash
# 检查服务状态
ps aux | grep ollama

# 重启服务
ollama serve
```

#### 问题2: 模型加载失败
```bash
# 检查模型是否已安装
ollama list

# 重新拉取模型
ollama pull bge-large-zh
```

#### 问题3: 内存不足
```bash
# 检查内存使用
free -h

# 调整批处理大小
export BATCH_SIZE=16
```

#### 问题4: 响应时间过长
```bash
# 检查 Ollama 配置
ollama show bge-large-zh

# 调整超时设置
export OLLAMA_TIMEOUT=600
```

### 7.2 性能调优

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

## 8. 部署建议

### 8.1 开发环境

```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_NUM_PARALLEL=2
      - OLLAMA_MAX_LOADED_MODELS=1

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

### 8.2 生产环境

```yaml
# docker-compose.prod.yml
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
      - OLLAMA_FLASH_ATTENTION=1
    deploy:
      resources:
        limits:
          memory: 8G
        reservations:
          memory: 4G

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - BATCH_SIZE=64
      - MAX_WORKERS=8
    depends_on:
      - ollama
    deploy:
      replicas: 3

volumes:
  ollama_data:
```

## 9. 总结

通过使用 Ollama + BGE-Large-ZH 的组合，您可以获得：

1. **高性能**: 本地部署，无网络延迟
2. **易管理**: 简单的模型管理和更新
3. **可扩展**: 支持多种模型和配置
4. **医疗优化**: 专门针对中文医疗场景优化
5. **成本效益**: 无需云服务费用

这个配置为 ACRAC 医疗系统提供了强大的向量化能力，支持智能搜索、语义匹配和医疗知识检索。
