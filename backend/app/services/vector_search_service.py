"""
向量搜索服务 - 基于SiliconFlow API
"""
import os
import requests
import numpy as np
import time
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from dotenv import load_dotenv
from pathlib import Path

# 加载环境变量（统一 backend/.env）
try:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(str(env_path))
    else:
        load_dotenv()
except Exception:
    load_dotenv()

logger = logging.getLogger(__name__)

class SiliconFlowEmbedder:
    """SiliconFlow API嵌入生成器"""
    
    def __init__(self, api_key: str = None, model: str = "BAAI/bge-m3"):
        self.api_key = api_key or os.getenv('SILICONFLOW_API_KEY')
        self.model = model
        self.base_url = "https://api.siliconflow.cn/v1/embeddings"
        
    def generate_embedding(self, text: str) -> List[float]:
        """生成单个文本的嵌入向量"""
        if not self.api_key:
            logger.warning("未设置SiliconFlow API密钥，使用随机向量")
            return np.random.normal(0, 0.1, 1024).tolist()
            
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "input": text,
                "encoding_format": "float"
            }
            
            response = requests.post(self.base_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            return result['data'][0]['embedding']
            
        except Exception as e:
            logger.error(f"SiliconFlow API调用失败: {e}")
            return np.random.normal(0, 0.1, 1024).tolist()

class VectorSearchService:
    """向量搜索服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.embedder = SiliconFlowEmbedder()
    
    def search_panels(
        self, 
        query_text: str, 
        top_k: int = 10, 
        similarity_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """搜索相似的科室"""
        try:
            query_vector = self.embedder.generate_embedding(query_text)
            vector_str = '[' + ','.join(map(str, query_vector)) + ']'
            
            query = text(f"""
                SELECT 
                    id,
                    semantic_id,
                    name_zh,
                    name_en,
                    description,
                    (1 - (embedding <=> '{vector_str}'::vector)) as similarity_score
                FROM panels 
                WHERE embedding IS NOT NULL
                AND (1 - (embedding <=> '{vector_str}'::vector)) >= {similarity_threshold}
                ORDER BY embedding <=> '{vector_str}'::vector
                LIMIT {top_k}
            """)
            
            result = self.db.execute(query)
            panels = []
            for row in result:
                panels.append({
                    "id": row.id,
                    "semantic_id": row.semantic_id,
                    "name_zh": row.name_zh,
                    "name_en": row.name_en,
                    "description": row.description,
                    "similarity_score": float(row.similarity_score)
                })
            
            return panels
            
        except Exception as e:
            logger.error(f"搜索科室失败: {e}")
            raise Exception(f"搜索科室失败: {str(e)}")
    
    def search_topics(
        self, 
        query_text: str, 
        top_k: int = 10, 
        similarity_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """搜索相似的主题"""
        try:
            query_vector = self.embedder.generate_embedding(query_text)
            vector_str = '[' + ','.join(map(str, query_vector)) + ']'
            
            query = text(f"""
                SELECT 
                    t.id,
                    t.semantic_id,
                    t.name_zh,
                    t.name_en,
                    t.description,
                    p.name_zh as panel_name,
                    (1 - (t.embedding <=> '{vector_str}'::vector)) as similarity_score
                FROM topics t
                LEFT JOIN panels p ON t.panel_id = p.id
                WHERE t.embedding IS NOT NULL
                AND (1 - (t.embedding <=> '{vector_str}'::vector)) >= {similarity_threshold}
                ORDER BY t.embedding <=> '{vector_str}'::vector
                LIMIT {top_k}
            """)
            
            result = self.db.execute(query)
            topics = []
            for row in result:
                topics.append({
                    "id": row.id,
                    "semantic_id": row.semantic_id,
                    "name_zh": row.name_zh,
                    "name_en": row.name_en,
                    "description": row.description,
                    "panel_name": row.panel_name,
                    "similarity_score": float(row.similarity_score)
                })
            
            return topics
            
        except Exception as e:
            logger.error(f"搜索主题失败: {e}")
            raise Exception(f"搜索主题失败: {str(e)}")
    
    def search_scenarios(
        self, 
        query_text: str, 
        top_k: int = 10, 
        similarity_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """搜索相似的临床场景"""
        try:
            query_vector = self.embedder.generate_embedding(query_text)
            vector_str = '[' + ','.join(map(str, query_vector)) + ']'
            
            query = text(f"""
                SELECT 
                    s.id,
                    s.semantic_id,
                    s.description_zh,
                    s.description_en,
                    s.patient_population,
                    s.risk_level,
                    s.age_group,
                    s.gender,
                    s.urgency_level,
                    s.symptom_category,
                    p.name_zh as panel_name,
                    t.name_zh as topic_name,
                    (1 - (s.embedding <=> '{vector_str}'::vector)) as similarity_score
                FROM clinical_scenarios s
                LEFT JOIN panels p ON s.panel_id = p.id
                LEFT JOIN topics t ON s.topic_id = t.id
                WHERE s.embedding IS NOT NULL
                AND (1 - (s.embedding <=> '{vector_str}'::vector)) >= {similarity_threshold}
                ORDER BY s.embedding <=> '{vector_str}'::vector
                LIMIT {top_k}
            """)
            
            result = self.db.execute(query)
            scenarios = []
            for row in result:
                scenarios.append({
                    "id": row.id,
                    "semantic_id": row.semantic_id,
                    "description_zh": row.description_zh,
                    "description_en": row.description_en,
                    "patient_population": row.patient_population,
                    "risk_level": row.risk_level,
                    "age_group": row.age_group,
                    "gender": row.gender,
                    "urgency_level": row.urgency_level,
                    "symptom_category": row.symptom_category,
                    "panel_name": row.panel_name,
                    "topic_name": row.topic_name,
                    "similarity_score": float(row.similarity_score)
                })
            
            return scenarios
            
        except Exception as e:
            logger.error(f"搜索临床场景失败: {e}")
            raise Exception(f"搜索临床场景失败: {str(e)}")
    
    def search_procedures(
        self, 
        query_text: str, 
        top_k: int = 10, 
        similarity_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """搜索相似的检查项目"""
        try:
            query_vector = self.embedder.generate_embedding(query_text)
            vector_str = '[' + ','.join(map(str, query_vector)) + ']'
            
            query = text(f"""
                SELECT 
                    p.id,
                    p.semantic_id,
                    p.name_zh,
                    p.name_en,
                    p.modality,
                    p.body_part,
                    p.contrast_used,
                    p.radiation_level,
                    p.exam_duration,
                    p.preparation_required,
                    p.description_zh,
                    (1 - (p.embedding <=> '{vector_str}'::vector)) as similarity_score
                FROM procedure_dictionary p
                WHERE p.embedding IS NOT NULL
                AND (1 - (p.embedding <=> '{vector_str}'::vector)) >= {similarity_threshold}
                ORDER BY p.embedding <=> '{vector_str}'::vector
                LIMIT {top_k}
            """)
            
            result = self.db.execute(query)
            procedures = []
            for row in result:
                procedures.append({
                    "id": row.id,
                    "semantic_id": row.semantic_id,
                    "name_zh": row.name_zh,
                    "name_en": row.name_en,
                    "modality": row.modality,
                    "body_part": row.body_part,
                    "contrast_used": row.contrast_used,
                    "radiation_level": row.radiation_level,
                    "exam_duration": row.exam_duration,
                    "preparation_required": row.preparation_required,
                    "description_zh": row.description_zh,
                    "similarity_score": float(row.similarity_score)
                })
            
            return procedures
            
        except Exception as e:
            logger.error(f"搜索检查项目失败: {e}")
            raise Exception(f"搜索检查项目失败: {str(e)}")
    
    def search_recommendations(
        self, 
        query_text: str, 
        top_k: int = 10, 
        similarity_threshold: float = 0.0
    ) -> List[Dict[str, Any]]:
        """搜索相似的临床推荐"""
        try:
            query_vector = self.embedder.generate_embedding(query_text)
            vector_str = '[' + ','.join(map(str, query_vector)) + ']'
            
            query = text(f"""
                SELECT 
                    cr.id,
                    cr.semantic_id,
                    cr.appropriateness_rating,
                    cr.appropriateness_category_zh,
                    cr.reasoning_zh,
                    cr.evidence_level,
                    cr.pregnancy_safety,
                    cr.adult_radiation_dose,
                    cr.pediatric_radiation_dose,
                    s.description_zh as scenario_description,
                    s.patient_population,
                    s.risk_level,
                    pd.name_zh as procedure_name,
                    pd.modality,
                    pd.body_part,
                    p.name_zh as panel_name,
                    t.name_zh as topic_name,
                    (1 - (cr.embedding <=> '{vector_str}'::vector)) as similarity_score
                FROM clinical_recommendations cr
                LEFT JOIN clinical_scenarios s ON cr.scenario_id = s.semantic_id
                LEFT JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
                LEFT JOIN panels p ON s.panel_id = p.id
                LEFT JOIN topics t ON s.topic_id = t.id
                WHERE cr.embedding IS NOT NULL
                AND (1 - (cr.embedding <=> '{vector_str}'::vector)) >= {similarity_threshold}
                ORDER BY cr.embedding <=> '{vector_str}'::vector
                LIMIT {top_k}
            """)
            
            result = self.db.execute(query)
            recommendations = []
            for row in result:
                recommendations.append({
                    "id": row.id,
                    "semantic_id": row.semantic_id,
                    "appropriateness_rating": row.appropriateness_rating,
                    "appropriateness_category_zh": row.appropriateness_category_zh,
                    "reasoning_zh": row.reasoning_zh,
                    "evidence_level": row.evidence_level,
                    "pregnancy_safety": row.pregnancy_safety,
                    "adult_radiation_dose": row.adult_radiation_dose,
                    "pediatric_radiation_dose": row.pediatric_radiation_dose,
                    "scenario_description": row.scenario_description,
                    "patient_population": row.patient_population,
                    "risk_level": row.risk_level,
                    "procedure_name": row.procedure_name,
                    "modality": row.modality,
                    "body_part": row.body_part,
                    "panel_name": row.panel_name,
                    "topic_name": row.topic_name,
                    "similarity_score": float(row.similarity_score)
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"搜索临床推荐失败: {e}")
            raise Exception(f"搜索临床推荐失败: {str(e)}")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        try:
            stats = {}
            
            # 统计各表记录数
            tables = ['panels', 'topics', 'clinical_scenarios', 'procedure_dictionary', 'clinical_recommendations']
            for table in tables:
                query = text(f"SELECT COUNT(*) as count FROM {table}")
                result = self.db.execute(query)
                count = result.scalar()
                stats[f"{table}_count"] = count
                
                # 统计向量覆盖率
                query = text(f"SELECT COUNT(*) as count FROM {table} WHERE embedding IS NOT NULL")
                result = self.db.execute(query)
                vector_count = result.scalar()
                coverage = (vector_count / count * 100) if count > 0 else 0
                stats[f"{table}_vector_coverage"] = round(coverage, 2)
            
            return stats
            
        except Exception as e:
            logger.error(f"获取数据库统计失败: {e}")
            raise Exception(f"获取数据库统计失败: {str(e)}")
