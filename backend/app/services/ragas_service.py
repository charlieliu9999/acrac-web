"""RAGAS评测服务"""
import os
import json
import uuid
import time
import logging
import requests
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.ragas_schemas import TestCaseBase, EvaluationResult, TaskStatus
from app.models.ragas_models import EvaluationTask, ScenarioResult, EvaluationMetrics

# 配置日志
logger = logging.getLogger(__name__)

# 文件上传配置
UPLOAD_DIR = Path("uploads/ragas")
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".json", ".csv", ".xlsx", ".txt"}

# ==================== 工具函数 ====================

def validate_file(file_path: Path, file_size: int) -> None:
    """验证上传文件"""
    if not file_path.name:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    
    file_ext = file_path.suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件类型: {file_ext}。支持的类型: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400, 
            detail=f"文件大小超过限制: {file_size} bytes > {MAX_FILE_SIZE} bytes"
        )

def parse_uploaded_file(file_path: Path, file_type: str) -> List[TestCaseBase]:
    """解析上传的文件"""
    test_cases = []
    
    try:
        if file_type == ".json":
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if isinstance(data, list):
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        test_case = TestCaseBase(
                            question_id=item.get('question_id', f"q_{i+1}"),
                            clinical_query=item.get('clinical_query', item.get('question', '')),
                            ground_truth=item.get('ground_truth', item.get('answer', '')),
                            metadata=item.get('metadata', {})
                        )
                        test_cases.append(test_case)
            elif isinstance(data, dict):
                test_case = TestCaseBase(
                    question_id=data.get('question_id', 'q_1'),
                    clinical_query=data.get('clinical_query', data.get('question', '')),
                    ground_truth=data.get('ground_truth', data.get('answer', '')),
                    metadata=data.get('metadata', {})
                )
                test_cases.append(test_case)
                
        elif file_type == ".csv":
            import pandas as pd
            df = pd.read_csv(file_path)
            
            for i, row in df.iterrows():
                test_case = TestCaseBase(
                    question_id=row.get('question_id', f"q_{i+1}"),
                    clinical_query=row.get('clinical_query', row.get('question', '')),
                    ground_truth=row.get('ground_truth', row.get('answer', '')),
                    metadata={col: row[col] for col in df.columns if col not in ['question_id', 'clinical_query', 'ground_truth']}
                )
                test_cases.append(test_case)
                
        elif file_type == ".xlsx":
            import pandas as pd
            df = pd.read_excel(file_path)
            
            column_mapping = {
                '题号': 'question_id',
                '临床场景': 'clinical_query', 
                '首选检查项目（标准化）': 'ground_truth',
                'question_id': 'question_id',
                'clinical_query': 'clinical_query',
                'ground_truth': 'ground_truth',
                'question': 'clinical_query',
                'answer': 'ground_truth'
            }
            
            df_renamed = df.rename(columns=column_mapping)
            
            for i, row in df_renamed.iterrows():
                question_id = row.get('question_id', f"q_{i+1}")
                clinical_query = row.get('clinical_query', '')
                ground_truth = row.get('ground_truth', '')
                
                if pd.isna(question_id):
                    question_id = f"q_{i+1}"
                if pd.isna(clinical_query):
                    clinical_query = ''
                if pd.isna(ground_truth):
                    ground_truth = ''
                    
                test_case = TestCaseBase(
                    question_id=str(question_id),
                    clinical_query=str(clinical_query),
                    ground_truth=str(ground_truth),
                    metadata={col: str(row[col]) if not pd.isna(row[col]) else '' 
                             for col in df.columns 
                             if col not in column_mapping.keys() and col not in column_mapping.values()}
                )
                test_cases.append(test_case)
                
        elif file_type == ".txt":
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            for i, line in enumerate(lines):
                line = line.strip()
                if line:
                    test_case = TestCaseBase(
                        question_id=f"q_{i+1}",
                        clinical_query=line,
                        ground_truth="",
                        metadata={}
                    )
                    test_cases.append(test_case)
                    
    except Exception as e:
        logger.error(f"文件解析失败: {e}")
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")
    
    return test_cases

