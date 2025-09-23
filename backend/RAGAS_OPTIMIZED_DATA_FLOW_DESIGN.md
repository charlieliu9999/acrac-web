# RAGAS评测系统优化数据流设计方案

## 1. 当前问题总结

基于对现有系统的深入分析，识别出以下核心问题：

### 1.1 API架构问题
- **主要RAGAS API被注释**：由于uvloop兼容性问题，`ragas_evaluation_api.py`和`ragas_api.py`被禁用
- **API端点不一致**：前端调用`/api/v1/ragas/evaluate`，但实际可用的是`/api/v1/ragas-standalone/evaluate`
- **多重实现混乱**：存在多个RAGAS评估器实现，功能重复且维护困难

### 1.2 数据流断裂
- **缺乏统一任务ID**：推理阶段和评测阶段无法有效关联
- **状态管理分散**：任务状态分别存储在前端和后端，缺乏一致性
- **结果持久化不完整**：评测结果主要存储在前端，后端缺乏完整记录

### 1.3 评测可靠性问题
- **Faithfulness低分**：评分为0.0000，表明答案与上下文不一致
- **数据格式不匹配**：RAG推理返回的数据格式与RAGAS要求不完全匹配
- **错误处理不完善**：评测失败时缺乏详细的错误信息和恢复机制

## 2. 优化数据流设计

### 2.1 统一任务管理架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端上传      │    │   任务创建      │    │   数据预处理    │
│   Excel文件     │───▶│   生成task_id   │───▶│   格式验证      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   结果汇总      │    │   RAGAS评测     │    │   批量RAG推理   │
│   报告生成      │◀───│   计算指标      │◀───│   保存记录      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 2.2 核心数据模型设计

#### 2.2.1 评测任务表（evaluation_tasks）
```sql
CREATE TABLE evaluation_tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(50) UNIQUE NOT NULL,
    task_name VARCHAR(200),
    task_type VARCHAR(50) DEFAULT 'ragas_evaluation',
    status VARCHAR(50) DEFAULT 'created',
    config JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT
);
```

