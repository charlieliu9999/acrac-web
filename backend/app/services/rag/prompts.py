from typing import Any, Dict, List, Optional


def prepare_llm_prompt(
    query: str,
    scenarios: List[Dict[str, Any]],
    scenarios_with_recs: List[Dict[str, Any]],
    *,
    is_low_similarity: bool = False,
    top_scenarios: int = 2,
    top_recs_per_scenario: int = 3,
    show_reasoning: bool = True,
    candidates: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Build the prompt for LLM reasoning.

    Supports two modes:
      - no-RAG (low similarity): concise prompt, optional candidates
      - RAG (with scenarios + recommendations): structured prompt with
        top K scenarios and top N recs per scenario.
    """
    # candidates list block (optional)
    candidates_block = ""
    if candidates:
        unique = []
        seen = set()
        for c in candidates:
            name = (
                c.get("procedure_name_zh")
                or c.get("name_zh")
                or c.get("procedure_name")
                or ""
            )
            modality = c.get("modality", "")
            key = (name, modality)
            if name and key not in seen:
                seen.add(key)
                unique.append({"name": name, "modality": modality})
        if unique:
            lines = [
                f"{i+1}. {u['name']} ({u['modality']})" for i, u in enumerate(unique[:30])
            ]
            candidates_block = (
                "\n候选检查（必须从下列候选中选择，不得输出候选之外的检查）：\n"
                + "\n".join(lines)
                + "\n"
            )

    if is_low_similarity:
        prompt = f"""
你是放射科医生，根据临床情况推荐最合适的影像检查项目。

患者查询: "{query}"

注意：数据库中未找到匹配场景，请根据专业经验推荐3个最合适的影像检查项目。

 {candidates_block}

严格输出要求：
仅输出有效JSON，不能包含任何解释、Markdown代码块或额外文字
不要使用```包裹，不要有多余的换行或注释
字段名必须严格一致；不要多输出未定义字段
字段名只能是以下集合，严禁添加任何前缀（如 log_ 等）：
rank, procedure_name, modality, appropriateness_rating, recommendation_reason, clinical_considerations
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
        return prompt

    # With RAG contexts
    scenarios_info = ""
    valid_scenarios = [s for s in scenarios_with_recs if s.get("recommendations")]
    for i, scenario_data in enumerate(valid_scenarios[:top_scenarios], 1):
        scenario_info = f"""
## 场景 {i}: {scenario_data['scenario_id']}
**描述**: {scenario_data['scenario_description']}
**科室**: {scenario_data['panel_name']}
**主题**: {scenario_data['topic_name']}

### 推荐检查:
"""
        if scenario_data["recommendations"]:
            for j, rec in enumerate(
                scenario_data["recommendations"][: top_recs_per_scenario], 1
            ):
                rec_info = f"""
{j}. **{rec['procedure_name_zh']}** ({rec['modality']})
   - 评分: {rec['appropriateness_rating']}/9 ({rec['appropriateness_category_zh']})"""
                if show_reasoning and rec.get("reasoning_zh"):
                    reasoning = rec.get("reasoning_zh", "N/A")
                    if len(reasoning) > 200:
                        reasoning = reasoning[:200] + "..."
                    rec_info += f"\n   - 理由: {reasoning}"
                rec_info += "\n\n"
                scenario_info += rec_info
        else:
            scenario_info += "   该场景暂无高评分推荐。\n\n"
        scenarios_info += scenario_info

    similarity_info = ""
    for i, scenario in enumerate(scenarios[:top_scenarios], 1):
        similarity_info += f"   场景{i}: {scenario['similarity']:.3f}\n"

    prompt = f"""
你是放射科医生，根据临床场景推荐最合适的影像检查项目。你要遵循医学诊断规范和ACR-AC指南的相关规则进行合理推荐.

**患者查询**: "{query}"

**相似度**:
{similarity_info}

{scenarios_info}

基于以上信息，必须输出且仅输出最合适的3个影像检查项目（严格3条）。

{candidates_block}

严格输出要求：
仅输出有效JSON，不能包含任何解释、Markdown代码块或额外文字
不要使用```包裹，不要有多余的换行或注释
字段名必须严格一致；不要多输出未定义字段
字段名只能是以下集合，严禁添加任何前缀（如 log_ 等）：
rank, procedure_name, modality, appropriateness_rating, recommendation_reason, clinical_considerations
JSON中不允许出现尾随逗号
必须基于上述上下文与候选进行推荐，并从候选中选择；不得输出候选之外的检查
对于每个被选择的检查项目，appropriateness_rating 必须与候选/上下文中展示的评分一致，不得改动或臆造；若上下文未提供评分，则省略该字段

输出JSON格式（严格3条，键名必须与下方完全一致，禁止 log_ 前缀）：
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
