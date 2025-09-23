#!/usr/bin/env python3
"""
RAGAS评估API
基于official_ragas_evaluation.py实现的RAGAS评估流程
"""

import os
import json
import time
import logging
import asyncio
import sys
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, JSON, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import json

# 修复 RAGAS 与 uvloop 的兼容性问题
if sys.platform != 'win32':
    try:
        # 设置默认事件循环策略，避免与 uvloop 冲突
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    except Exception:
        pass

# RAGAS相关导入
try:
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    from datasets import Dataset
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
except ImportError as e:
    logging.warning(f"RAGAS相关依赖未安装: {e}")
    evaluate = None
    faithfulness = None
    answer_relevancy = None
    context_precision = None
    context_recall = None
    Dataset = None
    ChatOpenAI = None
    OpenAIEmbeddings = None

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# 导入数据库相关
from app.core.database import get_db
from app.models.ragas_models import ScenarioResult

class RAGASEvaluationRequest(BaseModel):
    """RAGAS评估请求"""
    test_cases: List[Dict[str, Any]]
    model_name: str = "gpt-3.5-turbo"
    base_url: str = "https://api.siliconflow.cn/v1"
    
class RAGASEvaluationResponse(BaseModel):
    """RAGAS评估响应"""
    status: str
    results: Optional[List[Dict[str, Any]]] = None
    summary: Optional[Dict[str, float]] = None
    error: Optional[str] = None
    processing_time: Optional[float] = None

