# ACRAC V2.0 开发指南

## 🎯 开发环境设置

### 1. 环境要求
- **Python**: 3.8+ (推荐3.11)
- **PostgreSQL**: 13+ 
- **Node.js**: 16+ (用于前端开发)
- **操作系统**: macOS, Linux, Windows

### 2. 项目结构
```
ACRAC-web/
├── backend/                                # 后端代码
│   ├── app/
│   │   ├── models/acrac_models.py         # 数据模型
│   │   ├── schemas/acrac_schemas.py       # 数据模式
│   │   ├── services/acrac_service.py      # 核心服务
│   │   ├── api/api_v1/endpoints/acrac_simple.py # API端点
│   │   └── main.py                        # FastAPI应用
│   ├── scripts/
│   │   ├── ACRAC完整数据库向量库构建方案.py # 主构建脚本
│   │   └── start_acrac_v2.py             # 启动脚本
│   ├── requirements.txt                   # Python依赖
│   └── Dockerfile                        # Docker配置
├── frontend/                              # 前端代码（待更新）
├── ACR_data/
│   └── ACR_final.csv                     # 主数据源
├── docs/                                 # 文档目录
└── backup/                               # 备份目录
```

### 3. 开发环境初始化
```bash
# 1. 克隆项目
git clone <repository-url>
cd ACRAC-web

# 2. 设置后端环境
cd backend
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置数据库
# 确保PostgreSQL运行，创建数据库acrac_db
createdb acrac_db

# 5. 安装pgvector扩展
psql -d acrac_db -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 6. 构建数据库
cd scripts
python ACRAC完整数据库向量库构建方案.py rebuild --csv-file ../../ACR_data/ACR_final.csv

# 7. 启动开发服务器
cd ..
python -m uvicorn app.main:app --reload
```

## 🏗️ 数据模型开发

### 1. 数据模型结构

#### Panel模型
```python
class Panel(Base):
    __tablename__ = "panels"
    
    id = Column(Integer, primary_key=True, index=True)
    semantic_id = Column(String(20), unique=True, nullable=False)  # P0001
    name_en = Column(String(255), nullable=False)
    name_zh = Column(String(255), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    embedding = Column(Vector(1024))
    
    # 关系
    topics = relationship("Topic", back_populates="panel", cascade="all, delete-orphan")
```

#### 添加新字段
```python
# 1. 更新模型
class Panel(Base):
    # ... 现有字段
    new_field = Column(String(100), comment="新字段描述")

# 2. 创建迁移
alembic revision --autogenerate -m "添加new_field到panels表"

# 3. 执行迁移
alembic upgrade head
```

### 2. 语义化ID生成

#### 自动ID生成
```python
def _generate_next_semantic_id(self, entity_type: str) -> str:
    """生成下一个语义化ID"""
    if entity_type == 'panel':
        result = self.db.execute(text(
            "SELECT COALESCE(MAX(CAST(SUBSTRING(semantic_id FROM 2) AS INTEGER)), 0) + 1 FROM panels"
        ))
        next_num = result.scalar()
        return f"P{next_num:04d}"
    # ... 其他类型
```

#### 手动指定ID
```python
# 创建新Panel时可以手动指定semantic_id
panel = Panel(
    semantic_id="P9999",  # 手动指定
    name_en="Special Department",
    name_zh="特殊科室"
)
```

## 🔧 API开发

### 1. 添加新端点

#### 创建新端点
```python
@router.get("/custom-endpoint")
def custom_endpoint(
    param1: str = Query(..., description="参数1"),
    param2: Optional[int] = Query(None, description="参数2"),
    db: Session = Depends(get_db)
):
    """自定义端点描述"""
    try:
        # 业务逻辑
        result = db.query(Panel).filter(Panel.name_zh.like(f"%{param1}%")).all()
        
        return {
            "query": param1,
            "total": len(result),
            "data": [{"id": p.semantic_id, "name": p.name_zh} for p in result]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### 注册路由
```python
# 在 app/api/api_v1/endpoints/acrac_simple.py 中添加
# 或创建新的端点文件并在 api.py 中注册
```

### 2. 数据验证

#### 输入验证
```python
from pydantic import BaseModel, Field, validator

class CustomRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="名称")
    rating: int = Field(..., ge=1, le=9, description="评分")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('名称不能为空')
        return v.strip()
```

#### 输出格式化
```python
class CustomResponse(BaseModel):
    success: bool
    data: Optional[Dict] = None
    message: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True