def validate_test_cases(test_cases: List[TestCaseBase]) -> tuple[List[TestCaseBase], List[str]]:
    """验证测试用例"""
    valid_cases = []
    errors = []
    
    for i, case in enumerate(test_cases):
        if not case.clinical_query.strip():
            errors.append(f"第{i+1}个用例：临床查询不能为空")
            continue
            
        if not case.ground_truth.strip():
            errors.append(f"第{i+1}个用例：标准答案不能为空")
            continue
            
        valid_cases.append(case)
    
    return valid_cases, errors

async def run_real_rag_evaluation(
    test_cases: List[Dict[str, Any]],
    model_name: str,
    base_url: Optional[str] = None,
    task_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    执行真实的RAG评测流水线：
    - 逐条调用 RAG-LLM 推理（通过 HTTP API）
    - 可选计算 RAGAS 指标（若依赖与 API Key 可用）
    - 将单条结果与汇总结果写入数据库（若提供 db 与 task_id）

    注意：为在缺省环境下也能运行，本实现对外部依赖做了降级处理：
    - RAG_API_URL 不可用时，单条用例计为失败但不中断整体流程
    - RAGAS 依赖缺失或 API Key 缺失时，自动跳过评分，记 0 分
    """
    rag_api_url = os.getenv(
        "RAG_API_URL",
        "http://127.0.0.1:8002/api/v1/acrac/rag-llm/intelligent-recommendation",
    )

    evaluation_results: List[Dict[str, Any]] = []
    total_cases = len(test_cases or [])
    completed_cases = 0
    failed_cases = 0

    # 尝试初始化 RAGAS 评估器（可选）
    ragas_evaluator = None
    try:
        from app.services.ragas_evaluator_v2 import ACRACRAGASEvaluator  # type: ignore
        ragas_evaluator = ACRACRAGASEvaluator()
        logger.info("使用ACRAC RAGAS评估器")
    except Exception as e:
        logger.warning(f"RAGAS评估器初始化失败，将跳过RAGAS评分: {e}")

    for i, test_case in enumerate(test_cases or []):
        try:
            clinical_query = (
                test_case.get("clinical_query")
                or test_case.get("question")
                or test_case.get("clinical_scenario")
                or ""
            )
            ground_truth = test_case.get("ground_truth") or test_case.get("standard_answer") or ""
            question_id = test_case.get("question_id") or test_case.get("scenario_id") or f"case_{i+1}"

            # 构造 RAG 推理请求载荷（开启 debug 便于前端展示 trace）
            from app.core.config import settings as _settings
            # 从配置/环境读取检索参数，保持与RAG助手一致
            _top_scenarios = int(os.getenv('RAG_TOP_SCENARIOS', str(getattr(_settings, 'RAG_TOP_SCENARIOS', 3))))
            _top_recs = int(os.getenv('RAG_TOP_RECOMMENDATIONS_PER_SCENARIO', str(getattr(_settings, 'RAG_TOP_RECOMMENDATIONS_PER_SCENARIO', 3))))
            _sim_threshold = float(os.getenv('VECTOR_SIMILARITY_THRESHOLD', str(getattr(_settings, 'VECTOR_SIMILARITY_THRESHOLD', 0.6))))
            rag_payload = {
                "clinical_query": clinical_query,
                "top_scenarios": _top_scenarios,
                "top_recommendations_per_scenario": _top_recs,
                "show_reasoning": True,
                "similarity_threshold": _sim_threshold,
                "debug_mode": True,
                "include_raw_data": True,
                # 评分在本函数内进行，避免与远端重复
                "compute_ragas": False,
                "ground_truth": ground_truth,
            }

            inference_started_at = None
            inference_completed_at = None

            # 调用 RAG-LLM HTTP API
            try:
                inference_started_at = datetime.now()
                resp = requests.post(rag_api_url, json=rag_payload, timeout=120)
                resp.raise_for_status()
                rag_result = resp.json()
                inference_completed_at = datetime.now()
            except Exception as e:
                logger.error(f"RAG API 调用失败: {e}")
                failed_cases += 1
                # 更新进度（失败也计入）
                if db and task_id:
                    task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
                    if task:
                        task.completed_scenarios = completed_cases
                        task.failed_scenarios = failed_cases
                        task.progress_percentage = int(((completed_cases + failed_cases) / max(total_cases, 1)) * 100)
                        db.commit()
                # 限流/退避
                await asyncio.sleep(0.5)
                continue

            # 提取 LLM 推荐并拼接文本答案
            llm_recs = (rag_result or {}).get("llm_recommendations", {})
            recommendations = llm_recs.get("recommendations", []) if isinstance(llm_recs, dict) else []
            if recommendations:
                answer_text = "推荐的影像学检查：\n" + "\n".join(
                    [
                        f"- {rec.get('procedure_name','')} (适宜性: {rec.get('appropriateness_rating','')})"
                        for rec in recommendations[:3]
                    ]
                )
            else:
                answer_text = "暂无推荐的影像学检查"

            # 构造/兜底 trace（以便前端中间过程展示）
            trace = (rag_result or {}).get("trace") or {}
            if not trace:
                scenarios = (rag_result or {}).get("scenarios") or []
                # 构造 recall 视图
                recall_list = []
                for s in scenarios:
                    recall_list.append({
                        "id": s.get("semantic_id") or s.get("id"),
                        "similarity": s.get("similarity"),
                        "panel": s.get("panel_name"),
                        "topic": s.get("topic_name"),
                        "_rerank_score": s.get("_rerank_score"),
                    })
                # 构造 rerank 视图
                rerank_list = sorted(
                    recall_list,
                    key=lambda x: (
                        x.get("_rerank_score") is None,
                        -(x.get("_rerank_score") or 0.0),
                        -(x.get("similarity") or 0.0),
                    ),
                )
                # 最终 prompt 预览/长度
                dbg = (rag_result or {}).get("debug_info") or {}
                final_prompt = dbg.get("step_6_prompt_preview") if isinstance(dbg.get("step_6_prompt_preview"), str) else None
                trace = {
                    "recall_scenarios": recall_list,
                    "rerank_scenarios": rerank_list,
                    "final_prompt": final_prompt,
                    "llm_parsed": (rag_result or {}).get("llm_recommendations") or {},
                }

            # 提取场景上下文（用于 RAGAS 评分）
            contexts: List[str] = []
            for sc in (rag_result or {}).get("scenarios", [])[:3]:
                try:
                    ctx = f"场景: {sc.get('panel_name','')} - {sc.get('topic_name','')}"
                    if sc.get("clinical_scenario"):
                        ctx += f"\n临床场景: {sc['clinical_scenario']}"
                    contexts.append(ctx)
                except Exception:
                    continue

            # 计算 RAGAS 分数（若可用）
            evaluation_started_at = None
            evaluation_completed_at = None
            ragas_scores = {
                "faithfulness": 0.0,
                "answer_relevancy": 0.0,
                "context_precision": 0.0,
                "context_recall": 0.0,
            }
            if contexts and answer_text and ground_truth:
                try:
                    evaluation_started_at = datetime.now()
                    # 使用主服务中的统一实现，确保四项指标（含 answer_relevancy）一致
                    from app.services.rag_llm_recommendation_service import rag_llm_service  # 延迟导入避免环依赖
                    ragas_scores = rag_llm_service._compute_ragas_scores(
                        user_input=clinical_query,
                        answer=answer_text,
                        contexts=contexts,
                        reference=ground_truth,
                    )
                    evaluation_completed_at = datetime.now()
                    logger.info(f"RAGAS评分计算完成: {ragas_scores}")
                except Exception as e:
                    logger.warning(f"RAGAS评分计算失败，已跳过该样本评分: {e}")
                    evaluation_completed_at = datetime.now() if evaluation_started_at else None

            # 单条整体得分
            try:
                overall_score = (
                    ragas_scores.get("faithfulness", 0.0)
                    + ragas_scores.get("answer_relevancy", 0.0)
                    + ragas_scores.get("context_precision", 0.0)
                    + ragas_scores.get("context_recall", 0.0)
                ) / 4.0
            except Exception:
                overall_score = None

            # 写入数据库（若提供）
            if db and task_id:
                sr = ScenarioResult(
                    task_id=task_id,
                    scenario_id=str(question_id),
                    clinical_scenario=clinical_query,
                    rag_question=clinical_query,
                    rag_answer=answer_text,
                    rag_contexts=contexts,
                    rag_trace_data=trace,
                    standard_answer=ground_truth,
                    faithfulness_score=ragas_scores.get("faithfulness", 0.0),
                    answer_relevancy_score=ragas_scores.get("answer_relevancy", 0.0),
                    context_precision_score=ragas_scores.get("context_precision", 0.0),
                    context_recall_score=ragas_scores.get("context_recall", 0.0),
                    overall_score=overall_score,
                    evaluation_metadata={
                        "rag_result": rag_result,
                        "contexts": contexts,
                        "model_name": model_name,
                        "ragas_llm_model": getattr(ragas_evaluator, "llm_model_name", None),
                        "ragas_embedding_model": getattr(ragas_evaluator, "embedding_model_name", None),
                    },
                    status="completed",
                    processing_stage="evaluation",
                    inference_started_at=inference_started_at,
                    inference_completed_at=inference_completed_at,
                    evaluation_started_at=evaluation_started_at,
                    evaluation_completed_at=evaluation_completed_at,
                    inference_duration_ms=int(
                        (inference_completed_at - inference_started_at).total_seconds() * 1000
                    )
                    if (inference_started_at and inference_completed_at)
                    else None,
                    evaluation_duration_ms=int(
                        (evaluation_completed_at - evaluation_started_at).total_seconds() * 1000
                    )
                    if (evaluation_started_at and evaluation_completed_at)
                    else None,
                )
                try:
                    sr.update_duration()
                except Exception:
                    pass
                db.add(sr)

            # 收集结果（返回给调用方/前端）
            evaluation_results.append(
                {
                    "question_id": question_id,
                    "clinical_query": clinical_query,
                    "rag_answer": answer_text,
                    "ground_truth": ground_truth,
                    "ragas_scores": ragas_scores,
                    "contexts": contexts,
                }
            )

            completed_cases += 1

            # 更新任务进度
            if db and task_id:
                task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
                if task:
                    task.completed_scenarios = completed_cases
                    task.failed_scenarios = failed_cases
                    task.progress_percentage = int(((completed_cases + failed_cases) / max(total_cases, 1)) * 100)
                    db.commit()

            # 避免外部API限流
            await asyncio.sleep(1.0)

        except Exception as e:
            logger.error(f"处理测试用例失败: {e}")
            failed_cases += 1
            # 更新任务进度（失败也计入）
            if db and task_id:
                task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
                if task:
                    task.completed_scenarios = completed_cases
                    task.failed_scenarios = failed_cases
                    task.progress_percentage = int(((completed_cases + failed_cases) / max(total_cases, 1)) * 100)
                    db.commit()
            continue

    # 汇总统计
    summary = None
    if evaluation_results:
        scores = [r.get("ragas_scores", {}) for r in evaluation_results]
        try:
            summary = {
                "faithfulness": sum(s.get("faithfulness", 0.0) for s in scores) / len(scores),
                "answer_relevancy": sum(s.get("answer_relevancy", 0.0) for s in scores) / len(scores),
                "context_precision": sum(s.get("context_precision", 0.0) for s in scores) / len(scores),
                "context_recall": sum(s.get("context_recall", 0.0) for s in scores) / len(scores),
            }
        except Exception:
            summary = None

        # 写回任务聚合与指标历史
        if db and task_id:
            task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
            if task and summary:
                task.avg_faithfulness = summary.get("faithfulness")
                task.avg_answer_relevancy = summary.get("answer_relevancy")
                task.avg_context_precision = summary.get("context_precision")
                task.avg_context_recall = summary.get("context_recall")
                try:
                    task.avg_overall_score = (
                        (task.avg_faithfulness or 0)
                        + (task.avg_answer_relevancy or 0)
                        + (task.avg_context_precision or 0)
                        + (task.avg_context_recall or 0)
                    ) / 4.0
                except Exception:
                    task.avg_overall_score = None
                task.completed_scenarios = completed_cases
                task.failed_scenarios = failed_cases
                task.progress_percentage = 100
                task.completed_at = datetime.now()
                task.status = TaskStatus.COMPLETED if failed_cases < total_cases else TaskStatus.FAILED
                db.commit()

                # 指标历史记录
                try:
                    sample_size = len(evaluation_results)
                    for name, value in summary.items():
                        db.add(
                            EvaluationMetrics(
                                task_id=task_id,
                                metric_name=name,
                                metric_value=value,
                                metric_category="ragas",
                                calculation_method="mean",
                                sample_size=sample_size,
                            )
                        )
                    db.commit()
                except Exception as e:
                    logger.warning(f"保存指标历史失败: {e}")

    return {
        "status": "success",
        "results": evaluation_results,
        "summary": summary,
        "total_cases": total_cases,
        "completed_cases": completed_cases,
        "failed_cases": failed_cases,
    }
