#!/usr/bin/env python3
"""
独立的 RAGAS 评估 API
绕过 uvloop 兼容性问题，使用修复的评估器
"""

import logging
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio
import sys

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

class EvaluationRequest(BaseModel):
    test_data: List[Dict[str, Any]]

class EvaluationResponse(BaseModel):
    status: str
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_ragas(request: EvaluationRequest):
    """
    RAGAS 评估接口
    """
    try:
        logger.info(f"收到评估请求，包含 {len(request.test_data)} 个测试样本")
        
        # 使用子进程评估器，避免事件循环冲突
        try:
            from app.services.ragas_subprocess_evaluator import RAGASSubprocessEvaluator
            evaluator = RAGASSubprocessEvaluator()
            logger.info("RAGAS 子进程评估器初始化成功")
        except Exception as e:
            logger.error(f"RAGAS 子进程评估器初始化失败: {e}")
            return EvaluationResponse(
                status="error",
                error=f"评估器初始化失败: {str(e)}"
            )
        
        # 执行评估
        try:
            result = evaluator.run_evaluation(request.test_data)
            logger.info(f"评估完成，综合评分: {result.get('overall_score', 'N/A')}")
            
            return EvaluationResponse(
                status="success",
                results=result
            )
        except Exception as e:
            logger.error(f"评估执行失败: {e}")
            return EvaluationResponse(
                status="error",
                error=f"评估执行失败: {str(e)}"
            )
            
    except Exception as e:
        logger.error(f"评估接口异常: {e}")
        return EvaluationResponse(
            status="error",
            error=f"接口异常: {str(e)}"
        )

@router.get("/health")
async def health_check():
    """
    健康检查接口
    """
    try:
        # 检查子进程评估器是否可用
        from app.services.ragas_subprocess_evaluator import RAGASSubprocessEvaluator
        evaluator = RAGASSubprocessEvaluator()
        
        # 执行健康检查
        health_result = evaluator.health_check()
        return health_result
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"RAGAS 评估服务异常: {str(e)}"
        }