#### 2.2.2 评测样本表（evaluation_samples）
```sql
CREATE TABLE evaluation_samples (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(50) REFERENCES evaluation_tasks(task_id),
    sample_id VARCHAR(50),
    question_id VARCHAR(100),
    clinical_query TEXT NOT NULL,
    ground_truth TEXT,
    rag_answer TEXT,
    rag_contexts JSONB,
    rag_trace JSONB,
    ragas_scores JSONB,
    overall_score FLOAT DEFAULT 0.0,
    status VARCHAR(50) DEFAULT 'pending',
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### 2.2.3 评测结果表（evaluation_results）
```sql
CREATE TABLE evaluation_results (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(50) REFERENCES evaluation_tasks(task_id),
    total_samples INTEGER,
    completed_samples INTEGER,
    failed_samples INTEGER,
    average_scores JSONB,
    overall_score FLOAT,
    processing_time_ms INTEGER,
    report_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2.3 优化的API设计

#### 2.3.1 统一的评测API端点
```
POST /api/v1/ragas-evaluation/tasks/create
POST /api/v1/ragas-evaluation/tasks/{task_id}/start
GET  /api/v1/ragas-evaluation/tasks/{task_id}/status
GET  /api/v1/ragas-evaluation/tasks/{task_id}/results
GET  /api/v1/ragas-evaluation/tasks/{task_id}/report
DELETE /api/v1/ragas-evaluation/tasks/{task_id}
```

#### 2.3.2 API数据流设计
```python
# 1. 创建评测任务
POST /api/v1/ragas-evaluation/tasks/create
{
    "task_name": "医疗问答评测_20250122",
    "test_cases": [
        {
            "question_id": "Q001",
            "clinical_query": "患者出现胸痛症状，如何诊断？",
            "ground_truth": "需要进行心电图、胸片等检查..."
        }
    ],
    "config": {
        "model_name": "gpt-3.5-turbo",
        "base_url": "https://api.siliconflow.cn/v1",
        "metrics": ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    }
}

# 2. 启动评测任务
POST /api/v1/ragas-evaluation/tasks/{task_id}/start

# 3. 查询任务状态
GET /api/v1/ragas-evaluation/tasks/{task_id}/status
{
    "task_id": "task_20250122_001",
    "status": "running",
    "progress": {
        "total_samples": 100,
        "completed_samples": 45,
        "failed_samples": 2,
        "current_sample": "Q046"
    },
    "estimated_remaining_time": 300
}
```

### 2.4 数据处理流水线

#### 2.4.1 阶段一：数据预处理
```python
def preprocess_test_cases(test_cases: List[Dict]) -> List[Dict]:
    """
    数据预处理和验证
    """
    processed_cases = []
    for case in test_cases:
        # 1. 数据验证
        if not case.get('clinical_query'):
            continue
            
        # 2. 格式标准化
        processed_case = {
            'question_id': case.get('question_id', f"Q{len(processed_cases)+1:03d}"),
            'clinical_query': case['clinical_query'].strip(),
            'ground_truth': case.get('ground_truth', '').strip(),
            'metadata': {
                'source': case.get('source', 'excel'),
                'row_index': case.get('row_index'),
                'original_data': case
            }
        }
        processed_cases.append(processed_case)
    
    return processed_cases
```

#### 2.4.2 阶段二：批量RAG推理
```python
async def batch_rag_inference(task_id: str, samples: List[Dict]) -> List[Dict]:
    """
    批量RAG推理，支持并发和错误恢复
    """
    results = []
    semaphore = asyncio.Semaphore(5)  # 限制并发数
    
    async def process_single_sample(sample):
        async with semaphore:
            try:
                # 调用RAG推理API
                rag_result = await call_rag_api(sample['clinical_query'])
                
                # 格式化结果
                processed_result = {
                    'sample_id': sample['question_id'],
                    'rag_answer': rag_result.get('answer', ''),
                    'rag_contexts': format_contexts(rag_result.get('contexts', [])),
                    'rag_trace': rag_result.get('trace', {}),
                    'processing_time_ms': rag_result.get('processing_time_ms', 0),
                    'status': 'completed'
                }
                
                # 保存到数据库
                await save_sample_result(task_id, sample, processed_result)
                return processed_result
                
            except Exception as e:
                error_result = {
                    'sample_id': sample['question_id'],
                    'status': 'failed',
                    'error': str(e)
                }
                await save_sample_result(task_id, sample, error_result)
                return error_result
    
    # 并发处理所有样本
    tasks = [process_single_sample(sample) for sample in samples]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return results
```

#### 2.4.3 阶段三：RAGAS评测
```python
async def batch_ragas_evaluation(task_id: str) -> Dict:
    """
    批量RAGAS评测，基于已保存的RAG推理结果
    """
    # 1. 从数据库获取RAG推理结果
    samples = await get_completed_samples(task_id)
    
    # 2. 准备RAGAS数据集
    ragas_dataset = prepare_ragas_dataset(samples)
    
    # 3. 执行RAGAS评测
    try:
        evaluator = RAGASEvaluator()
        evaluation_results = await evaluator.evaluate_dataset(ragas_dataset)
        
        # 4. 保存评测结果
        for i, sample in enumerate(samples):
            ragas_scores = evaluation_results[i]
            await update_sample_ragas_scores(task_id, sample['sample_id'], ragas_scores)
        
        # 5. 计算汇总统计
        summary = calculate_evaluation_summary(evaluation_results)
        await save_evaluation_results(task_id, summary)
        
        return {
            'status': 'success',
            'summary': summary,
            'total_samples': len(samples)
        }
        
    except Exception as e:
        await update_task_status(task_id, 'failed', str(e))
        return {
            'status': 'error',
            'error': str(e)
        }
```

### 2.5 数据格式标准化

#### 2.5.1 RAG推理结果格式化
```python
def format_rag_result_for_ragas(rag_result: Dict) -> Dict:
    """
    将RAG推理结果格式化为RAGAS要求的格式
    """
    # 提取答案文本
    answer = ""
    if isinstance(rag_result.get('answer'), str):
        answer = rag_result['answer']
    elif isinstance(rag_result.get('answer'), dict):
        answer = rag_result['answer'].get('content', '')
    
    # 提取上下文列表
    contexts = []
    raw_contexts = rag_result.get('contexts', [])
    
    for ctx in raw_contexts:
        if isinstance(ctx, str):
            contexts.append(ctx)
        elif isinstance(ctx, dict):
            # 提取文档内容
            content = ctx.get('content') or ctx.get('text') or ctx.get('document', '')
            if content:
                contexts.append(content)
    
    # 确保至少有一个上下文
    if not contexts:
        contexts = ["无可用上下文信息"]
    
    return {
        'answer': answer.strip(),
        'contexts': contexts
    }
```

#### 2.5.2 RAGAS数据集准备
```python
def prepare_ragas_dataset(samples: List[Dict]) -> Dataset:
    """
    准备RAGAS评测数据集
    """
    questions = []
    answers = []
    contexts = []
    ground_truths = []
    
    for sample in samples:
        if sample.get('status') != 'completed':
            continue
            
        questions.append(sample['clinical_query'])
        
        # 格式化RAG结果
        rag_formatted = format_rag_result_for_ragas({
            'answer': sample.get('rag_answer', ''),
            'contexts': sample.get('rag_contexts', [])
        })
        
        answers.append(rag_formatted['answer'])
        contexts.append(rag_formatted['contexts'])
        ground_truths.append(sample.get('ground_truth', ''))
    
    return Dataset.from_dict({
        'question': questions,
        'answer': answers,
        'contexts': contexts,
        'ground_truth': ground_truths
    })
```

## 3. 实施计划

### 3.1 第一阶段：修复基础架构（1-2天）
1. **解决API路由问题**
   - 修复uvloop兼容性问题
   - 启用主要的RAGAS评测API
   - 统一API端点命名

2. **创建数据库表结构**
   - 创建评测任务相关表
   - 建立数据索引和约束
   - 迁移现有数据

### 3.2 第二阶段：实现优化数据流（2-3天）
1. **实现统一任务管理**
   - 创建任务管理服务
   - 实现任务状态跟踪
   - 添加错误恢复机制

2. **优化RAG推理流程**
   - 实现批量并发处理
   - 添加结果格式化
   - 完善错误处理

### 3.3 第三阶段：增强评测可靠性（2-3天）
1. **改进RAGAS评测**
   - 修复faithfulness低分问题
   - 优化数据格式转换
   - 增强评测结果验证

2. **完善结果存储**
   - 实现完整的结果持久化
   - 添加评测历史管理
   - 创建报告生成功能

### 3.4 第四阶段：前端优化（1-2天）
1. **更新前端API调用**
   - 适配新的API端点
   - 实现实时状态更新
   - 优化用户体验

2. **完善错误处理**
   - 添加详细错误信息
   - 实现重试机制
   - 改进进度展示

## 4. 预期效果

### 4.1 可靠性提升
- **数据完整性**：完整的数据追溯链路，确保每个环节可追踪
- **错误恢复**：完善的错误处理和恢复机制
- **结果一致性**：统一的数据格式和验证标准

### 4.2 性能优化
- **并发处理**：支持批量并发RAG推理，提升处理效率
- **资源管理**：合理的并发控制，避免系统过载
- **缓存机制**：减少重复计算，提升响应速度

### 4.3 用户体验改善
- **流程简化**：一键启动完整评测流程
- **实时反馈**：详细的进度信息和状态更新
- **结果展示**：直观的评测报告和历史管理

---
*设计时间: 2025-01-22*  
*设计范围: 完整的RAGAS评测数据流优化*  
*状态: 设计完成，待开始实施*