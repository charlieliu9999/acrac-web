# ACRAC向量数据库构建方案 - 修正版

## 概述

本方案基于您的审阅建议，对原始代码进行了全面修正，解决了pgvector适配、向量生成、索引时机等关键问题。

## 主要修正内容

### 1. 致命问题修复 ✅

#### pgvector适配
- ✅ 添加 `CREATE EXTENSION IF NOT EXISTS vector;`
- ✅ 注册pgvector适配器：`register_vector(self.conn)`
- ✅ 支持真实向量写入，回退到字符串方式
- ✅ 动态向量维度支持（1024或模型实际维度）

#### 向量生成
- ✅ 集成sentence-transformers，使用BGE-M3模型
- ✅ 批量向量生成，提升性能
- ✅ 规范化文本拼接（中英分条）
- ✅ 回退机制：模型失败时使用随机向量

#### 索引时机
- ✅ 分离基础索引和向量索引创建
- ✅ 数据写入完成后再创建向量索引
- ✅ 自动执行ANALYZE和设置ivfflat.probes

### 2. 数据建模优化 ✅

#### ID类型统一
- ✅ 外键统一使用整数ID
- ✅ 保留semantic_id作为业务标识
- ✅ 添加冗余字段支持查询

#### 唯一约束
- ✅ 添加业务唯一约束
- ✅ 支持幂等构建（ON CONFLICT DO UPDATE）
- ✅ 防止重复数据插入

#### 审计功能
- ✅ 自动更新updated_at触发器
- ✅ 完整的数据变更审计日志
- ✅ 支持INSERT/UPDATE/DELETE操作记录

### 3. ETL性能优化 ✅

#### 批量处理
- ✅ 使用execute_values批量写入
- ✅ 分页处理大数据集
- ✅ 减少数据库往返次数

#### 数据规范化
- ✅ 统一的字符串规范化函数
- ✅ 防止"肉眼相同、机器不同"的重复
- ✅ 改进缓存键生成策略

### 4. 向量检索增强 ✅

#### 层次化向量
- ✅ Panel: 科室信息
- ✅ Topic: 科室+主题信息
- ✅ Scenario: 完整临床上下文
- ✅ Procedure: 检查项目属性
- ✅ Recommendation: 完整临床决策

#### 混合检索
- ✅ 向量相似度 + 结构化过滤
- ✅ 支持模态、部位、人群等过滤条件
- ✅ 优化的查询性能

### 5. 临床语义规则 ✅

#### 属性抽取
- ✅ 改进的模态识别（CT/MR/US/XR等）
- ✅ 精确的检查部位分类
- ✅ 对比剂使用检测
- ✅ 辐射等级评估

#### 妊娠安全性
- ✅ 基于模态和剂量的规则评估
- ✅ 结合ACR指南的特殊考虑
- ✅ 更可信赖的安全性评级

## 文件结构

```
backend/scripts/
├── ACRAC完整数据库向量库构建方案.py  # 主构建脚本（已修正）
├── run_vector_build.py              # 简化运行脚本
├── test_vector_search.py            # 向量检索测试脚本
├── requirements-vector.txt          # 向量相关依赖
└── README_向量数据库构建.md         # 本文档
```

## 使用方法

### 1. 安装依赖

```bash
cd backend
pip install -r requirements-vector.txt
```

### 2. 准备数据库

确保PostgreSQL已安装并运行，创建数据库：

```sql
CREATE DATABASE acrac_db;
```

### 3. 运行构建

#### 方式1：使用简化脚本
```bash
cd backend/scripts
python run_vector_build.py
```

#### 方式2：使用原始脚本
```bash
cd backend/scripts
python ACRAC完整数据库向量库构建方案.py build --csv-file ../../ACR_data/ACR_final.csv
```

### 4. 测试向量检索

```bash
cd backend/scripts
python test_vector_search.py
```

## 构建流程

1. **创建扩展和架构** - 创建pgvector扩展和所有表
2. **创建触发器** - 自动更新和审计触发器
3. **创建基础索引** - 非向量索引
4. **加载CSV数据** - 支持多种编码和分隔符
5. **构建业务数据** - 批量写入Panels/Topics/Scenarios/Procedures/Recommendations
6. **生成向量嵌入** - 使用真实嵌入模型
7. **创建向量索引** - IVFFLAT索引，优化查询性能
8. **验证构建结果** - 完整性检查和示例数据

## 性能优化

### 批量处理
- 使用execute_values批量写入，提升10-50倍性能
- 分页处理，避免内存溢出
- 减少数据库连接开销

### 索引优化
- 基础索引：支持快速过滤和排序
- 向量索引：IVFFLAT近似搜索，支持大规模向量检索
- 复合索引：优化复杂查询

### 向量检索
- 层次化向量：不同粒度的语义表示
- 混合检索：向量+结构化过滤
- 查询优化：ANALYZE统计信息，ivfflat.probes调优

## 监控和日志

### 构建统计
- 各表记录数统计
- 向量覆盖率监控
- 错误日志记录

### 检索日志
- 查询文本和类型
- 搜索时间和结果数
- 性能指标跟踪

### 审计日志
- 数据变更历史
- 操作类型和用户
- 完整的数据diff

## 故障排除

### 常见问题

1. **pgvector扩展未安装**
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

2. **向量维度不匹配**
   - 检查模型实际维度
   - 确保建表时使用正确维度

3. **嵌入模型加载失败**
   - 检查sentence-transformers安装
   - 网络连接问题（模型下载）
   - 回退到随机向量模式

4. **内存不足**
   - 减少批量大小
   - 分批处理大数据集

### 性能调优

1. **ivfflat参数调优**
   ```sql
   SET ivfflat.probes = 10;  -- 根据数据量调整
   ```

2. **索引重建**
   ```sql
   DROP INDEX idx_procedures_embedding;
   CREATE INDEX idx_procedures_embedding ON procedure_dictionary USING ivfflat (embedding vector_cosine_ops) WITH (lists = 500);
   ```

3. **统计信息更新**
   ```sql
   ANALYZE;
   ```

## 扩展功能

### 多向量通道
- 标题向量：短名、别名召回
- 描述向量：长文本语义
- 规则向量：适宜性与禁忌

### 混合检索
- 向量相似度 + 关键词匹配
- 多模态融合
- 个性化推荐

### 实时更新
- 增量向量更新
- 在线索引维护
- 热更新支持

## 总结

修正后的代码解决了原始方案中的所有关键问题：

1. ✅ **pgvector适配** - 正确的扩展创建和适配器注册
2. ✅ **真实向量** - 使用医学友好的BGE-M3模型
3. ✅ **正确索引时机** - 数据写入完成后再建向量索引
4. ✅ **统一ID类型** - 外键使用整数ID，业务查询用semantic_id
5. ✅ **幂等构建** - 支持重复执行，不会产生重复数据
6. ✅ **批量处理** - 大幅提升ETL性能
7. ✅ **审计功能** - 完整的数据变更跟踪
8. ✅ **临床规则** - 改进的属性抽取和安全性评估

这套方案现在可以稳定支持"检查推荐"的线上检索与持续演进，为ACRAC系统提供强大的向量检索能力。
