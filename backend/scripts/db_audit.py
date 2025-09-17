#!/usr/bin/env python3
"""
Database audit and backup utility for ACRAC.

Features:
- Snapshot: export tables to CSV + compute data quality metrics (JSON)
- Compare: diff two audit JSONs to show changes/improvements

Usage:
  python backend/scripts/db_audit.py snapshot --out backup/db_snap
  python backend/scripts/db_audit.py compare --a path/to/audit_A.json --b path/to/audit_B.json

DB config taken from env (PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD).
"""
import os
import json
import argparse
import datetime as dt
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor


TABLES = [
    "panels",
    "topics",
    "clinical_scenarios",
    "procedure_dictionary",
    "clinical_recommendations",
]


def connect_db():
    cfg = {
        "host": os.getenv("PGHOST", "localhost"),
        "port": int(os.getenv("PGPORT", "5432")),
        "database": os.getenv("PGDATABASE", "acrac_db"),
        "user": os.getenv("PGUSER", "postgres"),
        "password": os.getenv("PGPASSWORD", "password"),
    }
    return psycopg2.connect(**cfg)


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def export_table_csv(cur, table: str, out_dir: str):
    path = os.path.join(out_dir, f"{table}.csv")
    with open(path, "w", encoding="utf-8") as f:
        cur.copy_expert(f"COPY {table} TO STDOUT WITH CSV HEADER", f)
    return path


