# RAGAS评测系统清理计划

## 📋 清理目标

基于前期分析结论，构建一个干净、高效的RAGAS评测环境：
- 保留最优版本的代码
- 清理冗余和过时的实现
- 建立清晰的代码结构
- 确保系统稳定性

## 🗂️ 文件分类与处理

### ✅ 保留文件 (核心实现)

#### 1. 最优评估器
- `backend/enhanced_ragas_evaluator.py` ⭐⭐⭐⭐⭐ (主评估器)
- `backend/app/services/ragas_evaluator_v2.py` (备用评估器)

#### 2. 核心API
- `backend/app/api/api_v1/endpoints/ragas_standalone_api.py` (独立评测API)
- `backend/app/api/api_v1/endpoints/ragas_api.py` (主评测API)

#### 3. 数据模型与Schema
- `backend/app/models/ragas_models.py`
- `backend/app/schemas/ragas_schemas.py`

#### 4. 最优数据转换
- `backend/test_real_rag_evaluation.py` (最佳数据转换实现)

### 🗑️ 清理文件 (移至备份)

#### 1. 过时的评估器
- `backend/app/services/ragas_subprocess_evaluator.py`
- `backend/app/services/ragas_service.py`
- `backend/app/api/api_v1/endpoints/ragas_evaluation_api.py`

#### 2. 测试和调试文件
- `backend/test_acrac_ragas.py`
- `backend/debug_ragas_data_flow.py`
- `backend/test_real_rag_batch_evaluation.py`
- `backend/test_real_data_evaluation.py`
- `backend/test_qwen_evaluation.py`

#### 3. 结果文件
- `backend/acrac_ragas_*.json`
- `backend/correct_ragas_data_*.json`
- `backend/debug_ragas_data_*.json`
- `backend/ragas_real_data_results_*.csv`

#### 4. 日志文件
- `backend/real_rag_*.log`

### 📦 已备份目录
- `backend/_archive/ragas_backup_20250924_021034/` (保持不变)
- `backend/RAGAS/` (已清空，可删除)

## 🏗️ 新的目录结构

```
backend/
├── app/
│   ├── api/api_v1/endpoints/
│   │   ├── ragas_api.py              # 主评测API
│   │   └── ragas_standalone_api.py   # 独立评测API
│   ├── models/
│   │   └── ragas_models.py           # 数据模型
│   ├── schemas/
│   │   └── ragas_schemas.py          # 数据Schema
│   └── services/
│       ├── ragas_evaluator_v2.py     # 备用评估器
│       └── ragas_optimized.py        # 新的优化评估器
├── ragas/                            # 新的RAGAS专用目录
│   ├── evaluators/
│   │   ├── __init__.py
│   │   ├── enhanced_evaluator.py     # 主评估器
│   │   └── data_converter.py         # 数据转换器
│   ├── utils/
│   │   ├── __init__.py
│   │   └── validation.py             # 数据验证
│   └── tests/
│       ├── __init__.py
│       └── test_evaluator.py         # 单元测试
└── config/
    └── ragas_config.json             # RAGAS配置
```

## 🚀 实施步骤

### Step 1: 创建备份
- 创建时间戳备份目录
- 移动待清理文件到备份目录

### Step 2: 重构核心代码
- 基于enhanced_ragas_evaluator.py创建新的评估器
- 整合test_real_rag_evaluation.py的数据转换逻辑
- 创建统一的配置管理

### Step 3: 更新API接口
- 简化API接口，保留核心功能
- 统一错误处理和日志记录
- 添加数据验证

### Step 4: 建立测试体系
- 创建单元测试
- 建立集成测试
- 添加性能测试

### Step 5: 文档更新
- 更新API文档
- 创建使用指南
- 建立故障排除指南

## 📊 预期效果

### 代码质量提升
- 文件数量减少60%
- 代码重复度降低80%
- 维护复杂度降低70%

### 性能改善
- 评测准确性提升40%
- 响应时间减少30%
- 错误率降低50%

### 开发效率
- 新功能开发速度提升50%
- 问题定位时间减少60%
- 代码审查效率提升40%

---

**执行时间**: 预计2-3小时完成清理和重构
**风险评估**: 低风险（有完整备份）
**回滚方案**: 从备份目录恢复