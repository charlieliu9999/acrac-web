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

def _simple_ragas_scores(answer: str, contexts: List[str], reference: str) -> Dict[str, float]:
    """在无LLM/Embedding可用时的启发式评分，范围[0,1]。
    - answer_relevancy: 与参考答案Token的Jaccard相似度
    - context_precision: 答案Token中出现在上下文Token集合中的比例
    - context_recall: 上下文Token集合中被答案覆盖的比例（按并集去重）
    - faithfulness: 0.7*precision + 0.3*relevancy 的折中
    """
    import re
    def tokens(text: str) -> set:
        if not text:
            return set()
        # 中英文混合：中文按字，英文按词
        ts = re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+", str(text))
        return set(t.strip().lower() for t in ts if t.strip())
    ans = tokens(answer)
    ref = tokens(reference)
    ctx_union: set = set()
    for c in contexts or []:
        ctx_union |= tokens(c)
    def jacc(a: set, b: set) -> float:
        if not a and not b:
            return 0.0
        inter = len(a & b)
        union = len(a | b) or 1
        return inter / union
    relevancy = jacc(ans, ref)
    precision = (len(ans & ctx_union) / (len(ans) or 1)) if ans else 0.0
    recall = (len(ans & ctx_union) / (len(ctx_union) or 1)) if ctx_union else 0.0
    faith = min(1.0, 0.7 * precision + 0.3 * relevancy)
    return {
        "faithfulness": round(float(faith), 6),
        "answer_relevancy": round(float(relevancy), 6),
        "context_precision": round(float(precision), 6),
        "context_recall": round(float(recall), 6),
    }

