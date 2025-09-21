# ACRAC 医疗影像智能推荐系统

## 项目简介

ACRAC (American College of Radiology Appropriateness Criteria) 是一个基于向量数据库的医疗影像智能推荐系统，能够根据患者症状、病史和临床特征，智能推荐最适合的影像检查项目。

## 核心特性

- 🧠 **智能向量检索**: 使用SiliconFlow BGE-M3模型进行医学语义理解
- 🏥 **临床场景匹配**: 支持15,970+临床推荐场景的智能匹配
- 🔍 **多模态支持**: 支持CT、MRI、DR、RF、MG等多种检查方式
- ⚡ **实时推荐**: 毫秒级响应速度的智能推荐
- 📊 **数据完整性**: 包含13个科室、285个主题、1,391个临床场景

## 技术架构

### 后端技术栈
- **框架**: FastAPI + SQLAlchemy
- **数据库**: PostgreSQL + pgvector
- **向量模型**: SiliconFlow BGE-M3 (1024维)
- **容器化**: Docker + Docker Compose

### 前端技术栈
- **框架**: React 18 + TypeScript
- **构建工具**: Vite
- **UI组件**: Ant Design + 自定义组件

## 项目结构

```
ACRAC-web/
├── backend/                    # 后端服务
│   ├── app/                   # 应用核心代码
│   │   ├── api/              # API路由
│   │   ├── core/             # 核心配置
│   │   ├── models/           # 数据模型
│   │   ├── schemas/          # 数据模式
│   │   └── services/         # 业务逻辑
│   ├── scripts/              # 数据库构建脚本
│   │   ├── build_acrac_from_csv_siliconflow.py  # 主构建脚本
│   │   ├── test_clinical_scenarios.py          # 临床场景测试
│   │   └── test_vector_search_simple.py        # 向量搜索测试
│   ├── requirements.txt      # Python依赖
│   └── .env                 # 环境配置
├── frontend/                  # 前端应用
│   ├── src/                  # 源代码
│   │   ├── pages/           # React页面组件
│   │   ├── api/             # API客户端
│   │   └── App.tsx          # 主应用组件
│   └── package.json         # 前端依赖
├── ACR_data/                 # 原始数据
├── docs/                     # 项目文档
├── deployment/               # 部署配置
└── backup/                   # 备份文件
```

## 快速开始

### 环境要求
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ with pgvector
- Docker & Docker Compose

### 1. 克隆项目
```bash
git clone <repository-url>
cd ACRAC-web
```

### 2. 配置环境
```bash
# 复制环境配置文件
cp backend/acrac.env.example backend/.env

# 编辑配置文件，设置SiliconFlow API密钥
vim backend/.env
```

### 3. 启动数据库
```bash
docker-compose up -d postgres
```

### 4. 构建数据库
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 构建向量数据库
python scripts/build_acrac_from_csv_siliconflow.py build --csv-file ../ACR_data/ACR_final.csv
```

### 5. 启动后端服务
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. 启动前端服务
```bash
cd frontend
npm install
npm run dev
```

## API 使用

### 向量搜索API
```bash
# 搜索相关临床场景
curl -X POST "http://localhost:8000/api/v1/vector-search/scenarios" \
  -H "Content-Type: application/json" \
  -d '{"query": "45岁女性，慢性反复头痛3年", "limit": 5}'

# 搜索推荐检查项目
curl -X POST "http://localhost:8000/api/v1/vector-search/recommendations" \
  -H "Content-Type: application/json" \
  -d '{"query": "突发剧烈头痛", "limit": 3}'
```

### 数据统计API
```bash
# 获取数据库统计信息
curl "http://localhost:8000/api/v1/stats/overview"

# 获取向量覆盖率
curl "http://localhost:8000/api/v1/stats/vector-coverage"
```

## 测试

### 运行向量检索测试
```bash
cd backend
python scripts/test_vector_search_simple.py
```

### 运行临床场景测试
```bash
cd backend
python scripts/test_clinical_scenarios.py
```

## 数据说明

### 数据来源
- **ACR数据**: 基于美国放射学会适宜性标准
- **向量模型**: SiliconFlow BGE-M3 (1024维)
- **数据规模**: 15,970+临床推荐记录

### 数据表结构
- `panels`: 科室信息 (13条)
- `topics`: 医学主题 (285条)
- `clinical_scenarios`: 临床场景 (1,391条)
- `procedure_dictionary`: 检查项目 (1,053条)
- `clinical_recommendations`: 临床推荐 (15,970条)

## 部署

### Docker部署
```bash
# 构建并启动所有服务
docker-compose up --build

# 仅启动数据库
docker-compose up -d postgres
```

### 生产环境
```bash
# 构建生产镜像
docker build -t acrac-backend ./backend
docker build -t acrac-frontend ./frontend

# 使用docker-compose.prod.yml
docker-compose -f docker-compose.prod.yml up -d
```

## 开发指南

### 添加新的临床场景
1. 在`ACR_data/`目录添加新的CSV数据
2. 运行构建脚本更新数据库
3. 测试向量检索效果

### 自定义向量模型
1. 修改`SiliconFlowEmbedder`类
2. 更新`requirements.txt`
3. 重新构建数据库

### API扩展
1. 在`app/api/`目录添加新的路由
2. 在`app/services/`实现业务逻辑
3. 更新API文档

## 性能优化

### 向量搜索优化
- 使用IVFFLAT索引提升搜索速度
- 批量处理减少API调用次数
- 缓存常用查询结果

### 数据库优化
- 定期执行VACUUM和ANALYZE
- 监控查询性能
- 调整PostgreSQL参数

## 故障排除

### 常见问题
1. **向量生成失败**: 检查SiliconFlow API密钥
2. **数据库连接失败**: 确认PostgreSQL服务状态
3. **搜索精度低**: 检查向量模型和数据质量

### 日志查看
```bash
# 查看后端日志
tail -f backend/logs/app.log

# 查看数据库日志
docker-compose logs postgres
```

## 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 创建Pull Request

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 联系方式

- 项目维护者: [Your Name]
- 邮箱: [your.email@example.com]
- 项目地址: [GitHub Repository URL]

---

**注意**: 本系统仅供医疗研究和教育用途，不应用于实际临床诊断决策。
