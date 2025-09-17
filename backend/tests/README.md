# ACRAC API测试指南

## 📋 测试概述

本测试套件为ACRAC医疗影像智能推荐系统提供全面的API端点测试，包括：

- 🗄️ **数据库向量功能测试** - 测试底层数据库和向量搜索功能
- 🔍 **向量搜索API测试** - 测试所有向量搜索相关的API端点
- 🏥 **综合API测试** - 测试完整的业务功能API
- 📊 **端到端场景测试** - 测试真实的临床使用场景

## 🚀 快速开始

### 环境准备

1. **安装测试依赖**
```bash
cd backend
pip install -r requirements-test.txt
```

2. **启动服务**
```bash
# 启动数据库
docker-compose up -d postgres

# 启动API服务
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. **配置环境变量**
```bash
# 确保以下环境变量已设置
export SILICONFLOW_API_KEY="your_api_key"
export DATABASE_URL="postgresql://postgres:password@localhost:5432/acrac_db"
```

### 运行测试

#### 🎯 运行所有测试（推荐）
```bash
cd backend/tests
python run_all_tests.py
```

#### 🔧 运行单独测试模块

**数据库向量功能测试**
```bash
python test_database_vector.py
```

**向量搜索API测试**
```bash
python test_vector_search_api.py
```

**综合API测试**
```bash
python test_comprehensive_api.py
```

## 📊 测试结果

### 测试报告文件

运行测试后会生成以下文件：

- `master_test_report_YYYYMMDD_HHMMSS.json` - 完整的JSON格式测试报告
- `master_test_report_YYYYMMDD_HHMMSS.html` - 可视化HTML测试报告
- `test_execution.log` - 详细的测试执行日志

### 成功率标准

- **🎉 优秀 (≥80%)**: 系统状态优秀，可以投入生产使用
- **⚠️ 良好 (60-79%)**: 系统基本可用，建议解决失败项后投入使用  
- **❌ 需改进 (<60%)**: 系统存在严重问题，需要修复后才能使用

## 🧪 测试详情

### 第一阶段: 数据库向量功能测试

**测试内容:**
- ✅ 数据库连接测试
- ✅ pgvector扩展检查
- ✅ 数据完整性验证
- ✅ 向量嵌入生成测试
- ✅ 向量相似度搜索测试
- ✅ 搜索准确性验证

**关键指标:**
- 数据库连接状态
- 向量覆盖率 (目标: 100%)
- 向量生成成功率 (目标: 100%)
- 搜索响应时间 (目标: <50ms)

### 第二阶段: 向量搜索API测试

**测试内容:**
- ✅ 健康检查API
- ✅ 综合向量搜索API
- ✅ 各实体类型搜索API (panels, topics, scenarios, procedures, recommendations)
- ✅ 输入参数验证
- ✅ 性能和并发测试

**测试查询:**
```
1. "45岁女性，慢性反复头痛3年"
2. "突发剧烈头痛"
3. "胸痛伴气促"
4. "腹痛伴发热"
5. "关节疼痛肿胀"
... 等临床查询
```

### 第三阶段: 综合API测试

**测试的API端点:**
- `/api/v1/acrac/search` - ACRAC搜索
- `/api/v1/acrac/recommend` - ACRAC推荐
- `/api/v1/acrac/analyze` - ACRAC分析
- `/api/v1/acrac/intelligent/analyze` - 智能分析
- `/api/v1/acrac/intelligent/recommend` - 智能推荐
- `/api/v1/acrac/methods/recommend` - 三种方法推荐
- `/api/v1/acrac/methods/compare` - 方法比较

### 第四阶段: 端到端场景测试

**临床场景:**
1. **急性头痛患者** - 45岁女性，突发剧烈头痛2小时，伴恶心呕吐
2. **胸痛患者** - 55岁男性，胸痛3天，活动后加重，伴气促
3. **腹痛患者** - 30岁女性，右下腹痛6小时，伴发热

**验证标准:**
- API调用成功率
- 推荐结果的临床相关性
- 期望检查项目的匹配率

## 🔧 故障排除

### 常见问题

#### 1. 数据库连接失败
```
❌ 数据库连接失败: connection refused
```
**解决方案:**
- 检查PostgreSQL服务是否启动: `docker-compose ps`
- 检查端口是否被占用: `lsof -i :5432`
- 验证连接配置: `DATABASE_URL`

#### 2. pgvector扩展未安装
```
❌ pgvector扩展未安装
```
**解决方案:**
- 使用官方pgvector镜像: `pgvector/pgvector:pg15`
- 检查扩展安装: `SELECT * FROM pg_extension WHERE extname = 'vector'`

#### 3. 向量生成失败
```
❌ 向量生成失败: API key not found
```
**解决方案:**
- 设置SiliconFlow API密钥: `export SILICONFLOW_API_KEY="your_key"`
- 检查网络连接到siliconflow.cn
- 验证API密钥有效性

#### 4. API服务无响应
```
❌ API测试失败: Connection timeout
```
**解决方案:**
- 检查API服务状态: `curl http://localhost:8000/health`
- 验证服务启动: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- 检查防火墙和端口配置

### 性能调优建议

#### 数据库性能
```sql
-- 检查索引状态
SELECT * FROM pg_indexes WHERE tablename IN ('panels', 'topics', 'clinical_scenarios', 'procedure_dictionary', 'clinical_recommendations');

-- 更新表统计信息
ANALYZE panels, topics, clinical_scenarios, procedure_dictionary, clinical_recommendations;
```

#### 向量搜索性能
- 调整相似度阈值 (0.3-0.7)
- 优化top_k参数 (5-20)
- 使用IVFFLAT索引

## 📈 性能基准

### 期望性能指标

| 测试项目 | 目标值 | 优秀值 |
|---------|--------|--------|
| 数据库连接时间 | <1s | <0.5s |
| 向量生成时间 | <2s | <1s |
| 向量搜索时间 | <50ms | <20ms |
| API响应时间 | <500ms | <200ms |
| 并发处理能力 | >50 req/s | >100 req/s |
| 内存使用 | <2GB | <1GB |

### 数据质量指标

| 指标 | 目标值 |
|------|--------|
| 向量覆盖率 | 100% |
| 数据完整性 | 100% |
| 相似度准确性 | >80% |
| 临床推荐相关性 | >70% |

## 🔄 持续集成

### GitHub Actions配置示例

```yaml
name: API Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg15
        env:
          POSTGRES_PASSWORD: password
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install -r backend/requirements-test.txt
      - name: Run tests
        run: |
          cd backend/tests
          python run_all_tests.py
        env:
          DATABASE_URL: postgresql://postgres:password@localhost:5432/acrac_db
          SILICONFLOW_API_KEY: ${{ secrets.SILICONFLOW_API_KEY }}
```

## 📞 支持和反馈

如果在运行测试过程中遇到问题：

1. 查看详细日志文件 `test_execution.log`
2. 检查测试报告中的建议和改进措施
3. 参考故障排除部分
4. 联系开发团队获取支持

---

**注意:** 测试需要真实的数据库和API服务，请确保在执行测试前所有依赖服务都已正确启动和配置。