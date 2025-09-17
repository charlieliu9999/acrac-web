from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import math

from app.services.rag_llm_recommendation_service import rag_llm_service

router = APIRouter()


class PageResp(BaseModel):
    items: List[Dict[str, Any]]
    page: int
    size: int
    total: int
    pages: int


def _page_params(page: int, size: int):
    page = max(1, page)
    size = min(200, max(1, size))
    return page, size


@router.get('/panels', summary='科室列表')
async def list_panels(active_only: bool = True) -> List[Dict[str, Any]]:
    try:
        conn = rag_llm_service.connect_db()
        with conn.cursor() as cur:
            where = "WHERE p.is_active = true" if active_only else ""
            cur.execute(
                f"""
                SELECT p.semantic_id, p.name_zh, p.name_en,
                       (SELECT COUNT(*) FROM topics t WHERE t.panel_id=p.id AND t.is_active=true) AS topics_count,
                       (SELECT COUNT(*) FROM clinical_scenarios cs WHERE cs.panel_id=p.id AND cs.is_active=true) AS scenarios_count
                FROM panels p
                {where}
                ORDER BY p.semantic_id
                """
            )
            cols = [d[0] for d in cur.description]
            items = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/topics/by-panel', summary='某科室下的主题列表')
async def list_topics_by_panel(panel_id: str) -> List[Dict[str, Any]]:
    try:
        conn = rag_llm_service.connect_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.semantic_id, t.name_zh, t.name_en,
                       (SELECT COUNT(*) FROM clinical_scenarios cs WHERE cs.topic_id=t.id AND cs.is_active=true) AS scenarios_count
                FROM topics t
                JOIN panels p ON t.panel_id=p.id
                WHERE p.semantic_id=%s AND t.is_active=true
                ORDER BY t.semantic_id
                """,
                (panel_id,)
            )
            cols = [d[0] for d in cur.description]
            items = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/scenarios/by-topic', summary='某主题下的临床场景列表')
async def list_scenarios_by_topic(topic_id: str) -> List[Dict[str, Any]]:
    try:
        conn = rag_llm_service.connect_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cs.semantic_id,
                       COALESCE(NULLIF(cs.description_zh,''), cs.description_en) AS description_zh,
                       cs.description_en, cs.pregnancy_status, cs.urgency_level,
                       cs.risk_level, cs.patient_population, cs.age_group, cs.gender,
                       (SELECT COUNT(*) FROM clinical_recommendations cr WHERE cr.scenario_id = cs.semantic_id AND cr.is_active=true) AS recs_count
                FROM clinical_scenarios cs
                JOIN topics t ON cs.topic_id=t.id
                WHERE t.semantic_id=%s AND cs.is_active=true
                ORDER BY cs.semantic_id
                """,
                (topic_id,)
            )
            cols = [d[0] for d in cur.description]
            items = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/scenarios', response_model=PageResp, summary='浏览临床场景')
async def list_scenarios(q: Optional[str] = Query(None), page: int = 1, size: int = 20):
    try:
        page, size = _page_params(page, size)
        conn = rag_llm_service.connect_db()
        with conn.cursor() as cur:
            where = "WHERE cs.is_active = true"
            args: List[Any] = []
            if q:
                where += " AND (cs.description_zh ILIKE %s OR cs.description_en ILIKE %s)"
                args += [f"%{q}%", f"%{q}%"]
            cur.execute(f"SELECT COUNT(*) FROM clinical_scenarios cs {where}", args)
            total = cur.fetchone()[0]
            cur.execute(
                f"""
                SELECT cs.semantic_id,
                       COALESCE(NULLIF(cs.description_zh,''), cs.description_en) AS description_zh,
                       cs.description_en, cs.pregnancy_status, cs.urgency_level,
                       p.name_zh AS panel_name, t.name_zh AS topic_name
                FROM clinical_scenarios cs
                JOIN panels p ON cs.panel_id = p.id
                JOIN topics t ON cs.topic_id = t.id
                {where}
                ORDER BY cs.semantic_id
                LIMIT %s OFFSET %s
                """,
                args + [size, (page-1)*size]
            )
            cols = [d[0] for d in cur.description]
            items = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        return PageResp(items=items, page=page, size=size, total=total, pages=math.ceil(total/size) if size else 0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/procedures', response_model=PageResp, summary='浏览检查项目')
async def list_procedures(q: Optional[str] = Query(None), page: int = 1, size: int = 20):
    try:
        page, size = _page_params(page, size)
        conn = rag_llm_service.connect_db()
        with conn.cursor() as cur:
            where = "WHERE pd.is_active = true"
            args: List[Any] = []
            if q:
                where += " AND (pd.name_zh ILIKE %s OR pd.name_en ILIKE %s)"
                args += [f"%{q}%", f"%{q}%"]
            cur.execute(f"SELECT COUNT(*) FROM procedure_dictionary pd {where}", args)
            total = cur.fetchone()[0]
            cur.execute(
                f"""
                SELECT semantic_id, name_zh, name_en, modality, body_part, contrast_used, radiation_level
                FROM procedure_dictionary pd
                {where}
                ORDER BY semantic_id
                LIMIT %s OFFSET %s
                """,
                args + [size, (page-1)*size]
            )
            cols = [d[0] for d in cur.description]
            items = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        return PageResp(items=items, page=page, size=size, total=total, pages=math.ceil(total/size) if size else 0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/recommendations', response_model=PageResp, summary='浏览推荐关系')
async def list_recommendations(scenario_id: Optional[str] = None, q: Optional[str] = Query(None), page: int = 1, size: int = 20):
    try:
        page, size = _page_params(page, size)
        conn = rag_llm_service.connect_db()
        with conn.cursor() as cur:
            where = "WHERE cr.is_active = true"
            args: List[Any] = []
            if scenario_id:
                where += " AND cr.scenario_id = %s"
                args.append(scenario_id)
            if q:
                where += " AND (pd.name_zh ILIKE %s OR pd.name_en ILIKE %s)"
                args += [f"%{q}%", f"%{q}%"]
            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM clinical_recommendations cr
                JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
                {where}
                """,
                args
            )
            total = cur.fetchone()[0]
            cur.execute(
                f"""
                SELECT cr.semantic_id, cr.scenario_id, cr.procedure_id,
                       cr.appropriateness_category_zh, cr.appropriateness_rating,
                       cr.reasoning_zh, cr.evidence_level,
                       cr.adult_radiation_dose, cr.pediatric_radiation_dose,
                       pd.name_zh AS procedure_name_zh, pd.modality
                FROM clinical_recommendations cr
                JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
                {where}
                ORDER BY cr.scenario_id, cr.appropriateness_category_zh NULLS LAST, cr.appropriateness_rating DESC
                LIMIT %s OFFSET %s
                """,
                args + [size, (page-1)*size]
            )
            cols = [d[0] for d in cur.description]
            items = [dict(zip(cols, r)) for r in cur.fetchall()]
        conn.close()
        return PageResp(items=items, page=page, size=size, total=total, pages=math.ceil(total/size) if size else 0)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
