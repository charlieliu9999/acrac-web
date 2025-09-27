"""RAGAS评测API端点"""
import os
import json
import uuid
import time
import logging
import requests
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, BackgroundTasks, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func, text

from app.core.database import get_db
from app.schemas.ragas_schemas import (
    FileUploadResponse, DataPreprocessRequest, DataPreprocessResponse,
    RAGASEvaluationRequest, RAGASEvaluationResponse, EvaluationResult,
    EvaluationTaskCreate, EvaluationTaskResponse, EvaluationTaskUpdate,
    EvaluationHistoryQuery, EvaluationHistoryResponse, EvaluationStats, MetricsAnalysis, ErrorResponse,
    TestCaseBase, TaskStatus, TaskDetailResponse
)
from app.models.ragas_models import EvaluationTask, ScenarioResult, EvaluationMetrics
from app.services.ragas_service import (
    validate_file, parse_uploaded_file, validate_test_cases, run_real_rag_evaluation as service_run_real_rag_evaluation
)

# 条件性导入 celery 任务，避免在没有 celery 的环境中出错
try:
    from app.tasks.ragas_tasks import process_batch_evaluation
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    process_batch_evaluation = None

# 配置日志
logger = logging.getLogger(__name__)

router = APIRouter()

# 文件上传配置
UPLOAD_DIR = Path("uploads/ragas")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".json", ".csv", ".xlsx", ".txt"}

# ==================== 工具函数 ====================

