from celery import current_task
from app.celery_app import celery_app
from typing import Dict, List, Any
import json
import logging
import asyncio
import time as _time
from datetime import datetime

from app.core.database import SessionLocal
from app.models.ragas_models import EvaluationTask
from app.schemas.ragas_schemas import TaskStatus
from app.services.ragas_service import run_real_rag_evaluation

logger = logging.getLogger(__name__)

@celery_app.task(bind=True)
def process_rag_llm_inference(self, scenario_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行RAG-LLM推理任务
    
    Args:
        scenario_data: 包含临床场景信息的字典
        
    Returns:
        推理结果字典
    """
    try:
        # 更新任务状态
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 1, 'status': '开始RAG-LLM推理...'}
        )
        
        # TODO: 实现RAG-LLM推理逻辑
        # 这里将调用现有的RAG-LLM服务
        
        logger.info(f"开始处理场景: {scenario_data.get('scenario_id')}")
        
        # 模拟推理过程（后续将替换为实际实现）
        result = {
            'scenario_id': scenario_data.get('scenario_id'),
            'question': scenario_data.get('question'),
            'answer': 'RAG-LLM推理结果',
            'contexts': ['上下文1', '上下文2'],
            'trace_data': {'retrieval': [], 'rerank': [], 'llm_response': {}}
        }
        
        self.update_state(
            state='SUCCESS',
            meta={'current': 1, 'total': 1, 'status': 'RAG-LLM推理完成'}
        )
        
        return result
        
    except Exception as exc:
        logger.error(f"RAG-LLM推理失败: {str(exc)}")
        self.update_state(
            state='FAILURE',
            meta={'current': 0, 'total': 1, 'status': f'推理失败: {str(exc)}'}
        )
        raise



@celery_app.task(bind=True)
def parse_inference_data(self, inference_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    解析RAG-LLM推理结果，转换为RAGAS标准格式
    
    Args:
        inference_result: RAG-LLM推理结果
        
    Returns:
        RAGAS标准格式的数据
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 1, 'status': '开始数据解析...'}
        )
        
        # 检查输入参数
        if not inference_result:
            raise ValueError("inference_result不能为空")
        
        # TODO: 实现数据适配器逻辑
        # 将RAG-LLM输出转换为RAGAS标准格式
        
        ragas_data = {
            'question': inference_result.get('question', ''),
            'answer': inference_result.get('answer', ''),
            'contexts': inference_result.get('contexts', []),
            'ground_truth': inference_result.get('ground_truth', '')
        }
        
        self.update_state(
            state='SUCCESS',
            meta={'current': 1, 'total': 1, 'status': '数据解析完成'}
        )
        
        return ragas_data
        
    except Exception as exc:
        logger.error(f"数据解析失败: {str(exc)}")
        self.update_state(
            state='FAILURE',
            meta={'current': 0, 'total': 1, 'status': f'解析失败: {str(exc)}'}
        )
        raise

@celery_app.task(bind=True)
def execute_ragas_evaluation(self, ragas_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    执行RAGAS评估
    
    Args:
        ragas_data: RAGAS标准格式的评估数据
        
    Returns:
        RAGAS评估结果
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': 1, 'status': '开始RAGAS评估...'}
        )
        
        # 检查输入参数
        if not ragas_data:
            raise ValueError("ragas_data不能为空")
        
        # TODO: 实现RAGAS评估逻辑
        # 调用RAGAS库进行评估
        
        evaluation_result = {
            'scenario_id': ragas_data.get('scenario_id', 'unknown'),
            'faithfulness': 0.85,
            'answer_relevancy': 0.90,
            'context_precision': 0.88,
            'context_recall': 0.82,
            'overall_score': 0.86
        }
        
        self.update_state(
            state='SUCCESS',
            meta={'current': 1, 'total': 1, 'status': 'RAGAS评估完成'}
        )
        
        return evaluation_result
        
    except Exception as exc:
        logger.error(f"RAGAS评估失败: {str(exc)}")
        self.update_state(
            state='FAILURE',
            meta={'current': 0, 'total': 1, 'status': f'评估失败: {str(exc)}'}
        )
        raise

@celery_app.task(bind=True)
def process_batch_evaluation(self, task_id: str, scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    批量处理RAGAS评估任务（真实流水线）

    Args:
        task_id: 评估任务ID
        scenarios: 场景列表（每项包含question_id/clinical_query/ground_truth等字段）

    Returns:
        批量评估结果（包含真实RAG-LLM调用与RAGAS评分）
    """
    try:
        total_scenarios = len(scenarios) if scenarios else 0

        # 标记任务开始，读取配置
        db = SessionLocal()
        try:
            task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
            if not task:
                raise ValueError(f"任务不存在: {task_id}")

            model_name = None
            base_url = None
            embedding_model = None
            data_count = None
            if task.evaluation_config and isinstance(task.evaluation_config, dict):
                model_name = task.evaluation_config.get("model_name")
                base_url = task.evaluation_config.get("base_url")
                embedding_model = task.evaluation_config.get("embedding_model")
                data_count = task.evaluation_config.get("data_count")

            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.now()
            task.progress_percentage = 0.0
            db.commit()

            # 统一构造测试用例
            test_cases = []
            for i, s in enumerate(scenarios or []):
                test_cases.append({
                    "question_id": s.get("question_id") or s.get("scenario_id") or f"case_{i+1}",
                    "question": s.get("clinical_query") or s.get("question") or s.get("clinical_scenario") or "",
                    "ground_truth": s.get("ground_truth") or s.get("standard_answer") or "",
                    "metadata": s.get("metadata") or {}
                })
            # 按 data_count 限制数量（>0 生效）
            if data_count and isinstance(data_count, int) and data_count > 0:
                test_cases = test_cases[:data_count]

            start_ts = _time.time()

            result = asyncio.run(run_real_rag_evaluation(
                test_cases=test_cases,
                model_name=model_name or "unknown",
                base_url=base_url,
                embedding_model=embedding_model,
                data_count=data_count,
                task_id=task_id,
                db=db
            ))

            duration = _time.time() - start_ts

            task.status = TaskStatus.COMPLETED if result.get("status") == "success" else TaskStatus.FAILED
            task.completed_scenarios = result.get("completed_cases", 0)
            task.failed_scenarios = result.get("failed_cases", 0)
            task.progress_percentage = 100.0
            task.completed_at = datetime.now()
            # removed: task.processing_time (no such ORM field)
            if result.get("status") != "success":
                task.error_message = result.get("error")
            # 若有平均分统计则写入
            summary = result.get("summary") or {}
            if summary:
                task.avg_faithfulness = summary.get("faithfulness")
                task.avg_answer_relevancy = summary.get("answer_relevancy")
                task.avg_context_precision = summary.get("context_precision")
                task.avg_context_recall = summary.get("context_recall")
                try:
                    task.avg_overall_score = (
                        (task.avg_faithfulness or 0) +
                        (task.avg_answer_relevancy or 0) +
                        (task.avg_context_precision or 0) +
                        (task.avg_context_recall or 0)
                    ) / 4.0
                except Exception:
                    task.avg_overall_score = None

            db.commit()

            final_result = {
                "task_id": task_id,
                "total_scenarios": total_scenarios,
                "completed_scenarios": result.get("completed_cases", 0),
                "individual_results": result.get("results", []),
                "summary_statistics": result.get("summary"),
                "status": result.get("status"),
                "export_file": result.get("output_file"),
                "export_path": result.get("output_path"),
            }

            self.update_state(
                state="SUCCESS",
                meta={
                    "current": total_scenarios,
                    "total": total_scenarios,
                    "status": "批量评估完成（真实）"
                }
            )

            return final_result
        finally:
            db.close()

    except Exception as exc:
        logger.error(f"批量评估失败: {str(exc)}")
        try:
            db2 = SessionLocal()
            try:
                task = db2.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
                if task:
                    task.status = TaskStatus.FAILED
                    task.completed_at = datetime.now()
                    task.error_message = str(exc)
                    db2.commit()
            finally:
                db2.close()
        except Exception:
            pass

        self.update_state(
            state="FAILURE",
            meta={
                "current": 0,
                "total": len(scenarios) if scenarios else 0,
                "status": f"批量评估失败: {str(exc)}"
            }
        )
        raise