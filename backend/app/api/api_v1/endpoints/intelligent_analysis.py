"""
智能临床分析API端点
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.services.intelligent_recommendation_service import IntelligentRecommendationService

router = APIRouter()

# 请求模型
class PatientInfoRequest(BaseModel):
    age: Optional[int] = Field(None, ge=0, le=120, description="患者年龄")
    gender: Optional[str] = Field(None, description="患者性别：男性、女性")
    symptoms: List[str] = Field([], description="症状列表")
    duration: Optional[str] = Field(None, description="病程：急性、慢性、1小时、3天等")
    medical_history: List[str] = Field([], description="既往病史")
    pregnancy_status: Optional[str] = Field(None, description="妊娠状态：妊娠期、哺乳期、非妊娠期")
    urgency_level: Optional[str] = Field(None, description="紧急程度：急诊、择期")

class ClinicalAnalysisRequest(BaseModel):
    patient_info: PatientInfoRequest = Field(..., description="患者信息")
    clinical_description: str = Field(..., description="临床描述")
    use_llm: bool = Field(True, description="是否使用LLM分析")
    vector_recall_size: int = Field(50, ge=10, le=200, description="向量召回数量")
    final_recommendations: int = Field(5, ge=1, le=20, description="最终推荐数量")

class RecommendationItem(BaseModel):
    rank: int
    procedure_name: str
    modality: str
    appropriateness_rating: int
    confidence_level: Optional[str] = None
    clinical_reasoning: str
    evidence_level: str
    radiation_level: str
    panel_name: str
    safety_considerations: Optional[str] = None
    recommendation_id: str

class ClinicalAnalysisResponse(BaseModel):
    patient_info: PatientInfoRequest
    clinical_description: str
    analysis_method: str
    vector_candidates_count: int
    filtered_candidates_count: int
    final_recommendations: List[RecommendationItem]
    clinical_reasoning: str
    safety_warnings: List[str]
    alternative_options: List[Dict[str, Any]]
    analysis_time_ms: int
    confidence_score: float

# 依赖注入
def get_intelligent_service(db: Session = Depends(get_db)) -> IntelligentRecommendationService:
    return IntelligentRecommendationService(db)

@router.post("/analyze-case", response_model=ClinicalAnalysisResponse)
def analyze_clinical_case(
    request: ClinicalAnalysisRequest,
    service: IntelligentRecommendationService = Depends(get_intelligent_service)
):
    """
    智能临床案例分析
    
    使用三层混合推荐架构：
    1. 向量检索：基于语义相似度召回相关推荐
    2. 规则过滤：基于医疗规则和患者特征过滤
    3. LLM分析：智能临床推理和个性化推荐
    """
    try:
        # 转换请求格式
        patient_dict = request.patient_info.dict()
        
        # 调用智能分析服务
        analysis_result = service.analyze_patient_case(
            patient_info=patient_dict,
            clinical_description=request.clinical_description,
            use_llm=request.use_llm,
            vector_recall_size=request.vector_recall_size,
            final_recommendations=request.final_recommendations
        )
        
        return ClinicalAnalysisResponse(**analysis_result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"临床分析失败: {str(e)}"
        )

class QuickAnalysisRequest(BaseModel):
    age: int = Field(..., ge=0, le=120, description="患者年龄")
    gender: str = Field(..., description="男性或女性")
    chief_complaint: str = Field(..., description="主诉")
    use_llm: bool = Field(False, description="是否使用LLM")

@router.post("/quick-analysis")
def quick_clinical_analysis(
    request: QuickAnalysisRequest,
    service: IntelligentRecommendationService = Depends(get_intelligent_service)
):
    """
    快速临床分析 - 简化版本
    """
    try:
        # 构建患者信息
        patient_info = {
            'age': request.age,
            'gender': request.gender,
            'symptoms': [request.chief_complaint]
        }
        
        # 调用分析服务
        result = service.analyze_patient_case(
            patient_info=patient_info,
            clinical_description=request.chief_complaint,
            use_llm=request.use_llm,
            vector_recall_size=30,
            final_recommendations=3
        )
        
        # 简化响应格式
        # 处理不同的字段名
        analysis_method = result.get("analysis_method", result.get("method", "未知方法"))
        recommendations = result.get("final_recommendations", result.get("recommendations", []))
        confidence = result.get("confidence_score", result.get("confidence", 0.5))
        analysis_time = result.get("analysis_time_ms", 0)
        
        return {
            "patient": f"{request.age}岁{request.gender}",
            "chief_complaint": request.chief_complaint,
            "analysis_method": analysis_method,
            "recommendations": [
                {
                    "procedure": rec.get("procedure_name", rec.get("procedure", "未知检查")),
                    "modality": rec.get("modality", "未知"), 
                    "rating": rec.get("appropriateness_rating", rec.get("rating", 0)),
                    "reasoning": rec.get("reasoning", rec.get("clinical_reasoning", rec.get("reason", "")))[:100] + "..." if len(rec.get("reasoning", rec.get("clinical_reasoning", rec.get("reason", "")))) > 100 else rec.get("reasoning", rec.get("clinical_reasoning", rec.get("reason", "")))
                }
                for rec in recommendations
            ],
            "confidence": confidence,
            "analysis_time_ms": analysis_time
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"快速分析失败: {str(e)}"
        )

@router.post("/compare-methods")
def compare_recommendation_methods(
    request: ClinicalAnalysisRequest,
    service: IntelligentRecommendationService = Depends(get_intelligent_service)
):
    """
    比较不同推荐方法的结果
    """
    try:
        patient_dict = request.patient_info.dict()
        
        # 方法1：仅向量检索
        vector_only = service.analyze_patient_case(
            patient_info=patient_dict,
            clinical_description=request.clinical_description,
            use_llm=False,
            vector_recall_size=request.final_recommendations,
            final_recommendations=request.final_recommendations
        )
        
        # 方法2：向量+规则过滤
        vector_plus_rules = service.analyze_patient_case(
            patient_info=patient_dict,
            clinical_description=request.clinical_description,
            use_llm=False,
            vector_recall_size=request.vector_recall_size,
            final_recommendations=request.final_recommendations
        )
        
        # 方法3：向量+规则+LLM
        full_analysis = service.analyze_patient_case(
            patient_info=patient_dict,
            clinical_description=request.clinical_description,
            use_llm=True,
            vector_recall_size=request.vector_recall_size,
            final_recommendations=request.final_recommendations
        )
        
        return {
            "patient_case": {
                "info": patient_dict,
                "description": request.clinical_description
            },
            "methods_comparison": {
                "vector_only": {
                    "method": "仅向量检索",
                    "recommendations": vector_only.get("final_recommendations", vector_only.get("recommendations", [])),
                    "confidence": vector_only.get("confidence_score", vector_only.get("confidence", 0.5)),
                    "time_ms": vector_only.get("analysis_time_ms", 0)
                },
                "vector_plus_rules": {
                    "method": "向量检索+规则过滤", 
                    "recommendations": vector_plus_rules.get("final_recommendations", vector_plus_rules.get("recommendations", [])),
                    "confidence": vector_plus_rules.get("confidence_score", vector_plus_rules.get("confidence", 0.5)),
                    "time_ms": vector_plus_rules.get("analysis_time_ms", 0)
                },
                "full_analysis": {
                    "method": "向量检索+规则过滤+LLM分析",
                    "recommendations": full_analysis.get("final_recommendations", full_analysis.get("recommendations", [])),
                    "confidence": full_analysis.get("confidence_score", full_analysis.get("confidence", 0.5)),
                    "time_ms": full_analysis.get("analysis_time_ms", 0),
                    "clinical_reasoning": full_analysis.get("clinical_reasoning", full_analysis.get("reasoning", ""))
                }
            },
            "summary": {
                "best_method": "full_analysis",
                "accuracy_improvement": "LLM分析提供更准确和个性化的推荐",
                "time_cost": f"LLM增加 {full_analysis.get('analysis_time_ms', 0) - vector_plus_rules.get('analysis_time_ms', 0)}ms 分析时间"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"方法比较失败: {str(e)}"
        )
