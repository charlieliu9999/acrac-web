#!/usr/bin/env python3
"""
A/B测试：LLM提示词是否携带“推荐理由”对效果与时延的影响

用法:
  python backend/scripts/ab_test_show_reasoning.py \
      --excel ACR_data/影像测试样例-0318-1.xlsx \
      --limit 100 \
      --top-scenarios 2 \
      --top-recs 3 \
      --sim-threshold 0.6 \
      [--with-ragas]

输出:
  - JSON: ab_test_show_reasoning_YYYYmmdd_HHMMSS.json
  - Markdown报告: docs/AB_TEST_SHOW_REASONING_REPORT.md (追加一节)
"""
import os
import sys
import time
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import app.services.rag_llm_recommendation_service as rag_mod  # type: ignore


def load_cases_from_excel(path: Path, limit: int = None) -> List[Dict[str, Any]]:
    df = pd.read_excel(path)
    required = ['题号', '临床场景', '首选检查项目（标准化）']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"Excel缺少列: {missing}")
    cases = []
    for i, row in df.iterrows():
        cases.append({
            'question_id': int(row['题号']),
            'clinical_query': str(row['临床场景']),
            'ground_truth': str(row['首选检查项目（标准化）']).strip('* '),
        })
        if limit and len(cases) >= limit:
            break
    return cases


def norm_name(s: str) -> str:
    if not s:
        return ''
    s = str(s)
    # 去除空白与常见符号差异
    repl = [('\u3000', ' '), ('（', '('), ('）', ')'), ('，', ','), ('：', ':'), ('；', ';')]
    for a, b in repl:
        s = s.replace(a, b)
    s = s.strip().lower()
    # 移除空白与无关符号
    for ch in [' ', '\n', '\t']:
        s = s.replace(ch, '')
    return s


def extract_topk_names(resp: Dict[str, Any], k: int = 3) -> List[str]:
    names = []
    recs = (resp or {}).get('llm_recommendations', {}).get('recommendations') or []
    for r in recs[:k]:
        name = r.get('name') or r.get('procedure_name') or r.get('recommendation') or r.get('procedure')
        if name:
            names.append(str(name))
    return names


def run_one_case(case: Dict[str, Any], show_reasoning: bool, top_scenarios: int, top_recs: int, sim_thres: float, with_ragas: bool) -> Dict[str, Any]:
    st = time.time()
    res = rag_mod.rag_llm_service.generate_intelligent_recommendation(
        query=case['clinical_query'],
        top_scenarios=top_scenarios,
        top_recommendations_per_scenario=top_recs,
        show_reasoning=show_reasoning,
        similarity_threshold=sim_thres,
        debug_flag=True,
        compute_ragas=with_ragas,
        ground_truth=case['ground_truth'] if with_ragas else None,
    )
    dur = time.time() - st
    # 收集指标
    prompt_len = None
    if isinstance(res.get('debug_info'), dict):
        prompt_len = res['debug_info'].get('step_6_prompt_length')
    ragas = None
    if isinstance(res.get('trace'), dict):
        ragas = res['trace'].get('ragas_scores')
    return {
        'success': bool(res.get('success')),
        'processing_time_ms': int(res.get('processing_time_ms') or dur * 1000),
        'prompt_length': int(prompt_len or 0),
        'names_top3': extract_topk_names(res, 3),
        'ragas_scores': ragas,
        'raw': res if not with_ragas else None,  # 避免报告过大
    }


