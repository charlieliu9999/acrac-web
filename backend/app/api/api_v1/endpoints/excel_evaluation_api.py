#!/usr/bin/env python3
"""
Excel评测数据处理API
支持上传Excel文件并进行RAG评测
"""

import os
import json
import time
import pandas as pd
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging
import asyncio
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.system_models import ExcelEvaluationData
import uuid

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# 全局变量存储评测状态
evaluation_status = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "current_case": None,
    "results": [],
    "error": None
}

class ExcelEvaluationService:
    """Excel评测服务"""
    
    def __init__(self, db: Session = None):
        self.api_url = os.getenv("RAG_API_URL", "http://127.0.0.1:8002/api/v1/acrac/rag-llm/intelligent-recommendation")
        self.timeout = 300  # API超时时间（RAGAS评测较慢，适当放宽）
        self.db = db
        
    def parse_excel_file(self, file_content: bytes) -> List[Dict[str, Any]]:
        """解析Excel文件"""
        try:
            # 使用pandas读取Excel
            df = pd.read_excel(file_content)
            
            # 验证必需的列
            required_columns = ['题号', '临床场景', '首选检查项目（标准化）']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise ValueError(f"Excel文件缺少必需的列: {missing_columns}")
            
            # 转换为评测数据格式
            test_cases = []
            for i, row in df.iterrows():
                test_case = {
                    "question_id": int(row['题号']),
                    "clinical_query": str(row['临床场景']),
                    "ground_truth": str(row['首选检查项目（标准化）']).strip('* '),
                    "row_index": i
                }
                test_cases.append(test_case)
            
            return test_cases
            
        except Exception as e:
            logger.error(f"解析Excel文件失败: {e}")
            raise HTTPException(status_code=400, detail=f"Excel文件解析失败: {str(e)}")
    
    def save_evaluation_data_to_db(self, task_id: str, filename: str, test_cases: List[Dict[str, Any]], results: List[Dict[str, Any]]):
        """保存评测数据到数据库"""
        if not self.db:
            return
        
        try:
            for i, test_case in enumerate(test_cases):
                result = results[i] if i < len(results) else {}
                
                # 创建评测数据记录
                eval_data = ExcelEvaluationData(
                    task_id=task_id,
                    filename=filename,
                    question=test_case.get('clinical_query', ''),
                    ground_truth=test_case.get('ground_truth', ''),
                    contexts=result.get('contexts', []),
                    answer=result.get('answer', ''),
                    faithfulness=result.get('ragas_scores', {}).get('faithfulness'),
                    answer_relevancy=result.get('ragas_scores', {}).get('answer_relevancy'),
                    context_precision=result.get('ragas_scores', {}).get('context_precision'),
                    context_recall=result.get('ragas_scores', {}).get('context_recall'),
                    status=result.get('status', 'pending'),
                    error_message=result.get('error', '')
                )
                
                self.db.add(eval_data)
            
            self.db.commit()
            logger.info(f"成功保存{len(test_cases)}条评测数据到数据库")
            
        except Exception as e:
            logger.error(f"保存评测数据到数据库失败: {e}")
            self.db.rollback()
    
    def evaluate_single_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """评测单个案例 - 集成trace_five_cases.py的逻辑"""
        try:
            question_id = test_case["question_id"]
            clinical_query = test_case["clinical_query"]
            ground_truth = test_case["ground_truth"]
            
            logger.info(f"开始处理案例 #{question_id}: {clinical_query[:50]}...")
            
            # 构造API请求payload（基于trace_five_cases.py）
            payload = {
                "clinical_query": clinical_query,
                "top_scenarios": 3,
                "top_recommendations_per_scenario": 3,
                "show_reasoning": True,
                "similarity_threshold": 0.6,
                "debug_mode": True,
                "include_raw_data": True,
                "compute_ragas": True,
                "ground_truth": ground_truth
            }
            
            # 调用API
            start_time = time.time()
            try:
                response = requests.post(self.api_url, json=payload, timeout=self.timeout)
                processing_time = time.time() - start_time
                
                if response.status_code != 200:
                    logger.error(f"API调用失败，状态码: {response.status_code}")
                    return {
                        "question_id": question_id,
                        "clinical_query": clinical_query,
                        "ground_truth": ground_truth,
                        "status": "error",
                        "error": f"API调用失败: {response.status_code} - {response.text}",
                        "processing_time": processing_time,
                        "timestamp": time.time()
                    }
                
                api_result = response.json()
                
                # 解析API响应（基于trace_five_cases.py的逻辑）
                trace = api_result.get('trace') or {}
                
                # 如果没有trace，从响应构造兼容的trace结构
                if not trace:
                    scenarios = api_result.get('scenarios') or []
                    rec_list = []
                    for s in scenarios:
                        rec_list.append({
                            'id': s.get('semantic_id'),
                            'similarity': s.get('similarity'),
                            'panel': s.get('panel_name'),
                            'topic': s.get('topic_name'),
                            '_rerank_score': s.get('_rerank_score')
                        })
                    
                    # rerank基于_rerank_score排序
                    rr = sorted(rec_list, key=lambda x: (x.get('_rerank_score') is None, -(x.get('_rerank_score') or 0.0), -(x.get('similarity') or 0.0)))
                    
                    trace = {
                        'recall_scenarios': rec_list,
                        'rerank_scenarios': rr,
                        'final_prompt': None,
                        'llm_parsed': api_result.get('llm_recommendations') or {}
                    }
                    
                    # 从debug_info补充prompt信息
                    debug_info = api_result.get('debug_info') or {}
                    if isinstance(debug_info.get('step_6_prompt_preview'), str):
                        trace['final_prompt'] = debug_info.get('step_6_prompt_preview')
                
                # 提取评测结果
                mode = "no-RAG" if api_result.get('is_low_similarity_mode') else "RAG"
                
                # 提取RAGAS评分
                ragas_scores = trace.get('ragas_scores') or {
                    "faithfulness": 0.0,
                    "answer_relevancy": 0.0,
                    "context_precision": 0.0,
                    "context_recall": 0.0
                }
                
                # 提取LLM推荐结果
                llm_parsed = trace.get('llm_parsed') or {}
                recommendations = llm_parsed.get('recommendations') or []
                
                result = {
                    "question_id": question_id,
                    "clinical_query": clinical_query,
                    "ground_truth": ground_truth,
                    "status": "success",
                    "mode": mode,
                    "ragas_scores": ragas_scores,
                    "llm_recommendations": recommendations,
                    "recall_count": len(trace.get('recall_scenarios') or []),
                    "rerank_count": len(trace.get('rerank_scenarios') or []),
                    "prompt_length": len(trace.get('final_prompt') or ""),
                    "processing_time": processing_time,
                    "timestamp": time.time(),
                    "trace": trace  # 保存完整trace用于调试
                }
                
                logger.info(f"案例 #{question_id} 处理成功，模式: {mode}，RAGAS评分: {ragas_scores}")
                return result
                
            except requests.exceptions.Timeout:
                logger.error(f"案例 #{question_id} API调用超时")
                return {
                    "question_id": question_id,
                    "clinical_query": clinical_query,
                    "ground_truth": ground_truth,
                    "status": "error",
                    "error": "API调用超时",
                    "processing_time": self.timeout,
                    "timestamp": time.time()
                }
            except requests.exceptions.RequestException as e:
                logger.error(f"案例 #{question_id} 网络请求异常: {e}")
                return {
                    "question_id": question_id,
                    "clinical_query": clinical_query,
                    "ground_truth": ground_truth,
                    "status": "error",
                    "error": f"网络请求异常: {str(e)}",
                    "processing_time": time.time() - start_time,
                    "timestamp": time.time()
                }
            
        except Exception as e:
            logger.error(f"案例处理异常: {e}")
            return {
                "question_id": test_case["question_id"],
                "clinical_query": test_case["clinical_query"],
                "ground_truth": test_case["ground_truth"],
                "status": "error",
                "error": str(e),
                "timestamp": time.time()
            }
    
    def run_batch_evaluation(self, test_cases: List[Dict[str, Any]], task_id: str = None, filename: str = None):
        """批量评测"""
        global evaluation_status
        
        try:
            evaluation_status["is_running"] = True
            evaluation_status["progress"] = 0
            evaluation_status["total"] = len(test_cases)
            evaluation_status["results"] = []
            evaluation_status["error"] = None
            
            for i, test_case in enumerate(test_cases):
                if not evaluation_status["is_running"]:
                    break
                    
                evaluation_status["current_case"] = test_case["clinical_query"]
                
                # 评测单个案例
                result = self.evaluate_single_case(test_case)
                evaluation_status["results"].append(result)
                
                # 更新进度
                evaluation_status["progress"] = i + 1
                
                # 避免API限流
                time.sleep(1.0)
            
            # 评测完成后保存到数据库
            if task_id and filename and self.db:
                self.save_evaluation_data_to_db(task_id, filename, test_cases, evaluation_status["results"])
            
        except Exception as e:
            evaluation_status["error"] = str(e)
            logger.error(f"批量评测失败: {e}")
        finally:
            evaluation_status["is_running"] = False
            evaluation_status["current_case"] = None

