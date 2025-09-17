"""
ACRAC 简化API端点 - 核心功能
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.models.acrac_models import Panel, Topic, ClinicalScenario, ProcedureDictionary, ClinicalRecommendation

router = APIRouter()

# ==================== 健康检查和统计 ====================

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """系统健康检查"""
    try:
        # 检查数据库连接
        db.execute(text("SELECT 1"))
        
        # 统计数据
        panels_count = db.query(Panel).count()
        topics_count = db.query(Topic).count()
        scenarios_count = db.query(ClinicalScenario).count()
        procedures_count = db.query(ProcedureDictionary).count()
        recommendations_count = db.query(ClinicalRecommendation).count()
        
        return {
            "status": "healthy",
            "database_status": "connected",
            "version": "2.0.0",
            "data_summary": {
                "panels": panels_count,
                "topics": topics_count,
                "scenarios": scenarios_count,
                "procedures": procedures_count,
                "recommendations": recommendations_count
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "version": "2.0.0"
        }

@router.get("/statistics")
def get_statistics(db: Session = Depends(get_db)):
    """获取详细统计信息"""
    try:
        stats = {}
        
        # 基础统计
        stats['panels_count'] = db.query(Panel).count()
        stats['topics_count'] = db.query(Topic).count()
        stats['scenarios_count'] = db.query(ClinicalScenario).count()
        stats['procedures_count'] = db.query(ProcedureDictionary).count()
        stats['recommendations_count'] = db.query(ClinicalRecommendation).count()
        
        # 活跃数据统计
        stats['active_panels'] = db.query(Panel).filter(Panel.is_active == True).count()
        stats['active_topics'] = db.query(Topic).filter(Topic.is_active == True).count()
        stats['active_scenarios'] = db.query(ClinicalScenario).filter(ClinicalScenario.is_active == True).count()
        stats['active_procedures'] = db.query(ProcedureDictionary).filter(ProcedureDictionary.is_active == True).count()
        stats['active_recommendations'] = db.query(ClinicalRecommendation).filter(ClinicalRecommendation.is_active == True).count()
        
        # 向量嵌入统计
        stats['vectors_panels'] = db.query(Panel).filter(Panel.embedding.isnot(None)).count()
        stats['vectors_topics'] = db.query(Topic).filter(Topic.embedding.isnot(None)).count()
        stats['vectors_scenarios'] = db.query(ClinicalScenario).filter(ClinicalScenario.embedding.isnot(None)).count()
        stats['vectors_procedures'] = db.query(ProcedureDictionary).filter(ProcedureDictionary.embedding.isnot(None)).count()
        stats['vectors_recommendations'] = db.query(ClinicalRecommendation).filter(ClinicalRecommendation.embedding.isnot(None)).count()
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ==================== 基础数据查询 ====================

@router.get("/panels")
def list_panels(
    active_only: bool = Query(True, description="只显示激活的Panel"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    db: Session = Depends(get_db)
):
    """列出所有Panels"""
    try:
        query = db.query(Panel)
        if active_only:
            query = query.filter(Panel.is_active == True)
        
        panels = query.order_by(Panel.semantic_id).limit(limit).all()
        
        return {
            "total": len(panels),
            "panels": [
                {
                    "semantic_id": panel.semantic_id,
                    "name_zh": panel.name_zh,
                    "name_en": panel.name_en,
                    "description": panel.description,
                    "is_active": panel.is_active
                }
                for panel in panels
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/panels/{semantic_id}/topics")
def get_topics_by_panel(
    semantic_id: str,
    active_only: bool = Query(True, description="只显示激活的Topic"),
    db: Session = Depends(get_db)
):
    """获取Panel下的所有Topics"""
    try:
        panel = db.query(Panel).filter(Panel.semantic_id == semantic_id).first()
        if not panel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Panel不存在")
        
        query = db.query(Topic).filter(Topic.panel_id == panel.id)
        if active_only:
            query = query.filter(Topic.is_active == True)
        
        topics = query.order_by(Topic.semantic_id).all()
        
        return {
            "panel_id": semantic_id,
            "panel_name": panel.name_zh,
            "total": len(topics),
            "topics": [
                {
                    "semantic_id": topic.semantic_id,
                    "name_zh": topic.name_zh,
                    "name_en": topic.name_en,
                    "description": topic.description,
                    "is_active": topic.is_active
                }
                for topic in topics
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/topics/{semantic_id}/scenarios")
def get_scenarios_by_topic(
    semantic_id: str,
    active_only: bool = Query(True, description="只显示激活的Scenario"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取Topic下的所有临床场景"""
    try:
        # 查找Topic
        topic = db.query(Topic).filter(Topic.semantic_id == semantic_id).first()
        if not topic:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic不存在")
        
        # 获取Panel信息
        panel = db.query(Panel).filter(Panel.id == topic.panel_id).first()
        
        # 查询Scenarios
        query = db.query(ClinicalScenario).filter(ClinicalScenario.topic_id == topic.id)
        if active_only:
            query = query.filter(ClinicalScenario.is_active == True)
        
        scenarios = query.order_by(ClinicalScenario.semantic_id).limit(limit).all()
        
        return {
            "topic_id": semantic_id,
            "topic_name": topic.name_zh,
            "panel_id": panel.semantic_id if panel else None,
            "panel_name": panel.name_zh if panel else None,
            "total": len(scenarios),
            "scenarios": [
                {
                    "semantic_id": scenario.semantic_id,
                    "description_zh": scenario.description_zh,
                    "description_en": scenario.description_en,
                    "patient_population": scenario.patient_population,
                    "risk_level": scenario.risk_level,
                    "age_group": scenario.age_group,
                    "gender": scenario.gender,
                    "urgency_level": scenario.urgency_level,
                    "symptom_category": scenario.symptom_category,
                    "is_active": scenario.is_active
                }
                for scenario in scenarios
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/procedures")
def list_procedures(
    modality: Optional[str] = Query(None, description="检查方式"),
    body_part: Optional[str] = Query(None, description="检查部位"),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    db: Session = Depends(get_db)
):
    """列出检查项目"""
    try:
        query = db.query(ProcedureDictionary).filter(ProcedureDictionary.is_active == True)
        
        if modality:
            query = query.filter(ProcedureDictionary.modality == modality)
        if body_part:
            query = query.filter(ProcedureDictionary.body_part == body_part)
        
        procedures = query.order_by(ProcedureDictionary.semantic_id).limit(limit).all()
        
        return {
            "total": len(procedures),
            "filters": {"modality": modality, "body_part": body_part},
            "procedures": [
                {
                    "semantic_id": proc.semantic_id,
                    "name_zh": proc.name_zh,
                    "name_en": proc.name_en,
                    "modality": proc.modality,
                    "body_part": proc.body_part,
                    "contrast_used": proc.contrast_used,
                    "radiation_level": proc.radiation_level
                }
                for proc in procedures
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ==================== 推荐查询 ====================

@router.get("/scenarios/{scenario_id}/recommendations")
def get_recommendations_for_scenario(
    scenario_id: str,
    min_rating: Optional[int] = Query(None, ge=1, le=9, description="最低适宜性评分"),
    db: Session = Depends(get_db)
):
    """获取场景的所有推荐"""
    try:
        # 验证场景存在
        scenario = db.query(ClinicalScenario).filter(ClinicalScenario.semantic_id == scenario_id).first()
        if not scenario:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="临床场景不存在")
        
        # 查询推荐
        query = db.query(ClinicalRecommendation).filter(ClinicalRecommendation.scenario_id == scenario_id)
        if min_rating:
            query = query.filter(ClinicalRecommendation.appropriateness_rating >= min_rating)
        
        recommendations = query.order_by(ClinicalRecommendation.appropriateness_rating.desc()).all()
        
        # 获取检查项目信息
        result = []
        for rec in recommendations:
            procedure = db.query(ProcedureDictionary).filter(
                ProcedureDictionary.semantic_id == rec.procedure_id
            ).first()
            
            result.append({
                "recommendation_id": rec.semantic_id,
                "appropriateness_rating": rec.appropriateness_rating,
                "appropriateness_category_zh": rec.appropriateness_category_zh,
                "reasoning_zh": rec.reasoning_zh,
                "evidence_level": rec.evidence_level,
                "pregnancy_safety": rec.pregnancy_safety,
                "procedure": {
                    "semantic_id": procedure.semantic_id if procedure else None,
                    "name_zh": procedure.name_zh if procedure else None,
                    "modality": procedure.modality if procedure else None,
                    "radiation_level": procedure.radiation_level if procedure else None
                }
            })
        
        return {
            "scenario_id": scenario_id,
            "scenario_description": scenario.description_zh,
            "total": len(result),
            "recommendations": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ==================== 数据分析 ====================

@router.get("/analytics/modality-distribution")
def get_modality_distribution(db: Session = Depends(get_db)):
    """获取检查方式分布"""
    try:
        result = db.execute(text("""
            SELECT modality, COUNT(*) as count
            FROM procedure_dictionary 
            WHERE is_active = TRUE AND modality IS NOT NULL
            GROUP BY modality 
            ORDER BY count DESC;
        """))
        
        return {
            "distribution": {row[0]: row[1] for row in result},
            "total_procedures": sum(row[1] for row in result)
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/analytics/rating-distribution")
def get_rating_distribution(db: Session = Depends(get_db)):
    """获取适宜性评分分布"""
    try:
        result = db.execute(text("""
            SELECT appropriateness_rating, COUNT(*) as count
            FROM clinical_recommendations 
            WHERE is_active = TRUE AND appropriateness_rating IS NOT NULL
            GROUP BY appropriateness_rating 
            ORDER BY appropriateness_rating;
        """))
        
        return {
            "distribution": {f"{row[0]}分": row[1] for row in result},
            "total_recommendations": sum(row[1] for row in result)
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ==================== 快捷查询 ====================

@router.get("/quick/high-rating-recommendations")
def get_high_rating_recommendations(
    min_rating: int = Query(8, ge=1, le=9, description="最低评分"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    db: Session = Depends(get_db)
):
    """获取高评分推荐"""
    try:
        result = db.execute(text("""
            SELECT 
                cr.semantic_id,
                cr.appropriateness_rating,
                cr.reasoning_zh,
                s.description_zh as scenario_desc,
                pd.name_zh as procedure_name,
                pd.modality,
                p.name_zh as panel_name,
                t.name_zh as topic_name
            FROM clinical_recommendations cr
            JOIN clinical_scenarios s ON cr.scenario_id = s.semantic_id
            JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
            JOIN topics t ON s.topic_id = t.id
            JOIN panels p ON s.panel_id = p.id
            WHERE cr.appropriateness_rating >= :min_rating 
              AND cr.is_active = TRUE
            ORDER BY cr.appropriateness_rating DESC, cr.semantic_id
            LIMIT :limit;
        """), {"min_rating": min_rating, "limit": limit})
        
        recommendations = []
        for row in result:
            recommendations.append({
                "recommendation_id": row[0],
                "rating": row[1],
                "reasoning": row[2][:100] + "..." if row[2] and len(row[2]) > 100 else row[2],
                "scenario": row[3][:80] + "..." if row[3] and len(row[3]) > 80 else row[3],
                "procedure": row[4],
                "modality": row[5],
                "panel": row[6],
                "topic": row[7]
            })
        
        return {
            "query_params": {"min_rating": min_rating, "limit": limit},
            "total_found": len(recommendations),
            "recommendations": recommendations
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/quick/procedures-by-modality/{modality}")
def get_procedures_by_modality(
    modality: str,
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    db: Session = Depends(get_db)
):
    """按检查方式获取检查项目"""
    try:
        procedures = db.query(ProcedureDictionary).filter(
            ProcedureDictionary.modality == modality,
            ProcedureDictionary.is_active == True
        ).order_by(ProcedureDictionary.semantic_id).limit(limit).all()
        
        return {
            "modality": modality,
            "total": len(procedures),
            "procedures": [
                {
                    "semantic_id": proc.semantic_id,
                    "name_zh": proc.name_zh,
                    "body_part": proc.body_part,
                    "contrast_used": proc.contrast_used,
                    "radiation_level": proc.radiation_level
                }
                for proc in procedures
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ==================== 示例数据查询 ====================

@router.get("/examples/complete-recommendation")
def get_complete_recommendation_example(db: Session = Depends(get_db)):
    """获取完整推荐示例"""
    try:
        result = db.execute(text("""
            SELECT 
                p.semantic_id as panel_id, p.name_zh as panel_name,
                t.semantic_id as topic_id, t.name_zh as topic_name,
                s.semantic_id as scenario_id, s.description_zh as scenario_desc,
                s.patient_population, s.risk_level, s.age_group,
                pd.semantic_id as procedure_id, pd.name_zh as procedure_name,
                pd.modality, pd.body_part, pd.radiation_level,
                cr.semantic_id as recommendation_id, cr.appropriateness_rating,
                cr.reasoning_zh, cr.evidence_level, cr.pregnancy_safety
            FROM clinical_recommendations cr
            JOIN clinical_scenarios s ON cr.scenario_id = s.semantic_id
            JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
            JOIN topics t ON s.topic_id = t.id
            JOIN panels p ON s.panel_id = p.id
            WHERE cr.appropriateness_rating >= 8
            ORDER BY cr.appropriateness_rating DESC
            LIMIT 5;
        """))
        
        examples = []
        for row in result:
            examples.append({
                "panel": {"id": row[0], "name": row[1]},
                "topic": {"id": row[2], "name": row[3]},
                "scenario": {
                    "id": row[4],
                    "description": row[5],
                    "patient_population": row[6],
                    "risk_level": row[7],
                    "age_group": row[8]
                },
                "procedure": {
                    "id": row[9],
                    "name": row[10],
                    "modality": row[11],
                    "body_part": row[12],
                    "radiation_level": row[13]
                },
                "recommendation": {
                    "id": row[14],
                    "rating": row[15],
                    "reasoning": row[16][:150] + "..." if row[16] and len(row[16]) > 150 else row[16],
                    "evidence_level": row[17],
                    "pregnancy_safety": row[18]
                }
            })
        
        return {
            "description": "完整推荐示例：展示Panel→Topic→Scenario→Procedure→Recommendation的完整链路",
            "total_examples": len(examples),
            "examples": examples
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# ==================== 搜索功能 ====================

@router.get("/search/procedures")
def search_procedures_simple(
    query: str = Query(..., description="搜索关键词"),
    modality: Optional[str] = Query(None, description="检查方式过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    db: Session = Depends(get_db)
):
    """简单的检查项目搜索"""
    try:
        # 构建搜索条件
        sql = """
            SELECT semantic_id, name_zh, name_en, modality, body_part, radiation_level
            FROM procedure_dictionary 
            WHERE is_active = TRUE 
              AND (name_zh ILIKE :query OR name_en ILIKE :query)
        """
        
        params = {"query": f"%{query}%", "limit": limit}
        
        if modality:
            sql += " AND modality = :modality"
            params["modality"] = modality
        
        sql += " ORDER BY name_zh LIMIT :limit"
        
        result = db.execute(text(sql), params)
        
        procedures = []
        for row in result:
            procedures.append({
                "semantic_id": row[0],
                "name_zh": row[1],
                "name_en": row[2],
                "modality": row[3],
                "body_part": row[4],
                "radiation_level": row[5]
            })
        
        return {
            "query": query,
            "modality_filter": modality,
            "total_found": len(procedures),
            "procedures": procedures
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/search/recommendations")
def search_recommendations_simple(
    query: str = Query(..., description="搜索关键词"),
    min_rating: Optional[int] = Query(None, ge=1, le=9, description="最低评分"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    db: Session = Depends(get_db)
):
    """简单的推荐搜索"""
    try:
        sql = """
            SELECT 
                cr.semantic_id, cr.appropriateness_rating, cr.reasoning_zh,
                s.description_zh as scenario_desc,
                pd.name_zh as procedure_name, pd.modality,
                p.name_zh as panel_name
            FROM clinical_recommendations cr
            JOIN clinical_scenarios s ON cr.scenario_id = s.semantic_id
            JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
            JOIN topics t ON s.topic_id = t.id
            JOIN panels p ON s.panel_id = p.id
            WHERE cr.is_active = TRUE 
              AND (s.description_zh ILIKE :query 
                   OR pd.name_zh ILIKE :query 
                   OR cr.reasoning_zh ILIKE :query)
        """
        
        params = {"query": f"%{query}%", "limit": limit}
        
        if min_rating:
            sql += " AND cr.appropriateness_rating >= :min_rating"
            params["min_rating"] = min_rating
        
        sql += " ORDER BY cr.appropriateness_rating DESC, cr.semantic_id LIMIT :limit"
        
        result = db.execute(text(sql), params)
        
        recommendations = []
        for row in result:
            recommendations.append({
                "recommendation_id": row[0],
                "rating": row[1],
                "reasoning": row[2][:100] + "..." if row[2] and len(row[2]) > 100 else row[2],
                "scenario": row[3][:80] + "..." if row[3] and len(row[3]) > 80 else row[3],
                "procedure": row[4],
                "modality": row[5],
                "panel": row[6]
            })
        
        return {
            "query": query,
            "min_rating": min_rating,
            "total_found": len(recommendations),
            "recommendations": recommendations
        }
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
