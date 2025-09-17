"""
RAG+LLM智能推荐服务
结合向量语义搜索和大语言模型的医疗检查推荐系统
"""

import json
import re
import logging
import time
import os
import requests
import numpy as np
from typing import List, Dict, Any, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import openai
from app.core.config import settings
from app.services.rules_engine import load_engine
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError, Field
from typing import Union
from pathlib import Path

# 加载环境变量：统一从 backend/.env 读取，若不存在则回退默认行为
try:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(str(env_path))
    else:
        load_dotenv()
except Exception:
    load_dotenv()

logger = logging.getLogger(__name__)

def embed_with_siliconflow(text: str, api_key: Optional[str] = None, model: str = "BAAI/bge-m3", timeout: int = 60) -> List[float]:
    """使用SiliconFlow API生成文本嵌入向量"""
    api_key = api_key or os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        logger.warning("SILICONFLOW_API_KEY not set; using random vector")
        return np.random.rand(1024).tolist()
    try:
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "input": text}
        resp = requests.post("https://api.siliconflow.cn/v1/embeddings", json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["data"][0]["embedding"]
    except Exception as e:
        logger.warning(f"SiliconFlow embedding failed: {e}; using random vector")
        return np.random.rand(1024).tolist()

class RAGLLMRecommendationService:
    """增强RAG+LLM医疗检查推荐服务"""
    
    def __init__(self):
        self.db_config = {
            'host': os.getenv('PGHOST', 'localhost'),
            'port': int(os.getenv('PGPORT', 5432)),
            'database': os.getenv('PGDATABASE', 'acrac_db'),
            'user': os.getenv('PGUSER', 'postgres'),
            'password': os.getenv('PGPASSWORD', 'password')
        }
        
        # 配置LLM客户端（使用SiliconFlow的Qwen2.5-32B）
        api_key = os.getenv("SILICONFLOW_API_KEY") or getattr(settings, "SILICONFLOW_API_KEY", "")
        base_url = os.getenv("SILICONFLOW_BASE_URL") or getattr(settings, "SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        self.llm_client = openai.OpenAI(api_key=api_key, base_url=base_url)
        
        # 配置参数
        self.llm_model = os.getenv("SILICONFLOW_LLM_MODEL") or getattr(settings, "SILICONFLOW_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct")
        self.similarity_threshold = float(os.getenv("VECTOR_SIMILARITY_THRESHOLD") or getattr(settings, "VECTOR_SIMILARITY_THRESHOLD", 0.6))
        self.debug_mode = (os.getenv("DEBUG_MODE", str(getattr(settings, "DEBUG_MODE", False))).lower() == "true")
        # 新增可调检索/候选参数
        self.scene_recall_topk = int(os.getenv("RAG_SCENE_RECALL_TOPK", "8"))  # 场景召回数量（用于检索，不等于展示数量）
        # reranker config
        self.use_reranker = os.getenv("RAG_USE_RERANKER", "true").lower() == "true"
        self.reranker_model = os.getenv("RERANKER_MODEL") or getattr(settings, "RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
        # candidate recall topk (to control prompt length)
        self.procedure_candidate_topk = int(os.getenv("PROCEDURE_CANDIDATE_TOPK", "8"))
        # keyword config path for dynamic management
        self.keyword_config_path = os.getenv("RAG_KEYWORD_CONFIG_PATH", str(Path(__file__).resolve().parents[2] / "config" / "rag_keywords.json"))
        self.keyword_config = self._load_keyword_config()
        # rerank boosts
        self.panel_boost = float(os.getenv("RAG_PANEL_BOOST", "0.10"))
        self.topic_boost = float(os.getenv("RAG_TOPIC_BOOST", "0.20"))
        self.keyword_boost = float(os.getenv("RAG_KEYWORD_BOOST", "0.05"))
        self.rating_boost = float(os.getenv("RAG_RATING_BOOST", "0.03"))
        
        # 提示词配置参数
        self.top_scenarios = int(os.getenv("RAG_TOP_SCENARIOS", "2"))
        self.top_recommendations_per_scenario = int(os.getenv("RAG_TOP_RECOMMENDATIONS_PER_SCENARIO", "3"))
        self.show_reasoning = os.getenv("RAG_SHOW_REASONING", "true").lower() == "true"
        # Rules engine (disabled by default)
        try:
            self.rules_engine = load_engine()
        except Exception:
            self.rules_engine = None
    
    def connect_db(self):
        """建立数据库连接"""
        return psycopg2.connect(**self.db_config)
    
    def search_clinical_scenarios(self, conn, query_vector: List[float], top_k: int = 3) -> List[Dict]:
        """搜索最相关的临床场景"""
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            vec_str = "[" + ",".join(map(str, query_vector)) + "]"
            sql = f"""
                SELECT
                    cs.semantic_id,
                    COALESCE(NULLIF(cs.description_zh,''), cs.description_en) AS description_zh,
                    cs.clinical_context,
                    cs.patient_population,
                    cs.risk_level,
                    cs.age_group,
                    cs.gender,
                    cs.urgency_level,
                    cs.symptom_category,
                    p.name_zh as panel_name,
                    t.name_zh as topic_name,
                    (1 - (cs.embedding <=> '{vec_str}'::vector)) AS similarity
                FROM clinical_scenarios cs
                LEFT JOIN panels p ON cs.panel_id = p.id
                LEFT JOIN topics t ON cs.topic_id = t.id
                WHERE cs.embedding IS NOT NULL AND cs.is_active = true
                ORDER BY cs.embedding <=> '{vec_str}'::vector
                LIMIT {top_k}
            """
            cur.execute(sql)
            return [dict(row) for row in cur.fetchall()]
    
    def get_scenario_with_recommendations(self, conn, scenario_ids: List[str]) -> List[Dict]:
        """获取场景及其相关的检查推荐（按场景组织）"""
        if not scenario_ids:
            return []
        
        scenario_ids_str = "','".join(scenario_ids)
        scenario_ids_placeholders = "'" + scenario_ids_str + "'"
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            sql = f"""
                SELECT 
                    cs.semantic_id as scenario_id,
                    cs.description_zh as scenario_description,
                    cs.patient_population,
                    cs.risk_level,
                    cs.age_group,
                    cs.gender,
                    cs.urgency_level,
                    p.name_zh as panel_name,
                    t.name_zh as topic_name,
                    cr.procedure_id,
                    pd.name_zh AS procedure_name_zh,
                    pd.name_en AS procedure_name_en,
                    pd.modality,
                    pd.body_part,
                    pd.contrast_used,
                    pd.radiation_level,
                    pd.exam_duration,
                    pd.preparation_required,
                    cr.appropriateness_rating,
                    cr.appropriateness_category_zh,
                    cr.reasoning_zh,
                    cr.evidence_level,
                    cr.contraindications,
                    cr.special_considerations,
                    cr.pregnancy_safety
                FROM clinical_scenarios cs
                LEFT JOIN panels p ON cs.panel_id = p.id
                LEFT JOIN topics t ON cs.topic_id = t.id
                LEFT JOIN clinical_recommendations cr ON cs.semantic_id = cr.scenario_id
                LEFT JOIN procedure_dictionary pd ON cr.procedure_id = pd.semantic_id
                WHERE cs.semantic_id IN ({scenario_ids_placeholders})
                    AND cs.is_active = true
                    AND cr.is_active = true
                    AND pd.is_active = true
                    AND cr.appropriateness_rating >= 5
                ORDER BY cs.semantic_id, cr.appropriateness_rating DESC
            """
            cur.execute(sql)
            results = [dict(row) for row in cur.fetchall()]
        
        # 按场景组织数据
        scenarios_with_recs = {}
        for row in results:
            scenario_id = row['scenario_id']
            if scenario_id not in scenarios_with_recs:
                scenarios_with_recs[scenario_id] = {
                    'scenario_id': scenario_id,
                    # 兼容下游评测：同时提供 scenario_description 与 description_zh
                    'scenario_description': row['scenario_description'],
                    'description_zh': row['scenario_description'],
                    'patient_population': row['patient_population'],
                    'risk_level': row['risk_level'],
                    'age_group': row['age_group'],
                    'gender': row['gender'],
                    'urgency_level': row['urgency_level'],
                    'panel_name': row['panel_name'],
                    'topic_name': row['topic_name'],
                    'recommendations': []
                }
            
            if row['procedure_id']:  # 有推荐的情况
                scenarios_with_recs[scenario_id]['recommendations'].append({
                    'procedure_name_zh': row['procedure_name_zh'],
                    'procedure_name_en': row['procedure_name_en'],
                    'modality': row['modality'],
                    'body_part': row['body_part'],
                    'contrast_used': row['contrast_used'],
                    'radiation_level': row['radiation_level'],
                    'exam_duration': row['exam_duration'],
                    'preparation_required': row['preparation_required'],
                    'appropriateness_rating': row['appropriateness_rating'],
                    'appropriateness_category_zh': row['appropriateness_category_zh'],
                    'reasoning_zh': row['reasoning_zh'],
                    'evidence_level': row['evidence_level'],
                    'contraindications': row['contraindications'],
                    'special_considerations': row['special_considerations'],
                    'pregnancy_safety': row['pregnancy_safety']
                })
        
        return list(scenarios_with_recs.values())
    
    def prepare_llm_prompt(self, query: str, scenarios: List[Dict], scenarios_with_recs: List[Dict], is_low_similarity: bool = False, 
                          top_scenarios: Optional[int] = None, top_recs_per_scenario: Optional[int] = None, show_reasoning: Optional[bool] = None,
                          candidates: Optional[List[Dict]] = None) -> str:
        """准备LLM推理提示词（按场景组织推荐）"""
        
        # 使用传入参数或默认配置
        top_scenarios = top_scenarios if top_scenarios is not None else self.top_scenarios
        top_recs_per_scenario = top_recs_per_scenario if top_recs_per_scenario is not None else self.top_recommendations_per_scenario
        show_reasoning = show_reasoning if show_reasoning is not None else self.show_reasoning
        
        # 生成候选清单文本（若提供）
        candidates_block = ""
        if candidates:
            unique = []
            seen = set()
            for c in candidates:
                name = c.get('procedure_name_zh') or c.get('name_zh') or c.get('procedure_name') or ''
                modality = c.get('modality', '')
                key = (name, modality)
                if name and key not in seen:
                    seen.add(key)
                    unique.append({'name': name, 'modality': modality})
            if unique:
                lines = [f"{i+1}. {u['name']} ({u['modality']})" for i, u in enumerate(unique[:30])]
                candidates_block = "\n候选检查（必须从下列候选中选择，不得输出候选之外的检查）：\n" + "\n".join(lines) + "\n"

        if is_low_similarity:
            # 低相似度时的无RAG推理（精简版）
            prompt = f"""
你是放射科医生，根据临床情况推荐最合适的影像检查项目。

患者查询: "{query}"

注意：数据库中未找到匹配场景，请根据专业经验推荐3个最合适的影像检查项目。

 {candidates_block}

 严格输出要求：
仅输出有效JSON，不能包含任何解释、Markdown代码块或额外文字
不要使用```包裹，不要有多余的换行或注释
字段名必须严格一致；不要多输出未定义字段
JSON中不允许出现尾随逗号
若上方提供了候选检查，必须仅从候选中选择；若不合适可减少数量，但不得新增候选外检查

输出JSON格式:
{{
    "recommendations": [
        {{
            "rank": 1,
            "procedure_name": "检查项目名称",
            "modality": "检查方式",
            "appropriateness_rating": "评分/9",  
            "recommendation_reason": "推荐理由",
            "clinical_considerations": "临床考虑"
        }},
        {{
            "rank": 2,
            "procedure_name": "检查项目名称",
            "modality": "检查方式",
            "appropriateness_rating": "评分/9",
            "recommendation_reason": "推荐理由",
            "clinical_considerations": "临床考虑"
        }},
        {{
            "rank": 3,
            "procedure_name": "检查项目名称",
            "modality": "检查方式",
            "appropriateness_rating": "评分/9",
            "recommendation_reason": "推荐理由",
            "clinical_considerations": "临床考虑"
        }}
    ],
    "summary": "推荐总结",
    "no_rag": true,
    "rag_note": "无RAG模式：基于医生专业经验生成"
}}
"""
        else:
            # 有RAG数据时的提示词（可配置版）
            scenarios_info = ""
            # 使用可配置的场景数量
            valid_scenarios = [s for s in scenarios_with_recs if s.get('recommendations')]
            for i, scenario_data in enumerate(valid_scenarios[:top_scenarios], 1):
                scenario_info = f"""
## 场景 {i}: {scenario_data['scenario_id']}
**描述**: {scenario_data['scenario_description']}
**科室**: {scenario_data['panel_name']}
**主题**: {scenario_data['topic_name']}

### 推荐检查:
"""
                
                if scenario_data['recommendations']:
                    # 使用可配置的推荐数量
                    for j, rec in enumerate(scenario_data['recommendations'][:top_recs_per_scenario], 1):
                        rec_info = f"""
{j}. **{rec['procedure_name_zh']}** ({rec['modality']})
   - 评分: {rec['appropriateness_rating']}/9 ({rec['appropriateness_category_zh']})"""
                        
                        # 根据配置决定是否显示推荐理由
                        if show_reasoning and rec.get('reasoning_zh'):
                            reasoning = rec.get('reasoning_zh', 'N/A')
                            # 限制理由长度以控制提示词大小
                            if len(reasoning) > 200:
                                reasoning = reasoning[:200] + '...'
                            rec_info += f"\n   - 理由: {reasoning}"
                        
                        rec_info += "\n\n"
                        scenario_info += rec_info
                else:
                    scenario_info += "   该场景暂无高评分推荐。\n\n"
                
                scenarios_info += scenario_info
            
            # 相似度信息（与配置的场景数量匹配）
            similarity_info = ""
            for i, scenario in enumerate(scenarios[:top_scenarios], 1):
                similarity_info += f"   场景{i}: {scenario['similarity']:.3f}\n"
            
            prompt = f"""
你是放射科医生，根据临床场景推荐最合适的影像检查项目。你要遵循医学诊断规范和ACR-AC指南的相关规则进行合理推荐.

**患者查询**: "{query}"

**相似度**:
{similarity_info}

{scenarios_info}

基于以上信息，推荐最合适的3个影像检查项目。

{candidates_block}

严格输出要求：
仅输出有效JSON，不能包含任何解释、Markdown代码块或额外文字
不要使用```包裹，不要有多余的换行或注释
字段名必须严格一致；不要多输出未定义字段
JSON中不允许出现尾随逗号
必须基于上述上下文与候选进行推荐，并从候选中选择；不得输出候选之外的检查
对于每个被选择的检查项目，appropriateness_rating 必须与候选/上下文中展示的评分一致，不得改动或臆造；若上下文未提供评分，则省略该字段

输出JSON格式:
{{
    "recommendations": [
        {{
            "rank": 1,
            "procedure_name": "检查项目名称",
            "modality": "检查方式",
            "appropriateness_rating": "评分/9",
            "recommendation_reason": "推荐理由",
            "clinical_considerations": "临床考虑"
        }},
        {{
            "rank": 2,
            "procedure_name": "检查项目名称",
            "modality": "检查方式",
            "appropriateness_rating": "评分/9",
            "recommendation_reason": "推荐理由",
            "clinical_considerations": "临床考虑"
        }},
        {{
            "rank": 3,
            "procedure_name": "检查项目名称",
            "modality": "检查方式",
            "appropriateness_rating": "评分/9",
            "recommendation_reason": "推荐理由",
            "clinical_considerations": "临床考虑"
        }}
    ],
    "summary": "推荐总结",
    "no_rag": false
}}
"""
        
        return prompt

    def search_procedure_candidates(self, conn, query_vector: List[float], top_k: int = 15) -> List[Dict]:
        """基于向量在procedure_dictionary中检索候选检查项目"""
        if conn is None:
            return []
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            vec_str = "[" + ",".join(map(str, query_vector)) + "]"
            sql = f"""
                SELECT
                    pd.semantic_id,
                    pd.name_zh,
                    pd.name_en,
                    pd.modality,
                    pd.body_part,
                    pd.description_zh,
                    (1 - (pd.embedding <=> '{vec_str}'::vector)) AS similarity
                FROM procedure_dictionary pd
                WHERE pd.embedding IS NOT NULL AND pd.is_active = true
                ORDER BY pd.embedding <=> '{vec_str}'::vector
                LIMIT {top_k}
            """
            cur.execute(sql)
            rows = [dict(r) for r in cur.fetchall()]
            # 统一字段以便prompt使用
            for r in rows:
                r['procedure_name_zh'] = r.get('name_zh')
            return rows
    
    def call_llm(self, prompt: str) -> str:
        """调用LLM进行推理（使用Qwen2.5-32B）"""
        try:
            if self.debug_mode:
                logger.info(f"LLM调用模型: {self.llm_model}")
                logger.info(f"LLM提示词长度: {len(prompt)} 字符")
            
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": (
                        "你是一位专业的放射科医生，擅长影像检查推荐。"
                        "必须仅输出有效JSON，不得包含解释、代码块(如```json)、或任何额外文字。"
                        "JSON字段名必须与要求完全一致，且不得包含尾随逗号。"
                    )},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # 降低随机性，提高一致性
                max_tokens=3000
            )
            
            result = response.choices[0].message.content
            
            if self.debug_mode:
                logger.info(f"LLM原始响应长度: {len(result)} 字符")
                logger.info(f"LLM原始响应: {result[:500]}...")  # 只显示前500字符
            
            return result
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return self._fallback_response()
    
    def _fallback_response(self) -> str:
        """LLM调用失败时的降级响应"""
        return """
{
    "recommendations": [
        {
            "rank": 1,
            "procedure_name": "系统暂时无法生成推荐",
            "modality": "N/A",
            "appropriateness_rating": "N/A",
            "recommendation_reason": "LLM服务暂时不可用，请稍后重试",
            "clinical_considerations": "建议咨询专业医生"
        }
    ],
    "summary": "系统暂时无法提供智能推荐，建议使用传统向量搜索功能"
}
"""
    
    def parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            text = llm_response.strip()
            # 去除代码块围栏
            if text.startswith("```"):
                lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
                text = "\n".join(lines)

            # 规范化引号（将中文弯引号转义为 \" 以避免破坏JSON字符串）
            text = text.replace("“", '\\"').replace("”", '\\"').replace("’", "'").replace("‘", "'")

            # 提取平衡的JSON对象
            def extract_balanced_json(s: str) -> Optional[str]:
                start = s.find('{')
                if start == -1:
                    return None
                depth = 0
                in_str = False
                esc = False
                for i in range(start, len(s)):
                    ch = s[i]
                    if in_str:
                        if esc:
                            esc = False
                        elif ch == '\\':
                            esc = True
                        elif ch == '"':
                            in_str = False
                        continue
                    else:
                        if ch == '"':
                            in_str = True
                        elif ch == '{':
                            depth += 1
                        elif ch == '}':
                            depth -= 1
                            if depth == 0:
                                return s[start:i+1]
                return None

            candidate = extract_balanced_json(text)
            if not candidate:
                raise ValueError("未找到有效的JSON对象")

            # 去掉可能的尾随逗号
            candidate = re.sub(r",\s*([}\]])", r"\1", candidate)

            # 尝试解析
            data = json.loads(candidate)

            # 结果规范化
            if not isinstance(data, dict):
                data = {"recommendations": data}
            if "recommendations" not in data or not isinstance(data["recommendations"], list):
                data["recommendations"] = []
            if "summary" not in data:
                data["summary"] = ""

            # 基于Pydantic进行校验与纠正
            class _RecItem(BaseModel):
                rank: Optional[int] = None
                procedure_name: str = Field(default_factory=str)
                modality: str = Field(default_factory=str)
                appropriateness_rating: Union[str, int, float] = Field(default_factory=str)
                recommendation_reason: str = Field(default_factory=str)
                clinical_considerations: str = Field(default_factory=str)

            class _LLMOut(BaseModel):
                recommendations: List[_RecItem] = Field(default_factory=list)
                summary: str = Field(default_factory=str)
                no_rag: Optional[bool] = None
                rag_note: Optional[str] = None

            # 同义键纠正
            fixed_recs = []
            for i, rec in enumerate(data.get("recommendations", []), start=1):
                if not isinstance(rec, dict):
                    continue
                rec = dict(rec)
                if "procedure" in rec and "procedure_name" not in rec:
                    rec["procedure_name"] = rec.pop("procedure")
                # 合并可能的理由字段
                for alt in ["reason", "reasoning", "clinical_reasoning"]:
                    if alt in rec and not rec.get("recommendation_reason"):
                        rec["recommendation_reason"] = rec.pop(alt)
                # rank默认
                if "rank" not in rec or rec["rank"] in (None, ""):
                    rec["rank"] = i
                # 评分标准化为 "x/9"
                ar = rec.get("appropriateness_rating")
                if isinstance(ar, (int, float)):
                    try:
                        val = int(round(float(ar)))
                        rec["appropriateness_rating"] = f"{val}/9"
                    except Exception:
                        rec["appropriateness_rating"] = str(ar)
                elif isinstance(ar, str):
                    # 简单归一化，如 "8" -> "8/9"
                    s = ar.strip()
                    if s.isdigit():
                        rec["appropriateness_rating"] = f"{s}/9"
                fixed_recs.append(rec)

            data["recommendations"] = fixed_recs

            try:
                validated = _LLMOut(**data)
            except ValidationError as ve:
                logger.warning(f"LLM响应字段校验警告: {ve}")
                # 尽力返回已纠正的数据
                validated = _LLMOut(recommendations=[_RecItem(**r) for r in fixed_recs], summary=data.get("summary", ""))

            # 转回dict
            out = {
                "recommendations": [r.model_dump() for r in validated.recommendations],
                "summary": validated.summary,
            }
            # 兼容前端/其他调用方字段：补充 name / recommendation / procedure 同义字段
            try:
                for rec in out.get("recommendations", []) or []:
                    pname = rec.get("procedure_name")
                    if pname:
                        rec.setdefault("name", pname)
                        rec.setdefault("recommendation", pname)
                        rec.setdefault("procedure", pname)
            except Exception:
                pass
            if validated.no_rag is not None:
                out["no_rag"] = validated.no_rag
            if validated.rag_note is not None:
                out["rag_note"] = validated.rag_note

            return out
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")
            if self.debug_mode:
                logger.error(f"原始响应: {llm_response}")
            # 容错解析：基于正则从原始文本提取核心字段，尽力返回结构化结果
            try:
                recs = []
                txt = llm_response
                # 容许中文引号和普通引号
                q = '"“”'
                def val(pattern):
                    m = re.search(pattern, txt, re.S)
                    return m.group(1).strip() if m else ""
                # 匹配多个recommendation块
                patt = re.compile(r'"?procedure_name"?\s*:\s*(["“”])([^"“”]+)\1.*?"?modality"?\s*:\s*(["“”])([^"“”]+)\3.*?"?appropriateness_rating"?\s*:\s*(["“”])?([0-9/ ]+)\5?.*?"?recommendation_reason"?\s*:\s*(["“”])([^"“”]+)\7', re.S)
                for m in patt.finditer(txt):
                    procedure_name = m.group(2).strip()
                    modality = m.group(4).strip()
                    rating = m.group(6).strip()
                    reason = m.group(8).strip()
                    recs.append({
                        "rank": len(recs)+1,
                        "procedure_name": procedure_name,
                        "modality": modality,
                        "appropriateness_rating": rating,
                        "recommendation_reason": reason,
                        "clinical_considerations": ""
                    })
                summary = val(r'"?summary"?\s*:\s*(["“”])([^"“”]+)\1')
                if recs or summary:
                    return {"recommendations": recs, "summary": summary}
            except Exception as ee:
                logger.warning(f"容错解析也失败: {ee}")
            return {"recommendations": [], "summary": f"解析LLM响应失败: {str(e)}"}
    
    def generate_intelligent_recommendation(self, query: str, top_scenarios: Optional[int] = None, 
                                          top_recommendations_per_scenario: Optional[int] = None, 
                                          show_reasoning: Optional[bool] = None,
                                          similarity_threshold: Optional[float] = None,
                                          debug_flag: Optional[bool] = None,
                                          compute_ragas: Optional[bool] = None,
                                          ground_truth: Optional[str] = None) -> Dict[str, Any]:
        """生成智能推荐（主入口函数）"""
        start_time = time.time()
        debug_info = {}
        
        # 使用传入参数或默认配置
        current_threshold = similarity_threshold if similarity_threshold is not None else self.similarity_threshold
        
        try:
            # 1. 生成查询向量
            logger.info(f"开始处理查询: {query}")
            do_debug = (debug_flag is True) or self.debug_mode
            if do_debug:
                debug_info["step_1_query"] = query
                
            query_vector = embed_with_siliconflow(query)
            if do_debug:
                debug_info["step_2_vector_generation"] = {
                    "vector_dimension": len(query_vector),
                    "vector_sample": query_vector[:5]  # 只显示前5个元素
                }
            
            # 2. 连接数据库（失败则降级为无RAG模式）
            conn = None
            db_ok = True
            try:
                conn = self.connect_db()
            except Exception as db_err:
                db_ok = False
                logger.warning(f"数据库连接失败，将使用无RAG模式: {db_err}")
                if self.debug_mode:
                    debug_info["db_connection_error"] = str(db_err)
            
            # 3. 搜索相关临床场景（使用可配置的召回 Top K），若DB不可用则跳过
            logger.info("搜索相关临床场景...")
            recall_k = self.scene_recall_topk
            scenarios = []
            if db_ok and conn is not None:
                scenarios = self.search_clinical_scenarios(conn, query_vector, top_k=recall_k)
                # 取出召回场景的推荐，增强rerank语料
                try:
                    recall_ids = [s['semantic_id'] for s in scenarios]
                    scenarios_with_recs_all = self.get_scenario_with_recommendations(conn, recall_ids)
                except Exception as re:
                    logger.warning(f"召回场景推荐获取失败: {re}")
                    scenarios_with_recs_all = []
                # 面向 panel/topic/关键词 的软重排 + reranker（优先）
                try:
                    target_panels, target_topics = self._infer_targets_from_query(query)
                    scenarios = self._rerank_scenarios(
                        query,
                        scenarios,
                        target_panels=target_panels,
                        target_topics=target_topics,
                        alpha_panel=self.panel_boost,
                        alpha_topic=self.topic_boost,
                        alpha_kw=self.keyword_boost,
                        scenarios_with_recs=scenarios_with_recs_all,
                    )
                except Exception as re:
                    logger.warning(f"场景重排失败: {re}")

                # 规则引擎：rerank阶段（启用时可加权/过滤），默认audit-only
                try:
                    if self.rules_engine and self.rules_engine.enabled:
                        rr_ctx = {
                            "query": query,
                            "query_signals": self._extract_query_signals(query),
                        }
                        rr_res = self.rules_engine.apply_rerank(rr_ctx, scenarios)
                        scenarios = rr_res.get('scenarios') or scenarios
                        if do_debug:
                            debug_info.setdefault('rules_audit', {})['rerank'] = rr_res.get('audit_logs') or []
                except Exception as re:
                    logger.warning(f"规则引擎(rerank)执行失败: {re}")
            
            if do_debug:
                debug_info["step_3_scenarios_search"] = {
                    "found_scenarios": len(scenarios),
                    "scenarios": [
                        {
                            "id": s["semantic_id"],
                            "similarity": s["similarity"],
                            "description": s["description_zh"][:50] + "..."
                        } for s in scenarios[:10]
                    ]
                }
                debug_info["step_3_recall_topk"] = recall_k
                try:
                    tp, tt = self._infer_targets_from_query(query)
                    debug_info["step_3_targets"] = {"panels": list(tp), "topics": list(tt)}
                    debug_info["step_3_boosts"] = {
                        "panel_boost": self.panel_boost,
                        "topic_boost": self.topic_boost,
                        "keyword_boost": self.keyword_boost,
                    }
                except Exception:
                    pass
            
            if db_ok and not scenarios:
                return {
                    "success": False,
                    "message": "未找到相关的临床场景",
                    "recommendations": [],
                    "scenarios": [],
                    "debug_info": debug_info if self.debug_mode else None
                }
            
            # 4. 检查相似度阈值（使用可配置阈值）
            max_similarity = max((s.get("similarity", 0.0) for s in scenarios), default=0.0)
            is_low_similarity = (not db_ok) or (max_similarity < current_threshold)
            
            if do_debug:
                debug_info["step_4_similarity_check"] = {
                    "max_similarity": max_similarity,
                    "threshold": current_threshold,
                    "is_low_similarity": is_low_similarity,
                    "similarity_status": "low" if is_low_similarity else "high"
                }
            
            # 5. 根据相似度决定处理方式
            if is_low_similarity:
                # 低相似度：无RAG模式
                logger.info(f"最高相似度 {max_similarity:.3f} 低于阈值 {current_threshold}，使用无RAG模式")
                
                # 候选检查（procedure_dictionary向量检索，半RAG）
                candidates = []
                if db_ok and conn is not None:
                    try:
                        candidates = self.search_procedure_candidates(conn, query_vector, top_k=self.procedure_candidate_topk)
                    except Exception as ce:
                        logger.warning(f"候选检查检索失败: {ce}")
                prompt = self.prepare_llm_prompt(
                    query, scenarios, [], is_low_similarity=True,
                    top_scenarios=top_scenarios,
                    top_recs_per_scenario=top_recommendations_per_scenario,
                    show_reasoning=show_reasoning,
                    candidates=candidates
                )
                scenarios_with_recs = []
                
                if do_debug:
                    debug_info["step_5_mode"] = "no_rag"
                    debug_info["step_6_prompt_length"] = len(prompt)
                    debug_info["step_6_prompt_preview"] = prompt[:300] + "..."
                    if candidates:
                        debug_info["step_5_candidates"] = {
                            "count": len(candidates),
                            "preview": [
                                {
                                    "name": c.get("procedure_name_zh") or c.get("name_zh"),
                                    "modality": c.get("modality"),
                                    "similarity": c.get("similarity")
                                } for c in candidates[:5]
                            ]
                        }
            else:
                # 高相似度：RAG模式
                logger.info(f"最高相似度 {max_similarity:.3f} 高于阈值 {current_threshold}，使用RAG模式")
                
                # 获取场景及其推荐（复用召回时已取的，若无则再取）
                scenario_ids = [s['semantic_id'] for s in scenarios]
                try:
                    # 从之前召回缓存中过滤
                    _map = {s['scenario_id']: s for s in (locals().get('scenarios_with_recs_all') or [])}
                    scenarios_with_recs = [ _map[sid] for sid in scenario_ids if sid in _map ]
                    if not scenarios_with_recs:
                        scenarios_with_recs = self.get_scenario_with_recommendations(conn, scenario_ids)
                except Exception:
                    scenarios_with_recs = self.get_scenario_with_recommendations(conn, scenario_ids)
                # 从场景推荐构建候选清单
                candidates = []
                for sc in scenarios_with_recs:
                    for rec in sc.get('recommendations', []) or []:
                        candidates.append({
                            'procedure_name_zh': rec.get('procedure_name_zh'),
                            'modality': rec.get('modality')
                        })
                prompt = self.prepare_llm_prompt(
                    query, scenarios, scenarios_with_recs, is_low_similarity=False,
                    top_scenarios=top_scenarios,
                    top_recs_per_scenario=top_recommendations_per_scenario,
                    show_reasoning=show_reasoning,
                    candidates=candidates
                )
                
                if do_debug:
                    debug_info["step_5_mode"] = "rag"
                    debug_info["step_5_scenarios_with_recs"] = {
                        "scenarios_count": len(scenarios_with_recs),
                        "total_recommendations": sum(len(s.get("recommendations", [])) for s in scenarios_with_recs),
                        "scenarios_summary": [
                            {
                                "id": s["scenario_id"],
                                "description": s["scenario_description"][:50] + "...",
                                "recommendations_count": len(s.get("recommendations", []))
                            } for s in scenarios_with_recs
                        ]
                    }
                    debug_info["step_6_prompt_length"] = len(prompt)
                    debug_info["step_6_prompt_preview"] = prompt[:500] + "..."
            
            # 6. 调用LLM进行推理
            logger.info("调用LLM进行推理...")
            llm_response = self.call_llm(prompt)

            # 7. 解析LLM响应（若LLM不可用则回退到基于RAG候选的确定性结果）
            parsed_result = self.parse_llm_response(llm_response)
            try:
                def _looks_like_llm_down(res: dict) -> bool:
                    recs = (res or {}).get("recommendations") or []
                    if len(recs) == 1 and (recs[0] or {}).get("procedure_name") == "系统暂时无法生成推荐":
                        return True
                    return False
                if _looks_like_llm_down(parsed_result):
                    # 基于已检索到的场景推荐，生成确定性Top-K作为降级结果
                    base = []
                    seen = set()
                    max_k = max(1, int(top_recommendations_per_scenario))
                    for sc in (scenarios_with_recs or []):
                        for rec in sc.get("recommendations", []) or []:
                            name = rec.get("procedure_name_zh") or rec.get("procedure_name_en")
                            if not name or name in seen:
                                continue
                            seen.add(name)
                            ar = rec.get("appropriateness_rating")
                            if isinstance(ar, (int, float)):
                                ar = f"{int(round(float(ar)))}/9"
                            elif isinstance(ar, str) and ar.strip().isdigit():
                                ar = f"{ar.strip()}/9"
                            base.append({
                                "rank": len(base) + 1,
                                "procedure_name": name,
                                "modality": rec.get("modality") or "",
                                "appropriateness_rating": ar or "",
                                "recommendation_reason": rec.get("reasoning_zh") or rec.get("special_considerations") or "",
                                "clinical_considerations": rec.get("contraindications") or "",
                            })
                            if len(base) >= max_k:
                                break
                        if len(base) >= max_k:
                            break
                    if base:
                        parsed_result = {
                            "recommendations": base,
                            "summary": "LLM不可用，已基于RAG检索与知识库生成确定性Top-K推荐"
                        }
                        if do_debug:
                            debug_info["fallback_mode"] = "baseline_from_rag"
            except Exception as _fe:
                logger.warning(f"构建降级结果失败: {_fe}")

            # 规则引擎：post阶段（审计/修订）
            try:
                if self.rules_engine and self.rules_engine.enabled:
                    post_ctx = {
                        "query": query,
                        "query_signals": self._extract_query_signals(query),
                        "scenarios": scenarios,
                    }
                    post_res = self.rules_engine.apply_post(post_ctx, parsed_result)
                    if do_debug:
                        debug_info.setdefault('rules_audit', {})['post'] = post_res.get('audit_logs') or []
                    parsed_result = post_res.get('parsed') or parsed_result
            except Exception as pe:
                logger.warning(f"规则引擎(post)执行失败: {pe}")

            end_time = time.time()
            processing_time = int((end_time - start_time) * 1000)

            if do_debug:
                debug_info["step_7_llm_response_length"] = len(llm_response)
                debug_info["step_8_parsing_success"] = "recommendations" in parsed_result
                debug_info["step_9_total_time_ms"] = processing_time

            result = {
                "success": True,
                "query": query,
                "scenarios": scenarios,
                "scenarios_with_recommendations": scenarios_with_recs,
                "llm_recommendations": parsed_result,
                "processing_time_ms": processing_time,
                "model_used": self.llm_model,
                "similarity_threshold": current_threshold,
                "max_similarity": max_similarity,
                "is_low_similarity_mode": is_low_similarity,
                "llm_raw_response": llm_response if do_debug else None,
                "debug_info": debug_info if do_debug else None
            }

            # 构建可选的“过程追踪”与RAGAS评估
            if do_debug:
                trace = {}
                def _scenario_text(entry: Dict[str, Any]) -> Optional[str]:
                    return (
                        entry.get("clinical_scenario")
                        or entry.get("description_zh")
                        or entry.get("scenario_description")
                        or entry.get("description")
                    )

                trace["recall_scenarios"] = [
                    {
                        "id": s.get("semantic_id"),
                        "panel": s.get("panel_name"),
                        "topic": s.get("topic_name"),
                        "similarity": s.get("similarity"),
                        "clinical_scenario": _scenario_text(s),
                    } for s in scenarios
                ]
                trace["rerank_scenarios"] = [
                    {
                        "id": s.get("semantic_id"),
                        "_rerank_score": s.get("_rerank_score"),
                        "panel": s.get("panel_name"),
                        "topic": s.get("topic_name"),
                        "similarity": s.get("similarity"),
                        "clinical_scenario": _scenario_text(s),
                    } for s in scenarios
                ]
                # 完整prompt（注意：可能较长）
                trace["final_prompt"] = prompt
                trace["llm_raw"] = llm_response
                trace["llm_parsed"] = parsed_result
                # 构造RAGAS上下文（与评测器一致）
                contexts = self._build_ragas_contexts_from_payload({
                    "scenarios": scenarios,
                    "scenarios_with_recommendations": scenarios_with_recs
                })
                trace["ragas_contexts_count"] = len(contexts)
                # 可选RAGAS评估
                if compute_ragas:
                    try:
                        ragas_scores = self._compute_ragas_scores(
                            user_input=query,
                            answer=self._format_answer_for_ragas(parsed_result),
                            contexts=contexts,
                            reference=ground_truth
                        )
                        trace["ragas_scores"] = ragas_scores
                    except Exception as e:
                        trace["ragas_error"] = str(e)
                result["trace"] = trace
            
            if do_debug:
                logger.info(f"推荐生成完成，总耗时: {processing_time}ms")
                logger.info(f"生成推荐数量: {len(parsed_result.get('recommendations', []))}")
            return result
            
        except Exception as e:
            logger.error(f"生成智能推荐失败: {e}")
            return {
                "success": False,
                "message": f"生成推荐失败: {str(e)}",
                "error": str(e),
                "debug_info": debug_info if self.debug_mode else None
            }
        finally:
            if 'conn' in locals() and conn:
                conn.close()

    def _extract_query_signals(self, query: str) -> Dict[str, Any]:
        """Lightweight, rule-friendly signals from query text.
        This avoids any online LLM; extend offline for better coverage.
        """
        q = query or ''
        signals: Dict[str, Any] = {}
        # pregnancy
        if any(k in q for k in ['孕', '妊娠', '孕妇', '围产', '产后']):
            signals['pregnancy_status'] = '妊娠/围产'
        # urgency / thunderclap
        kws = []
        for k in ['急诊', '急性', '突发', '雷击样', '霹雳样', 'TCH', 'SAH', '蛛网膜下腔出血']:
            if (k.lower() in q.lower()) or (k in q):
                kws.append(k)
        if kws:
            signals['keywords'] = kws
        return signals

    def _build_ragas_contexts_from_payload(self, payload: Dict[str, Any]) -> List[str]:
        contexts = []
        for sc in payload.get('scenarios_with_recommendations') or []:
            desc = sc.get('scenario_description') or sc.get('description_zh')
            if desc:
                contexts.append(desc)
            for r in (sc.get('recommendations') or []):
                reason = r.get('reasoning_zh')
                if reason:
                    contexts.append(reason)
        for sc in payload.get('scenarios') or []:
            desc = sc.get('description_zh')
            if desc:
                contexts.append(desc)
        return contexts

    def _format_answer_for_ragas(self, parsed: Dict[str, Any]) -> str:
        lines = []
        for r in parsed.get('recommendations') or []:
            name = r.get('procedure_name', '')
            mod = r.get('modality', '')
            rating = r.get('appropriateness_rating', '')
            reason = r.get('recommendation_reason', '')
            t = f"{name} ({mod}) - 评分: {rating}"
            if reason:
                t += f"\n理由: {reason}"
            lines.append(t)
        if parsed.get('summary'):
            lines.append(f"总结: {parsed.get('summary')}")
        return "\n".join(lines) if lines else "无"

    def _compute_ragas_scores(self, user_input: str, answer: str, contexts: List[str], reference: str) -> Dict[str, float]:
        """Compute RAGAS scores.
        Primary path runs in-process. If the runtime is under uvloop and
        ragas/nest_asyncio fails to patch the loop, fall back to an isolated
        subprocess that uses the default asyncio loop policy.
        """
        try:
            # 尝试常规（进程内）评测
            import ragas
            from datasets import Dataset
            from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
            from langchain_openai import ChatOpenAI, OpenAIEmbeddings
            from ragas.llms import LangchainLLMWrapper
            from ragas.embeddings import LangchainEmbeddingsWrapper

            api_key = os.getenv("SILICONFLOW_API_KEY")
            base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
            llm_model = os.getenv("SILICONFLOW_LLM_MODEL", self.llm_model)
            emb_model = os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")

            llm = ChatOpenAI(model=llm_model, api_key=api_key, base_url=base_url, temperature=0)
            emb = OpenAIEmbeddings(model=emb_model, api_key=api_key, base_url=base_url)
            w_llm = LangchainLLMWrapper(llm)
            w_emb = LangchainEmbeddingsWrapper(emb)

            has_ref = bool(reference and str(reference).strip())
            if has_ref:
                data_dict = {
                    "question": [user_input],
                    "answer": [answer],
                    "contexts": [contexts],
                    "ground_truth": [reference],
                }
                metrics = [
                    Faithfulness(llm=w_llm),
                    AnswerRelevancy(llm=w_llm, embeddings=w_emb),
                    ContextPrecision(llm=w_llm),
                    ContextRecall(llm=w_llm),
                ]
            else:
                # 未提供ground_truth时，计算不依赖参考答案的指标
                data_dict = {
                    "question": [user_input],
                    "answer": [answer],
                    "contexts": [contexts],
                }
                metrics = [
                    Faithfulness(llm=w_llm),
                    AnswerRelevancy(llm=w_llm, embeddings=w_emb),
                ]

            data = Dataset.from_dict(data_dict)
            res = ragas.evaluate(
                data,
                metrics=metrics,
            )
            # Normalize possible output formats
            if isinstance(res, dict):
                base = res
            elif hasattr(res, 'scores') and isinstance(res.scores, dict):
                base = res.scores
            else:
                try:
                    base = dict(res)
                except Exception:
                    base = {}
            def clean(v):
                try:
                    f = float(v)
                except Exception:
                    return 0.0
                return 0.0 if (f != f) else f
            return {
                'faithfulness': clean(base.get('faithfulness', 0.0)),
                'answer_relevancy': clean(base.get('answer_relevancy', 0.0)),
                'context_precision': clean(base.get('context_precision', 0.0)),
                'context_recall': clean(base.get('context_recall', 0.0)),
            }
        except Exception as e:
            # 进程内评测失败的兜底逻辑：
            # 1) uvloop/nest_asyncio 冲突 → 子进程隔离
            # 2) ImportError/No module named → 子进程隔离（避免热加载/路径差异导致的导入问题）
            msg = str(e)
            if isinstance(e, ImportError) or 'No module named' in msg:
                logger.warning(f"RAGAS进程内导入失败，尝试子进程隔离执行: {e}")
                try:
                    return self._compute_ragas_scores_isolated(user_input, answer, contexts, reference)
                except Exception as e2:
                    logger.error(f"RAGAS子进程评测失败: {e2}")
                    raise
            if "Can't patch loop of type <class 'uvloop.Loop'>" in msg or 'nest_asyncio' in msg or 'uvloop' in msg:
                logger.warning(f"RAGAS进程内评测失败，尝试子进程隔离执行: {e}")
                try:
                    return self._compute_ragas_scores_isolated(user_input, answer, contexts, reference)
                except Exception as e2:
                    logger.error(f"RAGAS子进程评测失败: {e2}")
                    # 将错误向上传递，让调用方在 trace 中记录 ragas_error
                    raise
            # 其它异常也上抛，由调用方记录错误
            logger.error(f"RAGAS评测失败: {e}")
            raise

    def _compute_ragas_scores_isolated(self, user_input: str, answer: str, contexts: List[str], reference: str) -> Dict[str, float]:
        """在隔离的子进程中计算RAGAS分数，避免与 uvloop 事件循环冲突。"""
        import json as _json
        import subprocess as _subprocess
        import sys as _sys

        payload = {
            "user_input": user_input,
            "answer": answer,
            "contexts": contexts,
            "reference": reference,
            # 将默认模型也传给子进程以保证一致性
            "llm_model": os.getenv("SILICONFLOW_LLM_MODEL", self.llm_model),
        }
        code = r"""
import os, json, asyncio
# 使用标准事件循环策略，避免 uvloop
try:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except Exception:
    pass

cfg = json.loads(os.environ.get('RAGAS_INPUT', '{}'))
user_input = cfg.get('user_input')
answer = cfg.get('answer')
contexts = cfg.get('contexts') or []
reference = cfg.get('reference')

import ragas
from datasets import Dataset
from ragas.metrics import Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

api_key = os.getenv('SILICONFLOW_API_KEY')
base_url = os.getenv('SILICONFLOW_BASE_URL', 'https://api.siliconflow.cn/v1')
llm_model = os.getenv('SILICONFLOW_LLM_MODEL', cfg.get('llm_model', 'Qwen/Qwen2.5-32B-Instruct'))
emb_model = os.getenv('SILICONFLOW_EMBEDDING_MODEL', 'BAAI/bge-m3')

llm = ChatOpenAI(model=llm_model, api_key=api_key, base_url=base_url, temperature=0)
emb = OpenAIEmbeddings(model=emb_model, api_key=api_key, base_url=base_url)
w_llm = LangchainLLMWrapper(llm)
w_emb = LangchainEmbeddingsWrapper(emb)

has_ref = bool(reference and str(reference).strip())
if has_ref:
    data_dict = {
        'question': [user_input],
        'answer': [answer],
        'contexts': [contexts],
        'ground_truth': [reference],
    }
    metrics = [
        Faithfulness(llm=w_llm),
        AnswerRelevancy(llm=w_llm, embeddings=w_emb),
        ContextPrecision(llm=w_llm),
        ContextRecall(llm=w_llm),
    ]
else:
    data_dict = {
        'question': [user_input],
        'answer': [answer],
        'contexts': [contexts],
    }
    metrics = [
        Faithfulness(llm=w_llm),
        AnswerRelevancy(llm=w_llm, embeddings=w_emb),
    ]

data = Dataset.from_dict(data_dict)
res = ragas.evaluate(
    data,
    metrics=metrics,
)
if isinstance(res, dict):
    base = res
elif hasattr(res, 'scores') and isinstance(res.scores, dict):
    base = res.scores
else:
    try:
        base = dict(res)
    except Exception:
        base = {}

def clean(v):
    try:
        f = float(v)
    except Exception:
        return 0.0
    return 0.0 if (f != f) else f

out = {
    'faithfulness': clean(base.get('faithfulness', 0.0)),
    'answer_relevancy': clean(base.get('answer_relevancy', 0.0)),
    'context_precision': clean(base.get('context_precision', 0.0)),
    'context_recall': clean(base.get('context_recall', 0.0)),
}
print(json.dumps(out))
"""
        env = dict(os.environ)
        env["RAGAS_INPUT"] = _json.dumps(payload, ensure_ascii=False)
        # 使用当前 Python 解释器执行子进程
        proc = _subprocess.run([
            _sys.executable, "-c", code
        ], env=env, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            raise RuntimeError(f"ragas subprocess failed: {proc.stderr.strip()}")
        try:
            return _json.loads(proc.stdout.strip())
        except Exception as je:
            raise RuntimeError(f"invalid ragas subprocess output: {je}; raw={proc.stdout[:2000]}")

    def _infer_targets_from_query(self, query: str):
        q = (query or "").lower()
        panels = set()
        topics = set()
        cfg = self.keyword_config or {}
        for grp in cfg.get('groups', []):
            kws = [k.lower() for k in grp.get('keywords', [])]
            if any(k in q for k in kws):
                for p in grp.get('panels', []) or []:
                    panels.add(p)
                for t in grp.get('topics', []) or []:
                    topics.add(t)
        return panels, topics

    def _rerank_scenarios(
        self,
        query: str,
        scenarios: List[Dict],
        target_panels: Optional[set] = None,
        target_topics: Optional[set] = None,
        alpha_panel: float = 0.1,
        alpha_topic: float = 0.2,
        alpha_kw: float = 0.05,
        scenarios_with_recs: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        if not scenarios:
            return scenarios
        # Try SiliconFlow reranker first
        if self.use_reranker:
            try:
                reranked = self._siliconflow_rerank_scenarios(query, scenarios, scenarios_with_recs)
                if reranked:
                    return reranked
            except Exception as e:
                logger.warning(f"SiliconFlow reranker failed, fallback to keyword rerank: {e}")
        target_panels = target_panels or set()
        target_topics = target_topics or set()
        q = (query or "").lower()
        kw_groups = [[k.lower() for k in grp] for grp in (self.keyword_config.get('keyword_groups_for_bonus', []) or [])]
        # Map scenario_id -> top rating
        top_rating_map = {}
        if scenarios_with_recs:
            for sc in scenarios_with_recs:
                rid = sc.get('scenario_id')
                ratings = [r.get('appropriateness_rating') or 0 for r in (sc.get('recommendations') or [])]
                ratings = [int(r) for r in ratings if r is not None]
                top_rating_map[rid] = max(ratings) if ratings else 0
        def kw_bonus(desc: str) -> float:
            d = (desc or "").lower()
            bonus = 0.0
            for grp in kw_groups:
                if any(k in q for k in grp) and any(k in d for k in grp):
                    bonus += alpha_kw
            return bonus
        rescored = []
        for s in scenarios:
            sim = float(s.get("similarity", 0.0))
            panel = (s.get("panel_name") or "").strip()
            topic = (s.get("topic_name") or "").strip()
            b_panel = alpha_panel if panel in target_panels else 0.0
            b_topic = alpha_topic if topic in target_topics else 0.0
            b_kw = kw_bonus(s.get("description_zh", ""))
            # rating bonus based on top rating in scenario (scaled 0..9)
            sid = s.get('semantic_id')
            top_rt = float(top_rating_map.get(sid, 0.0))
            b_rating = self.rating_boost * (top_rt / 9.0)
            score = sim * (1.0 + b_panel + b_topic + b_kw + b_rating)
            s2 = dict(s)
            s2["_rerank_score"] = score
            rescored.append(s2)
        rescored.sort(key=lambda x: x.get("_rerank_score", 0.0), reverse=True)
        return rescored

    def _load_keyword_config(self) -> dict:
        try:
            path = Path(self.keyword_config_path)
            if path.exists():
                return json.loads(path.read_text(encoding='utf-8'))
        except Exception as e:
            logger.warning(f"加载关键词配置失败: {e}")
        # 默认内置
        return {
            "groups": [
                {"keywords": ["tia", "短暂性", "弥散", "dwi", "无力", "卒中", "脑缺血"],
                 "panels": ["神经内科", "神经外科", "放射科"],
                 "topics": ["脑卒中", "短暂性脑缺血", "颅脑影像"]},
                {"keywords": ["孕", "妊娠", "孕妇"],
                 "panels": ["胸外科", "心血管内科", "放射科", "妇产科"],
                 "topics": ["疑似肺栓塞", "孕期影像"]},
                {"keywords": ["肺栓塞", "pe", "栓塞", "呼吸困难", "ctpa"],
                 "panels": ["胸外科", "心血管内科", "放射科"],
                 "topics": ["疑似肺栓塞", "胸部影像"]},
                {"keywords": ["头痛", "偏头痛", "颅内", "mri", "ct"],
                 "panels": ["神经内科", "放射科"],
                 "topics": ["头痛", "颅脑影像"]}
            ],
            "keyword_groups_for_bonus": [
                ["tia", "短暂性", "弥散", "dwi", "无力"],
                ["孕", "妊娠", "孕妇"],
                ["肺栓塞", "pe", "栓塞", "呼吸困难", "ctpa", "v/q", "灌注"],
                ["头痛", "颅", "mri", "ct"]
            ]
        }

    def _siliconflow_rerank_scenarios(self, query: str, scenarios: List[Dict], scenarios_with_recs: Optional[List[Dict]] = None) -> List[Dict]:
        """Use SiliconFlow rerank endpoint with BAAI/bge-reranker-v2-m3.
        Fallback gracefully if the endpoint/model is unavailable.
        """
        api_key = os.getenv("SILICONFLOW_API_KEY")
        base = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        if not api_key:
            raise RuntimeError("SILICONFLOW_API_KEY not set")
        # Build richer docs: description + top rec names + truncated reasoning
        rec_map = {}
        if scenarios_with_recs:
            for sc in scenarios_with_recs:
                recs = sc.get('recommendations') or []
                parts = []
                for r in recs[:3]:
                    name = r.get('procedure_name_zh') or ''
                    reason = r.get('reasoning_zh') or ''
                    if len(reason) > 160:
                        reason = reason[:160] + '...'
                    parts.append(f"{name}:{reason}")
                rec_map[sc.get('scenario_id')] = " ; ".join(parts)
        docs = []
        for s in scenarios:
            sid = s.get('semantic_id')
            extras = rec_map.get(sid, '')
            txt = " | ".join(filter(None, [s.get('description_zh'), s.get('panel_name'), s.get('topic_name'), extras]))
            docs.append(txt or "")
        payload = {
            "model": self.reranker_model,
            "query": query,
            "documents": docs,
            "top_n": len(docs)
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        url = f"{base}/rerank"
        resp = requests.post(url, json=payload, headers=headers, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"rerank API {resp.status_code}: {resp.text}")
        data = resp.json()
        # Expect data like {"results":[{"index":i,"relevance_score":score}, ...]}
        results = data.get("results") or data.get("data") or []
        if not results:
            return []
        # Map scores back
        scored = []
        for r in results:
            idx = r.get("index") if isinstance(r, dict) else None
            score = r.get("relevance_score") if isinstance(r, dict) else None
            if idx is None or score is None:
                continue
            if 0 <= idx < len(scenarios):
                s2 = dict(scenarios[idx])
                s2["_rerank_score"] = float(score)
                scored.append(s2)
        if not scored:
            return []
        scored.sort(key=lambda x: x.get("_rerank_score", 0.0), reverse=True)
        return scored

# 创建全局服务实例
rag_llm_service = RAGLLMRecommendationService()