class RAGASEvaluationService:
    """RAGAS评估服务 - 基于official_ragas_evaluation.py"""
    
    def __init__(self):
        # 兼容旧逻辑：优先 OPENAI_API_KEY，否则使用 SILICONFLOW_API_KEY
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("SILICONFLOW_API_KEY")
        if not self.api_key:
            logger.warning("未设置 OPENAI_API_KEY 或 SILICONFLOW_API_KEY 环境变量")

    def setup_models(self, model_name: str = None, base_url: str = None):
        """设置LLM和Embeddings模型（统一走模型配置的 evaluation 上下文）"""
        try:
            # 使用统一评测适配器，从 backend/config/model_contexts.json 的 contexts.evaluation 读取
            from app.services.ragas_evaluator import RAGASEvaluator
            evaluator = RAGASEvaluator()
            llm = evaluator.llm
            embeddings = evaluator.embeddings
            logger.info(f"RAGAS评估模型: LLM={evaluator.llm_model_name}, Embedding={evaluator.embedding_model_name}")
            return llm, embeddings
        except Exception as e:
            logger.error(f"模型初始化失败: {e}")
            raise
    
    def prepare_dataset(self, test_cases: List[Dict[str, Any]]) -> Dataset:
        """准备RAGAS评估数据集"""
        try:
            questions = []
            answers = []
            contexts = []
            ground_truths = []
            
            for case in test_cases:
                # 提取基本信息
                question = case.get('clinical_query', '')
                ground_truth = case.get('ground_truth', '')
                
                # 从trace中提取答案和上下文
                trace = case.get('trace', {})
                llm_parsed = trace.get('llm_parsed', {})
                
                # 构造答案（从LLM推荐结果）
                recommendations = llm_parsed.get('recommendations', [])
                if recommendations:
                    answer = f"推荐检查项目: {', '.join([rec.get('name', '') for rec in recommendations[:3]])}"
                else:
                    answer = "无推荐结果"
                
                # 构造上下文（从召回的场景）
                recall_scenarios = trace.get('recall_scenarios', [])
                context_list = []
                for scenario in recall_scenarios[:3]:  # 取前3个
                    panel = scenario.get('panel', '')
                    topic = scenario.get('topic', '')
                    if panel and topic:
                        context_list.append(f"{panel} - {topic}")
                
                context = '; '.join(context_list) if context_list else "无相关上下文"
                
                questions.append(question)
                answers.append(answer)
                contexts.append([context])  # RAGAS需要list格式
                ground_truths.append(ground_truth)
            
            # 创建Dataset
            dataset = Dataset.from_dict({
                "question": questions,
                "answer": answers,
                "contexts": contexts,
                "ground_truth": ground_truths
            })
            
            logger.info(f"准备了 {len(questions)} 个测试样本")
            return dataset
            
        except Exception as e:
            logger.error(f"数据集准备失败: {e}")
            raise
    
    def evaluate_sample(self, sample: Dict[str, Any], llm, embeddings) -> Dict[str, float]:
        """评估单个样本"""
        try:
            # 定义评估指标
            metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
            
            # 创建单样本数据集
            sample_dataset = Dataset.from_dict({
                "question": [sample["question"]],
                "answer": [sample["answer"]],
                "contexts": [sample["contexts"]],
                "ground_truth": [sample["ground_truth"]]
            })
            
            # 执行评估
            result = evaluate(
                dataset=sample_dataset,
                metrics=metrics,
                llm=llm,
                embeddings=embeddings
            )
            
            # 提取评分
            scores = {
                "faithfulness": float(result["faithfulness"]) if "faithfulness" in result else 0.0,
                "answer_relevancy": float(result["answer_relevancy"]) if "answer_relevancy" in result else 0.0,
                "context_precision": float(result["context_precision"]) if "context_precision" in result else 0.0,
                "context_recall": float(result["context_recall"]) if "context_recall" in result else 0.0
            }
            
            return scores
            
        except Exception as e:
            logger.error(f"样本评估失败: {e}")
            return {
                "faithfulness": 0.0,
                "answer_relevancy": 0.0,
                "context_precision": 0.0,
                "context_recall": 0.0
            }
    
    def run_evaluation(self, test_cases: List[Dict[str, Any]], model_name: str = "gpt-3.5-turbo", base_url: str = "https://api.siliconflow.cn/v1") -> Dict[str, Any]:
        """运行完整的RAGAS评估"""
        start_time = time.time()
        
        try:
            # 检查依赖
            if not all([evaluate, faithfulness, answer_relevancy, context_precision, context_recall]):
                raise ValueError("RAGAS相关依赖未安装，请安装ragas、datasets、langchain-openai等包")
            
            # 设置模型
            llm, embeddings = self.setup_models(model_name, base_url)
            
            # 准备数据集
            dataset = self.prepare_dataset(test_cases)
            
            # 执行批量评估
            logger.info("开始RAGAS评估...")
            
            # 定义评估指标
            metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
            
            # 执行评估
            result = evaluate(
                dataset=dataset,
                metrics=metrics,
                llm=llm,
                embeddings=embeddings
            )
            
            # 处理结果
            results = []
            for i, case in enumerate(test_cases):
                case_result = {
                    "question_id": case.get("question_id", i),
                    "clinical_query": case.get("clinical_query", ""),
                    "ground_truth": case.get("ground_truth", ""),
                    "ragas_scores": {
                        "faithfulness": float(result["faithfulness"][i]) if i < len(result["faithfulness"]) else 0.0,
                        "answer_relevancy": float(result["answer_relevancy"][i]) if i < len(result["answer_relevancy"]) else 0.0,
                        "context_precision": float(result["context_precision"][i]) if i < len(result["context_precision"]) else 0.0,
                        "context_recall": float(result["context_recall"][i]) if i < len(result["context_recall"]) else 0.0
                    },
                    "timestamp": time.time()
                }
                results.append(case_result)
            
            # 计算综合评分
            summary = {
                "faithfulness": float(result["faithfulness"].mean()) if "faithfulness" in result else 0.0,
                "answer_relevancy": float(result["answer_relevancy"].mean()) if "answer_relevancy" in result else 0.0,
                "context_precision": float(result["context_precision"].mean()) if "context_precision" in result else 0.0,
                "context_recall": float(result["context_recall"].mean()) if "context_recall" in result else 0.0
            }
            
            processing_time = time.time() - start_time
            
            logger.info(f"RAGAS评估完成，耗时: {processing_time:.2f}秒")
            logger.info(f"综合评分: {summary}")
            
            return {
                "status": "success",
                "results": results,
                "summary": summary,
                "processing_time": processing_time
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"RAGAS评估失败: {e}")
            return {
                "status": "error",
                "error": str(e),
                "processing_time": processing_time
            }

