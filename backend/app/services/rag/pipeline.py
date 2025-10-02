import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .prompts import prepare_llm_prompt
from .ragas_eval import (
    build_contexts_from_payload,
    compute_ragas_scores,
    format_answer_for_ragas,
)
from .reranker import rerank_scenarios

logger = logging.getLogger(__name__)


class PipelineDeps:
    """Dependencies and configuration needed by the RAG pipeline.

    Methods should be provided by the facade service, enabling reuse of this
    pipeline by other API servers.
    """

    # required callables
    embed_fn: Callable[[str], List[float]]
    db_connect: Callable[[], Any]
    db_search_scenarios: Callable[[Any, List[float], int], List[Dict[str, Any]]]
    db_get_scenario_with_recs: Callable[[Any, List[str]], List[Dict[str, Any]]]
    db_search_procedure_candidates: Callable[[Any, List[float], int], List[Dict[str, Any]]]
    call_llm: Callable[[str, Dict[str, Any]], str]
    parse_llm: Callable[[str], Dict[str, Any]]
    extract_query_signals: Callable[[str], Dict[str, Any]]
    resolve_inference_context: Callable[[Dict[str, Optional[str]]], Dict[str, Any]]
    extract_scope_info: Callable[[List[Dict[str, Any]]], Dict[str, Optional[str]]]

    # config fields
    debug_mode: bool
    top_scenarios: int
    top_recs_per_scenario: int
    procedure_candidate_topk: int
    use_reranker: bool
    rerank_provider: str
    panel_boost: float
    topic_boost: float
    keyword_boost: float
    rating_boost: float
    similarity_threshold: float
    keyword_config: Dict[str, Any]
    default_eval_context: Dict[str, Any]
    # optional rule hooks
    rules_apply_rerank: Optional[Callable[[Dict[str, Any], List[Dict[str, Any]]], Dict[str, Any]]] = None
    rules_apply_post: Optional[Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = None
    # recall topk
    scene_recall_topk: int = 3


def generate_recommendation(
    query: str,
    *,
    deps: PipelineDeps,
    show_reasoning: bool,
    similarity_threshold: Optional[float] = None,
    compute_ragas_flag: bool = False,
    ground_truth: Optional[str] = None,
) -> Dict[str, Any]:
    t0 = time.time()
    debug = deps.debug_mode
    debug_info: Dict[str, Any] = {} if debug else None  # type: ignore[assignment]

    # 1) embed
    t_embed = time.time()
    query_vec = deps.embed_fn(query)
    t_embed_ms = int((time.time() - t_embed) * 1000)

    # 2) resolve models context
    conn = None
    try:
        conn = deps.db_connect()
        db_ok = bool(conn)
    except Exception as e:
        logger.error(f"数据库连接失败，将在低相似度路径中忽略DB: {e}")
        db_ok = False

    try:
        scenarios: List[Dict[str, Any]] = []
        if db_ok and conn is not None:
            recall_k = int(getattr(deps, "scene_recall_topk", 0) or max(3, deps.top_scenarios))
            scenarios = deps.db_search_scenarios(conn, query_vec, top_k=recall_k)
        if debug:
            debug_info = debug_info or {}
            debug_info["step_1_embedding_ms"] = t_embed_ms
            debug_info["step_2_db_connected"] = db_ok
            debug_info["step_3_scenarios_search"] = {
                "found_scenarios": len(scenarios),
                "scenarios": [
                    {
                        "id": s.get("semantic_id"),
                        "similarity": s.get("similarity"),
                        "description": (s.get("description_zh") or "")[:50] + "...",
                    }
                    for s in scenarios[:10]
                ],
            }

        # 3) context & rerank
        scope = deps.extract_scope_info(scenarios)
        ctx = deps.resolve_inference_context(scope)
        context_base_url = ctx.get("base_url")
        context_llm_model = ctx.get("llm_model")
        context_embedding_model = ctx.get("embedding_model")
        context_reranker = ctx.get("reranker_model")

        current_threshold = similarity_threshold or deps.similarity_threshold
        scenarios_original = list(scenarios)
        if deps.use_reranker and len(scenarios) > 1:
            try:
                scenarios_with_recs_all: List[Dict[str, Any]] = []
                if db_ok and conn is not None:
                    try:
                        ids = [s["semantic_id"] for s in scenarios]
                        scenarios_with_recs_all = deps.db_get_scenario_with_recs(conn, ids)
                    except Exception as e:
                        logger.warning(f"预取场景推荐失败: {e}")
                scenarios = rerank_scenarios(
                    query,
                    scenarios,
                    provider=deps.rerank_provider,
                    base_url=context_base_url,
                    model_id=context_reranker,
                    use_reranker=True,
                    target_panels=set(),
                    target_topics=set(),
                    keyword_config=deps.keyword_config,
                    alpha_panel=deps.panel_boost,
                    alpha_topic=deps.topic_boost,
                    alpha_kw=deps.keyword_boost,
                    scenarios_with_recs=scenarios_with_recs_all,
                )
                # rules: rerank stage
                try:
                    if getattr(deps, "rules_apply_rerank", None):
                        rr_ctx = {
                            "query": query,
                            "query_signals": deps.extract_query_signals(query),
                        }
                        rr_res = deps.rules_apply_rerank(rr_ctx, scenarios)  # type: ignore[arg-type]
                        scenarios = rr_res.get("scenarios") or scenarios
                        if debug:
                            debug_info.setdefault("rules_audit", {})  # type: ignore[assignment]
                            debug_info["rules_audit"]["rerank"] = rr_res.get("audit_logs") or []  # type: ignore[index]
                except Exception as e:
                    logger.warning(f"规则引擎(rerank)执行失败: {e}")
                if debug:
                    debug_info["step_3_rerank"] = True  # type: ignore[index]
            except Exception as re:
                logger.warning(f"场景重排失败: {re}")

        if db_ok and not scenarios:
            return {
                "success": False,
                "message": "未找到相关的临床场景",
                "recommendations": [],
                "scenarios": [],
                "debug_info": debug_info if debug else None,
            }

        # 4) similarity check
        max_similarity = max((s.get("similarity", 0.0) for s in scenarios), default=0.0)
        is_low_similarity = (not db_ok) or (max_similarity < current_threshold)
        if debug:
            debug_info["step_4_similarity_check"] = {  # type: ignore[index]
                "max_similarity": max_similarity,
                "threshold": current_threshold,
                "is_low_similarity": is_low_similarity,
                "similarity_status": "low" if is_low_similarity else "high",
            }

        # 5) build prompt
        if is_low_similarity:
            candidates: List[Dict[str, Any]] = []
            if db_ok and conn is not None:
                try:
                    candidates = deps.db_search_procedure_candidates(
                        conn, query_vec, top_k=deps.procedure_candidate_topk
                    )
                except Exception as ce:
                    logger.warning(f"候选检查检索失败: {ce}")
            prompt = prepare_llm_prompt(
                query,
                scenarios,
                [],
                is_low_similarity=True,
                top_scenarios=deps.top_scenarios,
                top_recs_per_scenario=deps.top_recs_per_scenario,
                show_reasoning=show_reasoning,
                candidates=candidates,
            )
            scenarios_with_recs = []
        else:
            scenario_ids = [s["semantic_id"] for s in scenarios]
            try:
                _map = {
                    s["scenario_id"]: s
                    for s in (locals().get("scenarios_with_recs_all") or [])  # type: ignore[arg-type]
                }
                scenarios_with_recs = [_map[sid] for sid in scenario_ids if sid in _map]
                if not scenarios_with_recs and db_ok and conn is not None:
                    scenarios_with_recs = deps.db_get_scenario_with_recs(conn, scenario_ids)
            except Exception:
                scenarios_with_recs = deps.db_get_scenario_with_recs(conn, scenario_ids) if (db_ok and conn is not None) else []

            # build candidates list cap
            cap_dynamic = int(deps.top_scenarios * deps.top_recs_per_scenario)
            candidate_cap = max(int(deps.procedure_candidate_topk or 0), int(cap_dynamic or 0), 1)
            candidates: List[Dict[str, Any]] = []
            seen_keys: set = set()
            for sc in scenarios_with_recs:
                for rec in (sc.get("recommendations") or [])[: max(1, deps.top_recs_per_scenario)]:
                    name = rec.get("procedure_name_zh") or rec.get("procedure_name_en")
                    if not name:
                        continue
                    key = (name, rec.get("modality") or "")
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    candidates.append({"procedure_name_zh": name, "modality": rec.get("modality")})
                    if len(candidates) >= candidate_cap:
                        break
                if len(candidates) >= candidate_cap:
                    break

            if len(candidates) < candidate_cap:
                flat_recs: List[Dict[str, Any]] = []
                for sc in scenarios_with_recs:
                    for rec in sc.get("recommendations", []) or []:
                        name = rec.get("procedure_name_zh") or rec.get("procedure_name_en")
                        if not name:
                            continue
                        try:
                            rating = float(rec.get("appropriateness_rating") or 0)
                        except Exception:
                            rating = 0.0
                        if rating > 5.0:
                            flat_recs.append(
                                {"procedure_name_zh": name, "modality": rec.get("modality"), "rating": rating}
                            )
                best: Dict[tuple, Dict[str, Any]] = {}
                for r in flat_recs:
                    k = (r.get("procedure_name_zh") or "", r.get("modality") or "")
                    if not k[0]:
                        continue
                    if (k not in best) or (float(r.get("rating") or 0) > float(best[k].get("rating") or 0)):
                        best[k] = r
                for r in sorted(best.values(), key=lambda x: x.get("rating", 0.0), reverse=True):
                    k = (r.get("procedure_name_zh") or "", r.get("modality") or "")
                    if k in seen_keys:
                        continue
                    candidates.append({"procedure_name_zh": r["procedure_name_zh"], "modality": r.get("modality")})
                    seen_keys.add(k)
                    if len(candidates) >= candidate_cap:
                        break

            if len(candidates) < candidate_cap and db_ok and conn is not None:
                try:
                    more = deps.db_search_procedure_candidates(conn, query_vec, top_k=(candidate_cap - len(candidates)))
                    for c in more:
                        k = ((c.get("procedure_name_zh") or c.get("name_zh") or c.get("procedure_name") or ""), c.get("modality") or "")
                        if k[0] and k not in seen_keys:
                            seen_keys.add(k)
                            candidates.append({"procedure_name_zh": k[0], "modality": k[1]})
                        if len(candidates) >= candidate_cap:
                            break
                except Exception as ce:
                    logger.warning(f"候选补全失败: {ce}")

            prompt = prepare_llm_prompt(
                query,
                scenarios,
                scenarios_with_recs,
                is_low_similarity=False,
                top_scenarios=deps.top_scenarios,
                top_recs_per_scenario=deps.top_recs_per_scenario,
                show_reasoning=show_reasoning,
                candidates=candidates,
            )

        # 6) LLM
        t_llm = time.time()
        try:
            llm_response = deps.call_llm(prompt, ctx)
        except Exception as e:
            # Hard fail: do not fabricate recommendations
            end = time.time()
            processing_ms = int((end - t0) * 1000)
            result: Dict[str, Any] = {
                "success": False,
                "query": query,
                "message": f"LLM调用失败: {e}",
                "contexts": build_contexts_from_payload({"scenarios": scenarios, "scenarios_with_recommendations": []}),
                "processing_time_ms": processing_ms,
                "model_used": context_llm_model,
                "embedding_model_used": context_embedding_model,
                "reranker_model_used": context_reranker,
                "similarity_threshold": current_threshold,
                "max_similarity": max_similarity,
                "is_low_similarity_mode": is_low_similarity,
            }
            if debug:
                result["trace"] = {"final_prompt": prompt}
            return result
        t_llm_ms = int((time.time() - t_llm) * 1000)
        parsed_result = deps.parse_llm(llm_response)
        # ensure summary fallback if missing/placeholder
        try:
            summ = (parsed_result or {}).get('summary') or ''
            if not isinstance(summ, str):
                summ = str(summ)
            # consider too-short or placeholder-like summary as missing
            if len(summ.strip()) < 8 or summ.strip() in ("推荐总结", "N/A", "无"):
                names = []
                for it in (parsed_result.get('recommendations') or [])[:3]:
                    nm = it.get('procedure_name') or ''
                    md = it.get('modality') or ''
                    if nm:
                        names.append(f"{nm} ({md})" if md else nm)
                if names:
                    parsed_result = dict(parsed_result)
                    parsed_result['summary'] = '推荐：' + '；'.join(names)
        except Exception:
            pass
        # 规则：post 阶段
        try:
            if getattr(deps, "rules_apply_post", None):
                post_ctx = {
                    "query": query,
                    "query_signals": deps.extract_query_signals(query),
                    "scenarios": scenarios,
                }
                post_res = deps.rules_apply_post(post_ctx, parsed_result)  # type: ignore[arg-type]
                parsed_result = post_res.get("parsed") or parsed_result
                if debug:
                    debug_info.setdefault("rules_audit", {})  # type: ignore[assignment]
                    debug_info["rules_audit"]["post"] = post_res.get("audit_logs") or []  # type: ignore[index]
        except Exception as e:
            logger.warning(f"规则引擎(post)执行失败: {e}")

        # post-filter by candidates if present (robust name normalization)
        try:
            import re
            def _norm(x: str) -> str:
                s = (x or "").lower()
                # unify synonyms
                s = s.replace("造影", "血管成像")
                # strip punctuation/separators and parentheses
                s = re.sub(r"[\s\-_/|·,，:：;；]", "", s)
                s = s.replace("(", "").replace(")", "").replace("（", "").replace("）", "")
                return s
            cand_names = set()
            for c in (locals().get("candidates") or []):  # type: ignore[arg-type]
                nm = c.get("procedure_name_zh") or c.get("name_zh") or c.get("procedure_name")
                if nm:
                    cand_names.add(nm)
            recs = (parsed_result or {}).get("recommendations") or []
            if cand_names and recs:
                cand_norms = {_norm(n) for n in cand_names}
                filtered = []
                for r in recs:
                    rn = r.get("procedure_name") or ""
                    nr = _norm(rn)
                    keep = (rn in cand_names) or (nr in cand_norms) or any((nr in cn or cn in nr) for cn in cand_norms)
                    if keep:
                        filtered.append(r)
                if filtered and (len(filtered) != len(recs)):
                    parsed_result = dict(parsed_result)
                    parsed_result["recommendations"] = filtered
        except Exception:
            pass

        # 7) response
        end = time.time()
        processing_ms = int((end - t0) * 1000)
        contexts = build_contexts_from_payload(
            {"scenarios": scenarios, "scenarios_with_recommendations": scenarios_with_recs}
        )
        # If parser indicates non-JSON fallback and no recommendations, mark as failure
        parse_fallback = bool(parsed_result.get('no_rag')) and not parsed_result.get('recommendations')

        result: Dict[str, Any] = {
            "success": (not parse_fallback),
            "query": query,
            "scenarios": scenarios,
            "scenarios_with_recommendations": scenarios_with_recs,
            "llm_recommendations": parsed_result,
            "contexts": contexts,
            "processing_time_ms": processing_ms,
            "model_used": context_llm_model,
            "embedding_model_used": context_embedding_model,
            "reranker_model_used": context_reranker,
            "similarity_threshold": current_threshold,
            "max_similarity": max_similarity,
            "is_low_similarity_mode": is_low_similarity,
        }
        if parse_fallback:
            result["message"] = "LLM输出无效：未返回有效JSON"

        if debug:
            trace = {
                "final_prompt": prompt,
                "llm_raw": llm_response,
                "llm_parsed": parsed_result,
            }
            # recall and rerank snapshots
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
                }
                for s in (scenarios_original or scenarios)
            ]
            trace["rerank_scenarios"] = [
                {
                    "id": s.get("semantic_id"),
                    "_rerank_score": s.get("_rerank_score"),
                    "panel": s.get("panel_name"),
                    "topic": s.get("topic_name"),
                    "similarity": s.get("similarity"),
                    "clinical_scenario": _scenario_text(s),
                }
                for s in scenarios
            ]
            result["trace"] = trace
            result["debug_info"] = {
                **(debug_info or {}),
                "step_6_llm_time_ms": t_llm_ms,
                "step_6_prompt_length": len(prompt),
            }

        # Optional RAGAS
        if compute_ragas_flag:
            try:
                ragas_scores = compute_ragas_scores(
                    user_input=query,
                    answer=format_answer_for_ragas(parsed_result),
                    contexts=contexts,
                    reference=ground_truth or "",
                    eval_context=deps.default_eval_context,
                )
                result.setdefault("trace", {})["ragas_scores"] = ragas_scores  # type: ignore[index]
                result["ragas_scores"] = ragas_scores
            except Exception as e:
                result.setdefault("trace", {})["ragas_error"] = str(e)  # type: ignore[index]
                result["ragas_error"] = str(e)

        return result
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
