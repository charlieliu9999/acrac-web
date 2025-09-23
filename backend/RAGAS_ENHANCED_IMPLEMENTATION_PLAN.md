# RAGAS评测系统增强实施方案

## 概述

基于当前流程分析，针对用户提出的三个关键改进点，制定详细的实施方案，确保RAGAS评测系统具备完整的数据追溯能力和可靠的评测结果展示。

## 关键改进点分析

### 改进点1：Excel文件解析环节 - 唯一项目ID构建机制

**当前问题**：
- 缺乏统一的项目标识符
- 推理和评测环节数据关联困难
- 无法有效追溯原始数据来源

**解决方案**：
```typescript
interface ProjectSession {
  project_id: string;           // 唯一项目ID (UUID)
  session_name: string;         // 用户定义的会话名称
  excel_filename: string;       // 原始Excel文件名
  upload_timestamp: string;     // 上传时间戳
  total_cases: number;          // 总测试用例数
  status: 'uploaded' | 'processing' | 'completed' | 'failed';
  metadata: {
    file_hash: string;          // 文件哈希值，确保数据完整性
    columns_mapping: object;    // 列映射关系
    user_id?: string;           // 用户ID（如果有用户系统）
  }
}

interface TestCaseWithProject extends ExcelTestCase {
  project_id: string;           // 关联项目ID
  case_id: string;              // 唯一测试用例ID
  original_row_index: number;   // 原始Excel行号
}
```

### 改进点2：推理记录评测解析功能

**当前问题**：
- 推理结果直接传递给RAGAS，缺乏中间验证
- 数据格式转换逻辑分散
- 无法预览和验证评测数据

**解决方案**：
```typescript
interface InferenceAnalysisResult {
  project_id: string;
  case_id: string;
  inference_data: {
    question: string;
    answer: string;
    contexts: string[];
    ground_truth?: string;
  };
  analysis_status: 'pending' | 'analyzed' | 'ready_for_ragas' | 'failed';
  format_validation: {
    is_valid: boolean;
    issues: string[];
    suggestions: string[];
  };
  ragas_format: {
    question: string;
    answer: string;
    contexts: string[];
    ground_truth?: string;
  };
}

// 新增API端点
interface AnalysisAPI {
  // 分析推理记录并转换格式
  POST: '/api/v1/ragas/analysis/prepare';
  
  // 获取分析结果预览
  GET: '/api/v1/ragas/analysis/preview/{project_id}';
  
  // 确认并提交RAGAS评测
  POST: '/api/v1/ragas/analysis/submit/{project_id}';
}
```

### 改进点3：RAGAS评测结果完整展示

**当前问题**：
- 结果展示信息不完整
- 缺乏原始数据和评测结果的对比
- 无法进行深入的结果分析

**解决方案**：
```typescript
interface ComprehensiveEvaluationResult {
  project_id: string;
  case_id: string;
  
  // 原始数据
  original_data: {
    excel_row: number;
    clinical_query: string;
    ground_truth?: string;
    file_source: string;
  };
  
  // 推理结果
  inference_result: {
    rag_answer: string;
    retrieved_contexts: string[];
    inference_method: string;
    execution_time_ms: number;
    success: boolean;
  };
  
  // RAGAS评测结果
  ragas_evaluation: {
    faithfulness: number;
    answer_relevancy: number;
    context_precision?: number;
    context_recall?: number;
    answer_similarity?: number;
    answer_correctness?: number;
  };
  
  // 分析和建议
  analysis: {
    overall_score: number;
    strengths: string[];
    weaknesses: string[];
    improvement_suggestions: string[];
  };
  
  // 元数据
  metadata: {
    evaluation_timestamp: string;
    ragas_version: string;
    model_config: object;
  };
}
```

## 详细实施计划

### 阶段1：数据模型和数据库设计（1-2天）

