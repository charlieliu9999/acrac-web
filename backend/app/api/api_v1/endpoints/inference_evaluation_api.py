from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.database import SessionLocal
from app.models.system_models import InferenceLog, ExcelEvaluationData, EvaluationProject

router = APIRouter()

# Pydantic Models
class RAGASDataItem(BaseModel):
    """RAGAS评测数据项"""
    question: str = Field(..., description="问题")
    answer: str = Field(..., description="模型回答")
    contexts: List[str] = Field(..., description="上下文列表")
    ground_truth: str = Field(..., description="标准答案")

class InferenceToRAGASRequest(BaseModel):
    """推理记录转RAGAS格式请求"""
    project_id: str = Field(..., description="项目ID")
    inference_log_ids: List[int] = Field(..., description="推理记录ID列表")

class RAGASDataPreview(BaseModel):
    """RAGAS数据预览"""
    total_items: int
    preview_items: List[RAGASDataItem]
    conversion_summary: Dict[str, Any]

class RAGASEvaluationRequest(BaseModel):
    """RAGAS评测请求"""
    project_id: str = Field(..., description="项目ID")
    ragas_data: List[RAGASDataItem] = Field(..., description="RAGAS评测数据")
    evaluation_config: Optional[Dict[str, Any]] = Field(None, description="评测配置")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def extract_contexts_from_result(result: Dict[str, Any]) -> List[str]:
    """从推理结果中提取上下文信息"""
    contexts = []
    
    # 尝试从不同的字段中提取上下文
    if isinstance(result, dict):
        # 检查常见的上下文字段
        context_fields = ['contexts', 'context', 'retrieved_docs', 'documents', 'sources']
        for field in context_fields:
            if field in result:
                context_data = result[field]
                if isinstance(context_data, list):
                    for item in context_data:
                        if isinstance(item, str):
                            contexts.append(item)
                        elif isinstance(item, dict) and 'content' in item:
                            contexts.append(item['content'])
                        elif isinstance(item, dict) and 'text' in item:
                            contexts.append(item['text'])
                elif isinstance(context_data, str):
                    contexts.append(context_data)
                break
        
        # 如果没有找到上下文，尝试从其他字段提取
        if not contexts:
            if 'answer' in result and isinstance(result['answer'], dict):
                answer_data = result['answer']
                if 'sources' in answer_data:
                    sources = answer_data['sources']
                    if isinstance(sources, list):
                        contexts.extend([str(s) for s in sources])
    
    # 如果仍然没有上下文，返回默认值
    if not contexts:
        contexts = ["No context available"]
    
    return contexts

def extract_answer_from_result(result: Dict[str, Any]) -> str:
    """从推理结果中提取答案"""
    if isinstance(result, dict):
        # 检查常见的答案字段
        answer_fields = ['answer', 'response', 'output', 'result', 'text']
        for field in answer_fields:
            if field in result:
                answer_data = result[field]
                if isinstance(answer_data, str):
                    return answer_data
                elif isinstance(answer_data, dict) and 'content' in answer_data:
                    return answer_data['content']
                elif isinstance(answer_data, dict) and 'text' in answer_data:
                    return answer_data['text']
    
    # 如果没有找到答案，返回整个结果的字符串表示
    return str(result)

@router.post('/inference-to-ragas/preview', summary='预览推理记录转RAGAS格式', response_model=RAGASDataPreview)
async def preview_inference_to_ragas(
    request: InferenceToRAGASRequest,
    db: Session = Depends(get_db)
):
    """将推理记录转换为RAGAS评测格式并预览"""
    try:
        # 验证项目是否存在
        project = db.query(EvaluationProject).filter(
            EvaluationProject.project_id == request.project_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail='项目不存在')
        
        # 获取推理记录
        inference_logs = db.query(InferenceLog).filter(
            InferenceLog.id.in_(request.inference_log_ids),
            InferenceLog.project_id == request.project_id
        ).all()
        
        if not inference_logs:
            raise HTTPException(status_code=404, detail='未找到指定的推理记录')
        
        # 获取对应的Excel评测数据（用于获取ground_truth）
        excel_data_map = {}
        excel_data_list = db.query(ExcelEvaluationData).filter(
            ExcelEvaluationData.project_id == request.project_id
        ).all()
        
        for data in excel_data_list:
            excel_data_map[data.question] = data.ground_truth
        
        # 转换数据格式
        ragas_items = []
        conversion_issues = []
        
        for log in inference_logs:
            try:
                # 提取答案和上下文
                answer = extract_answer_from_result(log.result)
                contexts = extract_contexts_from_result(log.result)
                
                # 查找对应的ground_truth
                ground_truth = excel_data_map.get(log.query_text, "")
                if not ground_truth:
                    # 尝试模糊匹配
                    for question, gt in excel_data_map.items():
                        if log.query_text.strip() in question or question in log.query_text.strip():
                            ground_truth = gt
                            break
                
                if not ground_truth:
                    conversion_issues.append(f"推理记录ID {log.id}: 未找到对应的标准答案")
                    ground_truth = "未找到标准答案"
                
                ragas_item = RAGASDataItem(
                    question=log.query_text,
                    answer=answer,
                    contexts=contexts,
                    ground_truth=ground_truth
                )
                ragas_items.append(ragas_item)
                
            except Exception as e:
                conversion_issues.append(f"推理记录ID {log.id}: 转换失败 - {str(e)}")
        
        # 生成预览（最多显示5条）
        preview_items = ragas_items[:5]
        
        conversion_summary = {
            'total_inference_logs': len(inference_logs),
            'successful_conversions': len(ragas_items),
            'conversion_issues': conversion_issues,
            'has_ground_truth': sum(1 for item in ragas_items if item.ground_truth != "未找到标准答案"),
            'missing_ground_truth': sum(1 for item in ragas_items if item.ground_truth == "未找到标准答案")
        }
        
        return RAGASDataPreview(
            total_items=len(ragas_items),
            preview_items=preview_items,
            conversion_summary=conversion_summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'预览转换失败: {e}')

@router.post('/inference-to-ragas/convert', summary='转换推理记录为RAGAS格式')
async def convert_inference_to_ragas(
    request: InferenceToRAGASRequest,
    db: Session = Depends(get_db)
):
    """将推理记录完整转换为RAGAS评测格式"""
    try:
        # 验证项目是否存在
        project = db.query(EvaluationProject).filter(
            EvaluationProject.project_id == request.project_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail='项目不存在')
        
        # 获取推理记录
        inference_logs = db.query(InferenceLog).filter(
            InferenceLog.id.in_(request.inference_log_ids),
            InferenceLog.project_id == request.project_id
        ).all()
        
        if not inference_logs:
            raise HTTPException(status_code=404, detail='未找到指定的推理记录')
        
        # 获取对应的Excel评测数据
        excel_data_map = {}
        excel_data_list = db.query(ExcelEvaluationData).filter(
            ExcelEvaluationData.project_id == request.project_id
        ).all()
        
        for data in excel_data_list:
            excel_data_map[data.question] = data.ground_truth
        
        # 转换数据格式
        ragas_items = []
        
        for log in inference_logs:
            try:
                answer = extract_answer_from_result(log.result)
                contexts = extract_contexts_from_result(log.result)
                
                # 查找对应的ground_truth
                ground_truth = excel_data_map.get(log.query_text, "")
                if not ground_truth:
                    # 尝试模糊匹配
                    for question, gt in excel_data_map.items():
                        if log.query_text.strip() in question or question in log.query_text.strip():
                            ground_truth = gt
                            break
                
                if not ground_truth:
                    ground_truth = "未找到标准答案"
                
                ragas_item = RAGASDataItem(
                    question=log.query_text,
                    answer=answer,
                    contexts=contexts,
                    ground_truth=ground_truth
                )
                ragas_items.append(ragas_item)
                
            except Exception as e:
                continue  # 跳过转换失败的记录
        
        return {
            'ok': True,
            'total_items': len(ragas_items),
            'ragas_data': [item.dict() for item in ragas_items],
            'message': f'成功转换 {len(ragas_items)} 条记录'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'转换失败: {e}')

@router.get('/projects/{project_id}/inference-logs', summary='获取项目的推理记录')
async def get_project_inference_logs(
    project_id: str,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    success_only: bool = Query(False, description="只显示成功的记录"),
    db: Session = Depends(get_db)
):
    """获取指定项目的推理记录列表"""
    try:
        # 验证项目是否存在
        project = db.query(EvaluationProject).filter(
            EvaluationProject.project_id == project_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail='项目不存在')
        
        # 构建查询
        query = db.query(InferenceLog).filter(InferenceLog.project_id == project_id)
        
        if success_only:
            query = query.filter(InferenceLog.success == True)
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * page_size
        logs = query.order_by(InferenceLog.created_at.desc()).offset(offset).limit(page_size).all()
        
        items = [
            {
                'id': log.id,
                'query_text': log.query_text,
                'inference_method': log.inference_method,
                'success': log.success,
                'error_message': log.error_message,
                'execution_time': log.execution_time,
                'created_at': log.created_at,
                'result_preview': str(log.result)[:200] + '...' if len(str(log.result)) > 200 else str(log.result)
            }
            for log in logs
        ]
        
        return {
            'total': total,
            'items': items,
            'project_info': {
                'project_id': project.project_id,
                'project_name': project.project_name,
                'status': project.status
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取推理记录失败: {e}')