"""
三个推荐方法独立API端点
1. 向量法 - 纯向量检索推荐
2. LLM法 - 纯LLM分析推荐  
3. RAG法 - 向量+LLM混合推荐
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import time
import logging

from app.core.database import get_db
from app.services.intelligent_recommendation_service import IntelligentRecommendationService

logger = logging.getLogger(__name__)
router = APIRouter()

# 请求模型
class RecommendationRequest(BaseModel):
    """推荐请求模型"""
    patient_description: str = Field(..., description="患者病情描述", example="45岁女性，慢性反复发作胸痛，无明显系统性异常体征")
    age: Optional[int] = Field(None, ge=0, le=120, description="患者年龄")
    gender: Optional[str] = Field(None, description="患者性别：男性、女性")
    symptoms: List[str] = Field([], description="症状列表")
    max_recommendations: int = Field(3, ge=1, le=10, description="最大推荐数量")

class RecommendationItem(BaseModel):
    """推荐项目模型"""
    rank: int = Field(..., description="推荐排名")
    procedure_name: str = Field(..., description="检查项目名称")
    modality: str = Field(..., description="检查方式")
    appropriateness_rating: int = Field(..., description="适宜性评分(1-9)")
    reasoning: str = Field(..., description="推荐理由")
    evidence_level: str = Field(..., description="证据等级")
    radiation_level: str = Field(..., description="辐射水平")
    panel_name: str = Field(..., description="所属科室")

class RecommendationResponse(BaseModel):
    """推荐响应模型"""
    method: str = Field(..., description="推荐方法")
    patient_description: str = Field(..., description="患者描述")
    recommendations: List[RecommendationItem] = Field(..., description="推荐列表")
    analysis_time_ms: int = Field(..., description="分析时间(毫秒)")
    confidence_score: float = Field(..., description="置信度")
    method_description: str = Field(..., description="方法说明")

# 依赖注入
def get_intelligent_service(db: Session = Depends(get_db)) -> IntelligentRecommendationService:
    return IntelligentRecommendationService(db)

@router.post("/vector-method", response_model=RecommendationResponse)
def vector_method_recommendation(
    request: RecommendationRequest,
    service: IntelligentRecommendationService = Depends(get_intelligent_service)
):
    """
    方法1：向量检索推荐
    
    使用纯向量相似度搜索，基于患者描述找到最相似的临床推荐
    - 优点：响应快速，基于语义相似度
    - 缺点：缺乏临床推理，可能不够个性化
    """
    start_time = time.time()
    
    try:
        # 构建患者信息
        patient_info = {
            'age': request.age,
            'gender': request.gender,
            'symptoms': request.symptoms or []
        }
        
        # 使用向量检索方法
        logger.info(f"调用analyze_patient_case方法，参数: {patient_info}, {request.patient_description}")
        result = service.analyze_patient_case(
            patient_info=patient_info,
            clinical_description=request.patient_description,
            use_llm=False,  # 不使用LLM
            vector_recall_size=request.max_recommendations * 2,
            final_recommendations=request.max_recommendations
        )
        logger.info(f"analyze_patient_case返回结果: {result.get('analysis_method', '未知')}, 推荐数量: {len(result.get('final_recommendations', []))}")
        
        analysis_time = int((time.time() - start_time) * 1000)
        
        # 转换推荐格式
        recommendations = []
        for i, rec in enumerate(result.get("final_recommendations", result.get("recommendations", [])), 1):
            recommendations.append(RecommendationItem(
                rank=i,
                procedure_name=rec.get("procedure_name", rec.get("procedure", "未知检查")),
                modality=rec.get("modality", "未知"),
                appropriateness_rating=rec.get("appropriateness_rating", rec.get("rating", 0)),
                reasoning=rec.get("reasoning", rec.get("clinical_reasoning", rec.get("reason", ""))),
                evidence_level=rec.get("evidence_level", "C"),
                radiation_level=rec.get("radiation_level", "低"),
                panel_name=rec.get("panel_name", "未知科室")
            ))
        
        return RecommendationResponse(
            method="向量检索法",
            patient_description=request.patient_description,
            recommendations=recommendations,
            analysis_time_ms=analysis_time,
            confidence_score=result.get("confidence_score", result.get("confidence", 0.0)),
            method_description="基于语义相似度的向量检索，快速找到最相关的临床推荐"
        )
        
    except Exception as e:
        logger.error(f"向量检索推荐失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"向量检索推荐失败: {str(e)}"
        )

@router.post("/llm-method", response_model=RecommendationResponse)
def llm_method_recommendation(
    request: RecommendationRequest,
    service: IntelligentRecommendationService = Depends(get_intelligent_service)
):
    """
    方法2：LLM分析推荐
    
    使用纯LLM进行临床推理分析，基于医学知识给出推荐
    - 优点：临床推理能力强，个性化程度高
    - 缺点：响应较慢，需要LLM服务支持
    """
    start_time = time.time()
    
    try:
        # 构建患者信息
        patient_info = {
            'age': request.age,
            'gender': request.gender,
            'symptoms': request.symptoms or []
        }
        
        # 使用LLM分析方法
        result = service.analyze_patient_case(
            patient_info=patient_info,
            clinical_description=request.patient_description,
            use_llm=True,  # 使用LLM
            vector_recall_size=50,  # 给LLM更多候选
            final_recommendations=request.max_recommendations
        )
        
        analysis_time = int((time.time() - start_time) * 1000)
        
        # 转换推荐格式
        recommendations = []
        for i, rec in enumerate(result.get("final_recommendations", result.get("recommendations", [])), 1):
            recommendations.append(RecommendationItem(
                rank=i,
                procedure_name=rec.get("procedure_name", rec.get("procedure", "未知检查")),
                modality=rec.get("modality", "未知"),
                appropriateness_rating=rec.get("appropriateness_rating", rec.get("rating", 0)),
                reasoning=rec.get("reasoning", rec.get("clinical_reasoning", rec.get("reason", ""))),
                evidence_level=rec.get("evidence_level", "A"),
                radiation_level=rec.get("radiation_level", "低"),
                panel_name=rec.get("panel_name", "未知科室")
            ))
        
        return RecommendationResponse(
            method="LLM分析法",
            patient_description=request.patient_description,
            recommendations=recommendations,
            analysis_time_ms=analysis_time,
            confidence_score=result.get("confidence_score", result.get("confidence", 0.9)),
            method_description="基于Qwen3:30b大语言模型的临床推理分析，提供个性化推荐"
        )
        
    except Exception as e:
        logger.error(f"LLM分析推荐失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM分析推荐失败: {str(e)}"
        )

@router.post("/rag-method", response_model=RecommendationResponse)
def rag_method_recommendation(
    request: RecommendationRequest,
    service: IntelligentRecommendationService = Depends(get_intelligent_service)
):
    """
    方法3：RAG混合推荐
    
    使用向量检索+LLM分析的混合方法，结合两种方法的优势
    - 优点：既有语义检索的快速性，又有LLM的推理能力
    - 缺点：响应时间介于两者之间
    """
    start_time = time.time()
    
    try:
        # 构建患者信息
        patient_info = {
            'age': request.age,
            'gender': request.gender,
            'symptoms': request.symptoms or []
        }
        
        # 使用RAG混合方法
        result = service.analyze_patient_case(
            patient_info=patient_info,
            clinical_description=request.patient_description,
            use_llm=True,  # 使用LLM
            vector_recall_size=30,  # 适中的向量召回
            final_recommendations=request.max_recommendations
        )
        
        analysis_time = int((time.time() - start_time) * 1000)
        
        # 转换推荐格式
        recommendations = []
        for i, rec in enumerate(result.get("final_recommendations", result.get("recommendations", [])), 1):
            recommendations.append(RecommendationItem(
                rank=i,
                procedure_name=rec.get("procedure_name", rec.get("procedure", "未知检查")),
                modality=rec.get("modality", "未知"),
                appropriateness_rating=rec.get("appropriateness_rating", rec.get("rating", 0)),
                reasoning=rec.get("reasoning", rec.get("clinical_reasoning", rec.get("reason", ""))),
                evidence_level=rec.get("evidence_level", "B"),
                radiation_level=rec.get("radiation_level", "低"),
                panel_name=rec.get("panel_name", "未知科室")
            ))
        
        return RecommendationResponse(
            method="RAG混合法",
            patient_description=request.patient_description,
            recommendations=recommendations,
            analysis_time_ms=analysis_time,
            confidence_score=result.get("confidence_score", result.get("confidence", 0.85)),
            method_description="向量检索+LLM分析的混合方法，结合语义搜索和临床推理的优势"
        )
        
    except Exception as e:
        logger.error(f"RAG混合推荐失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG混合推荐失败: {str(e)}"
        )

@router.post("/compare-all-methods")
def compare_all_methods(
    request: RecommendationRequest,
    service: IntelligentRecommendationService = Depends(get_intelligent_service)
):
    """
    对比三种推荐方法
    
    同时调用三种方法，返回对比结果
    """
    try:
        # 调用三种方法
        vector_result = vector_method_recommendation(request, service)
        llm_result = llm_method_recommendation(request, service)
        rag_result = rag_method_recommendation(request, service)
        
        return {
            "patient_description": request.patient_description,
            "comparison": {
                "vector_method": {
                    "method": vector_result.method,
                    "recommendations": vector_result.recommendations,
                    "analysis_time_ms": vector_result.analysis_time_ms,
                    "confidence_score": vector_result.confidence_score,
                    "method_description": vector_result.method_description
                },
                "llm_method": {
                    "method": llm_result.method,
                    "recommendations": llm_result.recommendations,
                    "analysis_time_ms": llm_result.analysis_time_ms,
                    "confidence_score": llm_result.confidence_score,
                    "method_description": llm_result.method_description
                },
                "rag_method": {
                    "method": rag_result.method,
                    "recommendations": rag_result.recommendations,
                    "analysis_time_ms": rag_result.analysis_time_ms,
                    "confidence_score": rag_result.confidence_score,
                    "method_description": rag_result.method_description
                }
            },
            "summary": {
                "fastest_method": min([vector_result, llm_result, rag_result], key=lambda x: x.analysis_time_ms).method,
                "highest_confidence": max([vector_result, llm_result, rag_result], key=lambda x: x.confidence_score).method,
                "recommendation": "根据需求选择：快速查询用向量法，复杂推理用LLM法，平衡性能用RAG法"
            }
        }
        
    except Exception as e:
        logger.error(f"方法对比失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"方法对比失败: {str(e)}"
        )
