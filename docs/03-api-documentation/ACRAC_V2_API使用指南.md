# ACRAC V2.0 API使用指南

## 🎯 API概述

ACRAC V2.0 提供了完整的RESTful API，支持医疗影像检查推荐系统的所有功能，包括数据查询、智能搜索、临床推荐和数据分析。

### 基础信息
- **基础URL**: `http://127.0.0.1:8000/api/v1/acrac/`
- **API文档**: `http://127.0.0.1:8000/docs`
- **版本**: V2.0.0
- **认证**: 暂无（后续版本将添加）

## 📋 API端点详解

### 1. 系统状态检查

#### 健康检查
```bash
GET /api/v1/acrac/health
```

**响应示例**:
```json
{
    "status": "healthy",
    "database_status": "connected",
    "version": "2.0.0",
    "data_summary": {
        "panels": 13,
        "topics": 285,
        "scenarios": 1391,
        "procedures": 1383,
        "recommendations": 15970
    }
}
```

#### 详细统计
```bash
GET /api/v1/acrac/statistics
```

**响应示例**:
```json
{
    "panels_count": 13,
    "topics_count": 285,
    "scenarios_count": 1391,
    "procedures_count": 1383,
    "recommendations_count": 15970,
    "active_panels": 13,
    "active_topics": 285,
    "active_scenarios": 1391,
    "active_procedures": 1383,
    "active_recommendations": 15970,
    "vectors_panels": 13,
    "vectors_topics": 285,
    "vectors_scenarios": 1391,
    "vectors_procedures": 1383,
    "vectors_recommendations": 15970
}
```

### 2. 数据查询

#### 查询所有科室
```bash
GET /api/v1/acrac/panels?active_only=true&page=1&page_size=50
```

**参数**:
- `active_only`: 只显示激活的Panel（默认true）
- `page`: 页码（默认1）
- `page_size`: 每页大小（默认50，最大100）

**响应示例**:
```json
{
    "total": 13,
    "panels": [
        {
            "semantic_id": "P0001",
            "name_zh": "乳腺外科",
            "name_en": "Breast",
            "description": "",
            "is_active": true
        }
    ]
}
```

#### 查询科室下的主题
```bash
GET /api/v1/acrac/panels/P0001/topics?active_only=true
```

**响应示例**:
```json
{
    "panel_id": "P0001",
    "panel_name": "乳腺外科",
    "total": 15,
    "topics": [
        {
            "semantic_id": "T0001",
            "name_zh": "妊娠期乳腺影像学检查",
            "name_en": "Breast Imaging During Pregnancy",
            "description": "",
            "is_active": true
        }
    ]
}
```

#### 查询检查项目
```bash
GET /api/v1/acrac/procedures?modality=CT&body_part=头部&limit=20
```

**参数**:
- `modality`: 检查方式过滤（CT, MRI, US, XR等）
- `body_part`: 检查部位过滤
- `limit`: 返回数量限制

**响应示例**:
```json
{
    "total": 5,
    "filters": {"modality": "CT", "body_part": "头部"},
    "procedures": [
        {
            "semantic_id": "PR0156",
            "name_zh": "CT颅脑(平扫)",
            "name_en": "CT head without IV contrast",
            "modality": "CT",
            "body_part": "头部",
            "contrast_used": false,
            "radiation_level": "中"
        }
    ]
}
```

#### 查询场景推荐
```bash
GET /api/v1/acrac/scenarios/S0001/recommendations?min_rating=7
```

**响应示例**:
```json
{
    "scenario_id": "S0001",
    "scenario_description": "妊娠期女性，≥40岁，乳腺癌筛查，任何风险。",
    "total": 3,
    "recommendations": [
        {
            "recommendation_id": "CR000001",
            "appropriateness_rating": 9,
            "appropriateness_category_zh": "通常适宜",
            "reasoning_zh": "乳腺X线摄影被认为是40岁及以上孕妇筛查乳腺癌的安全方法...",
            "evidence_level": "LimitedReferences",
            "pregnancy_safety": "安全",
            "procedure": {
                "semantic_id": "PR0001",
                "name_zh": "MG双侧乳腺钼靶(筛查)",
                "modality": "MG",
                "radiation_level": "低"
            }
        }
    ]
}
```

### 3. 搜索功能

#### 关键词搜索检查项目
```bash
GET /api/v1/acrac/search/procedures?query=胸部CT&modality=CT&limit=10
```

#### 关键词搜索推荐
```bash
GET /api/v1/acrac/search/recommendations?query=孕妇&min_rating=8&limit=15
```

