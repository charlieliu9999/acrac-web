"""Hybrid production recommendation service.

This module implements a two阶段 quick recommendation流程：

1. 高相似度路径：
   - 先检索临床场景（Top-K）
   - 针对场景抓取评分最高的检查项目（Top-N）
   - 依据评分+相似度组合分数挑选最终检查，必要时交给轻量 LLM 整理输出
2. 低相似度路径：
   - 相似度低于阈值时，直接调用现有的 RAG+LLM 服务生成建议

这样既能保持确定性排序，又能在陌生病例时保留 LLM 兜底。
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.vector_search_service import VectorSearchService

try:  # Lazy import，避免在未启用LLM时增加启动成本
    from app.services import rag_llm_recommendation_service as rag_mod
except Exception:  # pragma: no cover - 防御
    rag_mod = None  # type: ignore


@dataclass
class RankedRecommendation:
    """Final recommendation entry consumed by API layer."""

    rank: int
    procedure_name: str
    modality: Optional[str]
    appropriateness_rating: Optional[float]
    appropriateness_category: Optional[str]
    scenario_id: Optional[str]
    scenario_description: Optional[str]
    panel_name: Optional[str]
    topic_name: Optional[str]
    similarity: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "procedure_name": self.procedure_name,
            "modality": self.modality,
            "appropriateness_rating": self.appropriateness_rating,
            "appropriateness_category": self.appropriateness_category,
            "similarity": self.similarity,
            "scenario": {
                "id": self.scenario_id,
                "description": self.scenario_description,
                "panel": self.panel_name,
                "topic": self.topic_name,
            },
        }


class ProductionRecommendationService:
    """Hybrid recommendation service optimised for production workloads."""

    def __init__(self, db: Session):
        self._db = db
        self._vector_service = VectorSearchService(db)

        # --- Configurable knobs
        self._top_scenarios = int(
            os.getenv("PRODUCTION_TOP_SCENARIOS", os.getenv("RAG_TOP_SCENARIOS", "3"))
        )
        self._top_recs_per_scenario = int(
            os.getenv(
                "PRODUCTION_TOP_RECOMMENDATIONS_PER_SCENARIO",
                os.getenv("RAG_TOP_RECOMMENDATIONS_PER_SCENARIO", "5"),
            )
        )
        self._default_top_k = max(
            1,
            int(
                os.getenv("PRODUCTION_DEFAULT_TOP_K", str(self._top_recs_per_scenario))
            ),
        )
        self._min_rating = float(os.getenv("PRODUCTION_MIN_RATING", "6"))
        self._similarity_threshold = float(
            os.getenv(
                "PRODUCTION_SIMILARITY_THRESHOLD",
                str(settings.VECTOR_SIMILARITY_THRESHOLD or 0.55),
            )
        )
        # score blending weights (rating vs similarity)
        self._rating_weight = float(os.getenv("PRODUCTION_RATING_WEIGHT", "0.7"))
        self._similarity_weight = float(
            os.getenv("PRODUCTION_SIMILARITY_WEIGHT", "0.3")
        )

        self._use_llm_ranker = os.getenv(
            "PRODUCTION_USE_LLM_RANKER", "true"
        ).lower() in (
            "1",
            "true",
            "yes",
        )
        self._llm_ranker_top_k = int(
            os.getenv("PRODUCTION_LLM_RANKER_TOP_K", str(self._default_top_k))
        )

        self._llm_service = (
            getattr(rag_mod, "rag_llm_service", None) if rag_mod else None
        )

    # ----------------------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------------------
    def recommend(self, query: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        clean_query = (query or "").strip()
        if not clean_query:
            raise ValueError("query must not be empty")

        limit = max(1, int(top_k or self._default_top_k))
        start = time.time()

        query_vector = self._vector_service.generate_embedding(clean_query)
        scenarios = self._vector_service.search_scenarios_by_vector(
            query_vector,
            top_k=max(self._top_scenarios * 2, self._top_scenarios),
            similarity_threshold=0.0,
        )

        scenarios_sorted = sorted(
            scenarios,
            key=lambda s: float(s.get("similarity_score", 0.0)),
            reverse=True,
        )
        max_similarity = max(
            (s.get("similarity_score", 0.0) for s in scenarios_sorted), default=0.0
        )

        if max_similarity < self._similarity_threshold:
            result = self._llm_fallback(clean_query, limit)
            result["mode"] = "llm-fallback"
            result["max_similarity"] = max_similarity
            result["processing_time_ms"] = int((time.time() - start) * 1000)
            result["similarity_threshold"] = self._similarity_threshold
            return result

        high_sim_scenarios = scenarios_sorted[: self._top_scenarios]
        scenario_ids = [
            s["semantic_id"] for s in high_sim_scenarios if s.get("semantic_id")
        ]
        scenario_payload = self._vector_service.fetch_recommendations_for_scenarios(
            scenario_ids,
            top_n=self._top_recs_per_scenario,
            min_rating=self._min_rating,
        )

        ranked = self._rank_candidates(high_sim_scenarios, scenario_payload, limit)

        llm_used = False
        if self._use_llm_ranker and self._llm_service:
            llm_limit = min(limit, self._llm_ranker_top_k)
            llm_recs = self._llm_rank(
                high_sim_scenarios, scenario_payload, clean_query, llm_limit
            )
            if llm_recs:
                ranked = llm_recs
                llm_used = True

        payload = {
            "query": clean_query,
            "recommendations": [rec.as_dict() for rec in ranked],
            "scenarios": [
                {
                    "id": s.get("semantic_id"),
                    "description": s.get("description_zh") or s.get("description_en"),
                    "similarity": float(s.get("similarity_score", 0.0)),
                    "panel": s.get("panel_name"),
                    "topic": s.get("topic_name"),
                }
                for s in high_sim_scenarios
            ],
            "processing_time_ms": int((time.time() - start) * 1000),
            "top_k": limit,
            "similarity_threshold": self._similarity_threshold,
            "max_similarity": max_similarity,
            "mode": "hybrid-rag",
            "source": "hybrid-llm" if llm_used else "hybrid-vector",
        }
        return payload

    def recommend_many(
        self, queries: Sequence[str], top_k: Optional[int] = None
    ) -> Dict[str, Any]:
        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        for idx, raw_query in enumerate(queries):
            try:
                result = self.recommend(raw_query, top_k=top_k)
                result["index"] = idx
                results.append(result)
            except Exception as exc:  # pragma: no cover - defensive catch for user data
                errors.append(
                    {
                        "index": idx,
                        "query": raw_query,
                        "error": str(exc),
                    }
                )
        return {
            "total": len(queries),
            "succeeded": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        }

    # ----------------------------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------------------------
    def _rank_candidates(
        self,
        scenarios: Sequence[Dict[str, Any]],
        scenario_payload: Dict[str, Dict[str, Any]],
        limit: int,
    ) -> List[RankedRecommendation]:
        scenario_by_id = {s.get("semantic_id"): s for s in scenarios}
        candidates: List[Tuple[float, Dict[str, Any], Dict[str, Any]]] = []

        for scenario_id, content in scenario_payload.items():
            scenario_meta = scenario_by_id.get(scenario_id) or content.get("scenario")
            if not scenario_meta:
                continue
            similarity = float(scenario_meta.get("similarity_score") or 0.0)
            for rec in content.get("recommendations", []):
                rating = rec.get("appropriateness_rating") or 0.0
                combined = (
                    self._rating_weight * (float(rating) / 9.0)
                    + self._similarity_weight * similarity
                )
                candidates.append((combined, scenario_meta, rec))

        candidates.sort(key=lambda x: x[0], reverse=True)

        final: List[RankedRecommendation] = []
        seen_keys = set()
        for score, scenario_meta, rec in candidates:
            proc_name = (rec.get("procedure_name") or "").strip()
            if not proc_name:
                continue
            key = (proc_name, (rec.get("modality") or "").strip())
            if key in seen_keys:
                continue
            seen_keys.add(key)

            final.append(
                RankedRecommendation(
                    rank=len(final) + 1,
                    procedure_name=proc_name,
                    modality=self._safe_str(rec.get("modality")),
                    appropriateness_rating=self._safe_float(
                        rec.get("appropriateness_rating")
                    ),
                    appropriateness_category=self._safe_str(
                        rec.get("appropriateness_category")
                    ),
                    scenario_id=scenario_meta.get("semantic_id")
                    or scenario_meta.get("scenario", {}).get("semantic_id"),
                    scenario_description=self._safe_str(
                        scenario_meta.get("description_zh")
                        or scenario_meta.get("description_en")
                        or scenario_payload.get(scenario_meta.get("semantic_id"), {})
                        .get("scenario", {})
                        .get("description_zh")
                    ),
                    panel_name=self._safe_str(
                        scenario_meta.get("panel_name")
                        or scenario_payload.get(scenario_meta.get("semantic_id"), {})
                        .get("scenario", {})
                        .get("panel_name")
                    ),
                    topic_name=self._safe_str(
                        scenario_meta.get("topic_name")
                        or scenario_payload.get(scenario_meta.get("semantic_id"), {})
                        .get("scenario", {})
                        .get("topic_name")
                    ),
                    similarity=round(
                        float(scenario_meta.get("similarity_score") or 0.0), 4
                    ),
                )
            )
            if len(final) >= limit:
                break

        return final

    def _llm_rank(
        self,
        scenarios: Sequence[Dict[str, Any]],
        scenario_payload: Dict[str, Dict[str, Any]],
        query: str,
        limit: int,
    ) -> Optional[List[RankedRecommendation]]:
        if not self._llm_service:
            return None

        try:
            prompt = self._build_llm_prompt(scenarios, scenario_payload, query, limit)
            raw = self._llm_service.call_llm(prompt)
            data = json.loads(raw)
            recs = []
            for idx, item in enumerate(data.get("recommendations", [])[:limit]):
                scenario_id = item.get("scenario_id")
                scenario_meta = scenario_payload.get(scenario_id, {}).get("scenario")
                if not scenario_meta:
                    scenario_meta = next(
                        (s for s in scenarios if s.get("semantic_id") == scenario_id),
                        None,
                    )
                if not scenario_meta:
                    continue
                recs.append(
                    RankedRecommendation(
                        rank=idx + 1,
                        procedure_name=self._safe_str(item.get("procedure_name")) or "",
                        modality=self._safe_str(item.get("modality")),
                        appropriateness_rating=self._safe_float(
                            item.get("appropriateness_rating")
                        ),
                        appropriateness_category=self._safe_str(
                            item.get("appropriateness_category")
                        ),
                        scenario_id=scenario_id,
                        scenario_description=self._safe_str(
                            scenario_meta.get("description_zh")
                            or scenario_meta.get("description_en")
                        ),
                        panel_name=self._safe_str(scenario_meta.get("panel_name")),
                        topic_name=self._safe_str(scenario_meta.get("topic_name")),
                        similarity=round(
                            float(
                                next(
                                    (
                                        s.get("similarity_score")
                                        for s in scenarios
                                        if s.get("semantic_id") == scenario_id
                                    ),
                                    0.0,
                                )
                            ),
                            4,
                        ),
                    )
                )
            if recs:
                return recs
        except Exception:
            # LLM 排序失败时继续使用确定性排序
            pass
        return None

    def _build_llm_prompt(
        self,
        scenarios: Sequence[Dict[str, Any]],
        scenario_payload: Dict[str, Dict[str, Any]],
        query: str,
        limit: int,
    ) -> str:
        scenario_lines = []
        for idx, sc in enumerate(scenarios, 1):
            scenario_lines.append(
                f"{idx}. 场景ID: {sc.get('semantic_id')} | 相似度: {sc.get('similarity_score'):.3f} | 科室: {sc.get('panel_name')} | 主题: {sc.get('topic_name')} | 描述: {sc.get('description_zh') or sc.get('description_en') or ''}"
            )

        candidate_lines = []
        for scenario_id, content in scenario_payload.items():
            for rec in content.get("recommendations", []):
                rating = rec.get("appropriateness_rating")
                candidate_lines.append(
                    f"- 场景 {scenario_id} -> {rec.get('procedure_name')} | 模态: {rec.get('modality') or '-'} | 评分: {rating or '-'} | 类别: {rec.get('appropriateness_category') or '-'}"
                )

        prompt = f"""
