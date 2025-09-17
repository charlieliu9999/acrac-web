# ACRAC 数据库构建脚本

本目录包含ACRAC系统的数据库构建和管理脚本。

## 核心脚本

### 1. build_acrac_from_csv_siliconflow.py
**主要数据库构建脚本**

```bash
# 完整构建数据库
python build_acrac_from_csv_siliconflow.py build --csv-file ../ACR_data/ACR_final.csv

# 仅生成向量（数据已存在）
python build_acrac_from_csv_siliconflow.py vectors --api-key your_api_key

# 验证数据库状态
python build_acrac_from_csv_siliconflow.py verify

# 清理数据库
python build_acrac_from_csv_siliconflow.py clean
```

**功能特性:**
- 使用SiliconFlow API生成真实向量嵌入
- 支持PostgreSQL + pgvector
- 批量数据处理优化
- 自动创建向量索引
- 数据完整性验证

### 2. test_vector_search_simple.py
**向量搜索功能测试**

```bash
python test_vector_search_simple.py
```

**测试内容:**
- 科室搜索
- 主题搜索
- 临床场景搜索
- 检查项目搜索
- 临床推荐搜索

### 3. test_clinical_scenarios.py
**临床场景案例测试**

```bash
python test_clinical_scenarios.py
```

**测试案例:**
- 头痛相关案例
- 神经科案例
- 心血管案例
- 认知功能障碍案例

## 辅助脚本

### 4. run_vector_build.py
**简化的构建启动器**

```bash
python run_vector_build.py
```

### 5. README_向量数据库构建.md
**详细的构建文档**

包含完整的构建流程说明和故障排除指南。

## 使用流程

### 首次构建
1. 确保PostgreSQL服务运行
2. 配置SiliconFlow API密钥
3. 运行主构建脚本
4. 验证构建结果

### 日常维护
1. 定期验证数据库状态
2. 监控向量覆盖率
3. 根据需要重新构建

### 测试验证
1. 运行向量搜索测试
2. 测试临床场景匹配
3. 验证API接口功能

## 配置要求

### 环境变量
- `SILICONFLOW_API_KEY`: SiliconFlow API密钥
- `DATABASE_URL`: PostgreSQL连接字符串

### 依赖包
- psycopg2-binary
- pgvector
- sentence-transformers
- requests
- pandas
- numpy

## 故障排除

### 常见问题
1. **API密钥错误**: 检查SiliconFlow API密钥配置
2. **数据库连接失败**: 确认PostgreSQL服务状态
3. **向量生成失败**: 检查网络连接和API配额
4. **内存不足**: 调整批处理大小

### 性能优化
1. 使用批量处理减少API调用
2. 调整向量索引参数
3. 监控数据库性能

## 数据质量

### 验证指标
- 向量覆盖率: 应达到100%
- 数据完整性: 无孤立记录
- 搜索精度: 相似度>0.5
- 响应时间: <100ms

### 监控命令
```bash
# 检查向量覆盖率
python build_acrac_from_csv_siliconflow.py verify

# 测试搜索性能
python test_vector_search_simple.py

# 验证临床场景匹配
python test_clinical_scenarios.py
```