# 生产推荐 API 使用说明

更新时间：2025 年 2 月

## 1. 概述

该文档介绍新增的快速生产推荐接口，面向对外推理服务场景。接口特点：
- 仅使用向量召回 + 确定性排序，避免 LLM 推理，响应更快
- 默认隐藏调试、理由等冗余字段，仅返回必要的推荐结构
- 支持单条实时调用与文件批量处理

所有接口通过 FastAPI `/api/v1` 暴露，需在网关层代理为 `/api`。

## 2. 单条推荐接口

- **URL**：`POST /api/v1/acrac/production/recommendation`
- **请求体**：

```json
{
  "clinical_query": "65岁男性，持续胸痛伴随呼吸困难，需要判断肺部病变",
  "top_k": 3
}
```

参数说明：
- `clinical_query`：必填，临床描述文本，建议 3-600 字符
- `top_k`：可选，返回检查项目数量，范围 1-10，默认沿用系统配置

- **响应体**：

```json
{
  "query": "65岁男性，持续胸痛伴随呼吸困难，需要判断肺部病变",
  "recommendations": [
    {
      "rank": 1,
      "procedure_name": "CT肺动脉造影",
      "modality": "CT",
      "appropriateness_rating": 8.0,
      "appropriateness_category": "通常适宜",
      "similarity": 0.8125,
      "scenario": {
        "description": "疑似肺栓塞的成人",
        "panel": "胸部影像",
        "topic": "肺动脉疾病",
        "risk_level": "高",
        "patient_population": "成人"
      }
    }
  ],
  "processing_time_ms": 128,
  "top_k": 3,
  "similarity_threshold": 0.6,
  "source": "vector-search"
}
```

字段说明：
- `recommendations`：按相似度与适宜性去重排序后的检查项目
- `scenario`：用于展示的场景摘要（无调试详情）
- `processing_time_ms`：毫秒级耗时，便于监控

## 3. 批量推荐接口

- **URL**：`POST /api/v1/acrac/production/recommendation/upload`
- **请求参数**：
  - `top_k`（Query，可选）同上
- **表单字段**：
  - `file`（必填）上传文件

支持文件类型：`csv`、`xlsx`、`xls`、`json`。文件需包含以下列之一：`query`、`clinical_query`、`clinical_description`、`description`、`case`、`patient_case`。重复行自动去重。

示例 `CSV`：

```csv
query,top_k
57岁女性，乳腺肿块，需进一步明确良恶性,3
65岁男性，持续胸痛伴随呼吸困难，需要判断肺部病变,5
```

- **响应体**：

```json
{
  "total": 2,
  "succeeded": 2,
  "failed": 0,
  "results": [
    {
      "index": 0,
      "query": "57岁女性，乳腺肿块，需进一步明确良恶性",
      "recommendations": [...],
      "processing_time_ms": 102,
      "top_k": 3,
      "similarity_threshold": 0.6,
      "source": "vector-search"
    }
  ],
  "errors": []
}
```

失败记录将出现在 `errors` 数组中，包含 `index`（文件中的行号，从 0 起）、`query`、`error` 描述。

## 4. 前端页面

前端新增页面 `ProductionRecommendation.tsx`，提供：
- 单条输入窗体，实时展示推荐表格
- 批量上传流程，展示成功统计、失败原因与逐条结果

页面已集成到左侧菜单「生产推荐」，构建无需额外环境变量。

## 5. 运维提示

- 可通过 `settings.VECTOR_SIMILARITY_THRESHOLD`、`RAG_TOP_RECOMMENDATIONS_PER_SCENARIO` 控制默认阈值与 Top K
- 批量接口默认限制 100 MB 文件，可在 `backend/app/core/config.py` 的 `MAX_UPLOAD_SIZE` 调整
- 若需要记录外部访问日志，可在 FastAPI 层的 `api_router` 中添加依赖或中间件

如需扩展字段或新增导出格式，请同步更新本文档与前端页面。