你是一名放射科专家，需要基于候选临床场景和候选检查项目，为下面的患者选择最合适的 {limit} 个检查。

患者描述：{query}

候选场景（按相似度排序）：
{chr(10).join(scenario_lines)}

候选检查项目（仅能从这些项目中选择）：
{chr(10).join(candidate_lines)}

请遵循以下规则：
1. 仅能输出候选列表里的项目。
2. 优先选择评分不低于 {self._min_rating} 的项目；若评分一致则优先关联更高相似度的场景。
3. 输出 JSON，不要包含任何额外文字或注释，格式如下：
{{
  "scenarios": [
    {{"id": "场景ID", "description": "场景简介"}}
  ],
  "recommendations": [
    {{
      "rank": 1,
      "scenario_id": "场景ID",
      "procedure_name": "检查名称",
      "modality": "检查模态",
      "appropriateness_rating": 8.0,
      "appropriateness_category": "通常适宜"
    }}
  ]
}}
只输出 JSON，且保证 rank 连续且从 1 开始。
"""
        return prompt

    def _llm_fallback(self, query: str, limit: int) -> Dict[str, Any]:
        if not self._llm_service:
            raise RuntimeError(
                "LLM service is not configured; unable to handle low-similarity queries"
            )

        result = self._llm_service.generate_intelligent_recommendation(
            query=query,
            top_scenarios=self._top_scenarios,
            top_recommendations_per_scenario=self._top_recs_per_scenario,
            show_reasoning=False,
            similarity_threshold=self._similarity_threshold,
            debug_flag=False,
        )

        recs = []
        llm_items = (result.get("llm_recommendations") or {}).get(
            "recommendations"
        ) or []
        for idx, item in enumerate(llm_items[:limit]):
            recs.append(
                RankedRecommendation(
                    rank=idx + 1,
                    procedure_name=self._safe_str(item.get("procedure_name")) or "",
                    modality=self._safe_str(item.get("modality")),
                    appropriateness_rating=self._safe_float(
                        item.get("appropriateness_rating")
                    ),
                    appropriateness_category=self._safe_str(
                        item.get("appropriateness_category")
                        or item.get("appropriateness_category_zh")
                    ),
                    scenario_id=None,
                    scenario_description=None,
                    panel_name=None,
                    topic_name=None,
                    similarity=0.0,
                )
            )

        payload = {
            "query": query,
            "recommendations": [rec.as_dict() for rec in recs],
            "scenarios": [],
            "mode": "llm-fallback",
            "source": "llm-fallback",
        }
        return payload

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