#### 智能推荐搜索
```bash
POST /api/v1/acrac/search/intelligent
Content-Type: application/json

{
    "clinical_query": "孕妇胸痛需要什么检查",
    "patient_profile": {
        "age": 30,
        "gender": "女性",
        "pregnancy_status": "妊娠期",
        "risk_level": "低风险"
    },
    "filters": {
        "min_rating": 7,
        "pregnancy_safety": "安全"
    },
    "limit": 10
}
```

### 4. 快捷查询

#### 高评分推荐
```bash
GET /api/v1/acrac/quick/high-rating-recommendations?min_rating=8&limit=20
```

#### 按检查方式查询
```bash
GET /api/v1/acrac/quick/procedures-by-modality/CT
```

#### 妊娠安全推荐
```bash
GET /api/v1/acrac/quick/pregnancy-safe-recommendations?limit=15
```

### 5. 数据分析

#### 检查方式分布
```bash
GET /api/v1/acrac/analytics/modality-distribution
```

**响应示例**:
```json
{
    "distribution": {
        "CT": 485,
        "MRI": 324,
        "US": 198,
        "XR": 156,
        "MG": 89,
        "NM": 67,
        "DSA": 45,
        "RF": 19
    },
    "total_procedures": 1383
}
```

#### 适宜性评分分布
```bash
GET /api/v1/acrac/analytics/rating-distribution
```

#### 患者人群统计
```bash
GET /api/v1/acrac/analytics/patient-population-stats
```

## 🔧 高级功能

### 1. 多条件查询
```bash
GET /api/v1/acrac/advanced/recommendations-by-criteria?panel_id=P0001&modality=CT&min_rating=8&limit=50
```

**支持的过滤条件**:
- `panel_id`: Panel语义化ID
- `topic_id`: Topic语义化ID  
- `modality`: 检查方式
- `patient_population`: 患者人群
- `min_rating`: 最低适宜性评分
- `pregnancy_safe`: 是否妊娠安全

### 2. 数据导出
```bash
GET /api/v1/acrac/export/recommendations-summary?format=json
```

### 3. 示例数据查询
```bash
GET /api/v1/acrac/examples/complete-recommendation
```

获取完整的推荐链路示例，展示Panel→Topic→Scenario→Procedure→Recommendation的完整关系。

## 🧪 测试用例

### 1. 基础功能测试
```bash
# 测试健康检查
curl "http://127.0.0.1:8000/api/v1/acrac/health"

# 测试数据查询
curl "http://127.0.0.1:8000/api/v1/acrac/panels"

# 测试搜索功能
curl "http://127.0.0.1:8000/api/v1/acrac/search/procedures?query=CT"
```

### 2. 业务场景测试
```bash
# 场景1：孕妇检查推荐
curl "http://127.0.0.1:8000/api/v1/acrac/search/recommendations?query=妊娠&min_rating=8"

# 场景2：CT检查项目查询
curl "http://127.0.0.1:8000/api/v1/acrac/quick/procedures-by-modality/CT"

# 场景3：高评分推荐
curl "http://127.0.0.1:8000/api/v1/acrac/quick/high-rating-recommendations?min_rating=9"
```

### 3. 性能测试
```bash
# 大量数据查询
curl "http://127.0.0.1:8000/api/v1/acrac/procedures?limit=200"

# 复杂搜索
curl "http://127.0.0.1:8000/api/v1/acrac/search/recommendations?query=检查&limit=100"
```

## ❌ 错误处理

### 常见错误码
- **200**: 成功
- **400**: 请求参数错误
- **404**: 资源不存在
- **500**: 服务器内部错误

### 错误响应格式
```json
{
    "detail": "错误描述信息"
}
```

### 故障排除
1. **连接超时**: 检查服务器是否运行
2. **404错误**: 检查API路径是否正确
3. **500错误**: 查看服务器日志
4. **数据不存在**: 检查语义化ID是否正确

## 💡 最佳实践

### 1. API调用建议
- 使用适当的分页避免大量数据传输
- 设置合理的超时时间
- 实现错误重试机制
- 缓存常用查询结果

### 2. 性能优化
- 使用具体的过滤条件减少结果集
- 避免频繁的全表查询
- 合理设置limit参数
- 使用语义化ID进行精确查询

### 3. 数据使用
- 理解语义化ID的含义和层次关系
- 利用appropriateness_rating进行排序
- 关注pregnancy_safety字段的安全提示
- 结合evidence_level评估推荐可靠性

---

**更多信息请参考完整的API文档: http://127.0.0.1:8000/docs**
