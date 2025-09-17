import json
import pytest

from app.services.rag_llm_recommendation_service import RAGLLMRecommendationService


def _svc():
    return RAGLLMRecommendationService()


def test_parse_llm_response_valid_minimal():
    svc = _svc()
    payload = {
        "recommendations": [
            {
                "rank": 1,
                "procedure_name": "CT 颅脑平扫",
                "modality": "CT",
                "appropriateness_rating": "9/9",
                "recommendation_reason": "急性重症首选",
                "clinical_considerations": "急诊优先"
            }
        ],
        "summary": "推荐CT排除出血"
    }
    out = svc.parse_llm_response(json.dumps(payload, ensure_ascii=False))
    assert isinstance(out, dict)
    assert out.get("recommendations") and out["recommendations"][0]["procedure_name"].startswith("CT")
    assert out["summary"]


def test_parse_llm_response_with_codefence_and_quotes():
    svc = _svc()
    txt = """```json
{
  "recommendations": [
    {"procedure_name": "MR 脑部平扫", "modality": "MRI", "appropriateness_rating": 8, "recommendation_reason": "神经评估", "clinical_considerations": "无辐射"}
  ],
  "summary": "MRI 可作为进一步评估"
}
```"""
    out = svc.parse_llm_response(txt)
    assert out["recommendations"][0]["appropriateness_rating"] in ("8/9", "8/9")


def test_parse_llm_response_tolerates_synonyms():
    svc = _svc()
    txt = json.dumps({
        "recommendations": [
            {
                "procedure": "DR 胸片",
                "modality": "XR",
                "reason": "初筛",
                "appropriateness_rating": "7"
            }
        ],
        "summary": "胸片可先行"
    }, ensure_ascii=False)
    out = svc.parse_llm_response(txt)
    rec = out["recommendations"][0]
    assert rec["procedure_name"].startswith("DR")
    assert rec["appropriateness_rating"].endswith("/9")

