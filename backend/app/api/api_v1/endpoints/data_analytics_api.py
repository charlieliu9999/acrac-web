from fastapi import APIRouter, HTTPException, Query
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

import app.services.rag_llm_recommendation_service as rag_mod

router = APIRouter()


def _csv(v: Optional[str]) -> List[str]:
    if not v:
        return []
    return [x.strip() for x in v.split(',') if x.strip()]


@router.get('/kpis', summary='数据KPI统计')
async def analytics_kpis() -> Dict[str, int]:
    try:
        conn = rag_mod.rag_llm_service.connect_db()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM panels WHERE is_active=true")
            panels = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM topics WHERE is_active=true")
            topics = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM clinical_scenarios WHERE is_active=true")
            scenarios = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM procedure_dictionary WHERE is_active=true")
            procedures = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM clinical_recommendations WHERE is_active=true")
            recommendations = cur.fetchone()[0]
        conn.close()
        return {
            'panels': panels,
            'topics': topics,
            'scenarios': scenarios,
            'procedures': procedures,
            'recommendations': recommendations,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/sankey', summary='层级Sankey数据（Panel→Topic→Scenario→Procedure）')
async def analytics_sankey(
    panel_id: Optional[str] = None,
    topic_ids: Optional[str] = None,
    pregnancy: Optional[str] = None,
    urgency: Optional[str] = None,
    risk: Optional[str] = None,
    population: Optional[str] = None,
    modality: Optional[str] = None,
    rating_min: Optional[float] = None,
    rating_max: Optional[float] = None,
    topN: int = Query(150, ge=10, le=1000),
):
    try:
        t_ids = _csv(topic_ids)
        conn = rag_mod.rag_llm_service.connect_db()
        nodes: Dict[str, Dict[str, Any]] = {}
        links: List[Dict[str, Any]] = []

        def add_node(_id: str, _type: str, label: Optional[str] = None, count: Optional[int] = None):
            if _id not in nodes:
                nodes[_id] = {'id': _id, 'type': _type, 'label': label, 'count': count}

        def add_link(src: str, tgt: str, value: int):
            links.append({'source': src, 'target': tgt, 'value': int(value)})

        with conn.cursor() as cur:
            # Build WHERE clauses for scenario-level filters
            where_cs = ["cs.is_active=true", "t.is_active=true", "p.is_active=true"]
            args_cs: List[Any] = []
            if panel_id:
                where_cs.append("p.semantic_id=%s")
                args_cs.append(panel_id)
            if t_ids:
                where_cs.append("t.semantic_id = ANY(%s)")
                args_cs.append(t_ids)
            if pregnancy:
                where_cs.append("cs.pregnancy_status=%s")
                args_cs.append(pregnancy)
            if urgency:
                where_cs.append("cs.urgency_level=%s")
                args_cs.append(urgency)
            if risk:
                where_cs.append("cs.risk_level=%s")
                args_cs.append(risk)
            if population:
                where_cs.append("cs.patient_population=%s")
                args_cs.append(population)

            where_cs_sql = " AND ".join(where_cs)

            # Panel -> Topic: value = 主题下符合筛选条件的场景数
            cur.execute(
                f"""
                SELECT p.semantic_id AS panel_sid, p.name_zh AS panel_name,
                       t.semantic_id AS topic_sid, t.name_zh AS topic_name,
                       COUNT(DISTINCT cs.id) AS cnt
                FROM clinical_scenarios cs
                JOIN topics t ON cs.topic_id=t.id
                JOIN panels p ON cs.panel_id=p.id
                WHERE {where_cs_sql}
                GROUP BY p.semantic_id, p.name_zh, t.semantic_id, t.name_zh
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (*args_cs, topN)
            )
            for panel_sid, panel_name, topic_sid, topic_name, cnt in cur.fetchall():
                add_node(f"panel:{panel_sid}", 'panel', f"{panel_sid} {panel_name or ''}")
                add_node(f"topic:{topic_sid}", 'topic', f"{topic_sid} {topic_name or ''}")
                add_link(f"panel:{panel_sid}", f"topic:{topic_sid}", cnt)

            # Topic -> Scenario: value = 推荐数（可按模态和评分过滤）
            where_cr = [where_cs_sql, "cr.is_active=true"]
            args_cr: List[Any] = list(args_cs)
            if modality:
                where_cr.append("pd.modality=%s")
                args_cr.append(modality)
            if rating_min is not None:
                where_cr.append("cr.appropriateness_rating >= %s")
                args_cr.append(rating_min)
            if rating_max is not None:
                where_cr.append("cr.appropriateness_rating <= %s")
                args_cr.append(rating_max)
            where_cr_sql = " AND ".join(where_cr)

            cur.execute(
                f"""
                SELECT t.semantic_id AS topic_sid, cs.semantic_id AS scenario_sid,
                       COALESCE(NULLIF(cs.description_zh,''), cs.description_en) AS scenario_desc,
                       COUNT(cr.semantic_id) AS recs_cnt
                FROM clinical_scenarios cs
                JOIN topics t ON cs.topic_id=t.id
                JOIN panels p ON cs.panel_id=p.id
                LEFT JOIN clinical_recommendations cr ON cr.scenario_id = cs.semantic_id
                LEFT JOIN procedure_dictionary pd ON pd.semantic_id = cr.procedure_id
                WHERE {where_cr_sql}
                GROUP BY t.semantic_id, cs.semantic_id, scenario_desc
                ORDER BY recs_cnt DESC
                LIMIT %s
                """,
                (*args_cr, topN)
            )
            for topic_sid, scenario_sid, scenario_desc, recs_cnt in cur.fetchall():
                add_node(f"topic:{topic_sid}", 'topic')
                add_node(f"scenario:{scenario_sid}", 'scenario', f"{scenario_sid} {scenario_desc or ''}")
                add_link(f"topic:{topic_sid}", f"scenario:{scenario_sid}", recs_cnt)

            # Scenario -> Procedure: value = 推荐数，添加评分信息
            cur.execute(
                f"""
                SELECT cs.semantic_id AS scenario_sid,
                       pd.semantic_id AS proc_sid,
                       COALESCE(NULLIF(pd.name_zh,''), pd.name_en) AS proc_name,
                       COUNT(*) AS cnt,
                       MAX(cr.appropriateness_rating) AS max_rating,
                       AVG(cr.appropriateness_rating) AS avg_rating
                FROM clinical_recommendations cr
                JOIN clinical_scenarios cs ON cs.semantic_id = cr.scenario_id
                JOIN topics t ON cs.topic_id=t.id
                JOIN panels p ON cs.panel_id=p.id
                JOIN procedure_dictionary pd ON pd.semantic_id = cr.procedure_id
                WHERE {where_cr_sql}
                GROUP BY cs.semantic_id, pd.semantic_id, proc_name
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (*args_cr, topN)
            )
            for scenario_sid, proc_sid, proc_name, cnt, max_rating, avg_rating in cur.fetchall():
                add_node(f"scenario:{scenario_sid}", 'scenario')
                add_node(f"procedure:{proc_sid}", 'procedure', f"{proc_sid} {proc_name or ''}")
                # 在link中添加评分信息
                link_data = {
                    'source': f"scenario:{scenario_sid}", 
                    'target': f"procedure:{proc_sid}", 
                    'value': int(cnt),
                    'max_rating': float(max_rating) if max_rating else None,
                    'avg_rating': float(avg_rating) if avg_rating else None
                }
                links.append(link_data)

            # 计算每个节点的计数（入/出边的最大值），用于节点大小与tooltip显示
            from collections import defaultdict
            deg = defaultdict(lambda: {'in': 0, 'out': 0})
            for l in links:
                try:
                    v = int(l.get('value') or 0)
                except Exception:
                    v = 0
                deg[l['source']]['out'] += v
                deg[l['target']]['in'] += v
            for node_id, node in nodes.items():
                d = deg.get(node_id, {'in': 0, 'out': 0})
                node['count'] = int(max(d['in'], d['out']))

        conn.close()
        return {
            'nodes': list(nodes.values()),
            'links': links,
            'meta': {'topN': topN}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SearchCompareReq(BaseModel):
    query: str
    top_k: int = 10
    sim_threshold: float = 0.0
    scope: str = "scenario"  # 预留：scenario|procedure|recommendation（MVP实现scenario）


@router.post('/search-compare', summary='关键词 vs 向量 检索对比（MVP: 场景级）')
async def analytics_search_compare(req: SearchCompareReq):
    """比较同一查询在关键词与向量检索下的TopK重叠与分布（MVP：场景级）。"""
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query不能为空")
    if req.scope != 'scenario':
        raise HTTPException(status_code=400, detail="当前仅支持 scope=scenario")
    try:
        conn = rag_mod.rag_llm_service.connect_db()
        with conn.cursor() as cur:
            # 生成向量
            vec = rag_mod.embed_with_siliconflow(req.query)
            vec_str = "[" + ",".join(map(str, vec)) + "]"
            # 提升IVFFLAT召回质量（如存在）
            try:
                if getattr(rag_mod.rag_llm_service, 'pgvector_probes', 0):
                    cur.execute(
                        f"SET LOCAL ivfflat.probes = {int(rag_mod.rag_llm_service.pgvector_probes)};"
                    )
            except Exception:
                pass

            # 向量检索（场景）
            cur.execute(
                f"""
                SELECT cs.semantic_id,
                       COALESCE(NULLIF(cs.description_zh,''), cs.description_en) AS description,
                       (1 - (cs.embedding <=> '{vec_str}'::vector)) AS similarity
                FROM clinical_scenarios cs
                WHERE cs.embedding IS NOT NULL
                  AND (1 - (cs.embedding <=> '{vec_str}'::vector)) >= %s
                ORDER BY cs.embedding <=> '{vec_str}'::vector
                LIMIT %s
                """,
                (float(req.sim_threshold or 0.0), int(max(1, req.top_k))),
            )
            vec_rows = cur.fetchall()

            # 关键词检索（简单 ILIKE）
            kw = req.query.strip()
            kw_pat = f"%{kw}%"
            cur.execute(
                """
                SELECT cs.semantic_id,
                       COALESCE(NULLIF(cs.description_zh,''), cs.description_en) AS description
                FROM clinical_scenarios cs
                WHERE cs.is_active=true AND (
                    cs.description_zh ILIKE %s OR cs.description_en ILIKE %s
                )
                ORDER BY cs.semantic_id
                LIMIT %s
                """,
                (kw_pat, kw_pat, int(max(1, req.top_k))),
            )
            kw_rows = cur.fetchall()

        conn.close()

        # 计算指标
        vec_ids = [r[0] for r in vec_rows]
        kw_ids = [r[0] for r in kw_rows]
        set_vec, set_kw = set(vec_ids), set(kw_ids)
        inter = list(set_vec & set_kw)
        union = list(set_vec | set_kw)

        # 相似度统计
        sims = [float(r[2]) for r in vec_rows if r[2] is not None]
        sims_sorted = sorted(sims)
        def pct(p: float) -> float:
            if not sims_sorted:
                return 0.0
            k = max(0, min(len(sims_sorted)-1, int(round(p * (len(sims_sorted)-1)))))
            return float(sims_sorted[k])

        resp = {
            'query': req.query,
            'top_k': int(req.top_k),
            'sim_threshold': float(req.sim_threshold or 0.0),
            'scope': req.scope,
            'vector': {
                'ids': vec_ids,
                'items': [
                    {
                        'id': r[0],
                        'description': r[1],
                        'similarity': float(r[2]) if r[2] is not None else None,
                    } for r in vec_rows
                ],
                'similarity_stats': {
                    'mean': float(sum(sims)/len(sims)) if sims else 0.0,
                    'p50': pct(0.5),
                    'p90': pct(0.9),
                },
            },
            'keyword': {
                'ids': kw_ids,
                'items': [
                    {
                        'id': r[0],
                        'description': r[1],
                    } for r in kw_rows
                ],
            },
            'overlap': {
                'count': len(inter),
                'jaccard': (len(inter)/len(union)) if union else 0.0,
                'ids': inter,
            },
        }
        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/heatmap', summary='场景×检查项目热力图')
async def analytics_heatmap(
    panel_id: Optional[str] = None,
    topic_ids: Optional[str] = None,
    pregnancy: Optional[str] = None,
    urgency: Optional[str] = None,
    risk: Optional[str] = None,
    population: Optional[str] = None,
    modality: Optional[str] = None,
    rating_min: Optional[float] = None,
    rating_max: Optional[float] = None,
    metric: str = Query('rating_mean', pattern='^(rating_mean|count)$'),
    limit_scenarios: int = Query(20, ge=5, le=100),
    limit_procedures: int = Query(20, ge=5, le=100),
):
    try:
        t_ids = _csv(topic_ids)
        conn = rag_mod.rag_llm_service.connect_db()
        with conn.cursor() as cur:
            # Base WHERE
            where = ["cs.is_active=true", "cr.is_active=true", "pd.is_active=true", "t.is_active=true", "p.is_active=true"]
            args: List[Any] = []
            if panel_id:
                where.append("p.semantic_id=%s")
                args.append(panel_id)
            if t_ids:
                where.append("t.semantic_id = ANY(%s)")
                args.append(t_ids)
            if pregnancy:
                where.append("cs.pregnancy_status=%s")
                args.append(pregnancy)
            if urgency:
                where.append("cs.urgency_level=%s")
                args.append(urgency)
            if risk:
                where.append("cs.risk_level=%s")
                args.append(risk)
            if population:
                where.append("cs.patient_population=%s")
                args.append(population)
            if modality:
                where.append("pd.modality=%s")
                args.append(modality)
            if rating_min is not None:
                where.append("cr.appropriateness_rating >= %s")
                args.append(rating_min)
            if rating_max is not None:
                where.append("cr.appropriateness_rating <= %s")
                args.append(rating_max)
            where_sql = " AND ".join(where)

            # Top scenarios by count
            cur.execute(
                f"""
                SELECT cs.semantic_id, COALESCE(NULLIF(cs.description_zh,''), cs.description_en) AS desc_zh,
                       COUNT(*) AS cnt
                FROM clinical_recommendations cr
                JOIN clinical_scenarios cs ON cs.semantic_id = cr.scenario_id
                JOIN topics t ON cs.topic_id=t.id
                JOIN panels p ON cs.panel_id=p.id
                JOIN procedure_dictionary pd ON pd.semantic_id = cr.procedure_id
                WHERE {where_sql}
                GROUP BY cs.semantic_id, desc_zh
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (*args, limit_scenarios)
            )
            top_scenarios = [(sid, desc or '') for sid, desc, _ in cur.fetchall()]
            if not top_scenarios:
                conn.close()
                return {'x_labels': [], 'y_labels': [], 'z': [], 'metric': metric}

            # Top procedures by count
            cur.execute(
                f"""
                SELECT pd.semantic_id, COALESCE(NULLIF(pd.name_zh,''), pd.name_en) AS name,
                       COUNT(*) AS cnt
                FROM clinical_recommendations cr
                JOIN clinical_scenarios cs ON cs.semantic_id = cr.scenario_id
                JOIN topics t ON cs.topic_id=t.id
                JOIN panels p ON cs.panel_id=p.id
                JOIN procedure_dictionary pd ON pd.semantic_id = cr.procedure_id
                WHERE {where_sql}
                GROUP BY pd.semantic_id, name
                ORDER BY cnt DESC
                LIMIT %s
                """,
                (*args, limit_procedures)
            )
            top_procs = [(pid, name or '') for pid, name, _ in cur.fetchall()]
            if not top_procs:
                conn.close()
                return {'x_labels': [], 'y_labels': [], 'z': [], 'metric': metric}

            # Matrix values
            cur.execute(
                f"""
                SELECT cr.scenario_id, cr.procedure_id,
                       AVG(cr.appropriateness_rating) AS avg_rating,
                       COUNT(*) AS cnt
                FROM clinical_recommendations cr
                JOIN clinical_scenarios cs ON cs.semantic_id = cr.scenario_id
                JOIN topics t ON cs.topic_id=t.id
                JOIN panels p ON cs.panel_id=p.id
                JOIN procedure_dictionary pd ON pd.semantic_id = cr.procedure_id
                WHERE {where_sql}
                GROUP BY cr.scenario_id, cr.procedure_id
                """,
                (*args,)
            )
            vals: Dict[str, Dict[str, Dict[str, float]]] = {}
            for sid, pid, avg_rating, cnt in cur.fetchall():
                vals.setdefault(sid, {})[pid] = {'avg': float(avg_rating) if avg_rating is not None else 0.0, 'cnt': int(cnt)}

        conn.close()
        # Build grid
        x_labels = [s for s, _ in top_scenarios]
        y_labels = [p for p, _ in top_procs]
        x_label_names = {sid: f"{sid} {desc[:30]}..." if len(desc) > 30 else f"{sid} {desc}" for sid, desc in top_scenarios}
        y_label_names = {pid: f"{pid} {name[:30]}..." if len(name) > 30 else f"{pid} {name}" for pid, name in top_procs}
        from typing import Optional
        z: List[List[Optional[float]]] = []
        for pid in y_labels:
            row: List[Optional[float]] = []
            for sid in x_labels:
                cell = vals.get(sid, {}).get(pid)
                if cell:
                    v = cell['avg'] if metric == 'rating_mean' else float(cell['cnt'])
                else:
                    # 评分均值场景下，缺失值用None返回，避免显示为0分
                    v = None if metric == 'rating_mean' else 0.0
                row.append(v)
            z.append(row)

        return {
            'x_labels': x_labels,
            'y_labels': y_labels,
            'x_label_names': x_label_names,
            'y_label_names': y_label_names,
            'z': z,
            'metric': metric,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/topic-heatmap', summary='指定Topic下的完整 场景×检查项目 评分矩阵')
async def analytics_topic_heatmap(
    topic_id: str,
    include_zero: bool = False,
    high_min: float = 7.0,
    low_max: float = 3.0,
):
    """返回某个Topic下：
    - 所有活跃场景列表
    - 所有关联检查项目列表
    - 矩阵 ratings[y=procedure][x=scenario] = max(appropriateness_rating) 或 None
    - 按procedure的统计（高/中/低/覆盖率/均值）
    """
    try:
        if not topic_id:
            raise HTTPException(status_code=400, detail="topic_id 必填")
        conn = rag_mod.rag_llm_service.connect_db()
        with conn.cursor() as cur:
            # 获取场景（按语义ID升序）
            cur.execute(
                """
                SELECT cs.semantic_id,
                       COALESCE(NULLIF(cs.description_zh,''), cs.description_en) AS desc_zh
                FROM clinical_scenarios cs
                JOIN topics t ON cs.topic_id=t.id
                WHERE t.semantic_id=%s AND cs.is_active=true
                ORDER BY cs.semantic_id
                """,
                (topic_id,),
            )
            scenarios = [(sid, desc or '') for sid, desc in cur.fetchall()]

            if not scenarios:
                conn.close()
                return {
                    'topic_id': topic_id,
                    'scenarios': [],
                    'procedures': [],
                    'ratings': [],
                    'procedure_stats': [],
                    'thresholds': {'high_min': high_min, 'low_max': low_max},
                }

            # 获取该Topic下所有被推荐过的检查项目
            cur.execute(
                """
                SELECT DISTINCT pd.semantic_id,
                       COALESCE(NULLIF(pd.name_zh,''), pd.name_en) AS name,
                       pd.modality
                FROM clinical_recommendations cr
                JOIN clinical_scenarios cs ON cs.semantic_id=cr.scenario_id
                JOIN topics t ON cs.topic_id=t.id
                JOIN procedure_dictionary pd ON pd.semantic_id=cr.procedure_id
                WHERE t.semantic_id=%s AND cr.is_active=true AND pd.is_active=true
                ORDER BY pd.semantic_id
                """,
                (topic_id,),
            )
            procedures = [(pid, name or '', mod or None) for pid, name, mod in cur.fetchall()]

            if not procedures:
                conn.close()
                return {
                    'topic_id': topic_id,
                    'scenarios': [{'id': s, 'desc': d} for s, d in scenarios],
                    'procedures': [],
                    'ratings': [],
                    'procedure_stats': [],
                    'thresholds': {'high_min': high_min, 'low_max': low_max},
                }

            # 获取场景×检查的评分（取最大值）
            cur.execute(
                """
                SELECT cr.scenario_id, cr.procedure_id, MAX(cr.appropriateness_rating) AS rating
                FROM clinical_recommendations cr
                JOIN clinical_scenarios cs ON cs.semantic_id=cr.scenario_id
                JOIN topics t ON cs.topic_id=t.id
                JOIN procedure_dictionary pd ON pd.semantic_id=cr.procedure_id
                WHERE t.semantic_id=%s AND cr.is_active=true AND pd.is_active=true
                GROUP BY cr.scenario_id, cr.procedure_id
                """,
                (topic_id,),
            )
            pairs = cur.fetchall()  # (scenario_id, procedure_id, rating)

        conn.close()

        x_labels = [s for s, _ in scenarios]
        y_labels = [p for p, _, _ in procedures]
        # map for quick lookup
        val: Dict[str, Dict[str, Optional[float]]] = {}
        for sid, pid, rating in pairs:
            val.setdefault(pid, {})[sid] = float(rating) if rating is not None else None

        ratings: List[List[Optional[float]]] = []
        stats: List[Dict[str, Any]] = []
        for pid, name, mod in procedures:
            row: List[Optional[float]] = []
            highs = mids = lows = zeros = 0
            sum_rating = 0.0
            cnt_rating = 0
            for sid in x_labels:
                r = val.get(pid, {}).get(sid)
                if r is None:
                    row.append(0.0 if include_zero else None)
                else:
                    row.append(r)
                    cnt_rating += 1
                    sum_rating += r
                    if r >= high_min:
                        highs += 1
                    elif r <= low_max:
                        lows += 1
                    else:
                        mids += 1
            coverage = cnt_rating / len(x_labels) if x_labels else 0.0
            avg_rating = (sum_rating / cnt_rating) if cnt_rating else 0.0
            stats.append({
                'procedure_id': pid,
                'name': name,
                'modality': mod,
                'high': highs,
                'mid': mids,
                'low': lows,
                'coverage': coverage,
                'avg_rating': avg_rating,
            })
            ratings.append(row)

        return {
            'topic_id': topic_id,
            'scenarios': [{'id': s, 'desc': d} for s, d in scenarios],
            'procedures': [{'id': p, 'name': n, 'modality': m} for p, n, m in procedures],
            'x_labels': x_labels,
            'y_labels': y_labels,
            'ratings': ratings,
            'procedure_stats': stats,
            'thresholds': {'high_min': high_min, 'low_max': low_max},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
