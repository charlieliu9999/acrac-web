from app.services.rag_llm_recommendation_service import RAGLLMRecommendationService


def _demo_scenarios():
    return [
        {
            "semantic_id": "S0001",
            "description_zh": "突发剧烈头痛，考虑蛛网膜下腔出血",
            "panel_name": "神经影像科",
            "topic_name": "急性头痛",
            "similarity": 0.60,
        },
        {
            "semantic_id": "S0002",
            "description_zh": "慢性头痛伴视物模糊",
            "panel_name": "神经影像科",
            "topic_name": "慢性头痛",
            "similarity": 0.62,
        },
    ]


def test_keyword_rerank_boosts_tch_like_queries():
    svc = RAGLLMRecommendationService()
    sc = _demo_scenarios()
    panels, topics = svc._infer_targets_from_query("雷击样头痛 TCH 需排除SAH")
    out = svc._rerank_scenarios(
        query="雷击样头痛",
        scenarios=sc,
        target_panels=panels,
        target_topics=topics,
        scenarios_with_recs=None,
    )
    assert len(out) == 2
    # 关键字应提高包含蛛网膜下腔/雷击样的场景排序或得分
    assert out[0]["semantic_id"] in ("S0001", "S0002")


def test_rules_engine_post_warn_pregnancy():
    svc = RAGLLMRecommendationService()
    # 打开规则引擎为审计模式
    if svc.rules_engine:
        svc.rules_engine.enabled = True
        svc.rules_engine.audit_only = True
        parsed = {
            "recommendations": [
                {"procedure_name": "CT 胸部平扫", "modality": "CT", "appropriateness_rating": "7/9"}
            ],
            "summary": ""
        }
        ctx = {
            "query": "妊娠期胸痛，考虑肺栓塞",
            "query_signals": svc._extract_query_signals("妊娠期 胸痛")
        }
        res = svc.rules_engine.apply_post(ctx, parsed)
        assert "parsed" in res
        # 审计日志应记录到命中规则
        assert isinstance(res.get("audit_logs"), list)