**1.1 创建项目会话表**
```sql
CREATE TABLE project_sessions (
    project_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_name VARCHAR(255) NOT NULL,
    excel_filename VARCHAR(255) NOT NULL,
    upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_cases INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'uploaded',
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**1.2 扩展测试用例表**
```sql
CREATE TABLE test_cases_enhanced (
    case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES project_sessions(project_id),
    original_row_index INTEGER NOT NULL,
    clinical_query TEXT NOT NULL,
    ground_truth TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**1.3 创建推理分析表**
```sql
CREATE TABLE inference_analysis (
    analysis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES project_sessions(project_id),
    case_id UUID REFERENCES test_cases_enhanced(case_id),
    inference_data JSONB NOT NULL,
    analysis_status VARCHAR(50) DEFAULT 'pending',
    format_validation JSONB,
    ragas_format JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**1.4 创建综合评测结果表**
```sql
CREATE TABLE comprehensive_evaluation_results (
    result_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES project_sessions(project_id),
    case_id UUID REFERENCES test_cases_enhanced(case_id),
    original_data JSONB NOT NULL,
    inference_result JSONB NOT NULL,
    ragas_evaluation JSONB NOT NULL,
    analysis JSONB,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 阶段2：后端API开发（3-4天）

**2.1 项目会话管理API**
```python
# app/api/v1/project_sessions.py
@router.post("/create")
async def create_project_session(
    session_data: ProjectSessionCreate,
    db: Session = Depends(get_db)
) -> ProjectSession:
    """创建新的项目会话"""
    pass

@router.get("/{project_id}")
async def get_project_session(
    project_id: str,
    db: Session = Depends(get_db)
) -> ProjectSession:
    """获取项目会话详情"""
    pass

@router.get("/")
async def list_project_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> List[ProjectSession]:
    """获取项目会话列表"""
    pass
```

**2.2 推理分析API**
```python
# app/api/v1/inference_analysis.py
@router.post("/prepare")
async def prepare_inference_analysis(
    project_id: str,
    db: Session = Depends(get_db)
) -> InferenceAnalysisResponse:
    """分析推理记录并准备RAGAS格式数据"""
    pass

@router.get("/preview/{project_id}")
async def preview_analysis_results(
    project_id: str,
    db: Session = Depends(get_db)
) -> List[InferenceAnalysisResult]:
    """预览分析结果"""
    pass

@router.post("/submit/{project_id}")
async def submit_for_ragas_evaluation(
    project_id: str,
    db: Session = Depends(get_db)
) -> TaskResponse:
    """提交RAGAS评测"""
    pass
```

**2.3 综合评测结果API**
```python
# app/api/v1/comprehensive_results.py
@router.get("/{project_id}/results")
async def get_comprehensive_results(
    project_id: str,
    db: Session = Depends(get_db)
) -> List[ComprehensiveEvaluationResult]:
    """获取综合评测结果"""
    pass

@router.get("/{project_id}/summary")
async def get_evaluation_summary(
    project_id: str,
    db: Session = Depends(get_db)
) -> EvaluationSummary:
    """获取评测摘要统计"""
    pass

@router.get("/{project_id}/export")
async def export_results(
    project_id: str,
    format: str = "excel",
    db: Session = Depends(get_db)
) -> FileResponse:
    """导出评测结果"""
    pass
```

### 阶段3：前端组件开发（3-4天）

**3.1 项目会话管理组件**
```typescript
// components/ProjectSessionManager.tsx
interface ProjectSessionManagerProps {
  onProjectCreated: (projectId: string) => void;
}

const ProjectSessionManager: React.FC<ProjectSessionManagerProps> = ({
  onProjectCreated
}) => {
  // 项目创建、列表展示、选择逻辑
  return (
    <div className="project-session-manager">
      <ProjectCreationForm onSubmit={handleCreateProject} />
      <ProjectSessionList onSelect={handleSelectProject} />
    </div>
  );
};
```

**3.2 推理分析预览组件**
```typescript
// components/InferenceAnalysisPreview.tsx
interface InferenceAnalysisPreviewProps {
  projectId: string;
  onConfirmSubmit: () => void;
}

const InferenceAnalysisPreview: React.FC<InferenceAnalysisPreviewProps> = ({
  projectId,
  onConfirmSubmit
}) => {
  // 分析结果预览、格式验证、提交确认
  return (
    <div className="inference-analysis-preview">
      <AnalysisResultsTable data={analysisResults} />
      <FormatValidationPanel validation={validationResults} />
      <SubmitConfirmationButton onClick={onConfirmSubmit} />
    </div>
  );
};
```

**3.3 综合结果展示组件**
```typescript
// components/ComprehensiveResultsDisplay.tsx
interface ComprehensiveResultsDisplayProps {
  projectId: string;
}

const ComprehensiveResultsDisplay: React.FC<ComprehensiveResultsDisplayProps> = ({
  projectId
}) => {
  // 完整结果展示、数据追溯、分析功能
  return (
    <div className="comprehensive-results-display">
      <ResultsSummaryPanel summary={evaluationSummary} />
      <DetailedResultsTable results={comprehensiveResults} />
      <AnalysisInsightsPanel insights={analysisInsights} />
      <ExportOptionsPanel projectId={projectId} />
    </div>
  );
};
```

### 阶段4：优化的工作流程（1天）

**4.1 新的评测流程**
```
1. 创建项目会话 → 生成project_id
2. Excel文件上传 → 解析并关联project_id
3. 批量RAG推理 → 保存推理记录（关联project_id和case_id）
4. 推理分析处理 → 格式转换和验证
5. 分析结果预览 → 用户确认数据质量
6. 提交RAGAS评测 → 执行评测任务
7. 综合结果展示 → 完整的数据追溯和分析
```

**4.2 数据流优化**
```
Excel → ProjectSession → TestCases → Inference → Analysis → Preview → RAGAS → Results
  ↓         ↓            ↓          ↓          ↓         ↓        ↓       ↓
project_id  case_ids    run_logs   analysis   preview   submit   scores  display
```

## 技术实现要点

### 1. 唯一ID生成策略
- 使用UUID确保全局唯一性
- 项目ID格式：`proj_yyyymmdd_hhmmss_uuid`
- 测试用例ID格式：`case_proj_id_row_index`

### 2. 数据格式验证
- 实现RAGAS格式验证器
- 提供数据质量检查报告
- 支持格式修复建议

### 3. 结果追溯机制
- 完整的数据血缘关系
- 支持从结果反向查找原始数据
- 提供详细的处理日志

### 4. 性能优化
- 批量数据处理
- 异步任务队列
- 结果缓存机制

## 预期效果

1. **完整的数据追溯**：从Excel原始数据到最终评测结果的完整链路
2. **可靠的评测质量**：通过分析预览环节确保数据质量
3. **友好的用户体验**：清晰的流程指导和丰富的结果展示
4. **高效的处理性能**：优化的数据流和批量处理机制

## 实施时间表

- **第1-2天**：数据模型设计和数据库创建
- **第3-6天**：后端API开发和测试
- **第7-10天**：前端组件开发和集成
- **第11天**：端到端测试和优化
- **第12天**：文档编写和部署准备

---
*创建时间: 2025-01-22*  
*基于: RAGAS_CURRENT_FLOW_ANALYSIS.md*  
*状态: 详细实施方案，待开始实施*