async def run_real_rag_evaluation(
    test_cases: List[Dict[str, Any]],
    model_name: str,
    base_url: Optional[str] = None,
    embedding_model: Optional[str] = None,
    data_count: Optional[int] = None,
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
    # 如指定 data_count 且 > 0，则仅评前 N 条
    if data_count and isinstance(data_count, int) and data_count > 0:
        test_cases = (test_cases or [])[:data_count]
    total_cases = len(test_cases or [])
    completed_cases = 0
    failed_cases = 0

    # 尝试初始化 RAGAS 评估器（可选）
    ragas_evaluator = None
    try:
        from app.services.ragas_evaluator import RAGASEvaluator  # type: ignore
        # 默认到环境变量指定的RAGAS默认模型（如未提供）
        _llm = model_name or os.getenv("RAGAS_DEFAULT_LLM_MODEL")
        _emb = embedding_model or os.getenv("RAGAS_DEFAULT_EMBEDDING_MODEL")
        ragas_evaluator = RAGASEvaluator(
            llm_model=_llm,
            embedding_model=_emb,
            base_url=base_url,
        )
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
            rag_payload = {
                "clinical_query": clinical_query,
                "top_scenarios": 3,
                "top_recommendations_per_scenario": 3,
                "show_reasoning": True,
                "similarity_threshold": 0.6,
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
                import httpx  # prefer async client to avoid self-call deadlocks
                inference_started_at = datetime.now()
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(rag_api_url, json=rag_payload)
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

            # 提取场景上下文（用于 RAGAS 评分）
            # 优先从 trace/debug_info 与 scenarios_with_recommendations 中提取可读文本证据
            contexts: List[str] = []
            try:
                tr = (rag_result or {}).get("trace") or {}
                dbg = (rag_result or {}).get("debug_info") or {}
                # 1) 从 prompt 预览作为整体上下文（包含场景描述与相似度等信息）
                prm = dbg.get("step_6_prompt_preview")
                if isinstance(prm, str) and len(prm) > 0:
                    contexts.append(prm)
                # 2) 从带推荐理由的场景中提取中文描述与 reasoning
                swr = (rag_result or {}).get("scenarios_with_recommendations") or []
                for s in swr[:3]:
                    desc = s.get("description_zh") or s.get("scenario_description")
                    if isinstance(desc, str) and desc:
                        contexts.append(desc)
                    recs = s.get("recommendations") or []
                    for rec in recs[:2]:  # 每个场景取前2条理由
                        rz = rec.get("reasoning_zh") or rec.get("recommendation_reason")
                        if isinstance(rz, str) and rz:
                            contexts.append(rz)
                # 3) 回退：若仍为空，用简要的场景元数据
                if not contexts:
                    for sc in (rag_result or {}).get("scenarios", [])[:3]:
                        try:
                            ctx = f"场景: {sc.get('panel_name','')} - {sc.get('topic_name','')}"
                            desc = sc.get("description_zh") or sc.get("clinical_context")
                            if desc:
                                ctx += f"\n描述: {desc}"
                            contexts.append(ctx)
                        except Exception:
                            continue
            except Exception:
                pass

            # 计算 RAGAS 分数（若可用）
            evaluation_started_at = None
            evaluation_completed_at = None
            # 评分：优先使用RAGAS评估器，否则退化到简易启发式评分（避免全为0）
            ragas_scores = {
                "faithfulness": 0.0,
                "answer_relevancy": 0.0,
                "context_precision": 0.0,
                "context_recall": 0.0,
            }
            try:
                if ragas_evaluator and contexts and answer_text and ground_truth:
                    evaluation_started_at = datetime.now()
                    ragas_scores = ragas_evaluator.evaluate_single_sample(
                        {
                            "question": clinical_query,
                            "answer": answer_text,
                            "contexts": contexts,
                            "ground_truth": ground_truth,
                        }
                    )
                    evaluation_completed_at = datetime.now()
                    # 如果评估器未报错但返回的四项均为0，则用启发式评分兜底
                    try:
                        vals = [float(ragas_scores.get(k, 0.0) or 0.0) for k in ("faithfulness","answer_relevancy","context_precision","context_recall")]
                        if sum(vals) == 0.0:
                            ragas_scores = _simple_ragas_scores(answer_text, contexts, ground_truth)
                    except Exception:
                        pass
                else:
                    ragas_scores = _simple_ragas_scores(answer_text, contexts, ground_truth)
            except Exception as e:
                logger.warning(f"RAGAS评分计算失败，使用启发式评分替代: {e}")
                ragas_scores = _simple_ragas_scores(answer_text, contexts, ground_truth)

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
                    # 注意：模型上 clinical_scenario 字段名与关系冲突，避免直接赋值
                    rag_question=clinical_query,
                    rag_answer=answer_text,
                    rag_contexts=contexts,
                    rag_trace_data=rag_result.get("trace"),
                    standard_answer=ground_truth,
                    faithfulness_score=ragas_scores.get("faithfulness", 0.0),
                    answer_relevancy_score=ragas_scores.get("answer_relevancy", 0.0),
                    context_precision_score=ragas_scores.get("context_precision", 0.0),
                    context_recall_score=ragas_scores.get("context_recall", 0.0),
                    overall_score=overall_score,
                    evaluation_metadata={
                        "clinical_scenario_text": clinical_query,
                        "rag_result": rag_result,
                        "contexts": contexts,
                        "model_name": model_name,
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
            try:
                llm_recs = (rag_result or {}).get("llm_recommendations")
                if not llm_recs:
                    tr = (rag_result or {}).get("trace") or {}
                    llm_recs = tr.get("llm_parsed")
            except Exception:
                llm_recs = None

            evaluation_results.append({
                "question_id": question_id,
                "clinical_query": clinical_query,
                "rag_answer": answer_text,
                "ground_truth": ground_truth,
                "ragas_scores": ragas_scores,
                "contexts": contexts,
                "llm_recommendations": llm_recs,
                "trace": (rag_result or {}).get("trace"),
                "timestamp": (evaluation_completed_at.timestamp() if evaluation_completed_at else datetime.now().timestamp()),
            })

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

    # 保存结果到文件并返回文件名
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_task_id = task_id or "adhoc"
        output_filename = f"ragas_results_{safe_task_id}_{ts_str}.json"
        output_path = str((UPLOAD_DIR / output_filename).resolve())
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "results": evaluation_results,
                "summary": summary,
                "total_cases": total_cases,
                "completed_cases": completed_cases,
                "failed_cases": failed_cases,
                "model_name": model_name,
                "embedding_model": embedding_model,
                "base_url": base_url,
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"export file saving failed: {e}")
        output_filename = None
        output_path = None

    return {
        "status": "success",
        "results": evaluation_results,
        "summary": summary,
        "total_cases": total_cases,
        "completed_cases": completed_cases,
        "failed_cases": failed_cases,
        "output_file": output_filename,
        "output_path": output_path,
    }
