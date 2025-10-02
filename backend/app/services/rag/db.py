import os
import time
import logging
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)


class _PooledConn:
    """Wrap a raw connection to return it back to pool on close()."""

    def __init__(self, raw, pool: ThreadedConnectionPool):
        self._raw = raw
        self._pool = pool

    def cursor(self, *a, **kw):
        return self._raw.cursor(*a, **kw)

    def close(self):
        try:
            self._pool.putconn(self._raw)
        except Exception:
            try:
                self._raw.close()
            except Exception:
                pass

    def commit(self):
        return self._raw.commit()

    def rollback(self):
        return self._raw.rollback()

    @property
    def raw(self):
        return self._raw


class DBManager:
    """Database access and query helpers for RAG.

    Holds a connection pool and provides search helpers used by
    the RAG pipeline. Designed for reuse across API servers.
    """

    def __init__(
        self,
        db_config: Dict[str, Any],
        pool_min: int = 1,
        pool_max: int = 10,
        pgvector_probes: int = 20,
    ) -> None:
        self.db_config = dict(db_config or {})
        self._db_pool: Optional[ThreadedConnectionPool] = None
        self._db_pool_min = int(pool_min)
        self._db_pool_max = int(pool_max)
        self.pgvector_probes = int(pgvector_probes or 0)

    def _init_pool(self, host: str) -> None:
        """Initialize the connection pool once for a given host."""
        if self._db_pool is not None:
            return
        cfg = dict(self.db_config)
        cfg["host"] = host
        self._db_pool = ThreadedConnectionPool(
            minconn=self._db_pool_min, maxconn=self._db_pool_max, **cfg
        )

    def connect(self):
        """Get a database connection with retry and host fallback.

        - Uses a pool if possible, otherwise falls back to a single connection.
        - When host is localhost/127.0.0.1, also tries service name 'postgres'.
        """
        host = self.db_config.get("host") or "localhost"
        port = int(self.db_config.get("port") or 5432)
        cfg_base = dict(self.db_config)
        fallback_hosts = [host]
        if str(host) in ("localhost", "127.0.0.1"):
            fallback_hosts.append("postgres")
        max_wait = int(os.getenv("DB_CONNECT_TIMEOUT", "30"))
        interval = 2
        start = time.time()
        last_err: Optional[Exception] = None

        # Try pool first if exists
        if self._db_pool is not None:
            try:
                conn = self._db_pool.getconn()
                return _PooledConn(conn, self._db_pool)
            except Exception as e:
                logger.warning(f"Pool getconn failed, rebuilding: {e}")
                try:
                    self._db_pool.closeall()
                except Exception:
                    pass
                self._db_pool = None

        while time.time() - start < max_wait:
            for h in fallback_hosts:
                try:
                    cfg = dict(cfg_base)
                    cfg["host"] = h
                    # try pool
                    self._init_pool(h)
                    if self._db_pool is not None:
                        conn = self._db_pool.getconn()
                        if h != host:
                            logger.warning(
                                f"DB fallback host '{h}' used (original: '{host}')"
                            )
                        return _PooledConn(conn, self._db_pool)
                    # fallback single connection (rare)
                    raw = psycopg2.connect(**cfg)
                    if h != host:
                        logger.warning(
                            f"DB fallback host '{h}' used (original: '{host}')"
                        )
                    return raw
                except Exception as e:
                    last_err = e
                    time.sleep(interval)

        hint = (
            "数据库连接失败。请检查: "
            "1) 在Docker内应使用 PGHOST=postgres；"
            "2) docker-compose 服务是否已healthy；"
            "3) 端口与网络是否被占用或被防火墙阻断。"
        )
        logger.error(f"DB连接失败（host={host}, port={port}）：{last_err}; {hint}")
        raise last_err  # type: ignore[misc]

    # ---- Search helpers ----
    def search_clinical_scenarios(
        self, conn, query_vector: List[float], top_k: int = 3
    ) -> List[Dict]:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                if self.pgvector_probes and self.pgvector_probes > 0:
                    cur.execute(
                        f"SET LOCAL ivfflat.probes = {int(self.pgvector_probes)};"
                    )
            except Exception:
                pass
            vec_str = "[" + ",".join(map(str, query_vector)) + "]"
            sql = f"""
                SELECT
                    cs.semantic_id,
                    COALESCE(NULLIF(cs.description_zh,''), cs.description_en) AS description_zh,
                    cs.clinical_context,
                    cs.patient_population,
                    cs.risk_level,
                    cs.age_group,
                    cs.gender,
                    cs.urgency_level,
                    cs.symptom_category,
                    p.semantic_id as panel_semantic_id,
                    p.name_zh as panel_name,
                    t.semantic_id as topic_semantic_id,
                    t.name_zh as topic_name,
                    (1 - (cs.embedding <=> '{vec_str}'::vector)) AS similarity
                FROM clinical_scenarios cs
                LEFT JOIN panels p ON cs.panel_id = p.id
                LEFT JOIN topics t ON cs.topic_id = t.id
                WHERE cs.embedding IS NOT NULL AND cs.is_active = true
                ORDER BY cs.embedding <=> '{vec_str}'::vector
                LIMIT {top_k}
            """
            cur.execute(sql)
            return [dict(row) for row in cur.fetchall()]

    def get_scenario_with_recommendations(
        self, conn, scenario_ids: List[str]
    ) -> List[Dict]:
        if not scenario_ids:
            return []
        scenario_ids_str = "','".join(scenario_ids)
        scenario_ids_placeholders = "'" + scenario_ids_str + "'"
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = f"""
                SELECT
                    cs.semantic_id as scenario_id,
                    cs.description_zh as scenario_description,
                    cs.patient_population,
                    cs.risk_level,
                    cs.age_group,
                    cs.gender,
                    cs.urgency_level,
                    p.semantic_id as panel_semantic_id,
                    p.name_zh as panel_name,
                    t.semantic_id as topic_semantic_id,
                    t.name_zh as topic_name,
                    cr.procedure_id,
                    pd.name_zh AS procedure_name_zh,
                    pd.name_en AS procedure_name_en,
                    pd.modality,
                    pd.body_part,
                    pd.contrast_used,
                    pd.radiation_level,
                    pd.exam_duration,
                    pd.preparation_required,
                    cr.appropriateness_rating,
                    cr.appropriateness_category_zh,
                    cr.reasoning_zh,
                    cr.evidence_level,
                    cr.contraindications,
                    cr.special_considerations,
                    cr.pregnancy_safety
                FROM clinical_scenarios cs
                LEFT JOIN panels p ON cs.panel_id = p.id
                LEFT JOIN topics t ON cs.topic_id = t.id
                LEFT JOIN clinical_recommendations cr ON cs.semantic_id = cr.scenario_id
                LEFT JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
                WHERE cs.semantic_id IN ({scenario_ids_placeholders})
                    AND cs.is_active = true
                    AND cr.is_active = true
                    AND pd.is_active = true
                    AND cr.appropriateness_rating > 5
                ORDER BY cs.semantic_id, cr.appropriateness_rating DESC
            """
            cur.execute(sql)
            results = [dict(row) for row in cur.fetchall()]

        scenarios_with_recs: Dict[str, Dict[str, Any]] = {}
        for row in results:
            scenario_id = row["scenario_id"]
            if scenario_id not in scenarios_with_recs:
                scenarios_with_recs[scenario_id] = {
                    "scenario_id": scenario_id,
                    "scenario_description": row["scenario_description"],
                    "description_zh": row["scenario_description"],
                    "patient_population": row["patient_population"],
                    "risk_level": row["risk_level"],
                    "age_group": row["age_group"],
                    "gender": row["gender"],
                    "urgency_level": row["urgency_level"],
                    "panel_semantic_id": row.get("panel_semantic_id"),
                    "panel_name": row["panel_name"],
                    "topic_semantic_id": row.get("topic_semantic_id"),
                    "topic_name": row["topic_name"],
                    "recommendations": [],
                }
            if row.get("procedure_id"):
                scenarios_with_recs[scenario_id]["recommendations"].append(
                    {
                        "procedure_name_zh": row["procedure_name_zh"],
                        "procedure_name_en": row["procedure_name_en"],
                        "modality": row["modality"],
                        "body_part": row["body_part"],
                        "contrast_used": row["contrast_used"],
                        "radiation_level": row["radiation_level"],
                        "exam_duration": row["exam_duration"],
                        "preparation_required": row["preparation_required"],
                        "appropriateness_rating": row["appropriateness_rating"],
                        "appropriateness_category_zh": row["appropriateness_category_zh"],
                        "reasoning_zh": row["reasoning_zh"],
                        "evidence_level": row["evidence_level"],
                        "contraindications": row["contraindications"],
                        "special_considerations": row["special_considerations"],
                        "pregnancy_safety": row["pregnancy_safety"],
                    }
                )
        return list(scenarios_with_recs.values())

    def search_procedure_candidates(
        self, conn, query_vector: List[float], top_k: int = 15
    ) -> List[Dict]:
        if conn is None:
            return []
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                if self.pgvector_probes and self.pgvector_probes > 0:
                    cur.execute(
                        f"SET LOCAL ivfflat.probes = {int(self.pgvector_probes)};"
                    )
            except Exception:
                pass
            vec_str = "[" + ",".join(map(str, query_vector)) + "]"
            sql = f"""
                SELECT
                    pd.semantic_id,
                    pd.name_zh,
                    pd.name_en,
                    pd.modality,
                    pd.body_part,
                    pd.description_zh,
                    (1 - (pd.embedding <=> '{vec_str}'::vector)) AS similarity
                FROM procedure_dictionary pd
                WHERE pd.embedding IS NOT NULL AND pd.is_active = true
                ORDER BY pd.embedding <=> '{vec_str}'::vector
                LIMIT {top_k}
            """
            cur.execute(sql)
            rows = [dict(r) for r in cur.fetchall()]
            for r in rows:
                r["procedure_name_zh"] = r.get("name_zh")
            return rows

