#!/usr/bin/env python3
"""
ACRAC完整数据库和向量库构建脚本
从CSV文件构建完整的数据库和向量嵌入
"""
import sys
import os
from pathlib import Path
import argparse
import json
from datetime import datetime
import re

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import psycopg2
import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CompleteDataBuilder:
    """完整数据库和向量库构建器"""
    
    def __init__(self, db_config: Dict = None):
        self.db_config = db_config or {
            "host": "localhost",
            "port": "5432", 
            "database": "acrac_db",
            "user": "postgres",
            "password": "password"
        }
        self.conn = None
        self.cursor = None
        
        # 统计信息
        self.stats = {
            'panels_created': 0,
            'topics_created': 0,
            'scenarios_created': 0,
            'procedures_created': 0,
            'recommendations_created': 0,
            'vectors_generated': 0,
            'errors': []
        }
        
        # ID计数器
        self.id_counters = {
            'panel': 0,
            'topic': 0,
            'scenario': 0,
            'procedure': 0,
            'recommendation': 0
        }
        
        # 缓存映射
        self.entity_cache = {
            'panels': {},      # name_key -> semantic_id
            'topics': {},      # name_key -> semantic_id
            'scenarios': {},   # desc_key -> semantic_id
            'procedures': {}   # name_key -> semantic_id
        }
    
    def connect(self) -> bool:
        """连接数据库"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor()
            logger.info("✅ 数据库连接成功")
            return True
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("✅ 数据库连接已关闭")
    
    def create_complete_schema(self) -> bool:
        """创建完整的数据库架构"""
        logger.info("🏗️ 创建完整数据库架构...")
        
        try:
            # 删除现有表（如果存在）
            drop_tables = [
                "DROP TABLE IF EXISTS vector_search_logs CASCADE;",
                "DROP TABLE IF EXISTS data_update_history CASCADE;",
                "DROP TABLE IF EXISTS clinical_recommendations CASCADE;",
                "DROP TABLE IF EXISTS procedure_dictionary CASCADE;",
                "DROP TABLE IF EXISTS clinical_scenarios CASCADE;",
                "DROP TABLE IF EXISTS topics CASCADE;",
                "DROP TABLE IF EXISTS panels CASCADE;"
            ]
            
            for drop_sql in drop_tables:
                self.cursor.execute(drop_sql)
            
            # 创建新表
            schema_sqls = [
                # 科室表
                """
                CREATE TABLE panels (
                    id SERIAL PRIMARY KEY,
                    semantic_id VARCHAR(20) UNIQUE NOT NULL,
                    name_en VARCHAR(255) NOT NULL,
                    name_zh VARCHAR(255) NOT NULL,
                    description TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    embedding VECTOR(1024)
                );
                """,
                
                # 主题表
                """
                CREATE TABLE topics (
                    id SERIAL PRIMARY KEY,
                    semantic_id VARCHAR(20) UNIQUE NOT NULL,
                    panel_id INTEGER REFERENCES panels(id) ON DELETE CASCADE,
                    name_en VARCHAR(500) NOT NULL,
                    name_zh VARCHAR(500) NOT NULL,
                    description TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    embedding VECTOR(1024)
                );
                """,
                
                # 临床场景表
                """
                CREATE TABLE clinical_scenarios (
                    id SERIAL PRIMARY KEY,
                    semantic_id VARCHAR(20) UNIQUE NOT NULL,
                    panel_id INTEGER REFERENCES panels(id) ON DELETE CASCADE,
                    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
                    description_en TEXT NOT NULL,
                    description_zh TEXT NOT NULL,
                    clinical_context TEXT,
                    patient_population VARCHAR(100),
                    risk_level VARCHAR(50),
                    age_group VARCHAR(50),
                    gender VARCHAR(20),
                    pregnancy_status VARCHAR(50),
                    urgency_level VARCHAR(50),
                    symptom_category VARCHAR(100),
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    embedding VECTOR(1024)
                );
                """,
                
                # 检查项目字典表
                """
                CREATE TABLE procedure_dictionary (
                    id SERIAL PRIMARY KEY,
                    semantic_id VARCHAR(20) UNIQUE NOT NULL,
                    name_en VARCHAR(500) NOT NULL,
                    name_zh VARCHAR(500) NOT NULL,
                    modality VARCHAR(50),
                    body_part VARCHAR(100),
                    contrast_used BOOLEAN DEFAULT FALSE,
                    radiation_level VARCHAR(50),
                    exam_duration INTEGER,
                    preparation_required BOOLEAN DEFAULT FALSE,
                    standard_code VARCHAR(50),
                    icd10_code VARCHAR(20),
                    cpt_code VARCHAR(20),
                    description_en TEXT,
                    description_zh TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    embedding VECTOR(1024)
                );
                """,
                
                # 临床推荐关系表
                """
                CREATE TABLE clinical_recommendations (
                    id SERIAL PRIMARY KEY,
                    semantic_id VARCHAR(50) UNIQUE NOT NULL,
                    scenario_id VARCHAR(20) REFERENCES clinical_scenarios(semantic_id) ON DELETE CASCADE,
                    procedure_id VARCHAR(20) REFERENCES procedure_dictionary(semantic_id) ON DELETE CASCADE,
                    appropriateness_rating INTEGER CHECK (appropriateness_rating >= 1 AND appropriateness_rating <= 9),
                    appropriateness_category VARCHAR(100),
                    appropriateness_category_zh VARCHAR(100),
                    reasoning_en TEXT,
                    reasoning_zh TEXT,
                    evidence_level VARCHAR(50),
                    median_rating FLOAT,
                    rating_variance FLOAT,
                    consensus_level VARCHAR(50),
                    adult_radiation_dose VARCHAR(50),
                    pediatric_radiation_dose VARCHAR(50),
                    contraindications TEXT,
                    special_considerations TEXT,
                    pregnancy_safety VARCHAR(50),
                    is_generated BOOLEAN DEFAULT FALSE,
                    confidence_score FLOAT DEFAULT 1.0,
                    last_reviewed_date DATE,
                    reviewer_id INTEGER,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    embedding VECTOR(1024),
                    UNIQUE(scenario_id, procedure_id)
                );
                """,
                
                # 向量搜索日志表
                """
                CREATE TABLE vector_search_logs (
                    id SERIAL PRIMARY KEY,
                    query_text TEXT NOT NULL,
                    query_type VARCHAR(50),
                    search_vector VECTOR(1024),
                    results_count INTEGER,
                    search_time_ms INTEGER,
                    user_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """,
                
                # 数据更新历史表
                """
                CREATE TABLE data_update_history (
                    id SERIAL PRIMARY KEY,
                    table_name VARCHAR(50) NOT NULL,
                    record_id VARCHAR(50) NOT NULL,
                    operation VARCHAR(20) NOT NULL,
                    old_data JSONB,
                    new_data JSONB,
                    user_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            ]
            
            for sql in schema_sqls:
                self.cursor.execute(sql)
            
            self.conn.commit()
            logger.info("✅ 数据库架构创建完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 创建数据库架构失败: {e}")
            self.conn.rollback()
            return False
    
    def create_indexes(self) -> bool:
        """创建索引"""
        logger.info("📊 创建数据库索引...")
        
        try:
            index_sqls = [
                # 基础索引
                "CREATE INDEX idx_panels_semantic_id ON panels (semantic_id);",
                "CREATE INDEX idx_topics_semantic_id ON topics (semantic_id);",
                "CREATE INDEX idx_topics_panel_id ON topics (panel_id);",
                "CREATE INDEX idx_scenarios_semantic_id ON clinical_scenarios (semantic_id);",
                "CREATE INDEX idx_scenarios_panel_topic ON clinical_scenarios (panel_id, topic_id);",
                "CREATE INDEX idx_procedures_semantic_id ON procedure_dictionary (semantic_id);",
                "CREATE INDEX idx_procedures_modality ON procedure_dictionary (modality);",
                "CREATE INDEX idx_recommendations_semantic_id ON clinical_recommendations (semantic_id);",
                "CREATE INDEX idx_recommendations_scenario ON clinical_recommendations (scenario_id);",
                "CREATE INDEX idx_recommendations_procedure ON clinical_recommendations (procedure_id);",
                "CREATE INDEX idx_recommendations_rating ON clinical_recommendations (appropriateness_rating);",
                
                # 复合索引
                "CREATE INDEX idx_scenarios_patient_features ON clinical_scenarios (patient_population, risk_level, age_group);",
                "CREATE INDEX idx_procedures_attributes ON procedure_dictionary (modality, body_part, contrast_used);",
                "CREATE INDEX idx_recommendations_quality ON clinical_recommendations (appropriateness_rating, evidence_level, confidence_score);",
                
                # 向量索引
                "CREATE INDEX idx_panels_embedding ON panels USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);",
                "CREATE INDEX idx_topics_embedding ON topics USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);",
                "CREATE INDEX idx_scenarios_embedding ON clinical_scenarios USING ivfflat (embedding vector_cosine_ops) WITH (lists = 500);",
                "CREATE INDEX idx_procedures_embedding ON procedure_dictionary USING ivfflat (embedding vector_cosine_ops) WITH (lists = 500);",
                "CREATE INDEX idx_recommendations_embedding ON clinical_recommendations USING ivfflat (embedding vector_cosine_ops) WITH (lists = 1000);"
            ]
            
            for sql in index_sqls:
                try:
                    self.cursor.execute(sql)
                    logger.info(f"   ✅ 创建索引")
                except Exception as e:
                    logger.warning(f"   ⚠️ 索引创建失败: {e}")
            
            self.conn.commit()
            logger.info("✅ 数据库索引创建完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 创建索引失败: {e}")
            self.conn.rollback()
            return False
    
    def load_csv_data(self, csv_path: str) -> pd.DataFrame:
        """加载CSV数据"""
        logger.info(f"📂 加载CSV数据: {csv_path}")
        
        try:
            if not os.path.exists(csv_path):
                raise FileNotFoundError(f"CSV文件不存在: {csv_path}")
            
            # 尝试不同编码和分隔符
            for encoding in ['utf-16', 'utf-8', 'gbk', 'gb2312']:
                for sep in ['\t', ',', ';']:
                    try:
                        df = pd.read_csv(csv_path, encoding=encoding, sep=sep)
                        if len(df.columns) >= 15:  # 确保有足够的列
                            logger.info(f"✅ 使用编码 {encoding} 和分隔符 '{sep}' 成功读取")
                            break
                    except Exception:
                        continue
                else:
                    continue
                break
            else:
                raise ValueError("无法读取CSV文件，尝试了多种编码和分隔符")
            
            # 数据清洗
            df = df.fillna('')
            
            # 标准化列名
            expected_columns = [
                'Panel', 'Panel Translation', 'Topic', 'Topic Translation',
                'Variant', 'Variant Translation', 'Appropriateness Category',
                'Appropriateness Category Translation', 'Rating', 'Median',
                'Procedure', 'Standardized', 'Recommendation', 'Recommendation Translation',
                'Generated', 'SOE', 'Adult RRL', 'Peds RRL'
            ]
            
            # 检查必要列是否存在
            missing_columns = [col for col in expected_columns[:12] if col not in df.columns]
            if missing_columns:
                raise ValueError(f"缺少必要列: {missing_columns}")
            
            logger.info(f"📊 数据加载完成: {len(df)} 行, {len(df.columns)} 列")
            return df
            
        except Exception as e:
            logger.error(f"❌ 加载CSV数据失败: {e}")
            return None
    
    def build_complete_database(self, df: pd.DataFrame) -> bool:
        """构建完整数据库"""
        logger.info("🚀 开始构建完整数据库...")
        
        try:
            # 第一步：预处理数据，提取唯一实体
            logger.info("📝 步骤1: 预处理数据")
            processed_data = self._preprocess_data(df)
            
            # 第二步：构建Panels
            logger.info("📝 步骤2: 构建Panels")
            self._build_panels(processed_data['panels'])
            
            # 第三步：构建Topics
            logger.info("📝 步骤3: 构建Topics")
            self._build_topics(processed_data['topics'])
            
            # 第四步：构建Clinical Scenarios
            logger.info("📝 步骤4: 构建Clinical Scenarios")
            self._build_clinical_scenarios(processed_data['scenarios'])
            
            # 第五步：构建Procedure Dictionary
            logger.info("📝 步骤5: 构建Procedure Dictionary")
            self._build_procedure_dictionary(processed_data['procedures'])
            
            # 第六步：构建Clinical Recommendations
            logger.info("📝 步骤6: 构建Clinical Recommendations")
            self._build_clinical_recommendations(processed_data['recommendations'])
            
            # 第七步：生成向量嵌入
            logger.info("📝 步骤7: 生成向量嵌入")
            self._generate_all_embeddings()
            
            logger.info("✅ 完整数据库构建完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 构建数据库失败: {e}")
            self.conn.rollback()
            return False
    
    def _preprocess_data(self, df: pd.DataFrame) -> Dict[str, List]:
        """预处理数据，提取唯一实体"""
        logger.info("🔄 预处理数据...")
        
        panels = {}
        topics = {}
        scenarios = {}
        procedures = {}
        recommendations = []
        
        for _, row in df.iterrows():
            # 提取Panel
            panel_key = f"{row['Panel']}|||{row['Panel Translation']}"
            if panel_key not in panels:
                panels[panel_key] = {
                    'name_en': row['Panel'],
                    'name_zh': row['Panel Translation']
                }
            
            # 提取Topic
            topic_key = f"{panel_key}|||{row['Topic']}|||{row['Topic Translation']}"
            if topic_key not in topics:
                topics[topic_key] = {
                    'panel_key': panel_key,
                    'name_en': row['Topic'],
                    'name_zh': row['Topic Translation']
                }
            
            # 提取Scenario
            scenario_key = f"{topic_key}|||{row['Variant']}|||{row['Variant Translation']}"
            if scenario_key not in scenarios:
                scenarios[scenario_key] = {
                    'panel_key': panel_key,
                    'topic_key': topic_key,
                    'description_en': row['Variant'],
                    'description_zh': row['Variant Translation']
                }
            
            # 提取Procedure
            proc_key = f"{row['Procedure']}|||{row['Standardized']}"
            if proc_key not in procedures:
                procedures[proc_key] = {
                    'name_en': row['Procedure'],
                    'name_zh': row['Standardized']
                }
            
            # 构建Recommendation
            recommendations.append({
                'scenario_key': scenario_key,
                'procedure_key': proc_key,
                'appropriateness_rating': self._safe_int(row.get('Rating')),
                'appropriateness_category': row.get('Appropriateness Category', ''),
                'appropriateness_category_zh': row.get('Appropriateness Category Translation', ''),
                'reasoning_en': row.get('Recommendation', ''),
                'reasoning_zh': row.get('Recommendation Translation', ''),
                'evidence_level': row.get('SOE', ''),
                'median_rating': self._safe_float(row.get('Median')),
                'adult_radiation_dose': row.get('Adult RRL', ''),
                'pediatric_radiation_dose': row.get('Peds RRL', ''),
                'is_generated': self._safe_bool(row.get('Generated'))
            })
        
        logger.info(f"   预处理完成: {len(panels)} Panels, {len(topics)} Topics, {len(scenarios)} Scenarios, {len(procedures)} Procedures, {len(recommendations)} Recommendations")
        
        return {
            'panels': list(panels.values()),
            'topics': list(topics.values()),
            'scenarios': list(scenarios.values()),
            'procedures': list(procedures.values()),
            'recommendations': recommendations
        }
    
    def _build_panels(self, panels_data: List[Dict]):
        """构建Panels"""
        for panel_data in panels_data:
            self.id_counters['panel'] += 1
            semantic_id = f"P{self.id_counters['panel']:04d}"
            
            self.cursor.execute("""
                INSERT INTO panels (semantic_id, name_en, name_zh, is_active)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """, (semantic_id, panel_data['name_en'], panel_data['name_zh'], True))
            
            panel_id = self.cursor.fetchone()[0]
            
            # 缓存映射
            panel_key = f"{panel_data['name_en']}|||{panel_data['name_zh']}"
            self.entity_cache['panels'][panel_key] = semantic_id
            
            self.stats['panels_created'] += 1
        
        self.conn.commit()
        logger.info(f"   ✅ 创建 {len(panels_data)} 个Panels")
    
    def _build_topics(self, topics_data: List[Dict]):
        """构建Topics"""
        for topic_data in topics_data:
            panel_semantic_id = self.entity_cache['panels'][topic_data['panel_key']]
            
            # 获取panel_id
            self.cursor.execute("SELECT id FROM panels WHERE semantic_id = %s", (panel_semantic_id,))
            panel_id = self.cursor.fetchone()[0]
            
            self.id_counters['topic'] += 1
            semantic_id = f"T{self.id_counters['topic']:04d}"
            
            self.cursor.execute("""
                INSERT INTO topics (semantic_id, panel_id, name_en, name_zh, is_active)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (semantic_id, panel_id, topic_data['name_en'], topic_data['name_zh'], True))
            
            topic_id = self.cursor.fetchone()[0]
            
            # 缓存映射
            topic_key = f"{topic_data['panel_key']}|||{topic_data['name_en']}|||{topic_data['name_zh']}"
            self.entity_cache['topics'][topic_key] = semantic_id
            
            self.stats['topics_created'] += 1
        
        self.conn.commit()
        logger.info(f"   ✅ 创建 {len(topics_data)} 个Topics")
    
    def _build_clinical_scenarios(self, scenarios_data: List[Dict]):
        """构建Clinical Scenarios"""
        for scenario_data in scenarios_data:
            panel_semantic_id = self.entity_cache['panels'][scenario_data['panel_key']]
            topic_semantic_id = self.entity_cache['topics'][scenario_data['topic_key']]
            
            # 获取panel_id和topic_id
            self.cursor.execute("SELECT id FROM panels WHERE semantic_id = %s", (panel_semantic_id,))
            panel_id = self.cursor.fetchone()[0]
            self.cursor.execute("SELECT id FROM topics WHERE semantic_id = %s", (topic_semantic_id,))
            topic_id = self.cursor.fetchone()[0]
            
            self.id_counters['scenario'] += 1
            semantic_id = f"S{self.id_counters['scenario']:04d}"
            
            # 提取患者特征
            patient_features = self._extract_patient_features(
                scenario_data['description_en'], 
                scenario_data['description_zh']
            )
            
            self.cursor.execute("""
                INSERT INTO clinical_scenarios 
                (semantic_id, panel_id, topic_id, description_en, description_zh,
                 patient_population, risk_level, age_group, gender, pregnancy_status,
                 urgency_level, symptom_category, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (semantic_id, panel_id, topic_id, scenario_data['description_en'], scenario_data['description_zh'],
                  patient_features['patient_population'], patient_features['risk_level'], 
                  patient_features['age_group'], patient_features['gender'], 
                  patient_features['pregnancy_status'], patient_features['urgency_level'],
                  patient_features['symptom_category'], True))
            
            scenario_id = self.cursor.fetchone()[0]
            
            # 缓存映射
            scenario_key = f"{scenario_data['topic_key']}|||{scenario_data['description_en']}|||{scenario_data['description_zh']}"
            self.entity_cache['scenarios'][scenario_key] = semantic_id
            
            self.stats['scenarios_created'] += 1
        
        self.conn.commit()
        logger.info(f"   ✅ 创建 {len(scenarios_data)} 个Clinical Scenarios")
    
    def _build_procedure_dictionary(self, procedures_data: List[Dict]):
        """构建Procedure Dictionary"""
        for proc_data in procedures_data:
            self.id_counters['procedure'] += 1
            semantic_id = f"PR{self.id_counters['procedure']:04d}"
            
            # 提取检查属性
            attributes = self._extract_procedure_attributes(
                proc_data['name_en'], 
                proc_data['name_zh']
            )
            
            self.cursor.execute("""
                INSERT INTO procedure_dictionary 
                (semantic_id, name_en, name_zh, modality, body_part, contrast_used,
                 radiation_level, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (semantic_id, proc_data['name_en'], proc_data['name_zh'],
                  attributes['modality'], attributes['body_part'], attributes['contrast_used'],
                  attributes['radiation_level'], True))
            
            proc_id = self.cursor.fetchone()[0]
            
            # 缓存映射
            proc_key = f"{proc_data['name_en']}|||{proc_data['name_zh']}"
            self.entity_cache['procedures'][proc_key] = semantic_id
            
            self.stats['procedures_created'] += 1
        
        self.conn.commit()
        logger.info(f"   ✅ 创建 {len(procedures_data)} 个Procedures")
    
    def _build_clinical_recommendations(self, recommendations_data: List[Dict]):
        """构建Clinical Recommendations"""
        for rec_data in recommendations_data:
            scenario_semantic_id = self.entity_cache['scenarios'][rec_data['scenario_key']]
            procedure_semantic_id = self.entity_cache['procedures'][rec_data['procedure_key']]
            
            self.id_counters['recommendation'] += 1
            semantic_id = f"CR{self.id_counters['recommendation']:06d}"
            
            # 评估妊娠安全性
            pregnancy_safety = self._assess_pregnancy_safety(
                rec_data['adult_radiation_dose'],
                rec_data['reasoning_zh']
            )
            
            self.cursor.execute("""
                INSERT INTO clinical_recommendations 
                (semantic_id, scenario_id, procedure_id, appropriateness_rating,
                 appropriateness_category, appropriateness_category_zh, reasoning_en, reasoning_zh,
                 evidence_level, median_rating, adult_radiation_dose, pediatric_radiation_dose,
                 pregnancy_safety, is_generated, confidence_score, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (scenario_id, procedure_id) DO NOTHING
                RETURNING id;
            """, (semantic_id, scenario_semantic_id, procedure_semantic_id, rec_data['appropriateness_rating'],
                  rec_data['appropriateness_category'], rec_data['appropriateness_category_zh'],
                  rec_data['reasoning_en'], rec_data['reasoning_zh'], rec_data['evidence_level'],
                  rec_data['median_rating'], rec_data['adult_radiation_dose'], rec_data['pediatric_radiation_dose'],
                  pregnancy_safety, rec_data['is_generated'], 1.0, True))
            
            result = self.cursor.fetchone()
            if result:
                self.stats['recommendations_created'] += 1
        
        self.conn.commit()
        logger.info(f"   ✅ 创建 {self.stats['recommendations_created']} 个Clinical Recommendations")
    
    def _generate_all_embeddings(self):
        """生成所有向量嵌入"""
        logger.info("🧠 生成向量嵌入...")
        
        # 生成Panel向量
        self._generate_panel_embeddings()
        
        # 生成Topic向量（层次化：包含Panel信息）
        self._generate_topic_embeddings()
        
        # 生成Scenario向量（层次化：包含Panel+Topic信息）
        self._generate_scenario_embeddings()
        
        # 生成Procedure向量（独立）
        self._generate_procedure_embeddings()
        
        # 生成Recommendation向量（完整临床决策）
        self._generate_recommendation_embeddings()
        
        logger.info(f"   ✅ 生成 {self.stats['vectors_generated']} 个向量嵌入")
    
    def _generate_panel_embeddings(self):
        """生成Panel向量"""
        self.cursor.execute("SELECT id, semantic_id, name_en, name_zh, description FROM panels;")
        panels = self.cursor.fetchall()
        
        for panel in panels:
            panel_id, semantic_id, name_en, name_zh, description = panel
            
            # 构建向量化文本
            text = f"科室: {name_zh} {name_en} {description or ''}"
            
            # 生成向量（实际应使用专业模型）
            embedding = np.random.rand(1024).tolist()
            
            self.cursor.execute("""
                UPDATE panels SET embedding = %s WHERE id = %s;
            """, (embedding, panel_id))
            
            self.stats['vectors_generated'] += 1
        
        self.conn.commit()
    
    def _generate_topic_embeddings(self):
        """生成Topic向量（层次化）"""
        self.cursor.execute("""
            SELECT t.id, t.semantic_id, t.name_en, t.name_zh, t.description,
                   p.name_zh as panel_name_zh, p.name_en as panel_name_en
            FROM topics t
            JOIN panels p ON t.panel_id = p.id;
        """)
        topics = self.cursor.fetchall()
        
        for topic in topics:
            topic_id, semantic_id, name_en, name_zh, description, panel_name_zh, panel_name_en = topic
            
            # 构建层次化向量化文本
            text = f"科室: {panel_name_zh} {panel_name_en} | 主题: {name_zh} {name_en} {description or ''}"
            
            # 生成向量
            embedding = np.random.rand(1024).tolist()
            
            self.cursor.execute("""
                UPDATE topics SET embedding = %s WHERE id = %s;
            """, (embedding, topic_id))
            
            self.stats['vectors_generated'] += 1
        
        self.conn.commit()
    
    def _generate_scenario_embeddings(self):
        """生成Scenario向量（层次化）"""
        self.cursor.execute("""
            SELECT s.id, s.semantic_id, s.description_en, s.description_zh, s.clinical_context,
                   s.patient_population, s.risk_level, s.age_group, s.gender, s.pregnancy_status,
                   p.name_zh as panel_name, t.name_zh as topic_name
            FROM clinical_scenarios s
            JOIN topics t ON s.topic_id = t.id
            JOIN panels p ON s.panel_id = p.id;
        """)
        scenarios = self.cursor.fetchall()
        
        for scenario in scenarios:
            (scenario_id, semantic_id, desc_en, desc_zh, clinical_context,
             patient_pop, risk_level, age_group, gender, pregnancy_status,
             panel_name, topic_name) = scenario
            
            # 构建完整的层次化向量化文本
            text_parts = [
                f"科室: {panel_name}",
                f"主题: {topic_name}",
                f"临床场景: {desc_zh}",
                f"患者人群: {patient_pop or ''}",
                f"风险等级: {risk_level or ''}",
                f"年龄组: {age_group or ''}",
                f"性别: {gender or ''}",
                f"妊娠状态: {pregnancy_status or ''}",
                f"临床上下文: {clinical_context or ''}"
            ]
            
            text = " | ".join([part for part in text_parts if not part.endswith(': ')])
            
            # 生成向量
            embedding = np.random.rand(1024).tolist()
            
            self.cursor.execute("""
                UPDATE clinical_scenarios SET embedding = %s WHERE id = %s;
            """, (embedding, scenario_id))
            
            self.stats['vectors_generated'] += 1
        
        self.conn.commit()
    
    def _generate_procedure_embeddings(self):
        """生成Procedure向量（独立）"""
        self.cursor.execute("""
            SELECT id, semantic_id, name_en, name_zh, modality, body_part, 
                   contrast_used, radiation_level, description_zh
            FROM procedure_dictionary;
        """)
        procedures = self.cursor.fetchall()
        
        for procedure in procedures:
            (proc_id, semantic_id, name_en, name_zh, modality, body_part,
             contrast_used, radiation_level, description) = procedure
            
            # 构建检查项目向量化文本
            text_parts = [
                f"检查项目: {name_zh}",
                f"检查方式: {modality or ''}",
                f"检查部位: {body_part or ''}",
                f"对比剂: {'使用' if contrast_used else '不使用'}",
                f"辐射等级: {radiation_level or ''}",
                f"描述: {description or ''}"
            ]
            
            text = " | ".join([part for part in text_parts if not part.endswith(': ')])
            
            # 生成向量
            embedding = np.random.rand(1024).tolist()
            
            self.cursor.execute("""
                UPDATE procedure_dictionary SET embedding = %s WHERE id = %s;
            """, (embedding, proc_id))
            
            self.stats['vectors_generated'] += 1
        
        self.conn.commit()
    
    def _generate_recommendation_embeddings(self):
        """生成Recommendation向量（完整临床决策）"""
        self.cursor.execute("""
            SELECT 
                cr.id, cr.semantic_id, cr.appropriateness_rating, cr.reasoning_zh, cr.evidence_level,
                s.description_zh as scenario_desc, s.patient_population, s.risk_level, s.age_group,
                pd.name_zh as proc_name, pd.modality, pd.body_part,
                p.name_zh as panel_name, t.name_zh as topic_name
            FROM clinical_recommendations cr
            JOIN clinical_scenarios s ON cr.scenario_id = s.semantic_id
            JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
            JOIN topics t ON s.topic_id = t.id
            JOIN panels p ON s.panel_id = p.id;
        """)
        recommendations = self.cursor.fetchall()
        
        for rec in recommendations:
            (rec_id, semantic_id, rating, reasoning, evidence_level,
             scenario_desc, patient_pop, risk_level, age_group,
             proc_name, modality, body_part, panel_name, topic_name) = rec
            
            # 构建完整临床决策向量化文本
            text_parts = [
                f"科室: {panel_name}",
                f"主题: {topic_name}",
                f"临床场景: {scenario_desc}",
                f"患者人群: {patient_pop or ''}",
                f"风险等级: {risk_level or ''}",
                f"年龄组: {age_group or ''}",
                f"检查项目: {proc_name}",
                f"检查方式: {modality or ''}",
                f"检查部位: {body_part or ''}",
                f"适宜性评分: {rating}分",
                f"证据强度: {evidence_level or ''}",
                f"推荐理由: {reasoning or ''}"
            ]
            
            text = " | ".join([part for part in text_parts if not part.endswith(': ')])
            
            # 生成向量
            embedding = np.random.rand(1024).tolist()
            
            self.cursor.execute("""
                UPDATE clinical_recommendations SET embedding = %s WHERE id = %s;
            """, (embedding, rec_id))
            
            self.stats['vectors_generated'] += 1
        
        self.conn.commit()
    
    # 辅助方法
    def _safe_int(self, value) -> Optional[int]:
        """安全转换为整数"""
        try:
            return int(float(value)) if value and str(value).strip() else None
        except (ValueError, TypeError):
            return None
    
    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数"""
        try:
            return float(value) if value and str(value).strip() else None
        except (ValueError, TypeError):
            return None
    
    def _safe_bool(self, value) -> bool:
        """安全转换为布尔值"""
        if not value:
            return False
        return str(value).lower() in ['true', '1', 'yes', '是', '真']
    
    def _extract_patient_features(self, desc_en: str, desc_zh: str) -> Dict[str, str]:
        """提取患者特征"""
        text = f"{desc_en} {desc_zh}".lower()
        
        # 患者人群
        patient_population = '一般人群'
        if any(keyword in text for keyword in ['pregnant', 'pregnancy', '孕妇', '妊娠']):
            patient_population = '孕妇'
        elif any(keyword in text for keyword in ['pediatric', 'child', 'children', '儿童', '小儿']):
            patient_population = '儿童'
        elif any(keyword in text for keyword in ['elderly', 'geriatric', '老年', '老人']):
            patient_population = '老年'
        elif any(keyword in text for keyword in ['adult', 'adults', '成人']):
            patient_population = '成人'
        
        # 风险等级
        risk_level = '未指定'
        if any(keyword in text for keyword in ['high risk', 'high-risk', '高风险', '高危']):
            risk_level = '高风险'
        elif any(keyword in text for keyword in ['moderate risk', 'intermediate risk', '中风险', '中危']):
            risk_level = '中风险'
        elif any(keyword in text for keyword in ['low risk', 'low-risk', '低风险', '低危']):
            risk_level = '低风险'
        elif any(keyword in text for keyword in ['average risk', '平均风险', '一般风险']):
            risk_level = '平均风险'
        
        # 年龄组
        age_group = '未指定'
        age_patterns = [
            ('40岁以上', ['40 years or older', '≥40', '40岁以上', '40岁及以上']),
            ('30岁以上', ['30 years or older', '≥30', '30岁以上', '30岁及以上']),
            ('25岁以上', ['25 years or older', '≥25', '25岁以上', '25岁及以上']),
            ('25岁以下', ['less than 25', '<25', '25岁以下']),
            ('30岁以下', ['less than 30', '<30', '30岁以下'])
        ]
        
        for age_group_name, patterns in age_patterns:
            if any(pattern in f"{desc_en} {desc_zh}" for pattern in patterns):
                age_group = age_group_name
                break
        
        # 性别
        gender = '不限'
        if any(keyword in text for keyword in ['female', 'woman', 'women', '女性', '女']):
            gender = '女性'
        elif any(keyword in text for keyword in ['male', 'man', 'men', '男性', '男']):
            gender = '男性'
        
        # 妊娠状态
        pregnancy_status = '非妊娠期'
        if any(keyword in text for keyword in ['pregnant', 'pregnancy', '妊娠', '孕妇', '怀孕']):
            pregnancy_status = '妊娠期'
        elif any(keyword in text for keyword in ['lactating', 'breastfeeding', '哺乳', '哺乳期']):
            pregnancy_status = '哺乳期'
        
        # 紧急程度
        urgency_level = '择期'
        if any(keyword in text for keyword in ['emergency', 'urgent', 'acute', '急诊', '紧急', '急性']):
            urgency_level = '急诊'
        
        # 症状分类
        symptom_category = '未指定'
        symptom_keywords = {
            '疼痛': ['pain', 'ache', '疼痛', '痛'],
            '肿块': ['mass', 'lump', 'nodule', '肿块', '结节', '包块'],
            '出血': ['bleeding', 'hemorrhage', '出血', '血'],
            '发热': ['fever', 'febrile', '发热', '发烧'],
            '呼吸困难': ['dyspnea', 'shortness of breath', '呼吸困难', '气促'],
            '筛查': ['screening', '筛查', '筛选']
        }
        
        for category, keywords in symptom_keywords.items():
            if any(keyword in text for keyword in keywords):
                symptom_category = category
                break
        
        return {
            'patient_population': patient_population,
            'risk_level': risk_level,
            'age_group': age_group,
            'gender': gender,
            'pregnancy_status': pregnancy_status,
            'urgency_level': urgency_level,
            'symptom_category': symptom_category
        }
    
    def _extract_procedure_attributes(self, name_en: str, name_zh: str) -> Dict[str, Any]:
        """提取检查项目属性"""
        text = f"{name_en} {name_zh}".upper()
        
        # 检查方式
        modality_map = {
            'CT': ['CT', 'COMPUTED TOMOGRAPHY'],
            'MRI': ['MRI', 'MR', 'MAGNETIC RESONANCE'],
            'US': ['US', 'ULTRASOUND', '超声'],
            'XR': ['XR', 'X-RAY', 'RADIOGRAPHY', 'X线', '射线', 'DR'],
            'MG': ['MG', 'MAMMOGRAPHY', '钼靶'],
            'NM': ['SPECT', 'PET', 'SCINTIGRAPHY', '核医学', '显像'],
            'RF': ['RF', 'FLUOROSCOPY', '透视'],
            'DSA': ['DSA', 'ANGIOGRAPHY', '血管造影']
        }
        
        modality = 'OTHER'
        for mod, keywords in modality_map.items():
            if any(keyword in text for keyword in keywords):
                modality = mod
                break
        
        # 检查部位
        body_parts = {
            '头部': ['HEAD', 'BRAIN', 'SKULL', '头', '脑', '颅'],
            '颈部': ['NECK', 'CERVICAL', '颈', '颈椎'],
            '胸部': ['CHEST', 'THORAX', 'LUNG', 'CARDIAC', '胸', '肺', '心脏'],
            '腹部': ['ABDOMEN', 'ABDOMINAL', 'LIVER', 'KIDNEY', '腹', '肝', '肾'],
            '盆腔': ['PELVIS', 'PELVIC', 'BLADDER', 'PROSTATE', '盆', '膀胱', '前列腺'],
            '脊柱': ['SPINE', 'SPINAL', 'VERTEBRA', '脊', '椎'],
            '四肢': ['EXTREMITY', 'ARM', 'LEG', 'LIMB', '肢', '臂', '腿'],
            '乳腺': ['BREAST', 'MAMMARY', '乳腺', '乳房'],
            '血管': ['VASCULAR', 'ARTERY', 'VEIN', '血管', '动脉', '静脉']
        }
        
        body_part = '其他'
        for part, keywords in body_parts.items():
            if any(keyword in text for keyword in keywords):
                body_part = part
                break
        
        # 对比剂使用
        contrast_keywords = ['CONTRAST', 'ENHANCED', 'WITH IV', '增强', '对比', '造影']
        contrast_used = any(keyword in text for keyword in contrast_keywords)
        
        # 辐射等级
        radiation_level = '未知'
        if modality in ['US']:
            radiation_level = '无'
        elif modality in ['XR', 'MG']:
            radiation_level = '低'
        elif modality in ['CT']:
            radiation_level = '中'
        elif modality in ['NM']:
            radiation_level = '高'
        elif modality in ['MRI']:
            radiation_level = '无'
        
        return {
            'modality': modality,
            'body_part': body_part,
            'contrast_used': contrast_used,
            'radiation_level': radiation_level
        }
    
    def _assess_pregnancy_safety(self, radiation_dose: str, reasoning: str) -> str:
        """评估妊娠安全性"""
        text = f"{radiation_dose} {reasoning}".lower()
        
        if any(keyword in text for keyword in ['contraindicated', 'not recommended', '禁忌', '不推荐', '不建议']):
            return '禁忌'
        elif any(keyword in text for keyword in ['safe', 'appropriate', '安全', '适宜']):
            return '安全'
        elif any(keyword in text for keyword in ['caution', 'consider', '谨慎', '考虑']):
            return '谨慎使用'
        else:
            return '未评估'
    
    def verify_build(self) -> Dict[str, Any]:
        """验证构建结果"""
        logger.info("🔍 验证构建结果...")
        
        try:
            verification = {}
            
            # 统计各表记录数
            tables = ['panels', 'topics', 'clinical_scenarios', 'procedure_dictionary', 'clinical_recommendations']
            for table in tables:
                self.cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = self.cursor.fetchone()[0]
                verification[f"{table}_count"] = count
            
            # 检查向量嵌入覆盖率
            for table in tables:
                self.cursor.execute(f"""
                    SELECT COUNT(*) as total, COUNT(embedding) as with_embedding 
                    FROM {table};
                """)
                total, with_embedding = self.cursor.fetchone()
                coverage = (with_embedding / total * 100) if total > 0 else 0
                verification[f"{table}_embedding_coverage"] = f"{with_embedding}/{total} ({coverage:.1f}%)"
            
            # 检查数据完整性
            self.cursor.execute("""
                SELECT COUNT(*) FROM clinical_recommendations cr
                WHERE cr.scenario_id NOT IN (SELECT semantic_id FROM clinical_scenarios)
                   OR cr.procedure_id NOT IN (SELECT semantic_id FROM procedure_dictionary);
            """)
            orphaned_recommendations = self.cursor.fetchone()[0]
            verification['orphaned_recommendations'] = orphaned_recommendations
            
            # 示例数据
            self.cursor.execute("""
                SELECT 
                    cr.semantic_id,
                    p.name_zh as panel_name,
                    t.name_zh as topic_name,
                    s.description_zh as scenario_desc,
                    pd.name_zh as procedure_name,
                    cr.appropriateness_rating
                FROM clinical_recommendations cr
                JOIN clinical_scenarios s ON cr.scenario_id = s.semantic_id
                JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
                JOIN topics t ON s.topic_id = t.id
                JOIN panels p ON s.panel_id = p.id
                ORDER BY cr.appropriateness_rating DESC
                LIMIT 5;
            """)
            
            examples = []
            for row in self.cursor.fetchall():
                examples.append({
                    'recommendation_id': row[0],
                    'panel': row[1],
                    'topic': row[2], 
                    'scenario': row[3][:50] + '...' if len(row[3]) > 50 else row[3],
                    'procedure': row[4],
                    'rating': row[5]
                })
            
            verification['examples'] = examples
            verification['build_stats'] = self.stats
            
            # 输出验证信息
            logger.info("📊 构建统计:")
            for key, value in verification.items():
                if key.endswith('_count'):
                    logger.info(f"   {key}: {value}")
                elif key.endswith('_coverage'):
                    logger.info(f"   {key}: {value}")
            
            if orphaned_recommendations == 0:
                logger.info("✅ 数据完整性检查通过")
            else:
                logger.warning(f"⚠️ 发现 {orphaned_recommendations} 条孤立的推荐记录")
            
            logger.info("📋 示例数据:")
            for i, example in enumerate(examples, 1):
                logger.info(f"   {i}. {example['recommendation_id']}: {example['procedure']} | {example['scenario']} | 评分:{example['rating']}")
            
            return verification
            
        except Exception as e:
            logger.error(f"❌ 验证构建结果失败: {e}")
            return {}

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='ACRAC完整数据库和向量库构建工具')
    parser.add_argument('action', choices=['build', 'verify', 'rebuild'], 
                       help='操作类型: build(构建), verify(验证), rebuild(重建)')
    parser.add_argument('--csv-file', default='../../ACR_data/ACR_final.csv',
                       help='CSV数据文件路径')
    parser.add_argument('--skip-schema', action='store_true',
                       help='跳过架构创建（用于增量更新）')
    
    args = parser.parse_args()
    
    logger.info("🚀 ACRAC完整数据库和向量库构建工具")
    logger.info("=" * 80)
    
    builder = CompleteDataBuilder()
    
    try:
        if not builder.connect():
            return 1
        
        if args.action in ['build', 'rebuild']:
            # 创建架构
            if not args.skip_schema:
                logger.info("📝 步骤1: 创建数据库架构")
                if not builder.create_complete_schema():
                    return 1
                
                logger.info("📝 步骤2: 创建索引")
                if not builder.create_indexes():
                    return 1
            
            # 加载数据
            logger.info("📝 步骤3: 加载CSV数据")
            df = builder.load_csv_data(args.csv_file)
            if df is None:
                return 1
            
            # 构建数据库
            logger.info("📝 步骤4: 构建完整数据库")
            if not builder.build_complete_database(df):
                return 1
            
            # 验证结果
            logger.info("📝 步骤5: 验证构建结果")
            verification = builder.verify_build()
            
            logger.info("\n🎉 完整数据库和向量库构建完成!")
            logger.info("=" * 80)
            logger.info(f"📊 最终统计: {builder.stats}")
        
        elif args.action == 'verify':
            verification = builder.verify_build()
            logger.info("✅ 验证完成")
        
    except Exception as e:
        logger.error(f"\n❌ 操作失败: {e}")
        return 1
    
    finally:
        builder.disconnect()
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
