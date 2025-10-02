import os
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


def rerank_scenarios(
    query: str,
    scenarios: List[Dict[str, Any]],
    *,
    provider: str = "auto",
    base_url: Optional[str] = None,
    model_id: Optional[str] = None,
    use_reranker: bool = True,
    target_panels: Optional[set] = None,
    target_topics: Optional[set] = None,
    keyword_config: Optional[Dict[str, Any]] = None,
    alpha_panel: float = 0.1,
    alpha_topic: float = 0.2,
    alpha_kw: float = 0.05,
    scenarios_with_recs: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Rerank scenarios using SiliconFlow / local cross-encoder or keyword boosts."""
    if not scenarios:
        return scenarios

    provider_eff = (provider or "auto").lower()
    base = (base_url or "").lower()
    is_ollama = ("11434" in base) or ("ollama" in base)
    if provider_eff == "auto":
        provider_eff = "ollama" if is_ollama else "siliconflow"

    if use_reranker:
        if provider_eff == "siliconflow":
            try:
                reranked = _siliconflow_rerank_scenarios(
                    query,
                    scenarios,
                    scenarios_with_recs=scenarios_with_recs,
                    base_url=base_url,
                    model_id=model_id,
                )
                if reranked:
                    return reranked
            except Exception as e:
                logger.warning(
                    f"SiliconFlow reranker failed, fallback to keyword rerank: {e}"
                )
        else:  # local/ollama
            try:
                reranked = _local_rerank_scenarios(
                    query,
                    scenarios,
                    scenarios_with_recs=scenarios_with_recs,
                    model_id=model_id,
                )
                if reranked:
                    return reranked
            except Exception as e:
                logger.warning(f"Local reranker failed, fallback: {e}")

    # keyword/boost fallback
    target_panels = target_panels or set()
    target_topics = target_topics or set()
    q = (query or "").lower()
    kw_groups = [
        [k.lower() for k in grp]
        for grp in (keyword_config.get("keyword_groups_for_bonus", []) if keyword_config else [])
    ]
    top_rating_map: Dict[str, int] = {}
    if scenarios_with_recs:
        for sc in scenarios_with_recs:
            rid = sc.get("scenario_id")
            ratings = [r.get("appropriateness_rating") or 0 for r in (sc.get("recommendations") or [])]
            try:
                ratings = [int(r) for r in ratings if r is not None]
            except Exception:
                ratings = [0]
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
        sid = s.get("semantic_id")
        top_rt = float(top_rating_map.get(sid, 0.0))
        b_rating = 0.03 * (top_rt / 9.0)  # default rating boost
        score = sim * (1.0 + b_panel + b_topic + b_kw + b_rating)
        s2 = dict(s)
        s2["_rerank_score"] = score
        rescored.append(s2)
    rescored.sort(key=lambda x: x.get("_rerank_score", 0.0), reverse=True)
    return rescored


def _siliconflow_rerank_scenarios(
    query: str,
    scenarios: List[Dict[str, Any]],
    *,
    scenarios_with_recs: Optional[List[Dict[str, Any]]] = None,
    base_url: Optional[str] = None,
    model_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("OPENAI_API_KEY")
    base = (base_url or os.getenv("SILICONFLOW_BASE_URL") or "https://api.siliconflow.cn/v1").rstrip("/")
    if not api_key:
        raise RuntimeError("SILICONFLOW_API_KEY not set")
    rec_map: Dict[str, str] = {}
    if scenarios_with_recs:
        for sc in scenarios_with_recs:
            recs = sc.get("recommendations") or []
            parts = []
            for r in recs[:3]:
                name = r.get("procedure_name_zh") or ""
                reason = r.get("reasoning_zh") or ""
                if len(reason) > 160:
                    reason = reason[:160] + "..."
                parts.append(f"{name}:{reason}")
            rec_map[sc.get("scenario_id")] = " ; ".join(parts)
    docs = []
    for s in scenarios:
        sid = s.get("semantic_id")
        extras = rec_map.get(sid, "")
        txt = " | ".join(
            filter(None, [s.get("description_zh"), s.get("panel_name"), s.get("topic_name"), extras])
        )
        docs.append(txt or "")
    payload = {
        "model": model_id or "BAAI/bge-reranker-v2-m3",
        "query": query,
        "documents": docs,
        "top_n": len(docs),
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{base}/rerank"
    resp = requests.post(url, json=payload, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"rerank API {resp.status_code}: {resp.text}")
    data = resp.json()
    results = data.get("results") or data.get("data") or []
    if not results:
        return []
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


def _local_rerank_scenarios(
    query: str,
    scenarios: List[Dict[str, Any]],
    *,
    scenarios_with_recs: Optional[List[Dict[str, Any]]] = None,
    model_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Use local sentence-transformers/transformers cross-encoder for reranking."""
    use_st = True
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
    except Exception:
        use_st = False
    rec_map: Dict[str, str] = {}
    if scenarios_with_recs:
        for sc in scenarios_with_recs:
            recs = sc.get("recommendations") or []
            parts = []
            for r in recs[:3]:
                name = r.get("procedure_name_zh") or ""
                reason = r.get("reasoning_zh") or ""
                if len(reason) > 160:
                    reason = reason[:160] + "..."
                parts.append(f"{name}:{reason}")
            rec_map[sc.get("scenario_id")] = " ; ".join(parts)
    docs = []
    for s in scenarios:
        sid = s.get("semantic_id")
        extras = rec_map.get(sid, "")
        txt = " | ".join(
            filter(None, [s.get("description_zh"), s.get("panel_name"), s.get("topic_name"), extras])
        )
        docs.append(txt or "")
    hf_model = model_id or "BAAI/bge-reranker-v2-m3"
    if use_st:
        ce = CrossEncoder(hf_model)
        pairs = [(query, d) for d in docs]
        scores = ce.predict(pairs)
    else:  # transformers fallback
        import torch  # type: ignore
        from transformers import (  # type: ignore
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )

        tok = AutoTokenizer.from_pretrained(hf_model)
        model = AutoModelForSequenceClassification.from_pretrained(hf_model)
        model.eval()
        scores = []
        for d in docs:
            with torch.no_grad():
                inputs = tok(query, d, return_tensors="pt", truncation=True, max_length=512)
                logits = model(**inputs).logits
                s = torch.sigmoid(logits.squeeze())
                try:
                    scores.append(float(s.item()))
                except Exception:
                    scores.append(0.0)
    scored: List[Dict[str, Any]] = []
    for i, s in enumerate(scenarios):
        s2 = dict(s)
        try:
            s2["_rerank_score"] = float(scores[i])
        except Exception:
            s2["_rerank_score"] = 0.0
        scored.append(s2)
    scored.sort(key=lambda x: x.get("_rerank_score", 0.0), reverse=True)
    return scored

