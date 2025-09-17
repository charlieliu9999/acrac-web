# 可配置RAG+LLM系统使用指南

## 🎯 系统概述

根据您的要求，我们已经将RAG+LLM系统升级为完全可配置的版本，提供了更高的灵活性和可定制性。您可以通过不同的参数组合来控制系统的行为和输出。

## 🔧 配置参数详解

### 1. 场景显示数量 (top_scenarios)
- **参数**: `top_scenarios`
- **类型**: 整数 (1-10)
- **默认值**: 2
- **说明**: 控制显示的临床场景数量
- **影响**: 
  - 数量越多，提供的上下文信息越丰富
  - 但会增加提示词长度，影响推理速度
  - 建议范围：2-5

### 2. 每个场景的推荐数量 (top_recommendations_per_scenario)  
- **参数**: `top_recommendations_per_scenario`
- **类型**: 整数 (1-10)
- **默认值**: 3
- **说明**: 控制每个场景下显示的检查项目数量
- **影响**:
  - 数量越多，推荐选择越丰富
  - 但会增加提示词复杂度
  - 建议范围：3-5

### 3. 推荐理由显示 (show_reasoning)
- **参数**: `show_reasoning`
- **类型**: 布尔值 (true/false)
- **默认值**: true
- **说明**: 控制是否显示详细的推荐理由
- **影响**:
  - true: 提供详细理由，提示词较长，推理质量更高
  - false: 简化提示词，推理速度更快，但信息较少

### 4. 相似度阈值 (similarity_threshold)
- **参数**: `similarity_threshold`
- **类型**: 浮点数 (0.1-0.9)
- **默认值**: 0.6
- **说明**: 控制RAG模式和无RAG模式的切换阈值
- **影响**:
  - 高阈值(0.7-0.9): 更严格，更容易触发无RAG模式
  - 中等阈值(0.5-0.7): 平衡，推荐设置
  - 低阈值(0.1-0.5): 宽松，几乎总是使用RAG模式

## 📱 使用方式

### 1. 环境变量配置（全局默认）

在 `.env` 文件中设置：

```env
# 提示词配置参数
RAG_TOP_SCENARIOS=2                           # 默认场景数量
RAG_TOP_RECOMMENDATIONS_PER_SCENARIO=3        # 默认每场景推荐数
RAG_SHOW_REASONING=true                       # 默认显示理由
VECTOR_SIMILARITY_THRESHOLD=0.6               # 默认相似度阈值
```

### 2. API请求参数（动态配置）

#### 2.1 POST API 请求

```bash
curl -X POST "http://localhost:8001/api/v1/acrac/rag-llm/intelligent-recommendation" \
  -H "Content-Type: application/json" \
  -d '{
    "clinical_query": "45岁女性，慢性反复头痛3年",
    "debug_mode": true,
    "top_scenarios": 3,
    "top_recommendations_per_scenario": 4,
    "show_reasoning": true,
    "similarity_threshold": 0.5
  }'
```

#### 2.2 GET API 请求（简化）

```bash
curl "http://localhost:8001/api/v1/acrac/rag-llm/intelligent-recommendation-simple?query=45岁女性慢性头痛&top_scenarios=3&top_recs=4&show_reasoning=true&threshold=0.5&debug=true"
```

## 🎨 配置方案示例

### 1. 极简配置（快速推理）
```json
{
  "top_scenarios": 1,
  "top_recommendations_per_scenario": 2,
  "show_reasoning": false,
  "similarity_threshold": 0.6
}
```
**适用场景**: 需要快速响应，对详细信息要求不高

### 2. 标准配置（推荐）
```json
{
  "top_scenarios": 2,
  "top_recommendations_per_scenario": 3,
  "show_reasoning": true,
  "similarity_threshold": 0.6
}
```
**适用场景**: 日常使用，平衡质量和速度

### 3. 详细配置（高质量推理）
```json
{
  "top_scenarios": 3,
  "top_recommendations_per_scenario": 5,
  "show_reasoning": true,
  "similarity_threshold": 0.5
}
```
**适用场景**: 复杂病例，需要全面分析

### 4. 严格配置（高准确性）
```json
{
  "top_scenarios": 2,
  "top_recommendations_per_scenario": 3,
  "show_reasoning": true,
  "similarity_threshold": 0.8
}
```
**适用场景**: 要求高精度匹配，宁可无RAG也不要低质量RAG