@router.post("/upload-excel")
async def upload_excel_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """上传Excel文件并解析"""
    try:
        # 验证文件类型
        if not file.filename.endswith(('.xlsx', '.xls')):
            raise HTTPException(status_code=400, detail="只支持Excel文件(.xlsx, .xls)")
        
        # 读取文件内容
        content = await file.read()
        
        # 创建服务实例
        service = ExcelEvaluationService(db=db)
        
        # 解析Excel文件
        test_cases = service.parse_excel_file(content)
        
        return {
            "success": True,
            "message": f"成功解析Excel文件，共{len(test_cases)}个测试案例",
            "total_cases": len(test_cases),
            "test_cases": test_cases,  # 返回全部数据，供评测与预览
            "preview_test_cases": test_cases[: min(10, len(test_cases))],  # 预览前10条
            "filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"上传Excel文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ExcelStartEvaluationRequest(BaseModel):
    test_cases: List[Dict[str, Any]]
    filename: Optional[str] = None

@router.post("/start-evaluation")
async def start_evaluation(
    req: ExcelStartEvaluationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """开始批量评测（兼容 body={ test_cases: [...], filename } 的请求体）"""
    global evaluation_status

    if evaluation_status["is_running"]:
        raise HTTPException(status_code=400, detail="评测正在进行中，请等待完成")

    # 生成任务ID
    task_id = str(uuid.uuid4())

    # 创建服务实例
    service = ExcelEvaluationService(db=db)

    # 在后台运行评测
    background_tasks.add_task(service.run_batch_evaluation, req.test_cases, task_id, req.filename)

    return {
        "success": True,
        "message": f"开始评测{len(req.test_cases)}个案例",
        "total_cases": len(req.test_cases),
        "task_id": task_id
    }

@router.get("/evaluation-status")
async def get_evaluation_status():
    """获取评测状态"""
    return evaluation_status

@router.post("/stop-evaluation")
async def stop_evaluation():
    """停止评测"""
    global evaluation_status
    evaluation_status["is_running"] = False
    
    return {
        "success": True,
        "message": "评测已停止"
    }

@router.get("/evaluation-results")
async def get_evaluation_results():
    """获取评测结果"""
    return {
        "success": True,
        "results": evaluation_status["results"],
        "total": evaluation_status["total"],
        "completed": evaluation_status["progress"]
    }

@router.post("/export-results")
async def export_results():
    """导出评测结果"""
    try:
        results = evaluation_status["results"]
        
        if not results:
            raise HTTPException(status_code=400, detail="没有可导出的结果")
        
        # 转换为DataFrame
        df_data = []
        for result in results:
            row = {
                "题号": result["question_id"],
                "临床场景": result["clinical_query"],
                "标准答案": result["ground_truth"],
                "评测状态": result["status"],
                "模式": result.get("mode", ""),
                "忠实度": result.get("ragas_scores", {}).get("faithfulness", 0),
                "答案相关性": result.get("ragas_scores", {}).get("answer_relevancy", 0),
                "上下文精确度": result.get("ragas_scores", {}).get("context_precision", 0),
                "上下文召回率": result.get("ragas_scores", {}).get("context_recall", 0),
                "错误信息": result.get("error", "")
            }
            df_data.append(row)
        
        df = pd.DataFrame(df_data)
        
        # 生成文件名
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        filename = f"evaluation_results_{timestamp}.xlsx"
        
        # 保存到临时目录
        temp_path = Path("/tmp") / filename
        df.to_excel(temp_path, index=False)
        
        return {
            "success": True,
            "message": "结果导出成功",
            "filename": filename,
            "path": str(temp_path)
        }
        
    except Exception as e:
        logger.error(f"导出结果失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/evaluation-history")
async def get_evaluation_history(db: Session = Depends(get_db), limit: int = 50, offset: int = 0):
    """获取Excel评测历史数据"""
    try:
        # 查询评测历史数据
        history_data = db.query(ExcelEvaluationData).offset(offset).limit(limit).all()
        
        # 转换为响应格式
        history_list = []
        for data in history_data:
            history_list.append({
                "id": data.id,
                "task_id": data.task_id,
                "filename": data.filename,
                "question": data.question,
                "ground_truth": data.ground_truth,
                "answer": data.answer,
                "ragas_scores": {
                    "faithfulness": data.faithfulness,
                    "answer_relevancy": data.answer_relevancy,
                    "context_precision": data.context_precision,
                    "context_recall": data.context_recall
                },
                "status": data.status,
                "error_message": data.error_message,
                "created_at": data.created_at.isoformat() if data.created_at else None,
                "updated_at": data.updated_at.isoformat() if data.updated_at else None
            })
        
        # 获取总数
        total_count = db.query(ExcelEvaluationData).count()
        
        return {
            "success": True,
            "data": history_list,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取评测历史失败: {str(e)}")

@router.get("/evaluation-history/{task_id}")
async def get_evaluation_by_task_id(task_id: str, db: Session = Depends(get_db)):
    """根据任务ID获取评测数据"""
    try:
        # 查询指定任务的评测数据
        task_data = db.query(ExcelEvaluationData).filter(
            ExcelEvaluationData.task_id == task_id
        ).all()
        
        if not task_data:
            raise HTTPException(status_code=404, detail="未找到指定任务的评测数据")
        
        # 转换为响应格式
        task_results = []
        for data in task_data:
            task_results.append({
                "id": data.id,
                "question": data.question,
                "ground_truth": data.ground_truth,
                "answer": data.answer,
                "contexts": data.contexts,
                "ragas_scores": {
                    "faithfulness": data.faithfulness,
                    "answer_relevancy": data.answer_relevancy,
                    "context_precision": data.context_precision,
                    "context_recall": data.context_recall
                },
                "status": data.status,
                "error_message": data.error_message,
                "created_at": data.created_at.isoformat() if data.created_at else None
            })
        
        return {
            "success": True,
            "task_id": task_id,
            "filename": task_data[0].filename,
            "total_cases": len(task_results),
            "results": task_results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务评测数据失败: {str(e)}")