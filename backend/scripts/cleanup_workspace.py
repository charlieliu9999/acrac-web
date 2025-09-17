#!/usr/bin/env python3
"""
Cleanup helper: move intermediate outputs to backup, remove caches, and
backup unclear duplicate code files.

Default behavior is dry-run. Use --apply to execute.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
from pathlib import Path
from datetime import datetime


ROOT = Path(__file__).resolve().parents[2]


PATTERNS_MOVE = [
    # backend traces and reports
    "backend/trace_5_cases_*.json",
    "backend/trace_5_cases_*.xlsx",
    "backend/data_integrity_report_*.json",
    "backend/database_operations_final_report_*.json",
    "backend/ragas_tables_check_*.json",
    "backend/table_structure_verification_*.json",
]

UNCLEAR_CODE = [
    "backend/app/services/rag_llm_recommendation_service_副本.py",
]


def glob_many(patterns):
    out = []
    for pat in patterns:
        out.extend(ROOT.glob(pat))
    return out


def rm_pycache(dry: bool):
    removed = []
    for p in ROOT.rglob("__pycache__"):
        if p.is_dir():
            removed.append(p)
            if not dry:
                shutil.rmtree(p, ignore_errors=True)
    return removed


def move_files(files, dest_dir: Path, dry: bool):
    moved = []
    dest_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        rel = f.relative_to(ROOT)
        target = dest_dir / rel.name
        moved.append((rel, target.relative_to(ROOT)))
        if not dry:
            shutil.move(str(f), str(target))
    return moved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="apply changes (default dry-run)")
    args = ap.parse_args()

    dry = not args.apply
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = ROOT / "backup" / "cleanups" / ts

    to_move = glob_many(PATTERNS_MOVE)
    moved = move_files(to_move, backup_dir, dry)

    unclear = [ROOT / p for p in UNCLEAR_CODE if (ROOT / p).exists()]
    unclear_dir = ROOT / "backup" / "unclear_code"
    unclear_moved = move_files(unclear, unclear_dir, dry)

    caches = rm_pycache(dry)

    print("Dry-run:" if dry else "Applied:")
    print(f"  moved {len(moved)} files to {backup_dir.relative_to(ROOT)}")
    for rel, tgt in moved[:20]:
        print(f"    {rel} -> {tgt}")
    if len(moved) > 20:
        print(f"    ... and {len(moved)-20} more")
    print(f"  backed up {len(unclear_moved)} unclear code files to {unclear_dir.relative_to(ROOT)}")
    for rel, tgt in unclear_moved:
        print(f"    {rel} -> {tgt}")
    print(f"  removed {len(caches)} __pycache__ directories")


if __name__ == "__main__":
    main()

