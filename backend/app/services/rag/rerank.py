from typing import List, Dict, Optional, Set


def keyword_bonus_score(query: str, desc: str, keyword_groups: List[List[str]]) -> float:
    q = (query or "").lower()
    d = (desc or "").lower()
    bonus = 0.0
    for grp in keyword_groups:
        if any(k in q for k in grp) and any(k in d for k in grp):
            bonus += 0.02
    return bonus


def rerank(
    query: str,
    scenarios: List[Dict],
    *,
    target_panels: Optional[Set[str]] = None,
    target_topics: Optional[Set[str]] = None,
    keyword_groups: Optional[List[List[str]]] = None,
) -> List[Dict]:
    """Lightweight rerank by similarity and soft bonuses.
    Mirrors current in-service logic to enable gradual migration.
    """
    target_panels = target_panels or set()
    target_topics = target_topics or set()
    out: List[Dict] = []
    for s in scenarios or []:
        sc = dict(s)
        base = float(sc.get("_rerank_score") or sc.get("similarity") or 0.0)
        bonus = 0.0
        if sc.get("panel_name") in target_panels:
            bonus += 0.05
        if sc.get("topic_name") in target_topics:
            bonus += 0.10
        if keyword_groups:
            bonus += keyword_bonus_score(query, sc.get("description_zh") or "", keyword_groups)
        sc["_rerank_score"] = base + bonus
        out.append(sc)
    out.sort(key=lambda x: x.get("_rerank_score", 0.0), reverse=True)
    return out

