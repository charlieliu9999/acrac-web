"""
ACRAC核心服务 - 支持完整的数据管理和智能搜索
"""
import numpy as np
import time
import json
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, text, func
from datetime import datetime, date

from app.models.acrac_models import (
    Panel, Topic, ClinicalScenario, ProcedureDictionary, 
    ClinicalRecommendation, VectorSearchLog, DataUpdateHistory
)
# 延迟导入schemas以避免循环依赖
# schemas将在方法中按需导入

class ACRACService:
    """ACRAC核心服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ==================== Panel 操作 ====================
    
    def create_panel(self, panel_data: PanelCreate) -> PanelResponse:
        """创建Panel"""
        # 检查重复
        existing = self.db.query(Panel).filter(
            and_(Panel.name_en == panel_data.name_en, Panel.name_zh == panel_data.name_zh)
        ).first()
        if existing:
            raise ValueError(f"Panel已存在: {panel_data.name_zh}")
        
        # 生成语义化ID
        semantic_id = self._generate_next_semantic_id('panel')
        
        panel = Panel(
            semantic_id=semantic_id,
            name_en=panel_data.name_en,
            name_zh=panel_data.name_zh,
            description=panel_data.description or "",
            is_active=panel_data.is_active
        )
        
        self.db.add(panel)
        self.db.commit()
        self.db.refresh(panel)
        
        # 生成向量嵌入
        self._generate_panel_embedding(panel)
        
        # 记录操作历史
        self._log_data_update('panels', panel.semantic_id, 'INSERT', None, panel_data.dict())
        
        return PanelResponse.from_orm(panel)
    
    def get_panel(self, semantic_id: str) -> Optional[PanelResponse]:
        """获取Panel"""
        panel = self.db.query(Panel).filter(Panel.semantic_id == semantic_id).first()
        return PanelResponse.from_orm(panel) if panel else None
    
    def list_panels(self, active_only: bool = True, page: int = 1, page_size: int = 50) -> Tuple[List[PanelResponse], int]:
        """列出Panels"""
        query = self.db.query(Panel)
        if active_only:
            query = query.filter(Panel.is_active == True)
        
        total = query.count()
        panels = query.order_by(Panel.semantic_id).offset((page - 1) * page_size).limit(page_size).all()
        
        return [PanelResponse.from_orm(panel) for panel in panels], total
    
    def update_panel(self, semantic_id: str, panel_update: PanelUpdate) -> Optional[PanelResponse]:
        """更新Panel"""
        panel = self.db.query(Panel).filter(Panel.semantic_id == semantic_id).first()
        if not panel:
            return None
        
        # 记录旧数据
        old_data = {
            'name_en': panel.name_en,
            'name_zh': panel.name_zh,
            'description': panel.description,
            'is_active': panel.is_active
        }
        
        # 更新字段
        update_data = panel_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(panel, field, value)
        
        panel.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(panel)
        
        # 重新生成向量
        self._generate_panel_embedding(panel)
        
        # 记录操作历史
        self._log_data_update('panels', semantic_id, 'UPDATE', old_data, update_data)
        
        return PanelResponse.from_orm(panel)
    
    def delete_panel(self, semantic_id: str) -> bool:
        """删除Panel（级联删除）"""
        panel = self.db.query(Panel).filter(Panel.semantic_id == semantic_id).first()
        if not panel:
            return False
        
        # 记录删除的数据
        deleted_data = {
            'semantic_id': panel.semantic_id,
            'name_zh': panel.name_zh,
            'name_en': panel.name_en
        }
        
        self.db.delete(panel)
        self.db.commit()
        
        # 记录操作历史
        self._log_data_update('panels', semantic_id, 'DELETE', deleted_data, None)
        
        return True
    
    # ==================== Topic 操作 ====================
    
    def create_topic(self, topic_data: TopicCreate) -> TopicResponse:
        """创建Topic"""
        # 检查Panel是否存在
        panel = self.db.query(Panel).filter(Panel.id == topic_data.panel_id).first()
        if not panel:
            raise ValueError(f"Panel不存在: {topic_data.panel_id}")
        
        # 检查重复
        existing = self.db.query(Topic).filter(
            and_(
                Topic.panel_id == topic_data.panel_id,
                Topic.name_en == topic_data.name_en,
                Topic.name_zh == topic_data.name_zh
            )
        ).first()
        if existing:
            raise ValueError(f"Topic已存在: {topic_data.name_zh}")
        
        # 生成语义化ID
        semantic_id = self._generate_next_semantic_id('topic')
        
        topic = Topic(
            semantic_id=semantic_id,
            panel_id=topic_data.panel_id,
            name_en=topic_data.name_en,
            name_zh=topic_data.name_zh,
            description=topic_data.description or "",
            is_active=topic_data.is_active
        )
        
        self.db.add(topic)
        self.db.commit()
        self.db.refresh(topic)
        
        # 生成层次化向量嵌入
        self._generate_topic_embedding(topic)
        
        # 记录操作历史
        self._log_data_update('topics', topic.semantic_id, 'INSERT', None, topic_data.dict())
        
        return TopicResponse.from_orm(topic)
    
    def get_topics_by_panel(self, panel_semantic_id: str, active_only: bool = True) -> List[TopicResponse]:
        """获取Panel下的所有Topics"""
        panel = self.db.query(Panel).filter(Panel.semantic_id == panel_semantic_id).first()
        if not panel:
            return []
        
        query = self.db.query(Topic).filter(Topic.panel_id == panel.id)
        if active_only:
            query = query.filter(Topic.is_active == True)
        
        topics = query.order_by(Topic.semantic_id).all()
        return [TopicResponse.from_orm(topic) for topic in topics]
    
    # ==================== Clinical Scenario 操作 ====================
    
    def create_scenario(self, scenario_data: ClinicalScenarioCreate) -> ClinicalScenarioResponse:
        """创建Clinical Scenario"""
        # 验证Panel和Topic存在
        panel = self.db.query(Panel).filter(Panel.id == scenario_data.panel_id).first()
        topic = self.db.query(Topic).filter(Topic.id == scenario_data.topic_id).first()
        
        if not panel or not topic:
            raise ValueError("Panel或Topic不存在")
        
        # 生成语义化ID
        semantic_id = self._generate_next_semantic_id('scenario')
        
        scenario = ClinicalScenario(
            semantic_id=semantic_id,
            panel_id=scenario_data.panel_id,
            topic_id=scenario_data.topic_id,
            description_en=scenario_data.description_en,
            description_zh=scenario_data.description_zh,
            clinical_context=scenario_data.clinical_context,
            patient_population=scenario_data.patient_population,
            risk_level=scenario_data.risk_level,
            age_group=scenario_data.age_group,
            gender=scenario_data.gender,
            pregnancy_status=scenario_data.pregnancy_status,
            urgency_level=scenario_data.urgency_level,
            symptom_category=scenario_data.symptom_category,
            is_active=scenario_data.is_active
        )
        
        self.db.add(scenario)
        self.db.commit()
        self.db.refresh(scenario)
        
        # 生成层次化向量嵌入
        self._generate_scenario_embedding(scenario)
        
        return ClinicalScenarioResponse.from_orm(scenario)
    
    def get_scenarios_by_topic(self, topic_semantic_id: str, active_only: bool = True) -> List[ClinicalScenarioResponse]:
        """获取Topic下的所有Scenarios"""
        topic = self.db.query(Topic).filter(Topic.semantic_id == topic_semantic_id).first()
        if not topic:
            return []
        
        query = self.db.query(ClinicalScenario).filter(ClinicalScenario.topic_id == topic.id)
        if active_only:
            query = query.filter(ClinicalScenario.is_active == True)
        
        scenarios = query.order_by(ClinicalScenario.semantic_id).all()
        return [ClinicalScenarioResponse.from_orm(scenario) for scenario in scenarios]
    
    # ==================== Procedure Dictionary 操作 ====================
    
    def create_procedure(self, procedure_data: ProcedureDictionaryCreate) -> ProcedureDictionaryResponse:
        """创建Procedure"""
        # 检查重复
        existing = self.db.query(ProcedureDictionary).filter(
            and_(
                ProcedureDictionary.name_en == procedure_data.name_en,
                ProcedureDictionary.name_zh == procedure_data.name_zh
            )
        ).first()
        if existing:
            raise ValueError(f"检查项目已存在: {procedure_data.name_zh}")
        
        # 生成语义化ID
        semantic_id = self._generate_next_semantic_id('procedure')
        
        procedure = ProcedureDictionary(
            semantic_id=semantic_id,
            name_en=procedure_data.name_en,
            name_zh=procedure_data.name_zh,
            modality=procedure_data.modality,
            body_part=procedure_data.body_part,
            contrast_used=procedure_data.contrast_used,
            radiation_level=procedure_data.radiation_level,
            exam_duration=procedure_data.exam_duration,
            preparation_required=procedure_data.preparation_required,
            standard_code=procedure_data.standard_code,
            icd10_code=procedure_data.icd10_code,
            cpt_code=procedure_data.cpt_code,
            description_en=procedure_data.description_en,
            description_zh=procedure_data.description_zh,
            is_active=procedure_data.is_active
        )
        
        self.db.add(procedure)
        self.db.commit()
        self.db.refresh(procedure)
        
        # 生成向量嵌入
        self._generate_procedure_embedding(procedure)
        
        return ProcedureDictionaryResponse.from_orm(procedure)
    
    def search_procedures(self, modality: str = None, body_part: str = None, 
                         contrast_used: bool = None, active_only: bool = True) -> List[ProcedureDictionaryResponse]:
        """搜索检查项目"""
        query = self.db.query(ProcedureDictionary)
        
        if modality:
            query = query.filter(ProcedureDictionary.modality == modality)
        if body_part:
            query = query.filter(ProcedureDictionary.body_part == body_part)
        if contrast_used is not None:
            query = query.filter(ProcedureDictionary.contrast_used == contrast_used)
        if active_only:
            query = query.filter(ProcedureDictionary.is_active == True)
        
        procedures = query.order_by(ProcedureDictionary.semantic_id).all()
        return [ProcedureDictionaryResponse.from_orm(proc) for proc in procedures]
    
    # ==================== Clinical Recommendation 操作 ====================
    
    def create_recommendation(self, recommendation_data: ClinicalRecommendationCreate) -> ClinicalRecommendationResponse:
        """创建Clinical Recommendation"""
        # 验证Scenario和Procedure存在
        scenario = self.db.query(ClinicalScenario).filter(
            ClinicalScenario.semantic_id == recommendation_data.scenario_id
        ).first()
        procedure = self.db.query(ProcedureDictionary).filter(
            ProcedureDictionary.semantic_id == recommendation_data.procedure_id
        ).first()
        
        if not scenario or not procedure:
            raise ValueError("临床场景或检查项目不存在")
        
        # 检查重复
        existing = self.db.query(ClinicalRecommendation).filter(
            and_(
                ClinicalRecommendation.scenario_id == recommendation_data.scenario_id,
                ClinicalRecommendation.procedure_id == recommendation_data.procedure_id
            )
        ).first()
        if existing:
            raise ValueError(f"推荐关系已存在")
        
        # 生成语义化ID
        semantic_id = self._generate_next_semantic_id('recommendation')
        
        recommendation = ClinicalRecommendation(
            semantic_id=semantic_id,
            scenario_id=recommendation_data.scenario_id,
            procedure_id=recommendation_data.procedure_id,
            appropriateness_rating=recommendation_data.appropriateness_rating,
            appropriateness_category=recommendation_data.appropriateness_category,
            appropriateness_category_zh=recommendation_data.appropriateness_category_zh,
            reasoning_en=recommendation_data.reasoning_en,
            reasoning_zh=recommendation_data.reasoning_zh,
            evidence_level=recommendation_data.evidence_level,
            median_rating=recommendation_data.median_rating,
            rating_variance=recommendation_data.rating_variance,
            consensus_level=recommendation_data.consensus_level,
            adult_radiation_dose=recommendation_data.adult_radiation_dose,
            pediatric_radiation_dose=recommendation_data.pediatric_radiation_dose,
            contraindications=recommendation_data.contraindications,
            special_considerations=recommendation_data.special_considerations,
            pregnancy_safety=recommendation_data.pregnancy_safety,
            is_generated=recommendation_data.is_generated,
            confidence_score=recommendation_data.confidence_score,
            last_reviewed_date=recommendation_data.last_reviewed_date,
            reviewer_id=recommendation_data.reviewer_id,
            is_active=recommendation_data.is_active
        )
        
        self.db.add(recommendation)
        self.db.commit()
        self.db.refresh(recommendation)
        
        # 生成完整临床决策向量嵌入
        self._generate_recommendation_embedding(recommendation)
        
        return ClinicalRecommendationResponse.from_orm(recommendation)
    
    def get_recommendations_for_scenario(self, scenario_id: str, min_rating: int = None) -> List[RecommendationWithDetails]:
        """获取场景的所有推荐"""
        query = self.db.query(ClinicalRecommendation).filter(
            ClinicalRecommendation.scenario_id == scenario_id
        )
        
        if min_rating:
            query = query.filter(ClinicalRecommendation.appropriateness_rating >= min_rating)
        
        recommendations = query.order_by(ClinicalRecommendation.appropriateness_rating.desc()).all()
        
        return [self._build_recommendation_with_details(rec) for rec in recommendations]
    
    def get_recommendations_for_procedure(self, procedure_id: str, min_rating: int = None) -> List[RecommendationWithDetails]:
        """获取检查项目的所有推荐场景"""
        query = self.db.query(ClinicalRecommendation).filter(
            ClinicalRecommendation.procedure_id == procedure_id
        )
        
        if min_rating:
            query = query.filter(ClinicalRecommendation.appropriateness_rating >= min_rating)
        
        recommendations = query.order_by(ClinicalRecommendation.appropriateness_rating.desc()).all()
        
        return [self._build_recommendation_with_details(rec) for rec in recommendations]
    
    # ==================== 智能搜索功能 ====================
    
    def vector_search(self, request: VectorSearchRequest) -> VectorSearchResponse:
        """向量搜索"""
        start_time = time.time()
        
        # 生成查询向量
        query_vector = self._generate_query_vector(request.query_text)
        
        # 构建搜索SQL
        table_mapping = {
            'panels': 'panels',
            'topics': 'topics', 
            'scenarios': 'clinical_scenarios',
            'procedures': 'procedure_dictionary',
            'recommendations': 'clinical_recommendations'
        }
        
        if request.table_name not in table_mapping:
            raise ValueError(f"不支持的表名: {request.table_name}")
        
        table = table_mapping[request.table_name]
        
        # 执行向量搜索
        sql = f"""
            SELECT semantic_id, name_zh, name_en, description_zh,
                   (1 - (embedding <=> %s::vector)) as similarity
            FROM {table}
            WHERE (1 - (embedding <=> %s::vector)) > %s
            ORDER BY embedding <=> %s::vector
            LIMIT %s;
        """
        
        if request.table_name == 'recommendations':
            # 对于推荐表，需要特殊处理
            sql = """
                SELECT cr.semantic_id, pd.name_zh, pd.name_en, s.description_zh,
                       cr.appropriateness_rating,
                       (1 - (cr.embedding <=> %s::vector)) as similarity
                FROM clinical_recommendations cr
                JOIN clinical_scenarios s ON cr.scenario_id = s.semantic_id
                JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
                WHERE (1 - (cr.embedding <=> %s::vector)) > %s
                ORDER BY cr.embedding <=> %s::vector
                LIMIT %s;
            """
        
        # 应用过滤条件
        if request.filters:
            sql = self._apply_search_filters(sql, request.filters, table)
        
        # 执行查询
        result = self.db.execute(text(sql), [
            query_vector, query_vector, request.similarity_threshold, query_vector, request.limit
        ])
        
        results = []
        for row in result:
            if request.table_name == 'recommendations':
                results.append(VectorSearchResult(
                    semantic_id=row[0],
                    name_zh=row[1],
                    name_en=row[2],
                    description_zh=row[3],
                    appropriateness_rating=row[4],
                    similarity_score=row[5],
                    table_name=request.table_name
                ))
            else:
                results.append(VectorSearchResult(
                    semantic_id=row[0],
                    name_zh=row[1],
                    name_en=row[2],
                    description_zh=row[3],
                    similarity_score=row[4],
                    table_name=request.table_name
                ))
        
        search_time = int((time.time() - start_time) * 1000)
        
        # 记录搜索日志
        self._log_vector_search(request.query_text, request.table_name, query_vector, len(results), search_time)
        
        return VectorSearchResponse(
            query_text=request.query_text,
            table_name=request.table_name,
            total_results=len(results),
            search_time_ms=search_time,
            results=results
        )
    
    def intelligent_recommendation(self, request: IntelligentRecommendationRequest) -> IntelligentRecommendationResponse:
        """智能推荐"""
        start_time = time.time()
        
        # 构建增强查询文本
        enhanced_query = request.clinical_query
        if request.patient_profile:
            profile_text = self._build_patient_profile_text(request.patient_profile)
            enhanced_query = f"{request.clinical_query} {profile_text}"
        
        # 生成查询向量
        query_vector = self._generate_query_vector(enhanced_query)
        
        # 搜索临床推荐
        sql = """
            SELECT cr.semantic_id, cr.appropriateness_rating, cr.reasoning_zh,
                   s.semantic_id as scenario_sid, s.description_zh as scenario_desc,
                   s.patient_population, s.risk_level, s.age_group,
                   pd.semantic_id as procedure_sid, pd.name_zh as procedure_name,
                   pd.modality, pd.body_part, pd.radiation_level,
                   (1 - (cr.embedding <=> %s::vector)) as similarity
            FROM clinical_recommendations cr
            JOIN clinical_scenarios s ON cr.scenario_id = s.semantic_id
            JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
            WHERE (1 - (cr.embedding <=> %s::vector)) > 0.6
        """
        
        # 应用过滤条件
        if request.filters:
            if 'min_rating' in request.filters:
                sql += f" AND cr.appropriateness_rating >= {request.filters['min_rating']}"
            if 'modality' in request.filters:
                modalities = "', '".join(request.filters['modality'])
                sql += f" AND pd.modality IN ('{modalities}')"
            if 'pregnancy_safety' in request.filters:
                sql += f" AND cr.pregnancy_safety = '{request.filters['pregnancy_safety']}'"
        
        sql += " ORDER BY similarity DESC, cr.appropriateness_rating DESC LIMIT %s"
        
        result = self.db.execute(text(sql), [query_vector, query_vector, request.limit])
        
        recommendations = []
        for row in result:
            # 构建详细推荐信息
            scenario_info = ScenarioInRecommendation(
                semantic_id=row[3],
                description_zh=row[4],
                patient_population=row[5],
                risk_level=row[6],
                age_group=row[7]
            )
            
            procedure_info = ProcedureInRecommendation(
                semantic_id=row[8],
                name_zh=row[9],
                modality=row[10],
                body_part=row[11],
                radiation_level=row[12]
            )
            
            # 获取完整的推荐信息
            rec_obj = self.db.query(ClinicalRecommendation).filter(
                ClinicalRecommendation.semantic_id == row[0]
            ).first()
            
            if rec_obj:
                rec_response = ClinicalRecommendationResponse.from_orm(rec_obj)
                recommendation = RecommendationWithDetails(
                    **rec_response.dict(),
                    scenario=scenario_info,
                    procedure=procedure_info
                )
                recommendations.append(recommendation)
        
        search_time = int((time.time() - start_time) * 1000)
        
        return IntelligentRecommendationResponse(
            query=request.clinical_query,
            total_found=len(recommendations),
            recommendations=recommendations,
            search_time_ms=search_time
        )
    
    # ==================== 统计和健康检查 ====================
    
    def get_statistics(self) -> DataStatistics:
        """获取数据统计"""
        stats = {}
        
        # 基础统计
        stats['panels_count'] = self.db.query(Panel).count()
        stats['topics_count'] = self.db.query(Topic).count()
        stats['scenarios_count'] = self.db.query(ClinicalScenario).count()
        stats['procedures_count'] = self.db.query(ProcedureDictionary).count()
        stats['recommendations_count'] = self.db.query(ClinicalRecommendation).count()
        
        # 活跃数据统计
        stats['active_panels'] = self.db.query(Panel).filter(Panel.is_active == True).count()
        stats['active_topics'] = self.db.query(Topic).filter(Topic.is_active == True).count()
        stats['active_scenarios'] = self.db.query(ClinicalScenario).filter(ClinicalScenario.is_active == True).count()
        stats['active_procedures'] = self.db.query(ProcedureDictionary).filter(ProcedureDictionary.is_active == True).count()
        stats['active_recommendations'] = self.db.query(ClinicalRecommendation).filter(ClinicalRecommendation.is_active == True).count()
        
        # 生成数据统计
        stats['generated_recommendations'] = self.db.query(ClinicalRecommendation).filter(
            ClinicalRecommendation.is_generated == True
        ).count()
        
        # 向量嵌入覆盖率
        embedding_coverage = {}
        tables = [
            ('panels', Panel),
            ('topics', Topic),
            ('scenarios', ClinicalScenario),
            ('procedures', ProcedureDictionary),
            ('recommendations', ClinicalRecommendation)
        ]
        
        for table_name, model in tables:
            total = self.db.query(model).count()
            with_embedding = self.db.query(model).filter(model.embedding.isnot(None)).count()
            embedding_coverage[table_name] = {
                'total': total,
                'with_embedding': with_embedding,
                'coverage_percent': (with_embedding / total * 100) if total > 0 else 0
            }
        
        stats['embedding_coverage'] = embedding_coverage
        stats['last_updated'] = datetime.utcnow()
        
        return DataStatistics(**stats)
    
    def health_check(self) -> HealthCheckResponse:
        """健康检查"""
        try:
            # 检查数据库连接
            self.db.execute(text("SELECT 1"))
            db_status = "connected"
            
            # 检查向量索引
            try:
                self.db.execute(text("SELECT COUNT(*) FROM clinical_recommendations WHERE embedding IS NOT NULL LIMIT 1"))
                vector_status = "healthy"
            except Exception:
                vector_status = "error"
            
            # 统计总记录数和向量数
            total_records = (
                self.db.query(Panel).count() +
                self.db.query(Topic).count() +
                self.db.query(ClinicalScenario).count() +
                self.db.query(ProcedureDictionary).count() +
                self.db.query(ClinicalRecommendation).count()
            )
            
            total_vectors = (
                self.db.query(Panel).filter(Panel.embedding.isnot(None)).count() +
                self.db.query(Topic).filter(Topic.embedding.isnot(None)).count() +
                self.db.query(ClinicalScenario).filter(ClinicalScenario.embedding.isnot(None)).count() +
                self.db.query(ProcedureDictionary).filter(ProcedureDictionary.embedding.isnot(None)).count() +
                self.db.query(ClinicalRecommendation).filter(ClinicalRecommendation.embedding.isnot(None)).count()
            )
            
            return HealthCheckResponse(
                status="healthy",
                database_status=db_status,
                vector_index_status=vector_status,
                total_records=total_records,
                total_vectors=total_vectors,
                last_build_time=datetime.utcnow(),
                version="2.0.0"
            )
            
        except Exception as e:
            return HealthCheckResponse(
                status="unhealthy",
                database_status="error",
                vector_index_status="error", 
                total_records=0,
                total_vectors=0,
                last_build_time=None,
                version="2.0.0"
            )
    
    # ==================== 辅助方法 ====================
    
    def _generate_next_semantic_id(self, entity_type: str) -> str:
        """生成下一个语义化ID"""
        if entity_type == 'panel':
            result = self.db.execute(text("SELECT COALESCE(MAX(CAST(SUBSTRING(semantic_id FROM 2) AS INTEGER)), 0) + 1 FROM panels"))
            next_num = result.scalar()
            return f"P{next_num:04d}"
        elif entity_type == 'topic':
            result = self.db.execute(text("SELECT COALESCE(MAX(CAST(SUBSTRING(semantic_id FROM 2) AS INTEGER)), 0) + 1 FROM topics"))
            next_num = result.scalar()
            return f"T{next_num:04d}"
        elif entity_type == 'scenario':
            result = self.db.execute(text("SELECT COALESCE(MAX(CAST(SUBSTRING(semantic_id FROM 2) AS INTEGER)), 0) + 1 FROM clinical_scenarios"))
            next_num = result.scalar()
            return f"S{next_num:04d}"
        elif entity_type == 'procedure':
            result = self.db.execute(text("SELECT COALESCE(MAX(CAST(SUBSTRING(semantic_id FROM 3) AS INTEGER)), 0) + 1 FROM procedure_dictionary"))
            next_num = result.scalar()
            return f"PR{next_num:04d}"
        elif entity_type == 'recommendation':
            result = self.db.execute(text("SELECT COALESCE(MAX(CAST(SUBSTRING(semantic_id FROM 3) AS INTEGER)), 0) + 1 FROM clinical_recommendations"))
            next_num = result.scalar()
            return f"CR{next_num:06d}"
        else:
            raise ValueError(f"未知的实体类型: {entity_type}")
    
    def _generate_query_vector(self, text: str) -> List[float]:
        """生成查询向量"""
        # 这里使用随机向量模拟，实际应使用专业的嵌入模型
        return np.random.rand(1024).tolist()
    
    def _generate_panel_embedding(self, panel: Panel):
        """生成Panel向量嵌入"""
        try:
            text = f"科室: {panel.name_zh} {panel.name_en} {panel.description or ''}"
            vector = self._generate_query_vector(text)
            
            panel.embedding = vector
            self.db.commit()
        except Exception as e:
            print(f"生成Panel向量失败: {e}")
    
    def _generate_topic_embedding(self, topic: Topic):
        """生成Topic向量嵌入（层次化）"""
        try:
            panel = self.db.query(Panel).filter(Panel.id == topic.panel_id).first()
            panel_text = f"{panel.name_zh} {panel.name_en}" if panel else ""
            
            text = f"科室: {panel_text} | 主题: {topic.name_zh} {topic.name_en} {topic.description or ''}"
            vector = self._generate_query_vector(text)
            
            topic.embedding = vector
            self.db.commit()
        except Exception as e:
            print(f"生成Topic向量失败: {e}")
    
    def _generate_scenario_embedding(self, scenario: ClinicalScenario):
        """生成Scenario向量嵌入（层次化）"""
        try:
            topic = self.db.query(Topic).filter(Topic.id == scenario.topic_id).first()
            panel = self.db.query(Panel).filter(Panel.id == scenario.panel_id).first()
            
            text_parts = [
                f"科室: {panel.name_zh}" if panel else "",
                f"主题: {topic.name_zh}" if topic else "",
                f"临床场景: {scenario.description_zh}",
                f"患者人群: {scenario.patient_population or ''}",
                f"风险等级: {scenario.risk_level or ''}",
                f"年龄组: {scenario.age_group or ''}",
                f"性别: {scenario.gender or ''}",
                f"妊娠状态: {scenario.pregnancy_status or ''}"
            ]
            
            text = " | ".join([part for part in text_parts if part and not part.endswith(': ')])
            vector = self._generate_query_vector(text)
            
            scenario.embedding = vector
            self.db.commit()
        except Exception as e:
            print(f"生成Scenario向量失败: {e}")
    
    def _generate_procedure_embedding(self, procedure: ProcedureDictionary):
        """生成Procedure向量嵌入（独立）"""
        try:
            text_parts = [
                f"检查项目: {procedure.name_zh}",
                f"检查方式: {procedure.modality or ''}",
                f"检查部位: {procedure.body_part or ''}",
                f"对比剂: {'使用' if procedure.contrast_used else '不使用'}",
                f"辐射等级: {procedure.radiation_level or ''}",
                f"描述: {procedure.description_zh or ''}"
            ]
            
            text = " | ".join([part for part in text_parts if not part.endswith(': ')])
            vector = self._generate_query_vector(text)
            
            procedure.embedding = vector
            self.db.commit()
        except Exception as e:
            print(f"生成Procedure向量失败: {e}")
    
    def _generate_recommendation_embedding(self, recommendation: ClinicalRecommendation):
        """生成Recommendation向量嵌入（完整临床决策）"""
        try:
            # 获取关联信息
            scenario = self.db.query(ClinicalScenario).filter(
                ClinicalScenario.semantic_id == recommendation.scenario_id
            ).first()
            procedure = self.db.query(ProcedureDictionary).filter(
                ProcedureDictionary.semantic_id == recommendation.procedure_id
            ).first()
            
            if scenario and procedure:
                topic = self.db.query(Topic).filter(Topic.id == scenario.topic_id).first()
                panel = self.db.query(Panel).filter(Panel.id == scenario.panel_id).first()
                
                text_parts = [
                    f"科室: {panel.name_zh}" if panel else "",
                    f"主题: {topic.name_zh}" if topic else "",
                    f"临床场景: {scenario.description_zh}",
                    f"患者人群: {scenario.patient_population or ''}",
                    f"风险等级: {scenario.risk_level or ''}",
                    f"年龄组: {scenario.age_group or ''}",
                    f"检查项目: {procedure.name_zh}",
                    f"检查方式: {procedure.modality or ''}",
                    f"检查部位: {procedure.body_part or ''}",
                    f"适宜性评分: {recommendation.appropriateness_rating}分",
                    f"证据强度: {recommendation.evidence_level or ''}",
                    f"推荐理由: {recommendation.reasoning_zh or ''}"
                ]
                
                text = " | ".join([part for part in text_parts if part and not part.endswith(': ')])
                vector = self._generate_query_vector(text)
                
                recommendation.embedding = vector
                self.db.commit()
        except Exception as e:
            print(f"生成Recommendation向量失败: {e}")
    
    def _build_recommendation_with_details(self, recommendation: ClinicalRecommendation) -> RecommendationWithDetails:
        """构建包含详情的推荐"""
        # 获取场景信息
        scenario = self.db.query(ClinicalScenario).filter(
            ClinicalScenario.semantic_id == recommendation.scenario_id
        ).first()
        
        # 获取检查项目信息
        procedure = self.db.query(ProcedureDictionary).filter(
            ProcedureDictionary.semantic_id == recommendation.procedure_id
        ).first()
        
        scenario_info = ScenarioInRecommendation.from_orm(scenario) if scenario else None
        procedure_info = ProcedureInRecommendation.from_orm(procedure) if procedure else None
        
        rec_response = ClinicalRecommendationResponse.from_orm(recommendation)
        
        return RecommendationWithDetails(
            **rec_response.dict(),
            scenario=scenario_info,
            procedure=procedure_info
        )
    
    def _apply_search_filters(self, sql: str, filters: Dict, table: str) -> str:
        """应用搜索过滤条件"""
        # 根据不同表类型应用不同的过滤逻辑
        # 这里简化处理，实际可以更复杂
        return sql
    
    def _build_patient_profile_text(self, profile: Dict) -> str:
        """构建患者特征文本"""
        parts = []
        if 'age' in profile:
            parts.append(f"年龄{profile['age']}岁")
        if 'gender' in profile:
            parts.append(f"性别{profile['gender']}")
        if 'pregnancy_status' in profile:
            parts.append(f"{profile['pregnancy_status']}")
        if 'risk_level' in profile:
            parts.append(f"{profile['risk_level']}")
        
        return " ".join(parts)
    
    def _log_vector_search(self, query_text: str, query_type: str, search_vector: List[float], 
                          results_count: int, search_time_ms: int, user_id: int = None):
        """记录向量搜索日志"""
        try:
            log = VectorSearchLog(
                query_text=query_text,
                query_type=query_type,
                search_vector=search_vector,
                results_count=results_count,
                search_time_ms=search_time_ms,
                user_id=user_id
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            print(f"记录搜索日志失败: {e}")
    
    def _log_data_update(self, table_name: str, record_id: str, operation: str, 
                        old_data: Dict = None, new_data: Dict = None, user_id: int = None):
        """记录数据更新历史"""
        try:
            history = DataUpdateHistory(
                table_name=table_name,
                record_id=record_id,
                operation=operation,
                old_data=json.dumps(old_data, ensure_ascii=False) if old_data else None,
                new_data=json.dumps(new_data, ensure_ascii=False) if new_data else None,
                user_id=user_id
            )
            self.db.add(history)
            self.db.commit()
        except Exception as e:
            print(f"记录数据更新历史失败: {e}")