async def run_real_rag_evaluation(
    test_cases: List[Dict],
    task_id: str,
    db: Session
) -> Dict[str, Any]:
    """运行真实的RAG评估"""
    try:
        logger.info(f"开始RAG评估任务: {task_id}")
        
        # 导入RAG-LLM服务和RAGAS评估器
        from app.services.rag_llm_recommendation_service import rag_llm_service
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent / "RAGAS"))
        
        try:
            from official_ragas_evaluation import CorrectRAGASEvaluator
            ragas_evaluator = CorrectRAGASEvaluator()
            ragas_available = True
        except ImportError as e:
            logger.warning(f"RAGAS评估器导入失败: {e}，将跳过RAGAS评分")
            ragas_available = False
        
        results = []
        failed_count = 0
        
        for i, case in enumerate(test_cases):
            try:
                question_id = case.get("question_id", f"q_{i+1}")
                clinical_query = case.get("clinical_query", "")
                ground_truth = case.get("ground_truth", "")
                
                logger.info(f"处理测试用例 {i+1}/{len(test_cases)}: {question_id}")
                
                # 调用真实的RAG-LLM API
                rag_result = rag_llm_service.generate_intelligent_recommendation(
                    query=clinical_query,
                    debug_flag=True,  # 获取完整trace信息
                    compute_ragas=False,  # 我们自己计算RAGAS
                    ground_truth=ground_truth
                )
                
                if not rag_result.get("success"):
                    logger.error(f"RAG-LLM调用失败: {rag_result.get('message', '未知错误')}")
                    failed_count += 1
                    continue
                
                # 提取RAG响应和trace信息
                llm_recommendations = rag_result.get("llm_recommendations", {})
                trace_info = rag_result.get("trace", {})
                
                # 构造RAGAS评估所需的数据格式
                ragas_data = {
                    "question": clinical_query,
                    "answer": json.dumps(llm_recommendations, ensure_ascii=False) if llm_recommendations else "",
                    "contexts": [],
                    "ground_truth": ground_truth
                }
                
                # 从trace信息中提取上下文
                if trace_info:
                    recall_scenarios = trace_info.get("recall_scenarios", [])
                    for scenario in recall_scenarios:
                        if isinstance(scenario, dict) and "description_zh" in scenario:
                            ragas_data["contexts"].append(scenario["description_zh"])
                
                # 如果没有上下文，使用默认值
                if not ragas_data["contexts"]:
                    ragas_data["contexts"] = ["无可用上下文信息"]
                
                # 计算RAGAS评分
                ragas_scores = {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_precision": 0.0, "context_recall": 0.0}
                if ragas_available and ragas_data["answer"]:
                    try:
                        ragas_scores = ragas_evaluator.safe_evaluate_sample(ragas_data)
                    except Exception as e:
                        logger.warning(f"RAGAS评估失败: {e}")
                
                # 计算综合评分
                valid_scores = [v for v in ragas_scores.values() if v > 0]
                overall_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
                
                # 构造结果
                result = {
                    "question_id": question_id,
                    "clinical_query": clinical_query,
                    "ground_truth": ground_truth,
                    "rag_response": llm_recommendations,
                    "trace": trace_info,
                    "ragas_scores": ragas_scores,
                    "overall_score": overall_score,
                    "processing_time_ms": rag_result.get("processing_time_ms", 0)
                }
                
                results.append(result)
                
                # 保存到数据库
                scenario_result = ScenarioResult(
                    task_id=task_id,
                    scenario_id=question_id,
                    clinical_query=clinical_query,
                    ground_truth=ground_truth,
                    rag_response=llm_recommendations,
                    trace_data=trace_info,
                    ragas_scores=ragas_scores,
                    overall_score=overall_score
                )
                db.add(scenario_result)
                
            except Exception as e:
                logger.error(f"处理测试用例 {i+1} 失败: {e}")
                failed_count += 1
                continue
        
        # 提交数据库更改
        db.commit()
        
        # 计算汇总统计
        if results:
            avg_scores = {
                "faithfulness": sum(r["ragas_scores"]["faithfulness"] for r in results) / len(results),
                "answer_relevancy": sum(r["ragas_scores"]["answer_relevancy"] for r in results) / len(results),
                "context_precision": sum(r["ragas_scores"]["context_precision"] for r in results) / len(results),
                "context_recall": sum(r["ragas_scores"]["context_recall"] for r in results) / len(results)
            }
            overall_avg = sum(avg_scores.values()) / len(avg_scores)
        else:
            avg_scores = {}
            overall_avg = 0.0
        
        summary = {
            "total_cases": len(test_cases),
            "successful_cases": len(results),
            "failed_cases": failed_count,
            "average_scores": avg_scores,
            "overall_average": overall_avg
        }
        
        return {
            "status": "success",
            "results": results,
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"RAG评估失败: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

# 创建服务实例
ragas_service = RAGASEvaluationService()

@router.post("/ragas-evaluate", response_model=RAGASEvaluationResponse)
async def evaluate_ragas(
    request: RAGASEvaluationRequest,
    db: Session = Depends(get_db)
):
    """执行RAGAS评估"""
    try:
        # 创建评估任务
        task = EvaluationTask(
            task_name=f"RAGAS评估_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            task_type="ragas",
            status="running",
            config={"test_cases": request.test_cases}
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # 使用真实的RAG评估
        evaluation_result = await run_real_rag_evaluation(
            test_cases=request.test_cases,
            task_id=str(task.id),
            db=db
        )
        
        # 保存结果
        result = EvaluationResult(
            task_id=task.id,
            result_data=evaluation_result,
            status="completed" if evaluation_result.get("status") == "success" else "failed"
        )
        db.add(result)
        
        # 更新任务状态
        task.status = "completed" if evaluation_result.get("status") == "success" else "failed"
        db.commit()
        
        if evaluation_result.get("status") == "error":
            raise HTTPException(status_code=500, detail=evaluation_result.get("error", "评估失败"))
        
        return RAGASEvaluationResponse(
            task_id=task.id,
            status="completed",
            results=evaluation_result.get("results", []),
            summary=evaluation_result.get("summary", {})
        )
        
    except Exception as e:
        logger.error(f"RAGAS评估失败: {e}")
        if 'task' in locals():
            task.status = "failed"
            db.commit()
        raise HTTPException(status_code=500, detail=f"评估失败: {str(e)}")

@router.get("/data/query")
async def query_evaluation_data(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db)
):
    """查询评测数据"""
    try:
        # 这里需要根据实际的数据表结构来查询
        # 假设有一个存储测试数据的表，比如TestData
        from app.models.evaluation import TestData  # 需要创建这个模型
        
        query = db.query(TestData)
        
        # 如果有搜索关键词，添加搜索条件
        if search:
            query = query.filter(
                TestData.clinical_query.contains(search) |
                TestData.ground_truth.contains(search)
            )
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * page_size
        items = query.offset(offset).limit(page_size).all()
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": item.id,
                    "question_id": item.question_id,
                    "clinical_query": item.clinical_query,
                    "ground_truth": item.ground_truth,
                    "created_at": item.created_at
                }
                for item in items
            ]
        }
        
    except Exception as e:
        logger.error(f"查询评测数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

@router.post("/data/select-evaluate")
async def evaluate_selected_data(
    data_ids: List[int] = Body(..., description="选中的数据ID列表"),
    db: Session = Depends(get_db)
):
    """对选中的数据进行评测"""
    try:
        # 查询选中的数据
        from app.models.evaluation import TestData
        
        selected_data = db.query(TestData).filter(TestData.id.in_(data_ids)).all()
        
        if not selected_data:
            raise HTTPException(status_code=404, detail="未找到选中的数据")
        
        # 转换为评测格式
        test_cases = [
            {
                "question_id": data.question_id,
                "clinical_query": data.clinical_query,
                "ground_truth": data.ground_truth
            }
            for data in selected_data
        ]
        
        # 创建评估任务
        task = EvaluationTask(
            task_name=f"选中数据评估_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            task_type="ragas",
            status="running",
            config={"selected_data_ids": data_ids, "test_cases": test_cases}
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # 使用真实的RAG评估
        evaluation_result = await run_real_rag_evaluation(
            test_cases=test_cases,
            task_id=str(task.id),
            db=db
        )
        
        # 保存结果
        result = EvaluationResult(
            task_id=task.id,
            result_data=evaluation_result,
            status="completed" if evaluation_result.get("status") == "success" else "failed"
        )
        db.add(result)
        
        # 更新任务状态
        task.status = "completed" if evaluation_result.get("status") == "success" else "failed"
        db.commit()
        
        if evaluation_result.get("status") == "error":
            raise HTTPException(status_code=500, detail=evaluation_result.get("error", "评估失败"))
        
        return {
            "task_id": task.id,
            "status": "completed",
            "message": f"成功评估 {len(test_cases)} 条数据",
            "results": evaluation_result.get("results", []),
            "summary": evaluation_result.get("summary", {})
        }
        
    except Exception as e:
        logger.error(f"选中数据评估失败: {e}")
        if 'task' in locals():
            task.status = "failed"
            db.commit()
        raise HTTPException(status_code=500, detail=f"评估失败: {str(e)}")

@router.get("/ragas-health")
async def ragas_health_check():
    """
    检查RAGAS服务健康状态
    """
    try:
        # 检查依赖
        dependencies_ok = all([evaluate, faithfulness, answer_relevancy, context_precision, context_recall])
        api_key_ok = bool(os.getenv("OPENAI_API_KEY"))
        
        return {
            "status": "healthy" if dependencies_ok and api_key_ok else "unhealthy",
            "dependencies_installed": dependencies_ok,
            "api_key_configured": api_key_ok,
            "timestamp": time.time()
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }