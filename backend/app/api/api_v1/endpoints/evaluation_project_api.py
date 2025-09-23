from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from pydantic import BaseModel, Field

from app.core.database import SessionLocal
from app.models.system_models import EvaluationProject, ExcelEvaluationData, InferenceLog

router = APIRouter()

# Pydantic Models
class EvaluationProjectCreate(BaseModel):
    project_name: str = Field(..., description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    excel_filename: str = Field(..., description="Excel文件名")
    total_questions: int = Field(0, description="总问题数")

class EvaluationProjectResponse(BaseModel):
    id: int
    project_id: str
    project_name: str
    description: Optional[str]
    excel_filename: str
    total_questions: int
    processed_questions: int
    status: str
    created_at: datetime
    updated_at: datetime

class EvaluationProjectList(BaseModel):
    total: int
    items: List[EvaluationProjectResponse]

class ProjectStatusUpdate(BaseModel):
    status: str = Field(..., description="新状态: created, processing, completed, failed")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post('/projects', summary='创建评测项目', response_model=EvaluationProjectResponse)
async def create_evaluation_project(
    payload: EvaluationProjectCreate,
    db: Session = Depends(get_db)
):
    """创建新的评测项目，生成唯一的项目ID"""
    try:
        # 生成唯一的项目ID
        project_id = f"eval_{uuid.uuid4().hex[:12]}"
        
        # 检查项目ID是否已存在（虽然概率很小）
        existing = db.query(EvaluationProject).filter(
            EvaluationProject.project_id == project_id
        ).first()
        if existing:
            project_id = f"eval_{uuid.uuid4().hex[:12]}"
        
        # 创建项目记录
        project = EvaluationProject(
            project_id=project_id,
            project_name=payload.project_name,
            description=payload.description,
            excel_filename=payload.excel_filename,
            total_questions=payload.total_questions,
            status="created"
        )
        
        db.add(project)
        db.commit()
        db.refresh(project)
        
        return EvaluationProjectResponse(
            id=project.id,
            project_id=project.project_id,
            project_name=project.project_name,
            description=project.description,
            excel_filename=project.excel_filename,
            total_questions=project.total_questions,
            processed_questions=project.processed_questions,
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f'创建评测项目失败: {e}')

@router.get('/projects', summary='获取评测项目列表', response_model=EvaluationProjectList)
async def list_evaluation_projects(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[str] = Query(None, description="状态筛选"),
    db: Session = Depends(get_db)
):
    """获取评测项目列表"""
    try:
        query = db.query(EvaluationProject)
        
        # 状态筛选
        if status:
            query = query.filter(EvaluationProject.status == status)
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * page_size
        projects = query.order_by(EvaluationProject.created_at.desc()).offset(offset).limit(page_size).all()
        
        items = [
            EvaluationProjectResponse(
                id=project.id,
                project_id=project.project_id,
                project_name=project.project_name,
                description=project.description,
                excel_filename=project.excel_filename,
                total_questions=project.total_questions,
                processed_questions=project.processed_questions,
                status=project.status,
                created_at=project.created_at,
                updated_at=project.updated_at
            )
            for project in projects
        ]
        
        return EvaluationProjectList(total=total, items=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取项目列表失败: {e}')

@router.get('/projects/{project_id}', summary='获取项目详情', response_model=Dict[str, Any])
async def get_evaluation_project(
    project_id: str,
    db: Session = Depends(get_db)
):
    """获取评测项目详情，包括关联的推理记录和评测数据"""
    try:
        # 获取项目基本信息
        project = db.query(EvaluationProject).filter(
            EvaluationProject.project_id == project_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail='项目不存在')
        
        # 获取关联的推理记录
        inference_logs = db.query(InferenceLog).filter(
            InferenceLog.project_id == project_id
        ).all()
        
        # 获取关联的评测数据
        evaluation_data = db.query(ExcelEvaluationData).filter(
            ExcelEvaluationData.project_id == project_id
        ).all()
        
        return {
            'project': EvaluationProjectResponse(
                id=project.id,
                project_id=project.project_id,
                project_name=project.project_name,
                description=project.description,
                excel_filename=project.excel_filename,
                total_questions=project.total_questions,
                processed_questions=project.processed_questions,
                status=project.status,
                created_at=project.created_at,
                updated_at=project.updated_at
            ),
            'inference_logs_count': len(inference_logs),
            'evaluation_data_count': len(evaluation_data),
            'inference_logs': [
                {
                    'id': log.id,
                    'query_text': log.query_text,
                    'inference_method': log.inference_method,
                    'success': log.success,
                    'created_at': log.created_at
                }
                for log in inference_logs
            ],
            'evaluation_data': [
                {
                    'id': data.id,
                    'task_id': data.task_id,
                    'question': data.question,
                    'status': data.status,
                    'faithfulness': data.faithfulness,
                    'answer_relevancy': data.answer_relevancy,
                    'context_precision': data.context_precision,
                    'context_recall': data.context_recall,
                    'created_at': data.created_at
                }
                for data in evaluation_data
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取项目详情失败: {e}')

@router.put('/projects/{project_id}/status', summary='更新项目状态')
async def update_project_status(
    project_id: str,
    payload: ProjectStatusUpdate,
    db: Session = Depends(get_db)
):
    """更新项目状态"""
    try:
        project = db.query(EvaluationProject).filter(
            EvaluationProject.project_id == project_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail='项目不存在')
        
        project.status = payload.status
        db.commit()
        
        return {'ok': True, 'message': '状态更新成功'}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f'更新项目状态失败: {e}')

@router.delete('/projects/{project_id}', summary='删除评测项目')
async def delete_evaluation_project(
    project_id: str,
    db: Session = Depends(get_db)
):
    """删除评测项目及其关联数据"""
    try:
        # 检查项目是否存在
        project = db.query(EvaluationProject).filter(
            EvaluationProject.project_id == project_id
        ).first()
        
        if not project:
            raise HTTPException(status_code=404, detail='项目不存在')
        
        # 删除关联的评测数据
        db.query(ExcelEvaluationData).filter(
            ExcelEvaluationData.project_id == project_id
        ).delete()
        
        # 删除关联的推理记录
        db.query(InferenceLog).filter(
            InferenceLog.project_id == project_id
        ).delete()
        
        # 删除项目
        db.delete(project)
        db.commit()
        
        return {'ok': True, 'message': '项目删除成功'}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f'删除项目失败: {e}')