"""
向量搜索服务 - 基于SiliconFlow API
"""
import os
import requests
import numpy as np
import time
import logging
from typing import List, Optional, Dict, Any, Sequence
from sqlalchemy.orm import Session
from sqlalchemy import text
from dotenv import load_dotenv
from pathlib import Path

# 加载环境变量（统一 backend/.env），在容器可通过 SKIP_LOCAL_DOTENV/DOCKER_CONTEXT 禁用
try:
    if (
        os.getenv("SKIP_LOCAL_DOTENV", "").lower() != "true"
        and os.getenv("DOCKER_CONTEXT", "").lower() != "true"
    ):
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.exists():
            load_dotenv(str(env_path))
        else:
            load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)


class SiliconFlowEmbedder:
    """OpenAI-compatible embeddings client (SiliconFlow / Ollama).
    - Base URL from env: OLLAMA_BASE_URL or SILICONFLOW_BASE_URL (default SF)
    - If base URL contains '11434' or 'ollama', no API key is required.
    """

    def __init__(self, api_key: str = None, model: str = None):
        self.model = model or os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")
        self.endpoint = (
            os.getenv("OLLAMA_BASE_URL")
            or os.getenv("SILICONFLOW_BASE_URL")
            or "https://api.siliconflow.cn/v1"
        ).rstrip("/")
        self.api_key = api_key or os.getenv("SILICONFLOW_API_KEY")

    def generate_embedding(self, text: str) -> List[float]:
        try:
            prefers_ollama = ("11434" in self.endpoint) or (
                "ollama" in self.endpoint.lower()
            )
            headers = {"Content-Type": "application/json"}
            if not prefers_ollama and self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            payload = {"model": self.model, "input": text}
            resp = requests.post(
                f"{self.endpoint}/embeddings", headers=headers, json=payload, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            emb = (data.get("data") or [{}])[0].get("embedding")
            if not isinstance(emb, list):
                raise ValueError("invalid embeddings response")
            return emb
        except Exception as e:
            logger.error(
                f"Embeddings failed ({self.endpoint}): {e}; using random vector"
            )
            return np.random.normal(0, 0.1, 1024).tolist()


class VectorSearchService:
    """向量搜索服务"""

    def __init__(self, db: Session):
        self.db = db
        self.embedder = SiliconFlowEmbedder()
        try:
            self.pgvector_probes = int(os.getenv("PGVECTOR_PROBES", "20"))
        except Exception:
            self.pgvector_probes = 20

    def generate_embedding(self, text: str) -> List[float]:
        """公开生成向量的方法，便于在上层复用同一个嵌入。"""
        return self.embedder.generate_embedding(text)

    def _vector_to_sql(self, vector: Sequence[float]) -> str:
        return "[" + ",".join(map(str, vector)) + "]"

    def _apply_pgvector_probes(self) -> None:
        try:
            if self.pgvector_probes and self.pgvector_probes > 0:
                self.db.execute(
                    text(f"SET LOCAL ivfflat.probes = {int(self.pgvector_probes)}")
                )
        except Exception:
            pass

    def search_panels(
        self, query_text: str, top_k: int = 10, similarity_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """搜索相似的科室"""
        try:
            query_vector = self.embedder.generate_embedding(query_text)
            vector_str = self._vector_to_sql(query_vector)

            self._apply_pgvector_probes()

            query = text(
                f"""
                SELECT 
                    id,
                    semantic_id,
                    name_zh,
                    name_en,
                    description,
                    (1 - (embedding <=> '{vector_str}'::vector)) as similarity_score
                FROM panels 
                WHERE embedding IS NOT NULL
                AND (1 - (embedding <=> '{vector_str}'::vector)) >= {similarity_threshold}
                ORDER BY embedding <=> '{vector_str}'::vector
                LIMIT {top_k}
            """
            )

            result = self.db.execute(query)
            panels = []
            for row in result:
                panels.append(
                    {
                        "id": row.id,
                        "semantic_id": row.semantic_id,
                        "name_zh": row.name_zh,
                        "name_en": row.name_en,
                        "description": row.description,
                        "similarity_score": float(row.similarity_score),
                    }
                )

            return panels

        except Exception as e:
            logger.error(f"搜索科室失败: {e}")
            raise Exception(f"搜索科室失败: {str(e)}")

    def search_topics(
        self, query_text: str, top_k: int = 10, similarity_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """搜索相似的主题"""
        try:
            query_vector = self.embedder.generate_embedding(query_text)
            vector_str = self._vector_to_sql(query_vector)

            self._apply_pgvector_probes()

            query = text(
                f"""
                SELECT 
                    t.id,
                    t.semantic_id,
                    t.name_zh,
                    t.name_en,
                    t.description,
                    p.name_zh as panel_name,
                    (1 - (t.embedding <=> '{vector_str}'::vector)) as similarity_score
                FROM topics t
                LEFT JOIN panels p ON t.panel_id = p.id
                WHERE t.embedding IS NOT NULL
                AND (1 - (t.embedding <=> '{vector_str}'::vector)) >= {similarity_threshold}
                ORDER BY t.embedding <=> '{vector_str}'::vector
                LIMIT {top_k}
            """
            )

            result = self.db.execute(query)
            topics = []
            for row in result:
                topics.append(
                    {
                        "id": row.id,
                        "semantic_id": row.semantic_id,
                        "name_zh": row.name_zh,
                        "name_en": row.name_en,
                        "description": row.description,
                        "panel_name": row.panel_name,
                        "similarity_score": float(row.similarity_score),
                    }
                )

            return topics

        except Exception as e:
            logger.error(f"搜索主题失败: {e}")
            raise Exception(f"搜索主题失败: {str(e)}")

    def search_scenarios(
        self, query_text: str, top_k: int = 10, similarity_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """搜索相似的临床场景"""
        try:
            query_vector = self.embedder.generate_embedding(query_text)
            vector_str = self._vector_to_sql(query_vector)

            self._apply_pgvector_probes()

            query = text(
                f"""
                SELECT 
                    s.id,
                    s.semantic_id,
                    s.description_zh,
                    s.description_en,
                    s.patient_population,
                    s.risk_level,
                    s.age_group,
                    s.gender,
                    s.urgency_level,
                    s.symptom_category,
                    p.name_zh as panel_name,
                    t.name_zh as topic_name,
                    (1 - (s.embedding <=> '{vector_str}'::vector)) as similarity_score
                FROM clinical_scenarios s
                LEFT JOIN panels p ON s.panel_id = p.id
                LEFT JOIN topics t ON s.topic_id = t.id
                WHERE s.embedding IS NOT NULL
                AND (1 - (s.embedding <=> '{vector_str}'::vector)) >= {similarity_threshold}
                ORDER BY s.embedding <=> '{vector_str}'::vector
                LIMIT {top_k}
            """
            )

            result = self.db.execute(query)
            scenarios = []
            for row in result:
                scenarios.append(
                    {
                        "id": row.id,
                        "semantic_id": row.semantic_id,
                        "description_zh": row.description_zh,
                        "description_en": row.description_en,
                        "patient_population": row.patient_population,
                        "risk_level": row.risk_level,
                        "age_group": row.age_group,
                        "gender": row.gender,
                        "urgency_level": row.urgency_level,
                        "symptom_category": row.symptom_category,
                        "panel_name": row.panel_name,
                        "topic_name": row.topic_name,
                        "similarity_score": float(row.similarity_score),
                    }
                )

            return scenarios

        except Exception as e:
            logger.error(f"搜索临床场景失败: {e}")
            raise Exception(f"搜索临床场景失败: {str(e)}")

    def search_procedures(
        self, query_text: str, top_k: int = 10, similarity_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """搜索相似的检查项目"""
        try:
            query_vector = self.embedder.generate_embedding(query_text)
            vector_str = self._vector_to_sql(query_vector)

            self._apply_pgvector_probes()

            query = text(
                f"""
                SELECT 
                    p.id,
                    p.semantic_id,
                    p.name_zh,
                    p.name_en,
                    p.modality,
                    p.body_part,
                    p.contrast_used,
                    p.radiation_level,
                    p.exam_duration,
                    p.preparation_required,
                    p.description_zh,
                    (1 - (p.embedding <=> '{vector_str}'::vector)) as similarity_score
                FROM procedure_dictionary p
                WHERE p.embedding IS NOT NULL
                AND (1 - (p.embedding <=> '{vector_str}'::vector)) >= {similarity_threshold}
                ORDER BY p.embedding <=> '{vector_str}'::vector
                LIMIT {top_k}
            """
            )

            result = self.db.execute(query)
            procedures = []
            for row in result:
                procedures.append(
                    {
                        "id": row.id,
                        "semantic_id": row.semantic_id,
                        "name_zh": row.name_zh,
                        "name_en": row.name_en,
                        "modality": row.modality,
                        "body_part": row.body_part,
                        "contrast_used": row.contrast_used,
                        "radiation_level": row.radiation_level,
                        "exam_duration": row.exam_duration,
                        "preparation_required": row.preparation_required,
                        "description_zh": row.description_zh,
                        "similarity_score": float(row.similarity_score),
                    }
                )

            return procedures

        except Exception as e:
            logger.error(f"搜索检查项目失败: {e}")
            raise Exception(f"搜索检查项目失败: {str(e)}")

    def search_recommendations(
        self, query_text: str, top_k: int = 10, similarity_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """搜索相似的临床推荐"""
        try:
            query_vector = self.embedder.generate_embedding(query_text)
            vector_str = self._vector_to_sql(query_vector)

            self._apply_pgvector_probes()

            query = text(
                f"""
                SELECT 
                    cr.id,
                    cr.semantic_id,
                    cr.appropriateness_rating,
                    cr.appropriateness_category_zh,
                    cr.reasoning_zh,
                    cr.evidence_level,
                    cr.pregnancy_safety,
                    cr.adult_radiation_dose,
                    cr.pediatric_radiation_dose,
                    s.description_zh as scenario_description,
                    s.patient_population,
                    s.risk_level,
                    pd.name_zh as procedure_name,
                    pd.modality,
                    pd.body_part,
                    p.name_zh as panel_name,
                    t.name_zh as topic_name,
                    (1 - (cr.embedding <=> '{vector_str}'::vector)) as similarity_score
                FROM clinical_recommendations cr
                LEFT JOIN clinical_scenarios s ON cr.scenario_id = s.semantic_id
                LEFT JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
                LEFT JOIN panels p ON s.panel_id = p.id
                LEFT JOIN topics t ON s.topic_id = t.id
                WHERE cr.embedding IS NOT NULL
                AND (1 - (cr.embedding <=> '{vector_str}'::vector)) >= {similarity_threshold}
                ORDER BY cr.embedding <=> '{vector_str}'::vector
                LIMIT {top_k}
            """
            )

            result = self.db.execute(query)
            recommendations = []
            for row in result:
                recommendations.append(
                    {
                        "id": row.id,
                        "semantic_id": row.semantic_id,
                        "appropriateness_rating": row.appropriateness_rating,
                        "appropriateness_category_zh": row.appropriateness_category_zh,
                        "reasoning_zh": row.reasoning_zh,
                        "evidence_level": row.evidence_level,
                        "pregnancy_safety": row.pregnancy_safety,
                        "adult_radiation_dose": row.adult_radiation_dose,
                        "pediatric_radiation_dose": row.pediatric_radiation_dose,
                        "scenario_description": row.scenario_description,
                        "patient_population": row.patient_population,
                        "risk_level": row.risk_level,
                        "procedure_name": row.procedure_name,
                        "modality": row.modality,
                        "body_part": row.body_part,
                        "panel_name": row.panel_name,
                        "topic_name": row.topic_name,
                        "similarity_score": float(row.similarity_score),
                    }
                )

            return recommendations

        except Exception as e:
            logger.error(f"搜索临床推荐失败: {e}")
            raise Exception(f"搜索临床推荐失败: {str(e)}")

    # --- Enhanced helpers for production recommendation flow ---

    def search_scenarios_by_vector(
        self,
        query_vector: Sequence[float],
        top_k: int,
        similarity_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """复用预计算向量的场景检索。"""
        try:
            vector_str = self._vector_to_sql(query_vector)
            self._apply_pgvector_probes()
            query = text(
                f"""
                SELECT 
                    s.id,
                    s.semantic_id,
                    s.description_zh,
                    s.description_en,
                    s.patient_population,
                    s.risk_level,
                    s.age_group,
                    s.gender,
                    s.urgency_level,
                    s.symptom_category,
                    p.name_zh as panel_name,
                    t.name_zh as topic_name,
                    (1 - (s.embedding <=> '{vector_str}'::vector)) as similarity_score
                FROM clinical_scenarios s
                LEFT JOIN panels p ON s.panel_id = p.id
                LEFT JOIN topics t ON s.topic_id = t.id
                WHERE s.embedding IS NOT NULL
                AND (1 - (s.embedding <=> '{vector_str}'::vector)) >= {similarity_threshold}
                ORDER BY s.embedding <=> '{vector_str}'::vector
                LIMIT {top_k}
                """
            )

            result = self.db.execute(query)
            scenarios: List[Dict[str, Any]] = []
            for row in result:
                scenarios.append(
                    {
                        "id": row.id,
                        "semantic_id": row.semantic_id,
                        "description_zh": row.description_zh,
                        "description_en": row.description_en,
                        "patient_population": row.patient_population,
                        "risk_level": row.risk_level,
                        "age_group": row.age_group,
                        "gender": row.gender,
                        "urgency_level": row.urgency_level,
                        "symptom_category": row.symptom_category,
                        "panel_name": row.panel_name,
                        "topic_name": row.topic_name,
                        "similarity_score": float(row.similarity_score),
                    }
                )
            return scenarios
        except Exception as e:
            logger.error(f"搜索临床场景失败: {e}")
            raise Exception(f"搜索临床场景失败: {str(e)}")

    def fetch_recommendations_for_scenarios(
        self,
        scenario_ids: Sequence[str],
        top_n: int,
        min_rating: float = 0.0,
    ) -> Dict[str, Dict[str, Any]]:
        """批量获取场景下评分最高的推荐检查。"""
        if not scenario_ids:
            return {}

        query = text(
            """
            WITH ranked AS (
                SELECT
                    s.semantic_id AS scenario_id,
                    s.description_zh,
                    s.description_en,
                    s.patient_population,
                    s.risk_level,
                    s.age_group,
                    s.gender,
                    s.urgency_level,
                    p.name_zh AS panel_name,
                    t.name_zh AS topic_name,
                    cr.semantic_id AS recommendation_id,
                    cr.appropriateness_rating,
                    cr.appropriateness_category_zh,
                    cr.is_active,
                    pd.name_zh AS procedure_name,
                    pd.modality,
                    pd.body_part,
                    pd.contrast_used,
                    pd.radiation_level,
                    ROW_NUMBER() OVER (
                        PARTITION BY s.semantic_id
                        ORDER BY cr.appropriateness_rating DESC NULLS LAST, cr.id
                    ) AS rn
                FROM clinical_recommendations cr
                JOIN clinical_scenarios s ON s.semantic_id = cr.scenario_id
                JOIN procedure_dictionary pd ON pd.semantic_id = cr.procedure_id
                LEFT JOIN topics t ON t.id = s.topic_id
                LEFT JOIN panels p ON p.id = s.panel_id
                WHERE s.semantic_id = ANY(:scenario_ids)
            )
            SELECT * FROM ranked
            WHERE rn <= :limit
              AND (appropriateness_rating IS NULL OR appropriateness_rating >= :min_rating)
            ORDER BY scenario_id, rn
            """
        )

        result = self.db.execute(
            query,
            {
                "scenario_ids": list(scenario_ids),
                "limit": int(max(1, top_n)),
                "min_rating": float(min_rating or 0.0),
            },
        )

        data: Dict[str, Dict[str, Any]] = {}
        for row in result:
            scenario_id = row.scenario_id
            scenario_entry = data.setdefault(
                scenario_id,
                {
                    "scenario": {
                        "semantic_id": scenario_id,
                        "description_zh": row.description_zh,
                        "description_en": row.description_en,
                        "patient_population": row.patient_population,
                        "risk_level": row.risk_level,
                        "age_group": row.age_group,
                        "gender": row.gender,
                        "urgency_level": row.urgency_level,
                        "panel_name": row.panel_name,
                        "topic_name": row.topic_name,
                    },
                    "recommendations": [],
                },
            )
            scenario_entry["recommendations"].append(
                {
                    "recommendation_id": row.recommendation_id,
                    "procedure_name": row.procedure_name,
                    "modality": row.modality,
                    "body_part": row.body_part,
                    "contrast_used": row.contrast_used,
                    "radiation_level": row.radiation_level,
                    "appropriateness_rating": float(row.appropriateness_rating)
                    if row.appropriateness_rating is not None
                    else None,
                    "appropriateness_category": row.appropriateness_category_zh,
                }
            )
        return data

    def get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            stats = {}

            # 统计各表记录数
            tables = [
                "panels",
                "topics",
                "clinical_scenarios",
                "procedure_dictionary",
                "clinical_recommendations",
            ]
            for table in tables:
                query = text(f"SELECT COUNT(*) as count FROM {table}")
                result = self.db.execute(query)
                count = result.scalar()
                stats[f"{table}_count"] = count

                # 统计向量覆盖率
                query = text(
                    f"SELECT COUNT(*) as count FROM {table} WHERE embedding IS NOT NULL"
                )
                result = self.db.execute(query)
                vector_count = result.scalar()
                coverage = (vector_count / count * 100) if count > 0 else 0
                stats[f"{table}_vector_coverage"] = round(coverage, 2)

            return stats

        except Exception as e:
            logger.error(f"获取数据库统计失败: {e}")
            raise Exception(f"获取数据库统计失败: {str(e)}")
