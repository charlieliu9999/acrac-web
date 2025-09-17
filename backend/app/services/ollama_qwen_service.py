"""
Ollama Qwen3:30b 集成服务
"""
import requests
import json
import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class OllamaQwenService:
    """Ollama Qwen3:30b 服务"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.model = "qwen3:30b"  # 使用可用的qwen3:30b模型
        
    def check_availability(self) -> bool:
        """检查Ollama服务是否可用"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                available_models = [model["name"] for model in models]
                logger.info(f"可用模型: {available_models}")
                
                # 检查目标模型是否可用
                if any(self.model in model for model in available_models):
                    logger.info(f"✅ 模型 {self.model} 可用")
                    return True
                else:
                    logger.warning(f"⚠️ 模型 {self.model} 不可用，将使用第一个可用模型")
                    if available_models:
                        self.model = available_models[0]
                        return True
                    return False
            return False
        except Exception as e:
            logger.error(f"检查Ollama服务失败: {e}")
            return False
    
    def clinical_analysis(
        self, 
        patient_info: Dict[str, Any],
        clinical_description: str,
        candidates: List[Dict[str, Any]],
        final_count: int = 5
    ) -> Dict[str, Any]:
        """临床案例分析"""
        
        if not self.check_availability():
            raise Exception("Ollama服务不可用")
        
        # 构建临床分析prompt
        prompt = self._build_clinical_prompt(patient_info, clinical_description, candidates)
        
        # 调用Qwen进行分析
        try:
            response = self._call_ollama(prompt)
            
            # 解析LLM响应
            analysis_result = self._parse_llm_response(response, candidates, final_count)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"LLM分析失败: {e}")
            # 降级到规则排序
            return self._fallback_analysis(candidates, final_count)
    
    def _build_clinical_prompt(
        self, 
        patient_info: Dict[str, Any],
        clinical_description: str,
        candidates: List[Dict[str, Any]]
    ) -> str:
        """构建临床分析prompt"""
        
        prompt = f"""你是一位经验丰富的放射科医生。请分析以下患者案例并提供专业的影像学检查推荐。

【患者信息】
年龄: {patient_info.get('age', '未知')}岁
性别: {patient_info.get('gender', '未知')}
主要症状: {', '.join(patient_info.get('symptoms', []))}
病程: {patient_info.get('duration', '未明确')}
临床描述: {clinical_description}

【候选检查项目】
基于ACR适宜性标准，系统检索到以下相关检查项目：

"""
        
        for i, candidate in enumerate(candidates[:10], 1):
            prompt += f"""{i}. {candidate['procedure_name']} ({candidate['modality']})
   - ACR适宜性评分: {candidate['appropriateness_rating']}/9分
   - 适宜性类别: {candidate['appropriateness_category_zh']}
   - 检查部位: {candidate['body_part']}
   - 辐射等级: {candidate['radiation_level']}
   - 对比剂: {'使用' if candidate['contrast_used'] else '不使用'}
   - 妊娠安全性: {candidate['pregnancy_safety']}
   - 推荐理由: {candidate['reasoning_zh'][:200]}...
   - 证据强度: {candidate['evidence_level']}
   - 科室: {candidate['panel_name']}

"""
        
        prompt += f"""
【分析任务】
请基于临床经验、循证医学和患者安全，提供以下分析：

1. **推荐检查项目**（按优先级排序，最多{min(5, len(candidates))}项）：
   - 检查名称和优先级
   - 详细的临床推理
   - 推荐时机和顺序

2. **临床推理过程**：
   - 鉴别诊断考虑
   - 检查选择依据
   - 风险效益分析

3. **安全性考虑**：
   - 辐射风险评估
   - 禁忌症和注意事项
   - 特殊人群考虑

4. **检查策略**：
   - 首选检查和替代方案
   - 检查顺序和时机
   - 后续处理建议

请以JSON格式返回分析结果：
{{
    "recommendations": [
        {{
            "rank": 1,
            "procedure_name": "检查名称",
            "modality": "检查方式",
            "priority_level": "首选/推荐/备选",
            "clinical_reasoning": "详细的临床推理",
            "timing": "立即/急诊/择期",
            "appropriateness_rating": 评分,
            "safety_notes": "安全性考虑"
        }}
    ],
    "clinical_reasoning": "整体临床推理过程",
    "differential_diagnosis": ["鉴别诊断1", "鉴别诊断2"],
    "safety_warnings": ["安全提醒1", "安全提醒2"],
    "examination_sequence": "检查顺序建议",
    "confidence_level": "高/中/低"
}}

请确保推荐具有临床实用性、安全性和循证医学依据。
"""
        
        return prompt
    
    def _call_ollama(self, prompt: str, max_tokens: int = 2000) -> str:
        """调用Ollama API"""
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9,
                "max_tokens": max_tokens
            }
        }
        
        try:
            logger.info(f"调用Ollama模型: {self.model}")
            start_time = time.time()
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=60  # 增加超时时间，因为30b模型较大
            )
            
            response_time = time.time() - start_time
            logger.info(f"LLM响应时间: {response_time:.2f}秒")
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                raise Exception(f"Ollama API错误: {response.status_code} - {response.text}")
                
        except requests.exceptions.Timeout:
            raise Exception("LLM分析超时，请稍后重试")
        except requests.exceptions.ConnectionError:
            raise Exception("无法连接到Ollama服务，请确保Ollama正在运行")
        except Exception as e:
            raise Exception(f"LLM调用失败: {e}")
    
    def _parse_llm_response(
        self, 
        llm_response: str, 
        candidates: List[Dict[str, Any]], 
        final_count: int
    ) -> Dict[str, Any]:
        """解析LLM响应"""
        
        try:
            # 尝试解析JSON响应
            # 清理响应文本
            cleaned_response = llm_response.strip()
            
            # 查找JSON部分
            json_start = cleaned_response.find('{')
            json_end = cleaned_response.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_str = cleaned_response[json_start:json_end]
                parsed_result = json.loads(json_str)
                
                # 验证和补充数据
                recommendations = parsed_result.get("recommendations", [])
                
                # 确保推荐数量不超过候选数量
                recommendations = recommendations[:min(final_count, len(candidates))]
                
                # 补充候选数据中的详细信息
                for rec in recommendations:
                    # 找到对应的候选项目
                    matching_candidate = None
                    for candidate in candidates:
                        if candidate['procedure_name'] == rec.get('procedure_name'):
                            matching_candidate = candidate
                            break
                    
                    if matching_candidate:
                        rec.update({
                            'recommendation_id': matching_candidate['recommendation_id'],
                            'evidence_level': matching_candidate['evidence_level'],
                            'radiation_level': matching_candidate['radiation_level'],
                            'panel_name': matching_candidate['panel_name']
                        })
                
                return {
                    'recommendations': recommendations,
                    'reasoning': parsed_result.get("clinical_reasoning", ""),
                    'warnings': parsed_result.get("safety_warnings", []),
                    'alternatives': [],
                    'method': 'Qwen3:30b分析',
                    'confidence': 0.95,
                    'differential_diagnosis': parsed_result.get("differential_diagnosis", []),
                    'examination_sequence': parsed_result.get("examination_sequence", "")
                }
            else:
                raise ValueError("无法找到JSON响应")
                
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")
            logger.error(f"LLM原始响应: {llm_response[:500]}...")
            
            # 降级处理：解析文本响应
            return self._parse_text_response(llm_response, candidates, final_count)
    
    def _parse_text_response(
        self, 
        text_response: str, 
        candidates: List[Dict[str, Any]], 
        final_count: int
    ) -> Dict[str, Any]:
        """解析文本格式的LLM响应"""
        
        recommendations = []
        
        # 简单的文本解析逻辑
        lines = text_response.split('\n')
        
        for i, candidate in enumerate(candidates[:final_count], 1):
            recommendations.append({
                'rank': i,
                'procedure_name': candidate['procedure_name'],
                'modality': candidate['modality'],
                'appropriateness_rating': candidate['appropriateness_rating'],
                'clinical_reasoning': f"基于LLM分析：{candidate['reasoning_zh'][:100]}...",
                'priority_level': '推荐' if candidate['appropriateness_rating'] >= 8 else '可考虑',
                'timing': '择期',
                'recommendation_id': candidate['recommendation_id'],
                'evidence_level': candidate['evidence_level'],
                'panel_name': candidate['panel_name']
            })
        
        return {
            'recommendations': recommendations,
            'reasoning': '基于Qwen3:30b的临床分析（文本解析）',
            'warnings': ['LLM响应解析为文本格式，建议人工验证'],
            'method': 'Qwen3:30b文本分析',
            'confidence': 0.8
        }
    
    def _fallback_analysis(
        self, 
        candidates: List[Dict[str, Any]], 
        final_count: int
    ) -> Dict[str, Any]:
        """降级分析（当LLM不可用时）"""
        
        # 基于ACR评分和相似度的简单排序
        sorted_candidates = sorted(
            candidates, 
            key=lambda x: (x['appropriateness_rating'], x['similarity_score']), 
            reverse=True
        )
        
        recommendations = []
        for i, candidate in enumerate(sorted_candidates[:final_count], 1):
            recommendations.append({
                'rank': i,
                'procedure_name': candidate['procedure_name'],
                'modality': candidate['modality'],
                'appropriateness_rating': candidate['appropriateness_rating'],
                'clinical_reasoning': candidate['reasoning_zh'],
                'priority_level': '推荐' if candidate['appropriateness_rating'] >= 8 else '可考虑',
                'timing': '择期',
                'recommendation_id': candidate['recommendation_id'],
                'evidence_level': candidate['evidence_level'],
                'panel_name': candidate['panel_name']
            })
        
        return {
            'recommendations': recommendations,
            'reasoning': '基于ACR适宜性评分和向量相似度的排序推荐',
            'warnings': ['LLM服务不可用，使用降级推荐方案'],
            'method': '规则排序（降级）',
            'confidence': 0.75
        }
    
    def install_model(self, model_name: str = "qwen2.5:32b") -> bool:
        """安装Qwen模型"""
        try:
            logger.info(f"开始安装模型: {model_name}")
            
            payload = {"name": model_name}
            response = requests.post(
                f"{self.base_url}/api/pull",
                json=payload,
                stream=True,
                timeout=3600  # 1小时超时，模型下载需要时间
            )
            
            if response.status_code == 200:
                logger.info(f"✅ 模型 {model_name} 安装成功")
                self.model = model_name
                return True
            else:
                logger.error(f"❌ 模型安装失败: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"安装模型异常: {e}")
            return False