def get_schema(cur, table: str) -> List[Dict[str, Any]]:
    cur.execute(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    return [dict(r) for r in cur.fetchall()]


def extract_modalities_and_parts(name_en: str, name_zh: str) -> Tuple[set, set]:
    t = f"{name_en or ''} {name_zh or ''}".upper()
    modality_map = {
        'CT': ['CT'],
        'MRI': ['MR', 'MRI'],
        'US': ['US', 'ULTRASOUND', '超声'],
        'XR': ['XR', 'X-RAY', 'X RAY', 'X光', 'X 线', 'DR', 'CR'],
        'NM': ['NM', 'PET', 'SPECT', '核医'],
        'MG': ['MG', 'MAMMO', '乳腺'],
        'ANGIO': ['DSA', 'ANGIO', '血管造影']
    }
    body_parts = {
        '头部': ['HEAD', 'BRAIN', 'SKULL', '颅', '脑', '头'],
        '颈部': ['NECK', 'CERVICAL', '颈', '颈椎'],
        '胸部': ['CHEST', 'THORAX', 'LUNG', 'CARDIAC', '心', '胸', '肺'],
        '腹部': ['ABDOMEN', 'ABDOMINAL', 'LIVER', 'KIDNEY', '肝', '肾', '腹'],
        '盆腔': ['PELVIS', 'PELVIC', 'BLADDER', 'PROSTATE', '盆', '膀胱', '前列腺'],
        '脊柱': ['SPINE', 'SPINAL', 'VERTEBRA', '脊', '椎'],
        '四肢': ['EXTREMITY', 'ARM', 'LEG', 'LIMB', '肢', '臂', '腿'],
        '乳腺': ['BREAST', 'MAMMARY', '乳腺', '乳房'],
        '血管': ['VASCULAR', 'ARTERY', 'VEIN', '血管', '动脉', '静脉']
    }
    ms, parts = set(), set()
    for m, kws in modality_map.items():
        if any(k in t for k in kws):
            ms.add(m)
    for name, kws in body_parts.items():
        if any(k in t for k in kws):
            parts.add(name)
    return ms, parts


def parse_contrast(name_en: str, name_zh: str) -> Optional[bool]:
    # Positive wins: any positive keyword -> True; else negative -> False; else None
    t_en = (name_en or '').upper()
    t_zh = str(name_zh or '')
    pos_en = ['WITH CONTRAST', 'W/ CONTRAST', 'WITH IV', 'W/IV', 'CONTRAST-ENHANCED', 'POSTCONTRAST', 'ENHANCED', 'CE']
    pos_zh = ['增强', '造影', '对比']
    neg_en = ['WITHOUT', 'W/O', 'NO CONTRAST', 'NONCONTRAST', 'UNENHANCED', 'PLAIN', 'NON-ENHANCED']
    neg_zh = ['非增强', '平扫', '无对比']
    if any(k in t_en for k in pos_en) or any(k in t_zh for k in pos_zh):
        return True
    if any(k in t_en for k in neg_en) or any(k in t_zh for k in neg_zh):
        return False
    return None


def calc_metrics(cur) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {"tables": {}, "quality": {}}

    # counts and schema
    for t in TABLES:
        cur.execute(f"SELECT COUNT(*) AS c FROM {t};")
        cnt = (cur.fetchone() or {}).get("c", 0)
        schema = get_schema(cur, t)
        metrics["tables"][t] = {"count": cnt, "schema": schema}

    # embedding coverage per table
    emb_cov: Dict[str, int] = {}
    for t in TABLES:
        try:
            cur.execute(f"SELECT COUNT(embedding) AS c FROM {t};")
            emb_cov[t] = (cur.fetchone() or {}).get("c", 0)
        except Exception:
            emb_cov[t] = 0
    metrics["quality"]["embedding_coverage"] = emb_cov

    # orphan recommendations
    cur.execute(
        """
        SELECT COUNT(*) AS c FROM clinical_recommendations cr
        WHERE cr.scenario_id NOT IN (SELECT semantic_id FROM clinical_scenarios)
           OR cr.procedure_id NOT IN (SELECT semantic_id FROM procedure_dictionary);
        """
    )
    metrics["quality"]["orphan_recommendations"] = (cur.fetchone() or {}).get("c", 0)

    # procedure_dictionary attribute completeness + multi-values
    cur.execute(
        """
        SELECT modality, body_part, contrast_used, radiation_level, name_en, name_zh
        FROM procedure_dictionary;
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
    total = len(rows)
    mv_mod = sum(1 for r in rows if (r.get('modality') or '').find('|') >= 0)
    mv_bp = sum(1 for r in rows if (r.get('body_part') or '').find('|') >= 0)
    mv_rad = sum(1 for r in rows if (r.get('radiation_level') or '').find('|') >= 0)
    nn_mod = sum(1 for r in rows if (r.get('modality') or '') != '')
    nn_bp = sum(1 for r in rows if (r.get('body_part') or '') != '')
    nn_con = sum(1 for r in rows if r.get('contrast_used') is not None)
    nn_rad = sum(1 for r in rows if (r.get('radiation_level') or '') != '')
    # cross-check contrast vs names (positive keyword implies should_be_true)
    pos_should_true = 0
    pos_but_false = 0
    for r in rows:
        inferred = parse_contrast(r.get('name_en'), r.get('name_zh'))
        if inferred is True:
            pos_should_true += 1
            if r.get('contrast_used') is False:
                pos_but_false += 1
    metrics["quality"]["procedure_attributes"] = {
        "total": total,
        "non_null": {"modality": nn_mod, "body_part": nn_bp, "contrast_used": nn_con, "radiation_level": nn_rad},
        "multi_values": {"modality": mv_mod, "body_part": mv_bp, "radiation_level": mv_rad},
        "contrast_checks": {"pos_should_true": pos_should_true, "pos_but_false": pos_but_false},
    }

    # clinical_recommendations coverage
    cur.execute(
        """
        SELECT COUNT(*) FILTER (WHERE appropriateness_rating IS NOT NULL) AS rating_nn,
               COUNT(*) FILTER (WHERE reasoning_zh IS NOT NULL AND reasoning_zh <> '') AS reason_nn,
               COUNT(*) AS total
        FROM clinical_recommendations;
        """
    )
    r = cur.fetchone() or {}
    metrics["quality"]["recommendations"] = {
        "total": r.get("total", 0), "rating_non_null": r.get("rating_nn", 0), "reasoning_zh_non_null": r.get("reason_nn", 0)
    }

    # clinical_scenarios pregnancy/urgency coverage
    cur.execute(
        """
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE pregnancy_status IS NOT NULL AND pregnancy_status <> '') AS preg_nn,
               COUNT(*) FILTER (WHERE urgency_level IS NOT NULL AND urgency_level <> '') AS urg_nn
        FROM clinical_scenarios;
        """
    )
    s = cur.fetchone() or {}
    metrics["quality"]["scenarios"] = {"total": s.get("total", 0), "pregnancy_status_non_null": s.get("preg_nn", 0), "urgency_level_non_null": s.get("urg_nn", 0)}

    return metrics


def snapshot(out_dir: Optional[str] = None) -> str:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = out_dir or f"backup/db_snapshot_{ts}"
    data_dir = os.path.join(base, "tables")
    ensure_dir(data_dir)
    with connect_db() as conn:
        with conn.cursor() as cur:
            for t in TABLES:
                export_table_csv(cur, t, data_dir)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            metrics = calc_metrics(cur)
    audit_path = os.path.join(base, f"db_audit_{ts}.json")
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"Snapshot saved to: {base}")
    return audit_path


def compare(a_path: str, b_path: str) -> Dict[str, Any]:
    with open(a_path, "r", encoding="utf-8") as f:
        A = json.load(f)
    with open(b_path, "r", encoding="utf-8") as f:
        B = json.load(f)

    diff: Dict[str, Any] = {"tables": {}, "quality": {}}

    # table counts diff
    for t in TABLES:
        a_cnt = ((A.get("tables", {}).get(t) or {}).get("count") or 0)
        b_cnt = ((B.get("tables", {}).get(t) or {}).get("count") or 0)
        diff["tables"][t] = {"before": a_cnt, "after": b_cnt, "delta": b_cnt - a_cnt}

    # selected quality diffs
    def pick(path: List[str], root: Dict[str, Any], default=None):
        cur = root
        for k in path:
            cur = cur.get(k) if isinstance(cur, dict) else None
            if cur is None:
                return default
        return cur

    keys = [
        ("embedding_coverage.panels", ["quality", "embedding_coverage", "panels"]),
        ("embedding_coverage.topics", ["quality", "embedding_coverage", "topics"]),
        ("embedding_coverage.clinical_scenarios", ["quality", "embedding_coverage", "clinical_scenarios"]),
        ("embedding_coverage.procedure_dictionary", ["quality", "embedding_coverage", "procedure_dictionary"]),
        ("embedding_coverage.clinical_recommendations", ["quality", "embedding_coverage", "clinical_recommendations"]),
        ("orphan_recommendations", ["quality", "orphan_recommendations"]),
        ("procedure_attributes.non_null.modality", ["quality", "procedure_attributes", "non_null", "modality"]),
        ("procedure_attributes.non_null.body_part", ["quality", "procedure_attributes", "non_null", "body_part"]),
        ("procedure_attributes.non_null.contrast_used", ["quality", "procedure_attributes", "non_null", "contrast_used"]),
        ("procedure_attributes.non_null.radiation_level", ["quality", "procedure_attributes", "non_null", "radiation_level"]),
        ("procedure_attributes.multi_values.modality", ["quality", "procedure_attributes", "multi_values", "modality"]),
        ("procedure_attributes.multi_values.body_part", ["quality", "procedure_attributes", "multi_values", "body_part"]),
        ("procedure_attributes.multi_values.radiation_level", ["quality", "procedure_attributes", "multi_values", "radiation_level"]),
        ("procedure_attributes.contrast_checks.pos_but_false", ["quality", "procedure_attributes", "contrast_checks", "pos_but_false"]),
        ("recommendations.rating_non_null", ["quality", "recommendations", "rating_non_null"]),
        ("recommendations.reasoning_zh_non_null", ["quality", "recommendations", "reasoning_zh_non_null"]),
        ("scenarios.pregnancy_status_non_null", ["quality", "scenarios", "pregnancy_status_non_null"]),
        ("scenarios.urgency_level_non_null", ["quality", "scenarios", "urgency_level_non_null"]),
    ]
    for name, path in keys:
        a_val = pick(path, A, 0)
        b_val = pick(path, B, 0)
        diff["quality"][name] = {"before": a_val, "after": b_val, "delta": (b_val - a_val) if isinstance(a_val, (int, float)) and isinstance(b_val, (int, float)) else None}

    return diff


def main():
    ap = argparse.ArgumentParser(description="ACRAC DB audit/backup tool")
    sub = ap.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("snapshot", help="Export CSVs and compute metrics")
    ps.add_argument("--out", default="", help="Output directory (default: backup/db_snapshot_<ts>)")

    pc = sub.add_parser("compare", help="Diff two audit JSON files")
    pc.add_argument("--a", required=True, help="Audit JSON A (before)")
    pc.add_argument("--b", required=True, help="Audit JSON B (after)")

    args = ap.parse_args()

    if args.cmd == "snapshot":
        audit_path = snapshot(out_dir=args.out or None)
        print(f"Audit JSON: {audit_path}")
    elif args.cmd == "compare":
        diff = compare(args.a, args.b)
        print(json.dumps(diff, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