```

## 🧠 向量化开发

### 1. 自定义向量生成

#### 替换随机向量
```python
def _generate_query_vector(self, text: str) -> List[float]:
    """生成查询向量"""
    # 当前使用随机向量，可替换为专业模型
    # 例如使用sentence-transformers
    
    from sentence_transformers import SentenceTransformer
    
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    vector = model.encode(text).tolist()
    
    # 确保维度为1024
    if len(vector) != 1024:
        # 填充或截断到1024维
        vector = (vector + [0] * 1024)[:1024]
    
    return vector
```

#### 优化向量内容
```python
def _build_recommendation_vector_text(self, recommendation):
    """构建推荐向量文本"""
    # 获取完整上下文信息
    scenario = self.get_scenario(recommendation.scenario_id)
    procedure = self.get_procedure(recommendation.procedure_id)
    
    # 构建结构化文本
    text_parts = [
        f"科室: {scenario.panel.name_zh}",
        f"主题: {scenario.topic.name_zh}",
        f"临床场景: {scenario.description_zh}",
        f"患者特征: {scenario.patient_population} {scenario.age_group} {scenario.risk_level}",
        f"检查项目: {procedure.name_zh}",
        f"检查方式: {procedure.modality} {procedure.body_part}",
        f"适宜性: {recommendation.appropriateness_rating}分 {recommendation.appropriateness_category_zh}",
        f"推荐理由: {recommendation.reasoning_zh}",
        f"证据强度: {recommendation.evidence_level}"
    ]
    
    return " | ".join([part for part in text_parts if part and not part.endswith(': ')])
```

### 2. 向量搜索优化

#### 相似度阈值调整
```python
# 不同类型数据使用不同阈值
SIMILARITY_THRESHOLDS = {
    'panels': 0.8,      # 科室匹配要求较高
    'topics': 0.75,     # 主题匹配中等
    'scenarios': 0.7,   # 场景匹配较宽松
    'procedures': 0.8,  # 检查项目匹配较严格
    'recommendations': 0.6  # 推荐匹配最宽松
}
```

#### 多阶段搜索
```python
def hierarchical_search(query_text: str, limit: int = 10):
    """层次化搜索"""
    results = {}
    
    # 第一阶段：搜索相关场景
    scenarios = vector_search('scenarios', query_text, limit=20)
    
    # 第二阶段：获取场景的推荐
    recommendations = []
    for scenario in scenarios:
        scene_recs = get_recommendations_for_scenario(scenario.semantic_id)
        recommendations.extend(scene_recs)
    
    # 第三阶段：按相关性和评分排序
    sorted_recs = sort_by_relevance_and_rating(recommendations)
    
    return sorted_recs[:limit]
