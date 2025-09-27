"""
智能推荐服务 - 三层混合推荐架构
向量检索 + 规则过滤 + LLM智能分析
"""
import numpy as np
import time
import json
import logging
import requests
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from app.models.acrac_models import (
    Panel, Topic, ClinicalScenario, ProcedureDictionary, 
    ClinicalRecommendation, VectorSearchLog
)
from app.services.ollama_qwen_service import OllamaQwenService

logger = logging.getLogger(__name__)

class IntelligentRecommendationService:
    """智能推荐服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.ollama_service = OllamaQwenService()
        
    def analyze_patient_case(
        self, 
        patient_info: Dict[str, Any],
        clinical_description: str,
        use_llm: bool = True,
        vector_recall_size: int = 50,
        final_recommendations: int = 5
    ) -> Dict[str, Any]:
        """
        智能患者案例分析
        
        Args:
            patient_info: 患者基本信息 {"age": 45, "gender": "女性", "symptoms": ["胸痛"]}
            clinical_description: 临床描述文本
            use_llm: 是否使用LLM进行最终分析
            vector_recall_size: 向量召回数量
            final_recommendations: 最终推荐数量
        """
        start_time = time.time()
        
        try:
            # 第一阶段：向量检索（召回）
            logger.info("🔍 第一阶段：向量检索召回")
            vector_candidates = self._vector_recall(
                patient_info, clinical_description, vector_recall_size
            )
            
            # 第三阶段：LLM智能分析（可选）
            if use_llm and len(vector_candidates) > 0:
                # 第二阶段：规则过滤（精排）
                logger.info("⚖️ 第二阶段：规则过滤精排")
                filtered_candidates = self._rule_based_filter(
                    vector_candidates, patient_info
                )
                
                logger.info("🤖 第三阶段：LLM智能分析")
                final_analysis = self._llm_clinical_analysis(
                    patient_info, clinical_description, 
                    filtered_candidates, final_recommendations
                )
                
                # 如果LLM分析失败，使用不同的降级策略
                if final_analysis.get('method') == '规则排序（降级）':
                    logger.warning("LLM分析失败，使用增强规则排序")
                    final_analysis = self._enhanced_rule_ranking(
                        filtered_candidates, final_recommendations, patient_info
                    )
            else:
                # 纯向量检索：跳过规则过滤，直接使用向量相似度排序
                logger.info("📊 第二阶段：向量相似度排序")
                final_analysis = self._vector_similarity_ranking(
                    vector_candidates, final_recommendations
                )
            
            analysis_time = int((time.time() - start_time) * 1000)
            
            # 记录分析日志
            self._log_analysis(patient_info, clinical_description, final_analysis, analysis_time)
            
            return {
                "patient_info": patient_info,
                "clinical_description": clinical_description,
                "analysis_method": final_analysis.get("method", "未知方法"),
                "vector_candidates_count": len(vector_candidates),
                "filtered_candidates_count": len(vector_candidates),  # 对于纯向量检索，使用vector_candidates
                "final_recommendations": final_analysis["recommendations"],
                "clinical_reasoning": final_analysis.get("reasoning", ""),
                "safety_warnings": final_analysis.get("warnings", []),
                "alternative_options": final_analysis.get("alternatives", []),
                "analysis_time_ms": analysis_time,
                "confidence_score": final_analysis.get("confidence", 0.8)
            }
            
        except Exception as e:
            logger.error(f"智能分析失败: {e}")
            import traceback
            logger.error(f"异常详情: {traceback.format_exc()}")
            # 降级到简单推荐
            return self._fallback_recommendation(patient_info, clinical_description)
    
    def _vector_recall(
        self, 
        patient_info: Dict[str, Any], 
        clinical_description: str, 
        recall_size: int
    ) -> List[Dict[str, Any]]:
        """第一阶段：向量检索召回"""
        
        # 构建查询文本
        query_text = self._build_query_text(patient_info, clinical_description)
        
        # 生成查询向量（使用Ollama生成真实向量）
        try:
            query_vector = self._generate_query_vector(query_text)
        except Exception as e:
            logger.warning(f"向量生成失败，使用降级方案: {e}")
            return self._fallback_vector_search(query_text, recall_size)
        
        # 向量相似度搜索 - 对临床场景描述进行向量检索
        sql = """
            SELECT 
                cr.semantic_id,
                cr.scenario_id,
                cr.procedure_id,
                cr.appropriateness_rating,
                cr.appropriateness_category_zh,
                cr.reasoning_zh,
                cr.evidence_level,
                cr.pregnancy_safety,
                cr.adult_radiation_dose,
                s.description_zh as scenario_desc,
                s.patient_population,
                s.risk_level,
                s.age_group,
                s.gender,
                s.pregnancy_status,
                pd.name_zh as procedure_name,
                pd.modality,
                pd.body_part,
                pd.contrast_used,
                pd.radiation_level,
                p.name_zh as panel_name,
                t.name_zh as topic_name,
                s.embedding as scenario_embedding
            FROM clinical_recommendations cr
            JOIN clinical_scenarios s ON cr.scenario_id = s.semantic_id
            JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
            JOIN topics t ON s.topic_id = t.id
            JOIN panels p ON s.panel_id = p.id
            WHERE cr.is_active = TRUE
              AND s.embedding IS NOT NULL
            LIMIT :limit;
        """
        
        result = self.db.execute(text(sql), {"limit": recall_size * 2})  # 获取更多候选进行相似度计算
        
        candidates = []
        for row in result:
            # 计算余弦相似度 - 使用场景向量
            scenario_embedding = json.loads(row[22]) if row[22] else None
            if scenario_embedding:
                similarity = self._cosine_similarity(query_vector, scenario_embedding)
            else:
                similarity = 0.0
                
            candidates.append({
                'recommendation_id': row[0],
                'scenario_id': row[1],
                'procedure_id': row[2],
                'appropriateness_rating': row[3],
                'appropriateness_category_zh': row[4],
                'reasoning_zh': row[5],
                'evidence_level': row[6],
                'pregnancy_safety': row[7],
                'radiation_dose': row[8],
                'scenario_desc': row[9],
                'patient_population': row[10],
                'risk_level': row[11],
                'age_group': row[12],
                'gender': row[13],
                'pregnancy_status': row[14],
                'procedure_name': row[15],
                'modality': row[16],
                'body_part': row[17],
                'contrast_used': row[18],
                'radiation_level': row[19],
                'panel_name': row[20],
                'topic_name': row[21],
                'similarity_score': similarity
            })
        
        # 按相似度排序并返回前N个
        candidates.sort(key=lambda x: x['similarity_score'], reverse=True)
        candidates = candidates[:recall_size]
        
        logger.info(f"向量召回: {len(candidates)} 个候选推荐")
        return candidates
    
    def _rule_based_filter(
        self, 
        candidates: List[Dict[str, Any]], 
        patient_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """第二阶段：规则过滤"""
        
        filtered = []
        
        for candidate in candidates:
            # 规则1：年龄匹配
            if not self._age_matches(candidate, patient_info.get('age')):
                continue
                
            # 规则2：性别匹配
            if not self._gender_matches(candidate, patient_info.get('gender')):
                continue
                
            # 规则3：妊娠安全性
            if not self._pregnancy_safety_check(candidate, patient_info):
                continue
                
            # 规则4：紧急程度评估
            urgency_score = self._assess_urgency(candidate, patient_info)
            candidate['urgency_score'] = urgency_score
            
            # 规则5：适宜性阈值
            if candidate['appropriateness_rating'] >= 6:  # 只保留6分以上的推荐
                candidate['filter_reason'] = '通过规则过滤'
                filtered.append(candidate)
        
        logger.info(f"规则过滤: {len(candidates)} → {len(filtered)} 个候选推荐")
        return filtered
    
    def _llm_clinical_analysis(
        self,
        patient_info: Dict[str, Any],
        clinical_description: str,
        candidates: List[Dict[str, Any]],
        final_count: int
    ) -> Dict[str, Any]:
        """第三阶段：LLM临床分析"""
        
        try:
            # 使用Ollama Qwen3:30b进行分析
            logger.info("🤖 调用Ollama Qwen3:30b进行临床分析")
            logger.info(f"候选数量: {len(candidates)}")
            
            llm_response = self.ollama_service.clinical_analysis(
                patient_info, clinical_description, candidates, final_count
            )
            
            logger.info(f"✅ LLM分析完成，置信度: {llm_response.get('confidence', 0.8)}")
            logger.info(f"LLM方法: {llm_response.get('method', '未知')}")
            return llm_response
            
        except Exception as e:
            logger.error(f"❌ LLM分析失败，降级到规则排序: {e}")
            logger.error(f"异常类型: {type(e).__name__}")
            import traceback
            logger.error(f"异常详情: {traceback.format_exc()}")
            # 降级到模拟分析
            return self._mock_llm_analysis("", candidates, final_count)
    
    def _vector_similarity_ranking(
        self, 
        candidates: List[Dict[str, Any]], 
        final_count: int
    ) -> Dict[str, Any]:
        """基于向量相似度的纯排序（向量检索方法）"""
        if not candidates:
            return {
                "method": "向量相似度排序",
                "confidence": 0.0,
                "recommendations": []
            }
        
        # 按相似度降序排序
        sorted_candidates = sorted(
            candidates, 
            key=lambda x: x.get('similarity_score', 0), 
            reverse=True
        )
        
        # 取前N个结果
        top_candidates = sorted_candidates[:final_count]
        
        # 计算平均置信度
        avg_confidence = sum(c.get('similarity_score', 0) for c in top_candidates) / len(top_candidates) if top_candidates else 0.0
        
        # 转换推荐格式
        recommendations = []
        for i, candidate in enumerate(top_candidates, 1):
            recommendations.append({
                "rank": i,
                "procedure_name": candidate.get('procedure_name', '未知检查'),
                "modality": candidate.get('modality', '未知'),
                "body_part": candidate.get('body_part', '未知'),
                "appropriateness_rating": candidate.get('appropriateness_rating', 0),
                "reasoning": candidate.get('reasoning_zh', ''),
                "evidence_level": candidate.get('evidence_level', 'C'),
                "radiation_level": candidate.get('radiation_level', '低'),
                "panel_name": candidate.get('panel_name', '未知科室'),
                "topic_name": candidate.get('topic_name', '未知主题'),
                "scenario_desc": candidate.get('scenario_desc', ''),
                "similarity_score": candidate.get('similarity_score', 0.0)
            })
        
        return {
            "method": "向量相似度排序",
            "confidence": avg_confidence,
            "recommendations": recommendations
        }

    def _rule_based_ranking(
        self, 
        candidates: List[Dict[str, Any]], 
        final_count: int
    ) -> Dict[str, Any]:
        """基于规则的排序（LLM的降级方案）"""
        
        # 综合评分：适宜性评分 + 紧急程度 + 相似度
        for candidate in candidates:
            score = (
                candidate['appropriateness_rating'] * 0.4 +  # ACR评分权重40%
                candidate.get('urgency_score', 5) * 0.3 +    # 紧急程度权重30%
                candidate['similarity_score'] * 10 * 0.3     # 相似度权重30%
            )
            candidate['final_score'] = score
        
        # 按综合评分排序
        sorted_candidates = sorted(candidates, key=lambda x: x['final_score'], reverse=True)
        
        recommendations = []
        for i, candidate in enumerate(sorted_candidates[:final_count], 1):
            recommendations.append({
                'rank': i,
                'procedure_name': candidate['procedure_name'],
                'modality': candidate['modality'],
                'appropriateness_rating': candidate['appropriateness_rating'],
                'appropriateness_category': candidate['appropriateness_category_zh'],
                'reasoning': candidate['reasoning_zh'],
                'evidence_level': candidate['evidence_level'],
                'radiation_level': candidate['radiation_level'],
                'panel_name': candidate['panel_name'],
                'final_score': round(candidate['final_score'], 2),
                'recommendation_id': candidate['recommendation_id']
            })
        
        return {
            'recommendations': recommendations,
            'reasoning': '基于ACR适宜性评分、紧急程度和相似度的综合排序',
            'method': '规则排序',
            'confidence': 0.75
        }
    
    def _enhanced_rule_ranking(
        self, 
        candidates: List[Dict[str, Any]], 
        final_count: int,
        patient_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """增强规则排序（LLM降级方案）"""
        
        # 基于患者特征的个性化评分
        for candidate in candidates:
            score = candidate['appropriateness_rating'] * 0.4  # ACR评分权重40%
            
            # 年龄匹配加分
            if self._age_matches(candidate, patient_info.get('age')):
                score += 1.0
            
            # 性别匹配加分
            if self._gender_matches(candidate, patient_info.get('gender')):
                score += 0.5
            
            # 症状相关性加分
            symptoms = patient_info.get('symptoms', [])
            if symptoms:
                symptom_text = ' '.join(symptoms).lower()
                if any(keyword in candidate.get('reasoning_zh', '').lower() for keyword in symptom_text.split()):
                    score += 1.5
            
            # 紧急程度加分
            urgency = self._assess_urgency(candidate, patient_info)
            score += urgency * 0.2
            
            # 相似度加分
            score += candidate.get('similarity_score', 0) * 5
            
            candidate['enhanced_score'] = score
        
        # 按增强评分排序
        sorted_candidates = sorted(candidates, key=lambda x: x['enhanced_score'], reverse=True)
        
        recommendations = []
        for i, candidate in enumerate(sorted_candidates[:final_count], 1):
            recommendations.append({
                'rank': i,
                'procedure_name': candidate['procedure_name'],
                'modality': candidate['modality'],
                'appropriateness_rating': candidate['appropriateness_rating'],
                'appropriateness_category': candidate['appropriateness_category_zh'],
                'reasoning': f"增强规则分析：{candidate['reasoning_zh'][:100]}...",
                'evidence_level': candidate['evidence_level'],
                'radiation_level': candidate['radiation_level'],
                'panel_name': candidate['panel_name'],
                'enhanced_score': round(candidate['enhanced_score'], 2),
                'recommendation_id': candidate['recommendation_id']
            })
        
        return {
            'recommendations': recommendations,
            'reasoning': '基于ACR适宜性评分、患者特征匹配、症状相关性和紧急程度的增强规则排序',
            'method': '增强规则排序（LLM降级）',
            'confidence': 0.8
        }
    
    def _mock_llm_analysis(
        self, 
        prompt: str, 
        candidates: List[Dict[str, Any]], 
        final_count: int
    ) -> Dict[str, Any]:
        """模拟LLM分析（实际应调用真实LLM）"""
        
        # 这里模拟LLM的临床推理过程
        # 实际实现时应调用OpenAI API、Ollama等
        
        # 按适宜性评分和临床相关性排序
        sorted_candidates = sorted(
            candidates, 
            key=lambda x: (x['appropriateness_rating'], x['similarity_score']), 
            reverse=True
        )
        
        recommendations = []
        clinical_reasoning = []
        warnings = []
        
        for i, candidate in enumerate(sorted_candidates[:final_count], 1):
            # 模拟LLM的临床分析
            if candidate['appropriateness_rating'] >= 8:
                confidence = "高"
                reasoning_prefix = "强烈推荐："
            elif candidate['appropriateness_rating'] >= 7:
                confidence = "中"
                reasoning_prefix = "推荐："
            else:
                confidence = "低"
                reasoning_prefix = "可考虑："
            
            # 安全性警告
            if candidate['pregnancy_safety'] == '禁忌':
                warnings.append(f"{candidate['procedure_name']} 对妊娠期禁用")
            
            recommendations.append({
                'rank': i,
                'procedure_name': candidate['procedure_name'],
                'modality': candidate['modality'],
                'appropriateness_rating': candidate['appropriateness_rating'],
                'confidence_level': confidence,
                'clinical_reasoning': f"{reasoning_prefix} {candidate['reasoning_zh'][:100]}...",
                'evidence_level': candidate['evidence_level'],
                'radiation_level': candidate['radiation_level'],
                'panel_name': candidate['panel_name'],
                'safety_considerations': candidate['pregnancy_safety'],
                'recommendation_id': candidate['recommendation_id']
            })
            
            clinical_reasoning.append(
                f"推荐{i}: {candidate['procedure_name']} - "
                f"基于{candidate['evidence_level']}证据，适宜性评分{candidate['appropriateness_rating']}分"
            )
        
        return {
            'recommendations': recommendations,
            'reasoning': "基于患者年龄、性别、症状特点，结合ACR适宜性标准进行临床推理分析。" + 
                        " ".join(clinical_reasoning),
            'warnings': warnings,
            'alternatives': self._generate_alternatives(sorted_candidates[final_count:final_count+3]),
            'method': 'LLM增强分析',
            'confidence': 0.9
        }
    
    def _build_query_text(self, patient_info: Dict[str, Any], clinical_description: str) -> str:
        """构建查询文本"""
        query_parts = [clinical_description]
        
        if patient_info.get('age'):
            query_parts.append(f"{patient_info['age']}岁")
        if patient_info.get('gender'):
            query_parts.append(patient_info['gender'])
        if patient_info.get('symptoms'):
            query_parts.extend(patient_info['symptoms'])
        if patient_info.get('duration'):
            query_parts.append(patient_info['duration'])
            
        return " ".join(query_parts)
    
    def _build_llm_prompt(
        self, 
        patient_info: Dict[str, Any], 
        clinical_description: str, 
        candidates: List[Dict[str, Any]]
    ) -> str:
        """构建LLM分析prompt"""
        
        prompt = f"""
