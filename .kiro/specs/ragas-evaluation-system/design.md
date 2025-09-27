# RAGAS评测系统设计文档

## 概述

本设计文档基于需求文档，详细描述了RAGAS评测系统的技术架构、组件设计和实现方案。系统旨在解决当前评测指标异常问题，构建一个高效、准确、易用的RAG系统评测平台。

## 架构设计

### 整体架构

```mermaid
graph TB
    subgraph "前端层 (React)"
        UI[评测界面]
        Upload[数据上传组件]
        Progress[进度监控组件]
        Results[结果展示组件]
    end
    
    subgraph "API层 (FastAPI)"
        Gateway[API网关]
        Auth[认证中间件]
        RateLimit[限流中间件]
    end
    
    subgraph "业务逻辑层"
        EvalEngine[评测引擎]
        DataProcessor[数据处理器]
        ConfigManager[配置管理器]
        TaskManager[任务管理器]
    end
    
    subgraph "数据层"
        FileStorage[文件存储]
        Cache[缓存层]
        Database[数据库]
    end
    
    subgraph "外部服务"
        LLM[LLM服务]
        RAG[RAG推理服务]
    end
    
    UI --> Gateway
    Gateway --> EvalEngine
    EvalEngine --> DataProcessor
    DataProcessor --> LLM
    EvalEngine --> RAG
    ConfigManager --> Database
    TaskManager --> Cache
分层架构
表现层 (Presentation Layer)

React前端界面
四阶段评测流程UI
实时进度反馈
结果可视化
API层 (API Layer)

FastAPI路由管理
请求验证和认证
限流和错误处理
异步任务调度
业务逻辑层 (Business Logic Layer)

RAGAS评测引擎
数据转换和验证
配置管理
任务编排
数据访问层 (Data Access Layer)

文件存储管理
数据库操作
缓存管理
外部API调用
组件和接口设计
1. 核心评测引擎 (EvaluationEngine)
class EvaluationEngine:
    """RAGAS评测引擎核心类"""
    
    def __init__(self, config: EvaluationConfig):
        self.config = config
        self.llm_client = self._init_llm_client()
        self.metrics = self._init_metrics()
    
    async def evaluate_single(self, data: RAGASData) -> EvaluationResult:
        """单个样本评测"""
        pass
    
    async def evaluate_batch(self, data_list: List[RAGASData]) -> BatchEvaluationResult:
        """批量评测"""
        pass
    
    def _init_metrics(self) -> Dict[str, Metric]:
        """初始化四个评测指标"""
        return {
            'answer_relevancy': AnswerRelevancyMetric(self.llm_client),
            'faithfulness': FaithfulnessMetric(self.llm_client),
            'context_precision': ContextPrecisionMetric(self.llm_client),
            'context_recall': ContextRecallMetric(self.llm_client)
        }
关键接口
evaluate_single(data: RAGASData) -> EvaluationResult
evaluate_batch(data_list: List[RAGASData]) -> BatchEvaluationResult
get_health_status() -> HealthStatus
2. 数据处理器 (DataProcessor)
class DataProcessor:
    """数据转换和验证处理器"""
    
    def __init__(self, config: ProcessorConfig):
        self.config = config
        self.validator = DataValidator()
    
    def convert_rag_to_ragas(self, rag_result: RAGResult) -> RAGASData:
        """将RAG推理结果转换为RAGAS格式"""
        pass
    
    def validate_ragas_data(self, data: RAGASData) -> ValidationResult:
        """验证RAGAS数据格式"""
        pass
    
    def process_contexts(self, contexts: List[str]) -> List[str]:
        """处理上下文数据：去重、截断、排序"""
        pass
    
    def infer_ground_truth(self, query: str) -> str:
        """基于临床查询推断基础答案"""
        pass
数据模型
@dataclass
class RAGASData:
    """RAGAS评测数据模型"""
    question: str
    answer: str
    contexts: List[str]
    ground_truth: str
    metadata: Optional[Dict] = None

@dataclass
class EvaluationResult:
    """评测结果模型"""
    sample_id: str
    scores: Dict[str, float]  # 四个指标分数
    details: Dict[str, Any]   # 详细评测信息
    execution_time: float
    status: str
3. 配置管理器 (ConfigManager)
class ConfigManager:
    """统一配置管理"""
    
    def __init__(self, config_path: str = "model_contexts.json"):
        self.config_path = config_path
        self.config = self._load_config()
    
    def get_evaluation_config(self) -> EvaluationConfig:
        """获取评测配置"""
        return self.config.get("evaluation", {})
    
    def get_llm_config(self, provider: str) -> LLMConfig:
        """获取LLM配置"""
        pass
    
    def update_config(self, section: str, updates: Dict) -> bool:
        """更新配置"""
        pass
4. 任务管理器 (TaskManager)
class TaskManager:
    """异步任务管理"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.task_queue = asyncio.Queue()
    
    async def submit_evaluation_task(self, task_data: Dict) -> str:
        """提交评测任务"""
        task_id = self._generate_task_id()
        await self.task_queue.put({
            'task_id': task_id,
            'data': task_data,
            'status': 'pending'
        })
        return task_id
    
    async def get_task_status(self, task_id: str) -> TaskStatus:
        """获取任务状态"""
        pass
    
    async def process_tasks(self):
        """处理任务队列"""
        pass
API接口设计
1. 评测相关接口
# 单个样本评测
POST /api/v1/evaluation/single
{
    "question": "string",
    "answer": "string", 
    "contexts": ["string"],
    "ground_truth": "string"
}

# 批量评测
POST /api/v1/evaluation/batch
{
    "data": [RAGASData],
    "async": true,
    "callback_url": "string"
}

# 获取评测结果
GET /api/v1/evaluation/result/{task_id}

# 健康检查
GET /api/v1/health
2. 数据处理接口
# 数据转换
POST /api/v1/data/convert
{
    "rag_results": [RAGResult],
    "conversion_options": {}
}

# 数据验证
POST /api/v1/data/validate
{
    "ragas_data": [RAGASData]
}

# 文件上传
POST /api/v1/data/upload
Content-Type: multipart/form-data
3. 配置管理接口
# 获取配置
GET /api/v1/config/{section}

# 更新配置
PUT /api/v1/config/{section}
{
    "updates": {}
}

# 获取模型列表
GET /api/v1/models
前端界面设计
四阶段评测流程
阶段1：数据上传与预览
interface DataUploadStage {
  fileUpload: FileUploadComponent;
  dataPreview: DataPreviewTable;
  validation: ValidationPanel;
  selectionControls: SelectionControls;
}

// 组件结构
<DataUploadStage>
  <FileUploadZone 
    acceptedTypes={['.xlsx', '.csv']}
    onUpload={handleFileUpload}
  />
  <DataPreviewTable 
    data={uploadedData}
    validation={validationResults}
    onRowSelect={handleRowSelection}
  />
  <ValidationPanel 
    results={validationResults}
    onFixSuggestion={handleFixSuggestion}
  />
</DataUploadStage>
阶段2：批量推理
interface InferenceStage {
  progressMonitor: ProgressMonitor;
  inferenceResults: InferenceResultsTable;
  detailsViewer: InferenceDetailsViewer;
}

<InferenceStage>
  <ProgressBar 
    current={currentProgress}
    total={totalTasks}
    status={inferenceStatus}
  />
  <InferenceResultsTable 
    results={inferenceResults}
    onRowClick={showDetails}
    filters={statusFilters}
  />
  <InferenceDetailsModal 
    data={selectedInference}
    onClose={closeDetails}
  />
</InferenceStage>
阶段3：结果管理
interface ResultsManagementStage {
  resultsTable: ResultsTable;
  selectionPanel: SelectionPanel;
  dataPreview: RAGASDataPreview;
}

<ResultsManagementStage>
  <ResultsTable 
    data={inferenceResults}
    onSelect={handleResultSelection}
    filters={resultFilters}
  />
  <RAGASDataPreview 
    convertedData={ragasData}
    onEdit={handleDataEdit}
  />
</ResultsManagementStage>
阶段4：RAGAS评测
interface EvaluationStage {
  evaluationProgress: EvaluationProgress;
  metricsDisplay: MetricsDisplay;
  resultsExport: ResultsExport;
}

<EvaluationStage>
  <EvaluationProgress 
    progress={evaluationProgress}
    currentSample={currentSample}
  />
  <MetricsDisplay 
    scores={evaluationScores}
    charts={metricsCharts}
  />
  <ResultsExport 
    data={completeResults}
    formats={['xlsx', 'json', 'pdf']}
  />
</EvaluationStage>
数据模型
核心数据结构
# RAGAS评测数据
@dataclass
class RAGASData:
    question: str
    answer: str
    contexts: List[str]
    ground_truth: str
    metadata: Optional[Dict] = None

# RAG推理结果
@dataclass  
class RAGResult:
    question_id: str
    clinical_query: str
    scenarios: List[Dict]
    contexts: List[str]
    llm_recommendations: str
    trace_info: Dict
    model_params: Dict

# 评测结果
@dataclass
class EvaluationResult:
    sample_id: str
    scores: Dict[str, float]
    details: Dict[str, Any]
    execution_time: float
    status: str
    error_message: Optional[str] = None

# 批量评测结果
@dataclass
class BatchEvaluationResult:
    task_id: str
    total_samples: int
    completed_samples: int
    average_scores: Dict[str, float]
    individual_results: List[EvaluationResult]
    summary_stats: Dict[str, Any]
数据库设计
-- 评测任务表
CREATE TABLE evaluation_tasks (
    id VARCHAR(36) PRIMARY KEY,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_samples INTEGER,
    completed_samples INTEGER DEFAULT 0,
    config JSON,
    results JSON
);

-- 评测结果表
CREATE TABLE evaluation_results (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(36) REFERENCES evaluation_tasks(id),
    sample_id VARCHAR(100),
    question TEXT,
    answer TEXT,
    contexts JSON,
    ground_truth TEXT,
    scores JSON,
    details JSON,
    execution_time FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 配置历史表
CREATE TABLE config_history (
    id SERIAL PRIMARY KEY,
    section VARCHAR(50),
    config JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100)
);
错误处理
错误分类和处理策略
class EvaluationError(Exception):
    """评测相关错误基类"""
    pass

class DataValidationError(EvaluationError):
    """数据验证错误"""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"Validation error in {field}: {message}")

class LLMParsingError(EvaluationError):
    """LLM输出解析错误"""
    def __init__(self, metric: str, output: str):
        self.metric = metric
        self.output = output
        super().__init__(f"Failed to parse LLM output for {metric}")

class ConfigurationError(EvaluationError):
    """配置错误"""
    pass

# 错误处理中间件
async def error_handler(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except DataValidationError as e:
        return JSONResponse(
            status_code=400,
            content={
                "error": "validation_error",
                "field": e.field,
                "message": e.message,
                "suggestions": get_fix_suggestions(e.field)
            }
        )
    except LLMParsingError as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "llm_parsing_error",
                "metric": e.metric,
                "message": "LLM output parsing failed",
                "retry_suggestion": "Try with different model or prompt"
            }
        )
测试策略
单元测试
# 评测引擎测试
class TestEvaluationEngine:
    def test_answer_relevancy_calculation(self):
        """测试Answer Relevancy计算准确性"""
        pass
    
    def test_faithfulness_scoring(self):
        """测试Faithfulness评分"""
        pass
    
    def test_context_precision_evaluation(self):
        """测试Context Precision评测"""
        pass
    
    def test_context_recall_measurement(self):
        """测试Context Recall测量"""
        pass

# 数据处理器测试
class TestDataProcessor:
    def test_rag_to_ragas_conversion(self):
        """测试RAG到RAGAS数据转换"""
        pass
    
    def test_context_processing(self):
        """测试上下文处理逻辑"""
        pass
    
    def test_ground_truth_inference(self):
        """测试基础答案推断"""
        pass
集成测试
class TestEvaluationAPI:
    def test_single_evaluation_endpoint(self):
        """测试单个评测API"""
        pass
    
    def test_batch_evaluation_workflow(self):
        """测试批量评测工作流"""
        pass
    
    def test_error_handling(self):
        """测试错误处理机制"""
        pass
性能测试
class TestPerformance:
    def test_single_evaluation_latency(self):
        """测试单次评测延迟"""
        # 目标：<30秒
        pass
    
    def test_batch_evaluation_throughput(self):
        """测试批量评测吞吐量"""
        # 目标：>2样本/分钟
        pass
    
    def test_concurrent_requests(self):
        """测试并发请求处理"""
        # 目标：100并发稳定运行
        pass
部署和运维
部署架构
# docker-compose.yml
version: '3.8'
services:
  ragas-api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/ragas
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
  
  ragas-frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - ragas-api
  
  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=ragas
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:6-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
监控和日志
# 监控指标
METRICS = {
    'evaluation_requests_total': Counter('evaluation_requests_total'),
    'evaluation_duration_seconds': Histogram('evaluation_duration_seconds'),
    'evaluation_errors_total': Counter('evaluation_errors_total'),
    'llm_api_calls_total': Counter('llm_api_calls_total'),
    'active_evaluation_tasks': Gauge('active_evaluation_tasks')
}

# 日志配置
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'ragas_evaluation.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'detailed'
        }
    },
    'loggers': {
        'ragas_evaluation': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False
        }
    }
}
安全考虑
API安全
# JWT认证
class JWTAuth:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
    
    def create_token(self, user_id: str) -> str:
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        return jwt.encode(payload, self.secret_key, algorithm='HS256')
    
    def verify_token(self, token: str) -> Dict:
        return jwt.decode(token, self.secret_key, algorithms=['HS256'])

# API密钥管理
class APIKeyManager:
    def __init__(self, encryption_key: str):
        self.cipher = Fernet(encryption_key)
    
    def encrypt_api_key(self, api_key: str) -> str:
        return self.cipher.encrypt(api_key.encode()).decode()
    
    def decrypt_api_key(self, encrypted_key: str) -> str:
        return self.cipher.decrypt(encrypted_key.encode()).decode()
数据保护
# 敏感数据脱敏
class DataMasker:
    @staticmethod
    def mask_patient_info(text: str) -> str:
        """脱敏患者信息"""
        # 替换姓名、身份证号等敏感信息
        patterns = {
            r'\b\d{15,18}\b': '[ID_NUMBER]',
            r'\b1[3-9]\d{9}\b': '[PHONE_NUMBER]',
            # 更多脱敏规则...
        }
        
        for pattern, replacement in patterns.items():
            text = re.sub(pattern, replacement, text)