def summarize(ab_items: List[Dict[str, Any]], label: str, gt_names: List[str]) -> Dict[str, Any]:
    total = len(ab_items)
    ok = sum(1 for it in ab_items if it['success'])
    avg_ms = round(sum(it['processing_time_ms'] for it in ab_items) / max(1, total), 2)
    avg_prompt = round(sum(it['prompt_length'] for it in ab_items) / max(1, total), 2)
    # 命中率
    top1_hit = 0
    top3_hit = 0
    for it, gt in zip(ab_items, gt_names):
        if not it['success']:
            continue
        topk = it['names_top3']
        if not topk:
            continue
        g = norm_name(gt)
        n1 = norm_name(topk[0]) if len(topk) >= 1 else ''
        n2 = [norm_name(x) for x in topk]
        if g and n1 and (g == n1 or g in n1 or n1 in g):
            top1_hit += 1
        if g and any((g == x or g in x or x in g) for x in n2):
            top3_hit += 1
    # RAGAS（若有）
    ragas_keys = ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']
    ragas_avg = {k: 0.0 for k in ragas_keys}
    ragas_cnt = 0
    for it in ab_items:
        sc = it.get('ragas_scores')
        if not sc:
            continue
        ragas_cnt += 1
        for k in ragas_keys:
            v = sc.get(k)
            if isinstance(v, (int, float)):
                ragas_avg[k] += float(v)
    if ragas_cnt:
        for k in ragas_keys:
            ragas_avg[k] = round(ragas_avg[k] / ragas_cnt, 4)

    return {
        'label': label,
        'total': total,
        'success': ok,
        'success_rate': round(ok / max(1, total), 4),
        'avg_processing_ms': avg_ms,
        'avg_prompt_length': avg_prompt,
        'top1_hit_rate': round(top1_hit / max(1, total), 4),
        'top3_hit_rate': round(top3_hit / max(1, total), 4),
        'ragas_avg': ragas_avg if ragas_cnt else None,
        'ragas_samples': ragas_cnt,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--excel', type=str, default=str(ROOT / 'ACR_data' / '影像测试样例-0318-1.xlsx'))
    ap.add_argument('--limit', type=int, default=50)
    ap.add_argument('--top-scenarios', type=int, default=int(os.getenv('RAG_TOP_SCENARIOS', '2')))
    ap.add_argument('--top-recs', type=int, default=int(os.getenv('RAG_TOP_RECOMMENDATIONS_PER_SCENARIO', '3')))
    ap.add_argument('--sim-threshold', type=float, default=float(os.getenv('VECTOR_SIMILARITY_THRESHOLD', '0.6')))
    ap.add_argument('--with-ragas', action='store_true')
    args = ap.parse_args()

    excel_path = Path(args.excel)
    if not excel_path.exists():
        raise SystemExit(f"Excel不存在: {excel_path}")

    cases = load_cases_from_excel(excel_path, args.limit)
    print(f"Loaded cases: {len(cases)} from {excel_path}")

    A_items = []  # show_reasoning=True
    B_items = []  # show_reasoning=False
    gt_list = [c['ground_truth'] for c in cases]

    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['clinical_query'][:40]}...")
        # A: 带理由
        a = run_one_case(case, True, args.top_scenarios, args.top_recs, args.sim_threshold, args.with_ragas)
        A_items.append(a)
        # B: 不带理由
        b = run_one_case(case, False, args.top_scenarios, args.top_recs, args.sim_threshold, args.with_ragas)
        B_items.append(b)

    A_sum = summarize(A_items, 'with_reasoning', gt_list)
    B_sum = summarize(B_items, 'without_reasoning', gt_list)

    results = {
        'meta': {
            'timestamp': datetime.now().isoformat(timespec='seconds'),
            'excel': str(excel_path),
            'limit': args.limit,
            'top_scenarios': args.top_scenarios,
            'top_recommendations_per_scenario': args.top_recs,
            'similarity_threshold': args.sim_threshold,
            'with_ragas': bool(args.with_ragas),
        },
        'A': A_sum,
        'B': B_sum,
        'delta': {
            'avg_processing_ms': round(A_sum['avg_processing_ms'] - B_sum['avg_processing_ms'], 2),
            'avg_prompt_length': round(A_sum['avg_prompt_length'] - B_sum['avg_prompt_length'], 2),
            'top1_hit_rate': round(A_sum['top1_hit_rate'] - B_sum['top1_hit_rate'], 4),
            'top3_hit_rate': round(A_sum['top3_hit_rate'] - B_sum['top3_hit_rate'], 4),
        },
    }

    out_json = ROOT / f"ab_test_show_reasoning_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Saved JSON: {out_json}")

    # 生成/追加 Markdown 报告
    md = ROOT / 'docs' / 'AB_TEST_SHOW_REASONING_REPORT.md'
    md.parent.mkdir(parents=True, exist_ok=True)
    def pct(x):
        return f"{x*100:.1f}%"
    lines = []
    lines.append(f"\n\n## A/B报告 {results['meta']['timestamp']}")
    lines.append(f"- 数据源: `{excel_path}` (n={results['meta']['limit']})")
    lines.append(f"- 参数: top_scenarios={results['meta']['top_scenarios']}, top_recs={results['meta']['top_recommendations_per_scenario']}, sim_thres={results['meta']['similarity_threshold']}, with_ragas={results['meta']['with_ragas']}")
    lines.append(f"- A 含理由: avg_ms={A_sum['avg_processing_ms']}, prompt_len={A_sum['avg_prompt_length']}, top1={pct(A_sum['top1_hit_rate'])}, top3={pct(A_sum['top3_hit_rate'])}")
    lines.append(f"- B 不含理由: avg_ms={B_sum['avg_processing_ms']}, prompt_len={B_sum['avg_prompt_length']}, top1={pct(B_sum['top1_hit_rate'])}, top3={pct(B_sum['top3_hit_rate'])}")
    lines.append(f"- 差值(A-B): Δms={results['delta']['avg_processing_ms']}, Δprompt={results['delta']['avg_prompt_length']}, Δtop1={pct(results['delta']['top1_hit_rate'])}, Δtop3={pct(results['delta']['top3_hit_rate'])}")
    if A_sum.get('ragas_avg') or B_sum.get('ragas_avg'):
        lines.append(f"- RAGAS样本数: A={A_sum.get('ragas_samples')}, B={B_sum.get('ragas_samples')}")
        lines.append(f"- RAGAS(A): {A_sum.get('ragas_avg')}")
        lines.append(f"- RAGAS(B): {B_sum.get('ragas_avg')}")
    lines.append("- 结论建议: 若不含理由方案 top1/top3 基本持平，且 avg_ms 与 prompt_len 显著下降，建议默认不带理由，并对评分并列/低相似度/高风险信号命中时再附简短理由。\n")
    with md.open('a', encoding='utf-8') as f:
        f.write("\n".join(lines))
    print(f"Updated report: {md}")


if __name__ == '__main__':
    main()