```

## 🗄️ 数据库开发

### 1. 添加新表
```python
# 1. 在models中定义新表
class NewTable(Base):
    __tablename__ = "new_table"
    
    id = Column(Integer, primary_key=True)
    semantic_id = Column(String(20), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    # ... 其他字段

# 2. 更新__init__.py导入
from app.models.acrac_models import NewTable

# 3. 创建迁移
alembic revision --autogenerate -m "添加new_table"
alembic upgrade head
```

### 2. 数据迁移
```python
# 创建数据迁移脚本
def migrate_data():
    """数据迁移示例"""
    # 连接数据库
    db = SessionLocal()
    
    try:
        # 查询需要迁移的数据
        old_data = db.query(OldModel).all()
        
        # 转换并插入新数据
        for item in old_data:
            new_item = NewModel(
                semantic_id=generate_semantic_id('new'),
                name=item.old_name,
                # ... 字段映射
            )
            db.add(new_item)
        
        db.commit()
        print(f"迁移完成: {len(old_data)} 条记录")
        
    except Exception as e:
        db.rollback()
        print(f"迁移失败: {e}")
    finally:
        db.close()
```

## 🧪 测试开发

### 1. 单元测试
```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    """测试健康检查"""
    response = client.get("/api/v1/acrac/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_panel_list():
    """测试Panel列表"""
    response = client.get("/api/v1/acrac/panels")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "panels" in data
```

### 2. 集成测试
```python
def test_complete_workflow():
    """测试完整工作流"""
    # 1. 查询科室
    panels_response = client.get("/api/v1/acrac/panels")
    panels = panels_response.json()["panels"]
    
    # 2. 查询科室下的主题
    panel_id = panels[0]["semantic_id"]
    topics_response = client.get(f"/api/v1/acrac/panels/{panel_id}/topics")
    topics = topics_response.json()["topics"]
    
    # 3. 搜索推荐
    search_response = client.get("/api/v1/acrac/search/recommendations?query=检查")
    recommendations = search_response.json()["recommendations"]
    
    assert len(panels) > 0
    assert len(topics) > 0
    assert len(recommendations) > 0
```

## 📊 性能优化

### 1. 数据库优化
```sql
-- 查询性能分析
EXPLAIN ANALYZE SELECT * FROM clinical_recommendations 
WHERE appropriateness_rating >= 8 
ORDER BY appropriateness_rating DESC;

-- 索引优化
CREATE INDEX CONCURRENTLY idx_custom ON clinical_recommendations (field1, field2);

-- 向量索引调优
DROP INDEX idx_recommendations_embedding;
CREATE INDEX idx_recommendations_embedding ON clinical_recommendations 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 2000);
```

### 2. API优化
```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_panels():
    """缓存Panel数据"""
    # 实现缓存逻辑
    pass

# 异步支持
@router.get("/async-endpoint")
async def async_endpoint(db: AsyncSession = Depends(get_async_db)):
    """异步端点示例"""
    result = await db.execute(select(Panel))
    return result.scalars().all()
```

### 3. 向量搜索优化
```python
def optimized_vector_search(query_vector, limit=10):
    """优化的向量搜索"""
    # 1. 预过滤
    candidates = pre_filter_by_business_rules()
    
    # 2. 向量搜索
    vector_results = vector_similarity_search(query_vector, candidates)
    
    # 3. 后处理
    final_results = post_process_results(vector_results)
    
    return final_results[:limit]
```

## 🔄 数据更新流程

### 1. CSV数据更新
```bash
# 1. 备份当前数据
python ACRAC完整数据库向量库构建方案.py export --file backup_$(date +%Y%m%d).xlsx

# 2. 更新CSV数据
# 将新的ACR_final.csv放入ACR_data目录

# 3. 重建数据库
python ACRAC完整数据库向量库构建方案.py rebuild --csv-file ../../ACR_data/ACR_final.csv

# 4. 验证数据
python ACRAC完整数据库向量库构建方案.py verify
```

### 2. 增量数据更新
```python
# 通过API添加新数据
def add_new_recommendation(scenario_id, procedure_id, rating, reasoning):
    """添加新推荐"""
    recommendation_data = {
        "scenario_id": scenario_id,
        "procedure_id": procedure_id,
        "appropriateness_rating": rating,
        "reasoning_zh": reasoning,
        "is_generated": True  # 标记为新增
    }
    
    response = requests.post(
        "http://127.0.0.1:8000/api/v1/acrac/recommendations",
        json=recommendation_data
    )
    
    return response.json()
```

## 🎨 前端集成

### 1. API客户端
```javascript
// frontend/src/api/acrac.ts
import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000/api/v1/acrac';

export class ACRACApi {
    // 健康检查
    static async healthCheck() {
        const response = await axios.get(`${API_BASE}/health`);
        return response.data;
    }
    
    // 获取科室列表
    static async getPanels(activeOnly = true) {
        const response = await axios.get(`${API_BASE}/panels`, {
            params: { active_only: activeOnly }
        });
        return response.data;
    }
    
    // 搜索检查项目
    static async searchProcedures(query, modality = null, limit = 20) {
        const response = await axios.get(`${API_BASE}/search/procedures`, {
            params: { query, modality, limit }
        });
        return response.data;
    }
    
    // 智能推荐
    static async getIntelligentRecommendations(clinicalQuery, patientProfile = {}) {
        const response = await axios.post(`${API_BASE}/search/intelligent`, {
            clinical_query: clinicalQuery,
            patient_profile: patientProfile,
            limit: 10
        });
        return response.data;
    }
}
```

### 2. Vue组件示例
```vue
<template>
  <div class="acrac-search">
    <el-input
      v-model="searchQuery"
      placeholder="输入临床场景或检查项目"
      @keyup.enter="handleSearch"
    />
    
    <div class="results" v-if="searchResults.length > 0">
      <div 
        v-for="result in searchResults" 
        :key="result.recommendation_id"
        class="recommendation-item"
      >
        <h4>{{ result.procedure }}</h4>
        <p>{{ result.scenario }}</p>
        <span class="rating">评分: {{ result.rating }}分</span>
      </div>
    </div>
  </div>
</template>

<script>
import { ACRACApi } from '@/api/acrac';

export default {
  name: 'ACRACSearch',
  data() {
    return {
      searchQuery: '',
      searchResults: []
    };
  },
  methods: {
    async handleSearch() {
      try {
        const result = await ACRACApi.searchProcedures(this.searchQuery);
        this.searchResults = result.procedures;
      } catch (error) {
        console.error('搜索失败:', error);
      }
    }
  }
};
</script>
```

## 🔍 调试和监控

### 1. 日志配置
```python
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/acrac.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
```

### 2. 性能监控
```python
import time
from functools import wraps

def monitor_performance(func):
    """性能监控装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        logger.info(f"{func.__name__} 执行时间: {(end_time - start_time) * 1000:.2f}ms")
        return result
    return wrapper

@monitor_performance
def expensive_operation():
    # 耗时操作
    pass
```

### 3. 错误处理
```python
from fastapi import HTTPException
import traceback

def handle_database_error(func):
    """数据库错误处理装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SQLAlchemyError as e:
            logger.error(f"数据库错误: {e}")
            raise HTTPException(status_code=500, detail="数据库操作失败")
        except Exception as e:
            logger.error(f"未知错误: {e}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail="服务器内部错误")
    return wrapper
```

## 🚀 部署指南

### 1. 开发环境部署
```bash
# 使用uvicorn开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 生产环境部署
```bash
# 使用gunicorn + uvicorn workers
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 3. Docker部署
```bash
# 构建镜像
docker build -t acrac-backend:v2.0 .

# 运行容器
docker run -d \
  --name acrac-backend \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:pass@host:5432/acrac_db" \
  acrac-backend:v2.0
```

### 4. 环境变量配置
```bash
# .env文件
DATABASE_URL=postgresql://postgres:password@localhost:5432/acrac_db
VECTOR_DIMENSION=1024
API_PREFIX=/api/v1/acrac
LOG_LEVEL=INFO
CORS_ORIGINS=["http://localhost:3000", "http://127.0.0.1:3000"]
```

## 📝 代码规范

### 1. Python代码规范
```python
# 使用类型提示
def create_panel(self, panel_data: PanelCreate) -> PanelResponse:
    """创建Panel"""
    pass

# 使用文档字符串
class ACRACService:
    """ACRAC核心服务
    
    提供完整的数据管理和智能搜索功能，包括：
    - Panel、Topic、Scenario、Procedure的CRUD操作
    - 基于向量的智能搜索和推荐
    - 数据分析和统计功能
    """

# 异常处理
try:
    result = risky_operation()
except SpecificException as e:
    logger.error(f"特定错误: {e}")
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    logger.error(f"未知错误: {e}")
    raise HTTPException(status_code=500, detail="内部服务器错误")
```

### 2. API设计规范
```python
# RESTful URL设计
GET    /api/v1/acrac/panels           # 获取列表
GET    /api/v1/acrac/panels/{id}      # 获取单个
POST   /api/v1/acrac/panels           # 创建
PUT    /api/v1/acrac/panels/{id}      # 更新
DELETE /api/v1/acrac/panels/{id}      # 删除

# 响应格式统一
{
    "success": true,
    "data": {...},
    "message": "操作成功",
    "timestamp": "2025-09-07T21:00:00Z"
}
```

## 🔧 常见开发任务

### 1. 添加新的搜索功能
```python
@router.get("/search/custom")
def custom_search(
    query: str,
    custom_filter: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """自定义搜索功能"""
    # 实现搜索逻辑
    pass
```

### 2. 添加新的分析功能
```python
@router.get("/analytics/custom-analysis")
def custom_analysis(db: Session = Depends(get_db)):
    """自定义分析功能"""
    result = db.execute(text("""
        SELECT 
            custom_field,
            COUNT(*) as count,
            AVG(rating) as avg_rating
        FROM clinical_recommendations
        GROUP BY custom_field
        ORDER BY count DESC;
    """))
    
    return {"analysis_result": dict(result)}
```

### 3. 数据导入功能扩展
```python
def import_additional_data(file_path: str, data_type: str):
    """导入额外数据"""
    if data_type == 'procedures':
        # 导入新的检查项目
        pass
    elif data_type == 'recommendations':
        # 导入新的推荐关系
        pass
```

## 💡 最佳实践

### 1. 开发流程
1. **需求分析**: 明确功能需求和数据结构
2. **模型设计**: 设计数据模型和关系
3. **API设计**: 设计RESTful API接口
4. **实现开发**: 编写业务逻辑和API
5. **测试验证**: 单元测试和集成测试
6. **文档更新**: 更新API文档和使用指南

### 2. 代码质量
- 使用类型提示提高代码可读性
- 编写完整的文档字符串
- 实现全面的错误处理
- 添加适当的日志记录
- 编写单元测试和集成测试

### 3. 性能考虑
- 使用适当的索引优化查询
- 实现缓存机制减少数据库访问
- 使用分页避免大量数据传输
- 监控API响应时间和资源使用

---

**ACRAC V2.0 开发指南**
*为开发者提供完整的开发环境设置、代码规范和最佳实践指导*