## 📊 配置效果对比

| 配置类型 | 提示词长度 | 推理速度 | 推荐质量 | 信息丰富度 | 适用场景 |
|---------|-----------|---------|---------|-----------|---------|
| **极简** | ~1200字符 | 很快 | 基础 | 低 | 快速筛查 |
| **标准** | ~1600字符 | 正常 | 好 | 中等 | 日常使用 |
| **详细** | ~2500字符 | 较慢 | 很好 | 高 | 复杂病例 |
| **严格** | ~1600字符 | 正常 | 高精度 | 中等 | 精准诊断 |

## 🔍 调试和监控

### 启用调试模式
```json
{
  "clinical_query": "您的查询",
  "debug_mode": true,
  "include_raw_data": true
}
```

### 调试信息包含
1. **步骤1**: 查询处理
2. **步骤2**: 向量生成 
3. **步骤3**: 场景搜索结果
4. **步骤4**: 相似度检查
5. **步骤5**: 推理模式选择
6. **步骤6**: 提示词生成
7. **步骤7-9**: LLM处理过程

## 💡 最佳实践建议

### 1. 场景数量选择
```
• 简单查询: top_scenarios = 1-2
• 复杂查询: top_scenarios = 2-3  
• 研究分析: top_scenarios = 3-5
```

### 2. 推荐数量选择
```
• 快速决策: top_recommendations_per_scenario = 2-3
• 全面分析: top_recommendations_per_scenario = 3-5
• 详细研究: top_recommendations_per_scenario = 5+
```

### 3. 阈值设置策略
```
• 高精度场景: similarity_threshold = 0.7-0.8
• 平衡使用: similarity_threshold = 0.5-0.7
• 宽松匹配: similarity_threshold = 0.3-0.5
```

### 4. 理由显示策略
```
• 临床决策: show_reasoning = true (需要详细依据)
• 快速筛查: show_reasoning = false (提升速度)
• 教学培训: show_reasoning = true (便于学习)
```

## 🚀 性能优化建议

### 1. 速度优先
- 减少场景数量 (top_scenarios = 1-2)
- 减少推荐数量 (top_recommendations_per_scenario = 2-3)
- 关闭推荐理由 (show_reasoning = false)

### 2. 质量优先  
- 适中场景数量 (top_scenarios = 2-3)
- 充分推荐数量 (top_recommendations_per_scenario = 3-5)
- 启用推荐理由 (show_reasoning = true)
- 合理阈值设置 (similarity_threshold = 0.5-0.7)

### 3. 成本优化
- 控制提示词总长度在2000字符以内
- 平衡参数设置，避免极端配置
- 根据实际需求动态调整

## 🧪 测试验证

我们提供了完整的测试脚本来验证不同配置的效果：

```bash
# 运行配置测试
cd /Users/charlieliu/git_project_vscode/09_medical/ACRAC-web/backend
python scripts/test_configurable_rag_llm.py
```

测试脚本会验证：
- ✅ 默认配置效果
- ✅ 各参数独立调整效果  
- ✅ 组合参数优化效果
- ✅ 极端配置稳定性
- ✅ 无RAG模式触发

## 📋 API 响应格式

配置生效后，API响应会包含配置信息：

```json
{
  "success": true,
  "query": "患者查询",
  "llm_recommendations": {
    "recommendations": [...],
    "summary": "推荐总结"
  },
  "similarity_threshold": 0.6,
  "max_similarity": 0.634,
  "is_low_similarity_mode": false,
  "processing_time_ms": 8000,
  "debug_info": {
    "step_5_scenarios_with_recs": {
      "scenarios_count": 2,
      "total_recommendations": 4
    },
    "step_6_prompt_length": 1666
  }
}
```

## 🎉 总结

通过这些可配置参数，您现在可以：

1. **🎛️ 灵活调整**: 根据具体需求调整系统行为
2. **⚡ 优化性能**: 平衡推理速度和质量
3. **🎯 精确控制**: 细粒度控制输出内容
4. **📊 监控效果**: 通过调试模式验证配置效果
5. **🔧 动态配置**: API请求时实时调整参数

系统现在具备了您要求的所有灵活性！🎊

---

**配置指南版本**: v1.0  
**更新时间**: 2025-09-08  
**技术支持**: ACRAC开发团队