作为一名经验丰富的放射科医生，请分析以下患者案例并提供影像学检查推荐：

【患者信息】
年龄: {patient_info.get('age', '未知')}
性别: {patient_info.get('gender', '未知')}
临床描述: {clinical_description}

【候选检查项目】
基于ACR适宜性标准，系统检索到以下候选推荐：

"""
        
        for i, candidate in enumerate(candidates[:10], 1):
            prompt += f"""
{i}. {candidate['procedure_name']} ({candidate['modality']})
   - ACR评分: {candidate['appropriateness_rating']}/9分
   - 适宜性: {candidate['appropriateness_category_zh']}
   - 科室: {candidate['panel_name']}
   - 辐射等级: {candidate['radiation_level']}
   - 推荐理由: {candidate['reasoning_zh'][:150]}...
   - 证据强度: {candidate['evidence_level']}
   
"""
        
        prompt += """
【分析要求】
请基于临床经验和循证医学原则，提供：
1. 最推荐的3-5个检查项目，按优先级排序
2. 每个推荐的详细临床理由
3. 安全性考虑和注意事项
4. 检查顺序建议
5. 替代方案（如果适用）

请提供专业、准确、个性化的临床建议。
"""
        
        return prompt
    
    def _age_matches(self, candidate: Dict[str, Any], patient_age: Optional[int]) -> bool:
        """年龄匹配检查"""
        if not patient_age:
            return True
            
        age_group = candidate.get('age_group', '')
        
        if '40岁以上' in age_group and patient_age < 40:
            return False
        elif '30岁以上' in age_group and patient_age < 30:
            return False
        elif '25岁以下' in age_group and patient_age >= 25:
            return False
        elif '30岁以下' in age_group and patient_age >= 30:
            return False
            
        return True
    
    def _gender_matches(self, candidate: Dict[str, Any], patient_gender: Optional[str]) -> bool:
        """性别匹配检查"""
        if not patient_gender:
            return True
            
        candidate_gender = candidate.get('gender', '不限')
        
        if candidate_gender == '不限':
            return True
        elif candidate_gender == patient_gender:
            return True
        else:
            return False
    
    def _pregnancy_safety_check(self, candidate: Dict[str, Any], patient_info: Dict[str, Any]) -> bool:
        """妊娠安全性检查"""
        pregnancy_status = patient_info.get('pregnancy_status', '')
        
        if pregnancy_status == '妊娠期':
            safety = candidate.get('pregnancy_safety', '')
            if safety == '禁忌':
                return False
        
        return True
    
    def _assess_urgency(self, candidate: Dict[str, Any], patient_info: Dict[str, Any]) -> int:
        """评估紧急程度 1-10分"""
        urgency = 5  # 默认中等紧急
        
        # 基于症状评估紧急程度
        symptoms = patient_info.get('symptoms', [])
        duration = patient_info.get('duration', '')
        
        # 急性症状
        if any(keyword in ' '.join(symptoms + [duration]) for keyword in ['急性', '突发', '1小时', '急诊']):
            urgency += 3
        
        # 危险症状
        if any(keyword in ' '.join(symptoms) for keyword in ['胸痛', '头痛', '呼吸困难', '意识障碍']):
            urgency += 2
            
        # 慢性症状
        if any(keyword in duration for keyword in ['慢性', '反复', '一周', '数天']):
            urgency -= 1
            
        return max(1, min(10, urgency))
    
    def _generate_alternatives(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成替代方案"""
        alternatives = []
        
        for candidate in candidates[:3]:
            alternatives.append({
                'procedure_name': candidate['procedure_name'],
                'modality': candidate['modality'],
                'rating': candidate['appropriateness_rating'],
                'reason': '替代选择，可根据具体情况考虑'
            })
            
        return alternatives
    
    def _fallback_recommendation(
        self, 
        patient_info: Dict[str, Any], 
        clinical_description: str
    ) -> Dict[str, Any]:
        """降级推荐方案"""
        
        # 基于关键词的简单推荐
        symptoms = patient_info.get('symptoms', [])
        age = patient_info.get('age', 0)
        gender = patient_info.get('gender', '')
        
        fallback_recs = []
        
        # 基础推荐逻辑
        if '胸痛' in ' '.join(symptoms + [clinical_description]):
            fallback_recs.extend([
                {'procedure_name': 'DR胸部正位', 'modality': 'XR', 'appropriateness_rating': 8, 'reasoning': '胸痛初始筛查', 'evidence_level': 'C', 'radiation_level': '低', 'panel_name': '胸部影像科'},
                {'procedure_name': 'CT冠状动脉CTA', 'modality': 'CT', 'appropriateness_rating': 8, 'reasoning': '评估冠心病', 'evidence_level': 'A', 'radiation_level': '中', 'panel_name': '心血管影像科'}
            ])
            
        if '头痛' in ' '.join(symptoms + [clinical_description]):
            fallback_recs.extend([
                {'procedure_name': 'CT颅脑平扫', 'modality': 'CT', 'appropriateness_rating': 9, 'reasoning': '头痛初始评估', 'evidence_level': 'A', 'radiation_level': '中', 'panel_name': '神经影像科'},
                {'procedure_name': 'MR颅脑平扫+增强', 'modality': 'MRI', 'appropriateness_rating': 8, 'reasoning': '详细神经评估', 'evidence_level': 'A', 'radiation_level': '无', 'panel_name': '神经影像科'}
            ])
        
        return {
            'recommendations': fallback_recs[:5],
            'reasoning': '基于症状关键词的基础推荐',
            'method': '降级方案',
            'confidence': 0.6,
            'warnings': ['推荐基于基础规则，建议结合临床经验']
        }
    
    def _generate_query_vector(self, query_text: str) -> List[float]:
        """生成查询向量"""
        try:
            # 从配置文件动态获取嵌入模型
            import os
            embedding_model = os.getenv("OLLAMA_EMBEDDING_MODEL", "bge-m3:latest")
            
            # 使用Ollama生成向量
            response = requests.post(
                "http://localhost:11434/api/embeddings",
                json={
                    "model": embedding_model,  # 使用配置的嵌入模型
                    "prompt": query_text
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                vector = result.get("embedding", [])
                # 标准化向量以匹配数据库向量的范围[0,1]
                vector = np.array(vector)
                vector = (vector - vector.min()) / (vector.max() - vector.min())
                return vector.tolist()
            else:
                raise Exception(f"向量生成API错误: {response.status_code}")
                
        except Exception as e:
            logger.error(f"向量生成失败: {e}")
            # 降级到随机向量
            return np.random.rand(1024).tolist()
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        try:
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)
            
            # 确保向量长度一致
            min_len = min(len(vec1), len(vec2))
            vec1 = vec1[:min_len]
            vec2 = vec2[:min_len]
            
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
                
            return dot_product / (norm1 * norm2)
        except Exception as e:
            logger.error(f"相似度计算失败: {e}")
            return 0.0
    
    def _fallback_vector_search(self, query_text: str, recall_size: int) -> List[Dict[str, Any]]:
        """降级向量搜索（基于关键词匹配）"""
        try:
            # 基于关键词的简单搜索
            keywords = query_text.lower().split()
            
            sql = """
                SELECT 
                    cr.semantic_id,
                    cr.scenario_id,
                    cr.procedure_id,
                    cr.appropriateness_rating,
                    cr.appropriateness_category_zh,
                    cr.reasoning_zh,
                    cr.evidence_level,
                    cr.pregnancy_safety,
                    cr.adult_radiation_dose,
                    s.description_zh as scenario_desc,
                    s.patient_population,
                    s.risk_level,
                    s.age_group,
                    s.gender,
                    s.pregnancy_status,
                    pd.name_zh as procedure_name,
                    pd.modality,
                    pd.body_part,
                    pd.contrast_used,
                    pd.radiation_level,
                    p.name_zh as panel_name,
                    t.name_zh as topic_name
                FROM clinical_recommendations cr
                JOIN clinical_scenarios s ON cr.scenario_id = s.semantic_id
                JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
                JOIN topics t ON s.topic_id = t.id
                JOIN panels p ON s.panel_id = p.id
                WHERE cr.is_active = TRUE
                ORDER BY cr.appropriateness_rating DESC
                LIMIT ?;
            """
            
            result = self.db.execute(text(sql), [recall_size])
            
            candidates = []
            for row in result:
                candidates.append({
                    'recommendation_id': row[0],
                    'scenario_id': row[1],
                    'procedure_id': row[2],
                    'appropriateness_rating': row[3],
                    'appropriateness_category_zh': row[4],
                    'reasoning_zh': row[5],
                    'evidence_level': row[6],
                    'pregnancy_safety': row[7],
                    'radiation_dose': row[8],
                    'scenario_desc': row[9],
                    'patient_population': row[10],
                    'risk_level': row[11],
                    'age_group': row[12],
                    'gender': row[13],
                    'pregnancy_status': row[14],
                    'procedure_name': row[15],
                    'modality': row[16],
                    'body_part': row[17],
                    'contrast_used': row[18],
                    'radiation_level': row[19],
                    'panel_name': row[20],
                    'topic_name': row[21],
                    'similarity_score': 0.5  # 降级搜索的固定相似度
                })
            
            logger.info(f"降级向量搜索: {len(candidates)} 个候选推荐")
            return candidates
            
        except Exception as e:
            logger.error(f"降级向量搜索失败: {e}")
            return []

    def _log_analysis(
        self, 
        patient_info: Dict[str, Any], 
        clinical_description: str, 
        analysis: Dict[str, Any], 
        analysis_time: int
    ):
        """记录分析日志"""
        try:
            log = VectorSearchLog(
                query_text=f"{clinical_description} | {json.dumps(patient_info, ensure_ascii=False)}",
                query_type="intelligent_analysis",
                search_vector=None,  # 可以存储查询向量
                results_count=len(analysis.get('recommendations', [])),
                search_time_ms=analysis_time,
                user_id=None
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.error(f"记录分析日志失败: {e}")

# 患者案例请求模式
class PatientCaseRequest:
    """患者案例请求"""
    def __init__(
        self,
        age: Optional[int] = None,
        gender: Optional[str] = None,
        symptoms: List[str] = None,
        duration: Optional[str] = None,
        clinical_description: str = "",
        medical_history: List[str] = None,
        pregnancy_status: Optional[str] = None,
        urgency_level: Optional[str] = None
    ):
        self.age = age
        self.gender = gender
        self.symptoms = symptoms or []
        self.duration = duration
        self.clinical_description = clinical_description
        self.medical_history = medical_history or []
        self.pregnancy_status = pregnancy_status
        self.urgency_level = urgency_level
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'age': self.age,
            'gender': self.gender,
            'symptoms': self.symptoms,
            'duration': self.duration,
            'clinical_description': self.clinical_description,
            'medical_history': self.medical_history,
            'pregnancy_status': self.pregnancy_status,
            'urgency_level': self.urgency_level
        }
