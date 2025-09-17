from typing import List, Dict


def format_vector(vec: List[float]) -> str:
    """Utility to format vector as SQL literal string."""
    return "[" + ",".join(map(str, vec)) + "]"


def scenarios_sql(vec_str: str, top_k: int) -> str:
    return f"""
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