def validate_file(file: UploadFile) -> None:
    """验证上传文件"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file_ext}。支持的类型: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 检查文件大小（这里只是预检查，实际大小在读取时检查）
    if hasattr(file, 'size') and file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制: {file.size} bytes > {MAX_FILE_SIZE} bytes"
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
                # 单个测试用例
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

            # 检查列名并进行映射
            column_mapping = {
                '题号': 'question_id',
                '临床场景': 'clinical_query',
                '首选检查项目（标准化）': 'ground_truth',
                # 兼容英文列名
                'question_id': 'question_id',
                'clinical_query': 'clinical_query',
                'ground_truth': 'ground_truth',
                'question': 'clinical_query',
                'answer': 'ground_truth'
            }

            # 重命名列
            df_renamed = df.rename(columns=column_mapping)

            for i, row in df_renamed.iterrows():
                # 获取映射后的值
                question_id = row.get('question_id', f"q_{i+1}")
                clinical_query = row.get('clinical_query', '')
                ground_truth = row.get('ground_truth', '')

                # 确保数据类型正确
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
                    # 简单的文本格式：每行一个问题
                    test_case = TestCaseBase(
                        question_id=f"q_{i+1}",
                        clinical_query=line,
                        ground_truth="",  # 文本文件通常只有问题
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

# ==================== API端点 ====================

@router.post("/data/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    description: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """上传测试数据文件并解析保存到数据库"""
    try:
        # 验证文件
        validate_file(file)

        # 生成唯一文件ID和路径
        file_id = str(uuid.uuid4())
        file_ext = Path(file.filename).suffix.lower()
        file_path = UPLOAD_DIR / f"{file_id}{file_ext}"

        # 读取并保存文件
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"文件大小超过限制: {len(content)} bytes > {MAX_FILE_SIZE} bytes"
            )

        with open(file_path, 'wb') as f:
            f.write(content)

        logger.info(f"文件上传成功: {file.filename} -> {file_path}")

        # 解析文件并保存到数据库
        from app.models.clinical_data_models import ClinicalScenarioData, DataUploadBatch

        # 生成简化的上传批次ID (10字符)
        import random
        timestamp_suffix = str(int(time.time()))[-4:]  # 取时间戳后4位
        random_suffix = ''.join(random.choices('0123456789ABCDEF', k=6))  # 6位随机字符
        upload_batch_id = f"{timestamp_suffix}{random_suffix}"

        try:
            # 解析文件数据
            test_cases = parse_uploaded_file(file_path, file_ext)
            valid_cases, errors = validate_test_cases(test_cases)

            # 创建上传批次记录
            upload_batch = DataUploadBatch(
                batch_id=upload_batch_id,
                batch_name=f"Upload_{file.filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                description=description or f"Uploaded from {file.filename}",
                original_filename=file.filename,
                file_path=str(file_path),
                file_size=len(content),
                total_rows=len(test_cases),
                valid_rows=len(valid_cases),
                invalid_rows=len(test_cases) - len(valid_cases),
                status="processing"
            )
            db.add(upload_batch)

            # 保存临床场景数据到数据库
            saved_scenarios = []
            for i, case in enumerate(valid_cases):
                scenario_data = ClinicalScenarioData(
                    question_id=case.question_id,
                    clinical_query=case.clinical_query,
                    ground_truth=case.ground_truth,
                    source_file=file.filename,
                    file_row_number=i + 1,
                    upload_batch_id=upload_batch_id,
                    is_active=True,
                    is_validated=False
                )
                db.add(scenario_data)
                saved_scenarios.append(scenario_data)

            # 更新批次状态
            upload_batch.status = "completed"
            upload_batch.processed_at = datetime.now()

            db.commit()

            logger.info(f"数据保存成功: 总记录{len(test_cases)}, 有效记录{len(valid_cases)}, 批次ID: {upload_batch_id}")

            return FileUploadResponse(
                file_id=file_id,
                file_name=file.filename,
                file_path=str(file_path),
                file_size=len(content),
                upload_time=datetime.now(),
                status="completed",
                batch_id=upload_batch_id,
                total_records=len(test_cases),
                valid_records=len(valid_cases),
                preview_data=valid_cases[:5] if valid_cases else []  # 返回前5条数据预览
            )

        except Exception as parse_error:
            # 解析失败，回滚事务
            db.rollback()
            logger.error(f"文件解析失败: {parse_error}")
            raise HTTPException(status_code=400, detail=f"文件解析失败: {str(parse_error)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

@router.post("/data/preprocess", response_model=DataPreprocessResponse)
async def preprocess_data(request: DataPreprocessRequest):
    """预处理上传的数据文件"""
    try:
        start_time = time.time()

        # 查找文件
        file_pattern = UPLOAD_DIR / f"{request.file_id}.*"
        matching_files = list(UPLOAD_DIR.glob(f"{request.file_id}.*"))

        if not matching_files:
            raise HTTPException(status_code=404, detail=f"文件未找到: {request.file_id}")

        file_path = matching_files[0]
        file_type = file_path.suffix.lower()

        # 解析文件
        logger.info(f"开始解析文件: {file_path}")
        test_cases = parse_uploaded_file(file_path, file_type)

        # 验证测试用例
        valid_cases, errors = validate_test_cases(test_cases)

        if errors:
            logger.warning(f"数据验证出现问题: {errors}")

        processing_time = time.time() - start_time

        logger.info(f"数据预处理完成: 总用例{len(test_cases)}, 有效用例{len(valid_cases)}, 耗时{processing_time:.2f}秒")

        return DataPreprocessResponse(
            file_id=request.file_id,
            processed_data=valid_cases,
            total_cases=len(test_cases),
            valid_cases=len(valid_cases),
            invalid_cases=len(test_cases) - len(valid_cases),
            processing_time=processing_time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"数据预处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据预处理失败: {str(e)}")

@router.get("/data/files")
async def list_uploaded_files():
    """列出已上传的文件"""
    try:
        files = []
        for file_path in UPLOAD_DIR.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "file_id": file_path.stem,
                    "file_name": file_path.name,
                    "file_size": stat.st_size,
                    "upload_time": datetime.fromtimestamp(stat.st_ctime),
                    "file_type": file_path.suffix
                })

        return {"files": files, "total": len(files)}

    except Exception as e:
        logger.error(f"获取文件列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")

@router.get("/data/scenarios")
async def list_clinical_scenarios(
    batch_id: Optional[str] = Query(None, description="批次ID"),
    status: Optional[str] = Query("active", description="数据状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    db: Session = Depends(get_db)
):
    """查询数据库中的临床场景数据"""
    try:
        from app.models.clinical_data_models import ClinicalScenarioData, DataUploadBatch

        # 构建查询条件
        query = db.query(ClinicalScenarioData)

        if batch_id:
            query = query.filter(ClinicalScenarioData.upload_batch_id == batch_id)
        if status == "active":
            query = query.filter(ClinicalScenarioData.is_active == True)
        elif status == "inactive":
            query = query.filter(ClinicalScenarioData.is_active == False)

        # 计算总数
        total = query.count()

        # 分页查询
        scenarios = query.offset((page - 1) * page_size).limit(page_size).all()

        # 转换为响应格式
        scenario_data = []
        for scenario in scenarios:
            scenario_data.append({
                "id": scenario.id,
                "upload_batch_id": scenario.upload_batch_id,
                "question_id": scenario.question_id,
                "clinical_query": scenario.clinical_query,
                "ground_truth": scenario.ground_truth,
                "keywords": scenario.keywords,
                "is_active": scenario.is_active,
                "created_at": scenario.created_at,
                "updated_at": scenario.updated_at
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "scenarios": scenario_data
        }

    except Exception as e:
        logger.error(f"查询临床场景数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询数据失败: {str(e)}")

@router.get("/data/batches")
async def list_upload_batches(
    status: Optional[str] = Query(None, description="批次状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    db: Session = Depends(get_db)
):
    """查询上传批次列表"""
    try:
        from app.models.clinical_data_models import DataUploadBatch

        # 构建查询条件
        query = db.query(DataUploadBatch)

        if status:
            query = query.filter(DataUploadBatch.status == status)

        # 按创建时间倒序排列
        query = query.order_by(desc(DataUploadBatch.created_at))

        # 计算总数
        total = query.count()

        # 分页查询
        batches = query.offset((page - 1) * page_size).limit(page_size).all()

        # 转换为响应格式
        batch_data = []
        for batch in batches:
            batch_data.append({
                "id": batch.id,
                "batch_id": batch.batch_id,
                "file_name": batch.file_name,
                "description": batch.description,
                "total_records": batch.total_records,
                "valid_records": batch.valid_records,
                "invalid_records": batch.invalid_records,
                "status": batch.status,
                "error_details": batch.error_details,
                "created_at": batch.created_at,
                "updated_at": batch.updated_at
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "batches": batch_data
        }

    except Exception as e:
        logger.error(f"查询上传批次失败: {e}")
        raise HTTPException(status_code=500, detail=f"查询批次失败: {str(e)}")

@router.delete("/data/files/{file_id}")
async def delete_uploaded_file(file_id: str):
    """删除上传的文件"""
    try:
        matching_files = list(UPLOAD_DIR.glob(f"{file_id}.*"))

        if not matching_files:
            raise HTTPException(status_code=404, detail=f"文件未找到: {file_id}")

        for file_path in matching_files:
            file_path.unlink()
            logger.info(f"文件已删除: {file_path}")

        return {"message": f"文件已删除: {file_id}", "deleted_files": len(matching_files)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")

# ==================== 评测相关端点 ====================

@router.post("/evaluate", response_model=RAGASEvaluationResponse)
async def start_evaluation(
    request: RAGASEvaluationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """启动RAGAS评测任务 - 从数据库选择数据进行评测"""
    try:
        # 验证输入参数
        try:
            request.validate_input()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # 获取测试用例
        test_cases = []

        if request.test_cases:
            # 直接使用提供的测试用例
            test_cases = request.test_cases
        elif hasattr(request, 'scenario_ids') and request.scenario_ids:
            # 从数据库根据ID选择临床场景数据
            from app.models.clinical_data_models import ClinicalScenarioData

            scenarios = db.query(ClinicalScenarioData).filter(
                ClinicalScenarioData.id.in_(request.scenario_ids),
                ClinicalScenarioData.is_active == True
            ).all()

            if not scenarios:
                raise HTTPException(status_code=404, detail="未找到指定的临床场景数据")

            # 转换为测试用例格式
            for scenario in scenarios:
                test_case = TestCaseBase(
                    question_id=str(scenario.question_id or scenario.id),
                    clinical_query=scenario.clinical_query,
                    ground_truth=scenario.ground_truth,
                    metadata={"keywords": scenario.keywords} if scenario.keywords else {}
                )
                test_cases.append(test_case)

        elif hasattr(request, 'batch_id') and request.batch_id:
            # 从数据库根据批次ID选择所有数据
            from app.models.clinical_data_models import ClinicalScenarioData

            scenarios = db.query(ClinicalScenarioData).filter(
                ClinicalScenarioData.upload_batch_id == request.batch_id,
                ClinicalScenarioData.is_active == True
            ).all()

            if not scenarios:
                raise HTTPException(status_code=404, detail=f"批次 {request.batch_id} 中未找到有效的临床场景数据")

            # 转换为测试用例格式
            for scenario in scenarios:
                test_case = TestCaseBase(
                    question_id=str(scenario.question_id or scenario.id),
                    clinical_query=scenario.clinical_query,
                    ground_truth=scenario.ground_truth,
                    metadata={"keywords": scenario.keywords} if scenario.keywords else {}
                )
                test_cases.append(test_case)

        elif request.file_id:
            # 兼容旧的文件上传方式
            # 查找上传的文件
            matching_files = list(UPLOAD_DIR.glob(f"{request.file_id}.*"))

            if not matching_files:
                raise HTTPException(status_code=404, detail=f"文件未找到: {request.file_id}")

            file_path = matching_files[0]  # 取第一个匹配的文件

            # 使用统一的文件解析函数
            try:
                file_type = file_path.suffix.lower()
                test_cases = parse_uploaded_file(file_path, file_type)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"文件格式错误: {str(e)}")
        else:
            raise HTTPException(status_code=400, detail="必须提供test_cases、scenario_ids、batch_id或file_id中的一个")

        # 验证测试用例
        if not test_cases:
            raise HTTPException(status_code=400, detail="测试用例不能为空")

        valid_cases, errors = validate_test_cases(test_cases)
        if not valid_cases:
            raise HTTPException(status_code=400, detail=f"没有有效的测试用例: {errors}")

        # 依赖的RAG-LLM服务健康检查，避免长时间排队失败
        rag_api_url_env = os.getenv("RAG_API_URL", "http://127.0.0.1:8002/api/v1/acrac/rag-llm/intelligent-recommendation")
        try:
            health_url = rag_api_url_env.replace("/intelligent-recommendation", "/rag-llm-status")
            resp = requests.get(health_url, timeout=10)
            if resp.status_code != 200:
                logger.warning(f"RAG-LLM服务健康检查警告: {resp.status_code}, 但继续执行评测")
        except Exception as e:
            logger.warning(f"RAG-LLM服务健康检查失败: {str(e)}, 但继续执行评测")

        # 创建评测任务
        task_id = str(uuid.uuid4())

        # 准备评测配置（不再写死 model_name，实际使用模型以运行期 RAGASEvaluator 为准）
        eval_config = request.evaluation_config or {}
        if request.base_url:
            eval_config['base_url'] = request.base_url
        eval_config['mode'] = 'online-evaluate'

        # 保存任务到数据库（描述不包含模型名，避免与真实使用模型不一致）
        task_name = request.task_name or f"RAGAS评测_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        db_task = EvaluationTask(
            task_id=task_id,
            task_name=task_name,
            description=f"评测{len(valid_cases)}个测试用例",
            total_scenarios=len(valid_cases),
            status=TaskStatus.PENDING,
            evaluation_config=eval_config,
            started_at=datetime.now()
        )

        db.add(db_task)
        db.commit()
        db.refresh(db_task)

        if request.async_mode and CELERY_AVAILABLE:
            # 异步执行评测
            task = process_batch_evaluation.delay(
                task_id=task_id,
                scenarios=[case.dict() for case in valid_cases]
            )

            logger.info(f"异步评测任务已启动: {task_id}")

            return RAGASEvaluationResponse(
                status="started",
                task_id=task_id,
                results=None,
                summary=None,
                processing_time=None
            )
        elif request.async_mode and not CELERY_AVAILABLE:
            # Celery不可用时，记录警告并转为同步模式
            logger.warning("Celery不可用，异步评测请求将转为同步执行")
            # 继续执行同步模式
        else:
            # 同步执行评测（不推荐用于大量数据）
            start_time = time.time()
            result = await service_run_real_rag_evaluation(
                test_cases=[case.dict() for case in valid_cases],
                model_name=request.model_name,
                base_url=getattr(request, 'base_url', None),
                task_id=task_id,
                db=db
            )
            processing_time = time.time() - start_time

            # 更新任务状态（对齐ORM字段）
            db_task.status = TaskStatus.COMPLETED if result["status"] == "success" else TaskStatus.FAILED
            db_task.completed_at = datetime.now()
            db_task.progress_percentage = 100
            db_task.completed_scenarios = result.get("completed_cases", 0)
            db_task.failed_scenarios = result.get("failed_cases", 0)
            if result["status"] == "error":
                db_task.error_message = result.get("error", "未知错误")

            db.commit()

            logger.info(f"同步评测任务完成: {task_id}, 耗时: {processing_time:.2f}秒")

            return RAGASEvaluationResponse(
                status=result["status"],
                task_id=task_id,
                results=result.get("results"),
                summary=result.get("summary"),
                processing_time=processing_time,
                error=result.get("error")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动评测任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动评测任务失败: {str(e)}")

@router.get("/evaluate/{task_id}/status")
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """获取评测任务状态（含中间过程与最近结果）"""
    try:
        task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail=f"任务未找到: {task_id}")

        # 统计信息
        total_cases = task.total_scenarios or 0
        completed_cases = task.completed_scenarios or 0
        failed_cases = task.failed_scenarios or 0
        processed = completed_cases + failed_cases

        # 估算用时与 ETA
        now_ts = datetime.now()
        elapsed_seconds = None
        eta_seconds = None
        if task.started_at:
            try:
                elapsed_seconds = (now_ts - task.started_at).total_seconds()
                if processed > 0 and total_cases > 0:
                    avg_per_case = elapsed_seconds / processed
                    eta_seconds = max(0.0, avg_per_case * (total_cases - processed))
            except Exception:
                pass

        # 最近结果（最多 10 条）
        recent_q = (
            db.query(ScenarioResult)
            .filter(ScenarioResult.task_id == task_id)
            .order_by(ScenarioResult.created_at.desc())
            .limit(10)
            .all()
        )
        recent_results = []
        for r in recent_q:
            item = {
                "question_id": r.scenario_id,
                "clinical_query": r.rag_question or r.clinical_scenario,
                "ground_truth": r.standard_answer,
                "rag_answer": r.rag_answer,
                "ragas_scores": {
                    "faithfulness": r.faithfulness_score,
                    "answer_relevancy": r.answer_relevancy_score,
                    "context_precision": r.context_precision_score,
                    "context_recall": r.context_recall_score,
                },
                "inference_ms": r.inference_duration_ms,
                "evaluation_ms": r.evaluation_duration_ms,
                "created_at": r.created_at,
                "model": (r.evaluation_metadata or {}).get("model_name") if isinstance(r.evaluation_metadata, dict) else None,
                "status": r.status or "completed",
            }
            # 从 trace 中提取中间过程指标
            trace = r.rag_trace_data if isinstance(r.rag_trace_data, dict) else {}
            rec = (trace.get("recall_scenarios") or []) if isinstance(trace, dict) else []
            rr = (trace.get("rerank_scenarios") or []) if isinstance(trace, dict) else []
            final_prompt = (trace.get("final_prompt") or "") if isinstance(trace, dict) else ""
            llm_parsed = (trace.get("llm_parsed") or {}) if isinstance(trace, dict) else {}
            llm_recs = (llm_parsed.get("recommendations") or []) if isinstance(llm_parsed, dict) else []
            item.update({
                "recall_count": len(rec),
                "rerank_count": len(rr),
                "prompt_length": len(final_prompt) if isinstance(final_prompt, str) else None,
                "llm_recommendations": llm_recs[:3],
            })
            # 轻量级中间过程预览，避免payload过大
            item["trace_preview"] = {
                "recall_scenarios": rec[:3],
                "rerank_scenarios": rr[:3],
                "final_prompt_preview": (final_prompt or "")[:300],
                "llm_recommendations": llm_recs[:3],
            }
            # 从元数据推断模式（RAG / no-RAG）
            meta = r.evaluation_metadata if isinstance(r.evaluation_metadata, dict) else {}
            rag_obj = meta.get("rag_result") if isinstance(meta, dict) else None
            if isinstance(rag_obj, dict):
                item["mode"] = "no-RAG" if rag_obj.get("is_low_similarity_mode") else "RAG"
            recent_results.append(item)

        # 吞吐率（条/分钟）
        throughput_cpm = None
        if elapsed_seconds and elapsed_seconds > 0:
            throughput_cpm = round((processed / elapsed_seconds) * 60, 2)

        return {
            "task_id": task.task_id,
            "status": task.status,
            # 百分比进度（0-100）
            "progress": task.progress_percentage,
            # 计数进度
            "total_cases": total_cases,
            "completed_cases": completed_cases,
            "failed_cases": failed_cases,
            "processed_cases": processed,
            # 时间信息
            "start_time": task.started_at,
            "last_update": task.updated_at if hasattr(task, "updated_at") else None,
            "end_time": task.completed_at,
            "elapsed_seconds": elapsed_seconds,
            "eta_seconds": eta_seconds,
            "throughput_cpm": throughput_cpm,
            # 最近结果片段
            "recent_results": recent_results,
            # 错误
            "error_message": task.error_message,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")

@router.get("/evaluate/{task_id}/results", response_model=TaskDetailResponse)
async def get_task_results(task_id: str, db: Session = Depends(get_db)):
    """获取评测任务结果"""
    try:
        task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()

        if not task:
            raise HTTPException(status_code=404, detail=f"任务未找到: {task_id}")

        if task.status != TaskStatus.COMPLETED:
            raise HTTPException(status_code=400, detail=f"任务尚未完成，当前状态: {task.status}")

        # 获取评测结果
        results = db.query(ScenarioResult).filter(ScenarioResult.task_id == task_id).all()

        # 获取评测指标
        metrics = db.query(EvaluationMetrics).filter(EvaluationMetrics.task_id == task_id).first()

        # 从evaluation_config中提取模型名称（优先 ragas_llm_model）
        model_name_from_config = "unknown"
        if task.evaluation_config and isinstance(task.evaluation_config, dict):
            model_name_from_config = task.evaluation_config.get('ragas_llm_model') or task.evaluation_config.get('model_name', 'unknown')

        # 构造响应
        task_response = EvaluationTaskResponse(
            id=task.id,
            task_id=task.task_id,
            task_name=task.task_name,
            description=task.description,
            model_name=model_name_from_config,
            total_cases=task.total_scenarios,
            status=task.status,
            progress=task.progress_percentage,
            completed_cases=task.completed_scenarios,
            failed_cases=task.failed_scenarios,
            start_time=task.started_at,
            end_time=task.completed_at,
            processing_time=((task.completed_at - task.started_at).total_seconds() if task.completed_at and task.started_at else None),
            error_message=task.error_message,
            created_at=task.created_at,
            updated_at=task.updated_at
        )

        evaluation_results = []
        for result in results:
            # extract indicators from trace
            _trace = result.rag_trace_data if isinstance(result.rag_trace_data, dict) else {}
            _rec = (_trace.get("recall_scenarios") or []) if isinstance(_trace, dict) else []
            _rr = (_trace.get("rerank_scenarios") or []) if isinstance(_trace, dict) else []
            _final_prompt = (_trace.get("final_prompt") or "") if isinstance(_trace, dict) else ""
            _llm_parsed = (_trace.get("llm_parsed") or {}) if isinstance(_trace, dict) else {}
            _llm_recs = (_llm_parsed.get("recommendations") or []) if isinstance(_llm_parsed, dict) else []
            _meta = result.evaluation_metadata if isinstance(result.evaluation_metadata, dict) else {}
            evaluation_results.append({
                "question_id": result.scenario_id or "unknown",
                "clinical_query": result.clinical_scenario or result.rag_question or "模拟临床场景",
                "ground_truth": result.standard_answer or "模拟标准答案",
                "ragas_scores": {
                    "faithfulness": result.faithfulness_score or 0.0,
                    "answer_relevancy": result.answer_relevancy_score or 0.0,
                    "context_precision": result.context_precision_score or 0.0,
                    "context_recall": result.context_recall_score or 0.0
                },
                # expand: text answer / contexts / trace
                "rag_answer": result.rag_answer,
                "contexts": result.rag_contexts,
                "model": _meta.get("model_name") if isinstance(_meta, dict) else None,
                "inference_ms": result.inference_duration_ms,
                "evaluation_ms": result.evaluation_duration_ms,
                "trace": _trace,
                # expand: recall/rerank counts, prompt length, LLM recs
                "recall_count": len(_rec),
                "rerank_count": len(_rr),
                "prompt_length": len(_final_prompt) if isinstance(_final_prompt, str) else None,
                "llm_recommendations": _llm_recs[:3],
                # expand: evaluation model names
                "ragas_llm_model": _meta.get("ragas_llm_model"),
                "ragas_embedding_model": _meta.get("ragas_embedding_model"),
                # expand: timestamp
                "timestamp": result.created_at.timestamp(),
                "metadata": result.evaluation_metadata
            })

        summary = None
        if any([
            task.avg_faithfulness is not None,
            task.avg_answer_relevancy is not None,
            task.avg_context_precision is not None,
            task.avg_context_recall is not None
        ]):
            summary = {
                "faithfulness": task.avg_faithfulness,
                "answer_relevancy": task.avg_answer_relevancy,
                "context_precision": task.avg_context_precision,
                "context_recall": task.avg_context_recall
            }

        return TaskDetailResponse(
            task=task_response,
            results=evaluation_results,
            summary=summary,
            metrics_distribution=None  # 可以后续添加分布统计
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取任务结果失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取任务结果失败: {str(e)}")

@router.delete("/evaluate/{task_id}")
async def cancel_task(task_id: str, db: Session = Depends(get_db)):
    """取消评测任务"""
    try:
        task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()

        if not task:
            raise HTTPException(status_code=404, detail=f"任务未找到: {task_id}")

        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            raise HTTPException(status_code=400, detail=f"任务已结束，无法取消，当前状态: {task.status}")

        # 更新任务状态
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()
        db.commit()

        logger.info(f"任务已取消: {task_id}")

        return {"message": f"任务已取消: {task_id}", "status": "cancelled"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")

# ==================== 历史记录相关端点 ====================

@router.get("/history", response_model=EvaluationHistoryResponse)
async def get_evaluation_history(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    status: Optional[TaskStatus] = Query(None, description="任务状态筛选"),
    model_name: Optional[str] = Query(None, description="模型名称筛选"),
    start_date: Optional[datetime] = Query(None, description="开始日期"),
    end_date: Optional[datetime] = Query(None, description="结束日期"),
    db: Session = Depends(get_db)
):
    """获取评测历史记录列表"""
    try:
        # 构建查询
        query = db.query(EvaluationTask)

        # 应用筛选条件
        if status:
            query = query.filter(EvaluationTask.status == status)
        if model_name:
            # 从evaluation_config中筛选模型名称
            query = query.filter(EvaluationTask.evaluation_config.contains({"model_name": model_name}))
        if start_date:
            query = query.filter(EvaluationTask.created_at >= start_date)
        if end_date:
            query = query.filter(EvaluationTask.created_at <= end_date)

        # 获取总数
        total = query.count()

        # 分页查询
        offset = (page - 1) * page_size
        tasks = query.order_by(EvaluationTask.created_at.desc()).offset(offset).limit(page_size).all()

        # 构造响应
        task_list = []
        for task in tasks:
            # 从evaluation_config中提取模型名称（优先 ragas_llm_model）
            model_name_from_config = "unknown"
            if task.evaluation_config and isinstance(task.evaluation_config, dict):
                model_name_from_config = task.evaluation_config.get('ragas_llm_model') or task.evaluation_config.get('model_name', 'unknown')

            task_response = EvaluationTaskResponse(
                id=task.id,
                task_id=task.task_id,
                task_name=task.task_name,
                description=task.description,
                model_name=model_name_from_config,
                total_cases=task.total_scenarios,
                status=_normalize_task_status(task.status),
                progress=task.progress_percentage,
                completed_cases=task.completed_scenarios,
                failed_cases=task.failed_scenarios,
                start_time=task.started_at,
                end_time=task.completed_at,
                processing_time=None,  # 不再使用processing_time字段
                error_message=task.error_message,
                created_at=task.created_at,
                updated_at=task.updated_at
            )
            task_list.append(task_response)

        return EvaluationHistoryResponse(
            items=task_list,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size
        )

    except Exception as e:
        logger.error(f"获取历史记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取历史记录失败: {str(e)}")

@router.get("/history/statistics")
async def get_evaluation_statistics(db: Session = Depends(get_db)):
    """获取评测统计信息"""
    try:
        # 总任务数
        total_tasks = db.query(EvaluationTask).count()

        # 各状态任务数
        status_counts = {}
        for status in TaskStatus:
            count = db.query(EvaluationTask).filter(EvaluationTask.status == status).count()
            status_counts[status.value] = count

        # 模型使用统计 - 从evaluation_config中提取模型信息
        all_tasks = db.query(EvaluationTask.evaluation_config).filter(
            EvaluationTask.evaluation_config.isnot(None)
        ).all()

        model_counts = {}
        for (config,) in all_tasks:
            if config and isinstance(config, dict) and 'model_name' in config:
                model_name = config['model_name']
                model_counts[model_name] = model_counts.get(model_name, 0) + 1
            else:
                model_counts['unknown'] = model_counts.get('unknown', 0) + 1

        model_usage_dict = model_counts

        # 最近7天的任务数
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_tasks = db.query(EvaluationTask).filter(
            EvaluationTask.created_at >= seven_days_ago
        ).count()

        # 平均处理时间（已完成的任务）- 计算started_at和completed_at之间的时间差
        completed_tasks = db.query(EvaluationTask).filter(
            EvaluationTask.status == TaskStatus.COMPLETED,
            EvaluationTask.started_at.isnot(None),
            EvaluationTask.completed_at.isnot(None)
        ).all()

        if completed_tasks:
            total_time = sum([
                (task.completed_at - task.started_at).total_seconds() / 60  # 转换为分钟
                for task in completed_tasks
            ])
            avg_processing_time = total_time / len(completed_tasks)
        else:
            avg_processing_time = None

        return {
            "total_tasks": total_tasks,
            "status_distribution": status_counts,
            "model_usage": model_usage_dict,
            "recent_tasks_7days": recent_tasks,
            "average_processing_time_minutes": float(avg_processing_time) if avg_processing_time else None
        }

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")

@router.get("/history/{task_id}", response_model=TaskDetailResponse)
async def get_history_detail(task_id: str, db: Session = Depends(get_db)):
    """获取历史记录详情"""
    try:
        task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()

        if not task:
            raise HTTPException(status_code=404, detail=f"任务未找到: {task_id}")

        # 获取评测结果（如果有的话）
        results = db.query(ScenarioResult).filter(ScenarioResult.task_id == task_id).all()

        # 获取评测指标（如果有的话）
        metrics = db.query(EvaluationMetrics).filter(EvaluationMetrics.task_id == task_id).first()

        # 从evaluation_config中提取模型名称（优先 ragas_llm_model）
        model_name_from_config = "unknown"
        if task.evaluation_config and isinstance(task.evaluation_config, dict):
            model_name_from_config = task.evaluation_config.get('ragas_llm_model') or task.evaluation_config.get('model_name', 'unknown')

        # 构造响应
        task_response = EvaluationTaskResponse(
            id=task.id,
            task_id=task.task_id,
            task_name=task.task_name,
            description=task.description,
            model_name=model_name_from_config,
            total_cases=task.total_scenarios,
            status=_normalize_task_status(task.status),
            progress=task.progress_percentage,
            completed_cases=task.completed_scenarios,
            failed_cases=task.failed_scenarios,
            start_time=task.started_at,
            end_time=task.completed_at,
            processing_time=((task.completed_at - task.started_at).total_seconds() if task.completed_at and task.started_at else None),
            error_message=task.error_message,
            created_at=task.created_at,
            updated_at=task.updated_at
        )

        evaluation_results = []
        for result in results:
            evaluation_results.append({
                "question_id": result.scenario_id or "unknown",
                "clinical_query": result.clinical_scenario or result.rag_question or "模拟临床场景",
                "ground_truth": result.standard_answer or "模拟标准答案",
                "ragas_scores": {
                    "faithfulness": result.faithfulness_score or 0.0,
                    "answer_relevancy": result.answer_relevancy_score or 0.0,
                    "context_precision": result.context_precision_score or 0.0,
                    "context_recall": result.context_recall_score or 0.0
                },
                "rag_answer": result.rag_answer,
                "contexts": result.rag_contexts,
                "model": (result.evaluation_metadata or {}).get("model_name") if isinstance(result.evaluation_metadata, dict) else None,
                "inference_ms": result.inference_duration_ms,
                "evaluation_ms": result.evaluation_duration_ms,
                "trace": result.rag_trace_data,
                "timestamp": result.created_at.timestamp(),
                "metadata": result.evaluation_metadata
            })

        summary = None
        if any([
            task.avg_faithfulness is not None,
            task.avg_answer_relevancy is not None,
            task.avg_context_precision is not None,
            task.avg_context_recall is not None
        ]):
            summary = {
                "faithfulness": task.avg_faithfulness,
                "answer_relevancy": task.avg_answer_relevancy,
                "context_precision": task.avg_context_precision,
                "context_recall": task.avg_context_recall
            }

        return TaskDetailResponse(
            task=task_response,
            results=evaluation_results,
            summary=summary,
            metrics_distribution=None  # 可以后续添加分布统计
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取历史记录详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取历史记录详情失败: {str(e)}")

@router.delete("/history/{task_id}")
async def delete_history_record(task_id: str, db: Session = Depends(get_db)):
    """删除历史记录"""
    try:
        task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail=f"任务未找到: {task_id}")

        # 删除相关的评测结果
        db.query(ScenarioResult).filter(ScenarioResult.task_id == task_id).delete()
        # 删除相关的评测指标
        db.query(EvaluationMetrics).filter(EvaluationMetrics.task_id == task_id).delete()
        # 删除任务记录
        db.delete(task)
        db.commit()

        logger.info(f"历史记录已删除: {task_id}")
        return {"status": "success", "task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"删除历史记录失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除历史记录失败: {str(e)}")


# ============ 管理：清空评测数据库（带备份） ============
from pydantic import BaseModel

class ClearAllRequest(BaseModel):
    confirm: str
    backup: bool = True

@router.post("/admin/clear-all", summary="清空评测相关数据（evaluation_tasks/scenario_results/evaluation_metrics）")
async def admin_clear_all(req: ClearAllRequest, db: Session = Depends(get_db)):
    """
    危险操作：清空评测相关三张表数据。默认先做备份。
    - 备份表名：<table>_bak_YYYYMMDDHH24MISS
    - 仅当 req.confirm == "I-UNDERSTAND" 才执行
    """
    if req.confirm != "I-UNDERSTAND":
        raise HTTPException(status_code=400, detail="需要确认字段 confirm=I-UNDERSTAND")
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    try:
        if req.backup:
            db.execute(text(f"CREATE TABLE IF NOT EXISTS evaluation_tasks_bak_{ts} AS TABLE evaluation_tasks WITH DATA"))
            db.execute(text(f"CREATE TABLE IF NOT EXISTS scenario_results_bak_{ts} AS TABLE scenario_results WITH DATA"))
            db.execute(text(f"CREATE TABLE IF NOT EXISTS evaluation_metrics_bak_{ts} AS TABLE evaluation_metrics WITH DATA"))
        # 清空（使用 TRUNCATE + CASCADE 确保外键一致）
        db.execute(text("TRUNCATE TABLE evaluation_metrics, scenario_results, evaluation_tasks RESTART IDENTITY CASCADE"))
        # 可选：创建/刷新按样本一行的只读视图（便于前端统一读取）
        db.execute(text("""
        CREATE OR REPLACE VIEW v_ragas_case_results AS
        SELECT
          sr.id,
          sr.task_id,
          sr.scenario_id,
          sr.clinical_scenario,
          sr.standard_answer,
          sr.rag_question,
          sr.rag_answer,
          sr.rag_contexts,
          sr.rag_trace_data,
          sr.faithfulness_score,
          sr.answer_relevancy_score,
          sr.context_precision_score,
          sr.context_recall_score,
          sr.overall_score,
          sr.inference_started_at,
          sr.inference_completed_at,
          sr.evaluation_started_at,
          sr.evaluation_completed_at,
          sr.inference_duration_ms,
          sr.evaluation_duration_ms,
          sr.created_at,
          COALESCE((et.evaluation_config ->> 'ragas_llm_model'), (et.evaluation_config ->> 'model_name')) AS ragas_llm_model
        FROM scenario_results sr
        LEFT JOIN evaluation_tasks et ON et.task_id = sr.task_id;
        """))
        db.commit()
        return {"ok": True, "message": "已清空评测数据并创建/刷新 v_ragas_case_results 视图", "backup": req.backup, "timestamp": ts}
    except Exception as e:
        db.rollback()
        logger.exception("清空评测数据库失败")
        raise HTTPException(status_code=500, detail=f"操作失败: {e}")


# ==================== 辅助函数 ====================
# 统一规范化任务状态，兼容历史遗留值（如 RUNNING）
from typing import Optional as _Optional

def _normalize_task_status(value: _Optional[str]):
    try:
        if value is None:
            return TaskStatus.PENDING
        s = str(value).strip()
        if not s:
            return TaskStatus.PENDING
        sl = s.lower()
        if sl in {"running", "in_progress", "processing"}:
            return TaskStatus.PROCESSING
        if sl in {"pending", "created", "queued"}:
            return TaskStatus.PENDING
        if sl in {"completed", "success", "done"}:
            return TaskStatus.COMPLETED
        if sl in {"failed", "error"}:
            return TaskStatus.FAILED
        if sl in {"cancelled", "canceled"}:
            return TaskStatus.CANCELLED
        # 尝试直接映射到合法枚举
        return TaskStatus(sl)
    except Exception:
        return TaskStatus.PENDING

# ==================== 离线评测（基于历史推理） ====================
from pydantic import BaseModel
from app.models.system_models import InferenceLog

class OfflineEvaluateRequest(BaseModel):
    run_ids: List[int]
    ground_truths: Optional[Dict[int, str]] = None  # 可选：按运行ID提供GT
    async_mode: bool = True
    task_name: Optional[str] = None
@router.post("/offline-evaluate")
async def offline_evaluate_from_runs(req: OfflineEvaluateRequest, db: Session = Depends(get_db)):
    """
    基于已保存的推理历史（InferenceLog）执行RAGAS评测：
    - 读取 run_ids 对应的运行结果（包含 llm_recommendations、scenarios、trace）
    - 提取 answer 与 contexts
    - 使用统一的 RAGASEvaluator（从模型配置 evaluation 上下文读取 LLM/Embedding）计算四项指标
    - 写入 EvaluationTask/ScenarioResult，返回 task_id 与结果
    """
    try:
        run_ids = list(dict.fromkeys(req.run_ids or []))
        if not run_ids:
            raise HTTPException(status_code=400, detail="run_ids 不能为空")

        # 读取运行日志
        runs = (
            db.query(InferenceLog)
              .filter(InferenceLog.id.in_(run_ids))
              .order_by(InferenceLog.created_at.asc())
              .all()
        )
        if not runs:
            raise HTTPException(status_code=404, detail="未找到指定的运行记录")

        # 初始化评测器（严格使用模型配置中的 evaluation 上下文）
        try:
            from app.services.ragas_evaluator_v2 import ACRACRAGASEvaluator
            evaluator = ACRACRAGASEvaluator()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"RAGASEvaluator 初始化失败: {e}")

        # 创建任务
        task_id = str(uuid.uuid4())
        # 兼容历史数据：修复非法任务状态值（如 RUNNING → processing；以及全部统一为小写）
        try:
            db.execute(text("UPDATE evaluation_tasks SET status='processing' WHERE UPPER(status)='RUNNING'"))
            db.execute(text("UPDATE evaluation_tasks SET status=LOWER(status) WHERE status IN ('PENDING','PROCESSING','COMPLETED','FAILED','CANCELLED')"))
            db.commit()
        except Exception:
            db.rollback()

        task = EvaluationTask(
            task_id=task_id,
            task_name=req.task_name or f"离线评测_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            description=f"Offline evaluate {len(runs)} runs",
            total_scenarios=len(runs),
            status=TaskStatus.PROCESSING,
            evaluation_config={
                "ragas_llm_model": getattr(evaluator, "llm_model_name", None),
                "ragas_embedding_model": getattr(evaluator, "embedding_model_name", None),
                "mode": "offline-from-runs"
            },
            started_at=datetime.now()
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # 同步执行（若 async_mode=True，后续可接 Celery，这里先同步保证功能）
        completed = 0
        failed = 0
        results: List[Dict[str, Any]] = []

        for r in runs:
            try:
                import json as _json
                question = r.query_text or ""
                raw_res = r.result
                if isinstance(raw_res, str):
                    try:
                        rag_result = _json.loads(raw_res) or {}
                    except Exception:
                        rag_result = {}
                elif isinstance(raw_res, dict):
                    rag_result = raw_res
                else:
                    rag_result = {}

                # 构造 answer（参考 app/services/ragas_service.py 的逻辑）
                llm_recs = (rag_result or {}).get("llm_recommendations", {})
                recs = llm_recs.get("recommendations", []) if isinstance(llm_recs, dict) else []
                if recs:
                    answer_text = "推荐的影像学检查：\n" + "\n".join([
                        f"- {rec.get('procedure_name','')} (适宜性: {rec.get('appropriateness_rating','')})"
                        for rec in recs[:3]
                    ])
                else:
                    answer_text = "暂无推荐的影像学检查"

                # 构造 contexts（参考 ragas_service 提取 scenarios）
                contexts: List[str] = []
                for sc in (rag_result or {}).get("scenarios", [])[:3]:
                    try:
                        ctx = f"场景: {sc.get('panel_name','')} - {sc.get('topic_name','')}"
                        if sc.get("clinical_scenario"):
                            ctx += f"\n临床场景: {sc['clinical_scenario']}"
                        contexts.append(ctx)
                    except Exception:
                        continue

                # ground truth：优先从请求提供的映射中取
                gt = None
                if req.ground_truths and isinstance(req.ground_truths, dict):
                    gt = req.ground_truths.get(int(r.id)) or req.ground_truths.get(str(r.id))

                # 计算RAGAS（优先使用标准评测器；若分数无效则回退到增强评测器并记录详细信息）
                ragas_scores = {
                    "faithfulness": 0.0,
                    "answer_relevancy": 0.0,
                    "context_precision": 0.0,
                    "context_recall": 0.0,
                }
                evaluation_details = {
                    "method": "ragas_v2",
                    "ragas_llm_model": getattr(evaluator, "llm_model_name", None),
                    "ragas_embedding_model": getattr(evaluator, "embedding_model_name", None),
                    "contexts_count": len(contexts),
                    "has_ground_truth": bool(gt),
                }
                try:
                    sample = {
                        "question": question,
                        "answer": answer_text,
                        "contexts": contexts,
                    }
                    if gt:
                        sample["ground_truth"] = gt
                    ragas_scores = evaluator.evaluate_sample(sample)
                except Exception as e:
                    logger.warning(f"RAGAS单样本评分失败(run_id={r.id}): {e}")

                # 若所有分数为0，则回退到增强评测器（LLM提示词+启发式），以避免全零结果
                valid_scores_try = [v for v in ragas_scores.values() if isinstance(v, (int, float)) and v > 0]
                if not valid_scores_try:
                    try:
                        from app.services.enhanced_ragas_evaluator import EnhancedRAGASEvaluator, EvaluationConfig
                        enhanced = EnhancedRAGASEvaluator(evaluation_config=EvaluationConfig())
                        detailed = await enhanced.evaluate_with_detailed_results({
                            "id": str(r.id),
                            "question": question,
                            "answer": answer_text,
                            "contexts": contexts,
                            "ground_truth": gt or "",
                        })
                        ragas_scores = detailed.metrics or ragas_scores
                        evaluation_details.update({
                            "method": "enhanced_fallback",
                            "process_data": detailed.process_data,
                            "chinese_processing": detailed.chinese_processing_info,
                        })
                    except Exception as fe:
                        logger.warning(f"增强评测回退失败(run_id={r.id}): {fe}")

                valid_scores = [v for v in ragas_scores.values() if isinstance(v, (int, float)) and v > 0]
                overall_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

                # 保存单条结果
                sr = ScenarioResult(
                    task_id=task_id,
                    scenario_id=str(r.id),
                    # 不设置 clinical_scenario，避免与关系属性同名导致映射冲突
                    rag_question=question,
                    rag_answer=answer_text,
                    rag_contexts=contexts,
                    rag_trace_data=(rag_result.get("trace") if isinstance(rag_result, dict) else None) or {},
                    standard_answer=gt,
                    faithfulness_score=ragas_scores.get("faithfulness", 0.0),
                    answer_relevancy_score=ragas_scores.get("answer_relevancy", 0.0),
                    context_precision_score=ragas_scores.get("context_precision", 0.0),
                    context_recall_score=ragas_scores.get("context_recall", 0.0),
                    overall_score=overall_score,
                    evaluation_metadata={
                        "source_run_id": r.id,
                        "ragas_llm_model": getattr(evaluator, "llm_model_name", None),
                        "ragas_embedding_model": getattr(evaluator, "embedding_model_name", None),
                        "ragas_details": evaluation_details,
                    },
                    status="completed",
                    processing_stage="offline-evaluation",
                    created_at=datetime.now(),
                )
                try:
                    db.add(sr)
                    db.flush()  # 及时检测约束/映射问题
                except Exception as add_err:
                    logger.warning(f"保存单条评测结果失败(run_id={r.id}): {add_err}")

                results.append({
                    "question_id": r.id,
                    "clinical_query": question,
                    "ground_truth": gt,
                    "rag_answer": answer_text,
                    "ragas_scores": ragas_scores,
                    "contexts": contexts,
                    "evaluation_details": evaluation_details,
                })
                completed += 1
            except Exception as e:
                logger.error(f"离线评测处理失败(run_id={r.id}): {e}")
                failed += 1
                continue

        # 更新任务
        try:
            task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
            if task:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.progress_percentage = 100
                task.completed_scenarios = completed
                task.failed_scenarios = failed
                # 汇总写入平均分（如有GT才有意义，这里以实际分为准）
                if results:
                    def _avg(key):
                        vals = [x["ragas_scores"].get(key) or 0.0 for x in results]
                        return sum(vals) / len(vals) if vals else 0.0
                    task.avg_faithfulness = _avg("faithfulness")
                    task.avg_answer_relevancy = _avg("answer_relevancy")
                    task.avg_context_precision = _avg("context_precision")
                    task.avg_context_recall = _avg("context_recall")
                db.commit()
        except Exception as e:
            logger.warning(f"更新任务统计失败: {e}")

        return {
            "status": "completed",
            "task_id": task_id,
            "results": results,
            "summary": {
                "faithfulness": getattr(task, "avg_faithfulness", None),
                "answer_relevancy": getattr(task, "avg_answer_relevancy", None),
                "context_precision": getattr(task, "avg_context_precision", None),
                "context_recall": getattr(task, "avg_context_recall", None),
                "completed": completed,
                "failed": failed,
                "total": len(runs)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"离线评测失败: {e}")
        raise HTTPException(status_code=500, detail=f"离线评测失败: {str(e)}")


async def run_ragas_evaluation_task(
    task_id: str,
    test_cases: List[dict],
    model_name: str,
    base_url: Optional[str] = None,
    evaluation_config: Optional[dict] = None
):
    """异步执行RAGAS评测任务"""
    from app.core.database import SessionLocal
    from app.api.api_v1.endpoints.ragas_evaluation_api import ragas_service

    db = SessionLocal()
    try:
        # 更新任务状态为运行中
        task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
        if task:
            task.status = TaskStatus.PROCESSING
            task.started_at = datetime.now()
            db.commit()

        # 执行评测
        start_time = time.time()
        result = ragas_service.run_evaluation(
            test_cases=test_cases,
            model_name=model_name,
            base_url=base_url
        )
        processing_time = time.time() - start_time

        # 更新任务状态
        if task:
            task.status = TaskStatus.COMPLETED if result["status"] == "success" else TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.progress_percentage = 100

            if result["status"] == "error":
                task.error_message = result.get("error", "未知错误")
            else:
                task.completed_scenarios = len(test_cases)
                task.failed_scenarios = 0

            db.commit()

        logger.info(f"异步评测任务完成: {task_id}, 耗时: {processing_time:.2f}秒")

    except Exception as e:
        logger.error(f"异步评测任务失败: {task_id}, 错误: {e}")

        # 更新任务状态为失败
        if task:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error_message = str(e)
            db.commit()

    finally:
        db.close()

# ==================== 健康检查端点 ====================

@router.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "ragas-api", "timestamp": datetime.now().isoformat()}

# ==================== 真实RAG评测实现 ====================

async def run_real_rag_evaluation(
    test_cases: List[dict],
    model_name: str,
    base_url: Optional[str] = None,
    task_id: str = None,
    db: Session = None
) -> Dict[str, Any]:
    """运行真实的RAG-LLM API调用和RAGAS评估"""

    try:
        logger.info(f"开始真实RAG评测，任务ID: {task_id}, 测试用例数: {len(test_cases)}")

        # RAG-LLM API端点
        rag_api_url = os.getenv("RAG_API_URL", "http://127.0.0.1:8002/api/v1/acrac/rag-llm/intelligent-recommendation")

        evaluation_results = []
        total_cases = len(test_cases)
        completed_cases = 0
        failed_cases = 0

        # 初始化RAGAS评估器（并回写任务实际使用的评测模型）
        try:
            from app.services.ragas_evaluator_v2 import ACRACRAGASEvaluator
            ragas_evaluator = ACRACRAGASEvaluator()
            if db and task_id:
                try:
                    _task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
                    if _task:
                        cfg = _task.evaluation_config or {}
                        cfg["ragas_llm_model"] = getattr(ragas_evaluator, "llm_model", None)
                        cfg["ragas_embedding_model"] = getattr(ragas_evaluator, "embedding_model", None)
                        _task.evaluation_config = cfg
                        db.commit()
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"RAGAS评估器初始化失败: {e}，将跳过RAGAS评分")
            ragas_evaluator = None

        for i, test_case in enumerate(test_cases):
            try:
                # 从测试用例中提取信息
                clinical_query = test_case.get("clinical_query") or test_case.get("question") or test_case.get("clinical_scenario", "")
                ground_truth = test_case.get("ground_truth") or test_case.get("standard_answer", "")
                question_id = test_case.get("question_id") or test_case.get("scenario_id", f"case_{i+1}")

                logger.info(f"处理测试用例 {i+1}/{total_cases}: {question_id}")

                # 构造RAG API请求
                rag_payload = {
                    "clinical_query": clinical_query,
                    "top_scenarios": 3,
                    "top_recommendations_per_scenario": 3,
                    "show_reasoning": True,
                    "similarity_threshold": 0.6,
                    "debug_mode": True,
                    "include_raw_data": True,
                    "compute_ragas": False,  #  ourselves compute RAGAS
                    "ground_truth": ground_truth
                }

                # 推理阶段时间戳
                inference_started_at = None
                inference_completed_at = None

                # 调用RAG-LLM API
                try:
                    inference_started_at = datetime.now()
                    response = requests.post(rag_api_url, json=rag_payload, timeout=120)
                    if response.status_code != 200:
                        logger.error(f"RAG API调用失败: {response.status_code}, {response.text}")
                        failed_cases += 1
                        continue
                    rag_result = response.json()
                    inference_completed_at = datetime.now()
                except Exception as e:
                    logger.error(f"RAG API调用异常: {e}")
                    failed_cases += 1
                    continue

                # 提取RAG响应信息
                llm_recommendations = rag_result.get("llm_recommendations", {})
                recommendations = llm_recommendations.get("recommendations", [])

                # 构造答案文本
                if recommendations:
                    answer_text = "推荐的影像学检查：\n"
                    for rec in recommendations[:3]:  # 取前3个推荐
                        procedure = rec.get("procedure_name", "")
                        rating = rec.get("appropriateness_rating", "")
                        answer_text += f"- {procedure} (适宜性: {rating})\n"
                else:
                    answer_text = "暂无推荐的影像学检查"

                # 提取上下文信息
                contexts = []
                scenarios = rag_result.get("scenarios", [])
                for scenario in scenarios[:3]:  # 取前3个相关场景
                    context_text = f"场景: {scenario.get('panel_name', '')} - {scenario.get('topic_name', '')}"
                    if scenario.get('clinical_scenario'):
                        context_text += f"\n临床场景: {scenario['clinical_scenario']}"
                    contexts.append(context_text)

                # 评估阶段时间戳
                evaluation_started_at = None
                evaluation_completed_at = None

                # 计算RAGAS评分
                ragas_scores = {
                    "faithfulness": 0.0,
                    "answer_relevancy": 0.0,
                    "context_precision": 0.0,
                    "context_recall": 0.0
                }

                if ragas_evaluator and contexts and answer_text and ground_truth:
                    try:
                        evaluation_started_at = datetime.now()
                        ragas_data = {
                            "question": clinical_query,
                            "answer": answer_text,
                            "contexts": contexts,
                            "ground_truth": ground_truth
                        }
                        ragas_scores = ragas_evaluator.evaluate_sample(ragas_data)
                        evaluation_completed_at = datetime.now()
                    except Exception as e:
                        logger.warning(f"RAGAS评分计算失败: {e}")
                        evaluation_completed_at = datetime.now() if evaluation_started_at else None

                # 计算单条overall_score
                try:
                    overall_score = (
                        ragas_scores.get("faithfulness", 0.0) +
                        ragas_scores.get("answer_relevancy", 0.0) +
                        ragas_scores.get("context_precision", 0.0) +
                        ragas_scores.get("context_recall", 0.0)
                    ) / 4.0
                except Exception:
                    overall_score = None

                # 保存结果到数据库
                if db and task_id:
                    scenario_result = ScenarioResult(
                        task_id=task_id,
                        scenario_id=str(question_id),
                        clinical_scenario=clinical_query,
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
                            "rag_result": rag_result,
                            "contexts": contexts,
                            "model_name": (getattr(ragas_evaluator, "llm_model_name", None) if ragas_evaluator else model_name),
                            "ragas_llm_model": getattr(ragas_evaluator, "llm_model_name", None),
                            "ragas_embedding_model": getattr(ragas_evaluator, "embedding_model_name", None)
                        },
                        status="completed",
                        processing_stage="evaluation",
                        inference_started_at=inference_started_at,
                        inference_completed_at=inference_completed_at,
                        evaluation_started_at=evaluation_started_at,
                        evaluation_completed_at=evaluation_completed_at,
                        inference_duration_ms=int((inference_completed_at - inference_started_at).total_seconds() * 1000) if (inference_started_at and inference_completed_at) else None,
                        evaluation_duration_ms=int((evaluation_completed_at - evaluation_started_at).total_seconds() * 1000) if (evaluation_started_at and evaluation_completed_at) else None,
                    )
                    # 计算总耗时
                    try:
                        scenario_result.update_duration()
                    except Exception:
                        pass
                    db.add(scenario_result)

                # 添加到结果列表
                evaluation_results.append({
                    "question_id": question_id,
                    "clinical_query": clinical_query,
                    "rag_answer": answer_text,
                    "ground_truth": ground_truth,
                    "ragas_scores": ragas_scores,
                    "contexts": contexts,
                    "rag_result": rag_result
                })

                completed_cases += 1

                # 更新任务进度
                if db and task_id:
                    task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
                    if task:
                        task.completed_scenarios = completed_cases
                        task.failed_scenarios = failed_cases
                        task.progress_percentage = int((completed_cases + failed_cases) / total_cases * 100)
                        db.commit()

                # 避免API限流
                await asyncio.sleep(1.0)

            except Exception as e:
                logger.error(f"处理测试用例失败: {e}")
                failed_cases += 1
                continue

        # 计算汇总统计
        if evaluation_results:
            all_scores = [result["ragas_scores"] for result in evaluation_results]
            summary = {
                "faithfulness": sum(s["faithfulness"] for s in all_scores) / len(all_scores),
                "answer_relevancy": sum(s["answer_relevancy"] for s in all_scores) / len(all_scores),
                "context_precision": sum(s["context_precision"] for s in all_scores) / len(all_scores),
                "context_recall": sum(s["context_recall"] for s in all_scores) / len(all_scores)
            }

            # 保存汇总指标到数据库（更新任务聚合指标 + 指标历史）
            if db and task_id:
                task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
                if task:
                    task.avg_faithfulness = summary["faithfulness"]
                    task.avg_answer_relevancy = summary["answer_relevancy"]
                    task.avg_context_precision = summary["context_precision"]
                    task.avg_context_recall = summary["context_recall"]
                    # 计算总体得分（简单平均）
                    try:
                        task.avg_overall_score = (
                            summary["faithfulness"] + summary["answer_relevancy"] +
                            summary["context_precision"] + summary["context_recall"]
                        ) / 4.0
                    except Exception:
                        task.avg_overall_score = None
                    task.completed_scenarios = completed_cases
                    task.failed_scenarios = failed_cases
                    task.progress_percentage = 100
                    task.completed_at = datetime.now()
                    # 设置任务状态
                    if failed_cases == total_cases:
                        task.status = TaskStatus.FAILED
                    else:
                        task.status = TaskStatus.COMPLETED
                    db.commit()

                # 记录指标历史
                try:
                    sample_size = len(evaluation_results)
                    for name, value in summary.items():
                        db.add(EvaluationMetrics(
                            task_id=task_id,
                            metric_name=name,
                            metric_value=value,
                            metric_category="ragas",
                            calculation_method="mean",
                            sample_size=sample_size
                        ))
                    db.commit()
                except Exception as e:
                    logger.warning(f"保存指标历史失败: {e}")
        else:
            summary = None

        logger.info(f"真实RAG评测完成: 总计{total_cases}个用例，成功{completed_cases}个，失败{failed_cases}个")

        return {
            "status": "success",
            "results": evaluation_results,
            "summary": summary,
            "total_cases": total_cases,
            "completed_cases": completed_cases,
            "failed_cases": failed_cases
        }

    except Exception as e:
        logger.error(f"真实RAG评测失败: {e}")
        # 失败时更新任务状态
        if db and task_id:
            try:
                task = db.query(EvaluationTask).filter(EvaluationTask.task_id == task_id).first()
                if task:
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                    task.progress_percentage = 100
                    task.completed_at = datetime.now()
                    db.commit()
            except Exception:
                pass
        return {
            "status": "error",
            "error": str(e),
            "results": [],
            "summary": None
        }