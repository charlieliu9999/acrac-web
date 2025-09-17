"""
Lightweight Rules Engine for ACRAC RAG+LLM pipeline.

Goals
- Non-invasive hooks at pre-retrieval, rerank, and post-LLM stages
- File-based rule packs (JSON) with audit logging
- Default disabled; safe to ship without changing behavior

Condition Language (simple JSON)
- Operators supported: and, or, not, eq, ne, gt, gte, lt, lte,
  in, any_in, all_in, contains, exists, regex (very basic)
- Values resolve from context via string keys using dot-paths, e.g. "query_signals.pregnancy_status"

Actions (effect)
- boost: add a score bonus to scenarios (rerank stage)
- filter: drop scenarios or candidate procedures by condition
- override/fix: adjust fields on LLM parsed output (post stage)
- warn: record a warning in audit logs

Rule pack JSON schema (example)
{
  "packs": [
    {
      "id": "pregnancy_safety",
      "scope": "post_llm",
      "enabled": true,
      "priority": 10,
      "rules": [
        {
          "id": "avoid_high_radiation_pregnancy",
          "enabled": true,
          "condition": {"in": ["query_signals.pregnancy_status", ["妊娠/围产"]]},
          "action": {"type": "warn", "message": "Pregnancy case: ensure low radiation"}
        }
      ]
    }
  ]
}
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


RuleScope = str  # "pre", "rerank", "post"


def _get(ctx: Dict[str, Any], path: str, default=None):
    cur: Any = ctx
    for part in str(path).split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def _as_list(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


class ConditionEval:
    @staticmethod
    def eval(cond: Any, ctx: Dict[str, Any]) -> bool:
        if cond is None:
            return True
        if isinstance(cond, bool):
            return cond
        if isinstance(cond, dict):
            if not cond:
                return True
            if 'and' in cond:
                return all(ConditionEval.eval(c, ctx) for c in _as_list(cond['and']))
            if 'or' in cond:
                lst = _as_list(cond['or'])
                return any(ConditionEval.eval(c, ctx) for c in lst)
            if 'not' in cond:
                return not ConditionEval.eval(cond['not'], ctx)
            # Binary ops expect [left, right]
            def _lr(op: str) -> Tuple[Any, Any]:
                arr = cond.get(op)
                if isinstance(arr, list) and len(arr) == 2:
                    l = _get(ctx, arr[0], arr[0]) if isinstance(arr[0], str) else arr[0]
                    r = _get(ctx, arr[1], arr[1]) if isinstance(arr[1], str) else arr[1]
                    return l, r
                return None, None
            for op in ('eq','ne','gt','gte','lt','lte','in','contains','exists','regex','any_in','all_in'):
                if op in cond:
                    l, r = _lr(op)
                    if op == 'eq':
                        return l == r
                    if op == 'ne':
                        return l != r
                    if op == 'gt':
                        try:
                            return float(l) > float(r)
                        except Exception:
                            return False
                    if op == 'gte':
                        try:
                            return float(l) >= float(r)
                        except Exception:
                            return False
                    if op == 'lt':
                        try:
                            return float(l) < float(r)
                        except Exception:
                            return False
                    if op == 'lte':
                        try:
                            return float(l) <= float(r)
                        except Exception:
                            return False
                    if op == 'in':
                        return l in _as_list(r)
                    if op == 'any_in':
                        la = _as_list(l)
                        rb = set(_as_list(r))
                        return any(x in rb for x in la)
                    if op == 'all_in':
                        la = _as_list(l)
                        rb = set(_as_list(r))
                        return all(x in rb for x in la)
                    if op == 'contains':
                        if isinstance(l, list):
                            return r in l
                        if isinstance(l, str) and isinstance(r, str):
                            return r in l
                        return False
                    if op == 'exists':
                        return _get(ctx, l) is not None  # l is path
                    if op == 'regex':
                        try:
                            pat = re.compile(str(r))
                            return bool(pat.search(str(l)))
                        except Exception:
                            return False
            # Unknown dict -> truthy
            return True
        # Primitives -> truthy if non-empty
        return bool(cond)


@dataclass
class Rule:
    id: str
    enabled: bool
    condition: Dict[str, Any]
    action: Dict[str, Any]
    priority: int = 100


@dataclass
class RulePack:
    id: str
    scope: RuleScope
    enabled: bool = True
    priority: int = 100
    rules: List[Rule] = field(default_factory=list)


class RulesEngine:
    def __init__(self, packs: List[RulePack], *, enabled: bool = False, audit_only: bool = True):
        self.packs = packs
        self.enabled = enabled
        self.audit_only = audit_only

    @staticmethod
    def from_file(path: str | Path) -> "RulesEngine":
        path = Path(path)
        enabled = os.getenv("RULES_ENABLED", "false").lower() == "true"
        audit_only = os.getenv("RULES_AUDIT_ONLY", "true").lower() == "true"
        if not path.exists():
            return RulesEngine(packs=[], enabled=enabled, audit_only=audit_only)
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except Exception:
            data = {}
        packs_json = data.get('packs') or []
        packs: List[RulePack] = []
        for pj in packs_json:
            rules = []
            for rj in (pj.get('rules') or []):
                rules.append(Rule(
                    id=str(rj.get('id') or ''),
                    enabled=bool(rj.get('enabled', True)),
                    condition=rj.get('condition') or {},
                    action=rj.get('action') or {},
                    priority=int(rj.get('priority', 100))
                ))
            packs.append(RulePack(
                id=str(pj.get('id') or ''),
                scope=str(pj.get('scope') or ''),
                enabled=bool(pj.get('enabled', True)),
                priority=int(pj.get('priority', 100)),
                rules=sorted(rules, key=lambda x: x.priority)
            ))
        packs = sorted(packs, key=lambda p: p.priority)
        return RulesEngine(packs=packs, enabled=enabled, audit_only=audit_only)

    def _iter_rules(self, scope: RuleScope):
        for p in self.packs:
            if not p.enabled or p.scope != scope:
                continue
            for r in p.rules:
                if not r.enabled:
                    continue
                yield r

    # -------- Scopes --------
    def apply_pre(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Pre-retrieval hook. Can derive query_signals, expansions, warnings.
        Returns {audit_logs: [...], updates: {...}}
        """
        logs: List[Dict[str, Any]] = []
        updates: Dict[str, Any] = {}
        if not self.enabled:
            return {"audit_logs": logs, "updates": updates}
        for r in self._iter_rules('pre'):
            hit = ConditionEval.eval(r.condition, ctx)
            if not hit:
                continue
            logs.append({"rule": r.id, "scope": "pre", "effect": r.action.get('type'), "detail": r.action})
            # Currently no mutating pre actions (kept audit-only); extend as needed
        return {"audit_logs": logs, "updates": updates}

    def apply_rerank(self, ctx: Dict[str, Any], scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Rerank hook. Can boost or filter scenarios. Returns {scenarios, audit_logs}.
        """
        logs: List[Dict[str, Any]] = []
        if not self.enabled:
            return {"scenarios": scenarios, "audit_logs": logs}
        out: List[Dict[str, Any]] = []
        for s in scenarios:
            s2 = dict(s)
            s2.setdefault('_rule_bonus', 0.0)
            out.append(s2)
        for r in self._iter_rules('rerank'):
            for s in out:
                ctx2 = dict(ctx)
                ctx2['scenario'] = s
                if not ConditionEval.eval(r.condition, ctx2):
                    continue
                logs.append({"rule": r.id, "scope": "rerank", "effect": r.action.get('type'), "scenario": s.get('semantic_id')})
                if r.action.get('type') == 'boost':
                    by = float(r.action.get('by', 0.0))
                    s['_rule_bonus'] = s.get('_rule_bonus', 0.0) + by
                if r.action.get('type') == 'filter' and not self.audit_only:
                    s['_filtered'] = True
        # Apply filter and resort by (rerank_score or similarity) * (1+_rule_bonus)
        kept = [s for s in out if not s.get('_filtered')]
        def base_score(s):
            return float(s.get('_rerank_score') or s.get('similarity') or 0.0)
        kept.sort(key=lambda s: base_score(s) * (1.0 + float(s.get('_rule_bonus') or 0.0)), reverse=True)
        return {"scenarios": kept, "audit_logs": logs}

    def apply_post(self, ctx: Dict[str, Any], llm_parsed: Dict[str, Any]) -> Dict[str, Any]:
        """Post-LLM hook. Can warn/fix/override. Returns {parsed, audit_logs}.
        """
        logs: List[Dict[str, Any]] = []
        parsed = dict(llm_parsed or {})
        recs = list(parsed.get('recommendations') or [])
        for r in self._iter_rules('post_llm'):
            if not ConditionEval.eval(r.condition, ctx):
                continue
            a = r.action or {}
            typ = a.get('type')
            logs.append({"rule": r.id, "scope": "post", "effect": typ, "detail": a})
            if typ == 'warn':
                # audit only
                pass
            elif typ == 'fix' and not self.audit_only:
                field = a.get('field')
                strategy = a.get('strategy')
                if field == 'filter_procedures_by_keywords' and strategy == 'deny_if_any_contains':
                    deny_keywords = set(_as_list(a.get('keywords')))
                    kept = []
                    for it in recs:
                        name = (it.get('procedure_name') or '') + ' ' + (it.get('modality') or '')
                        if any(k for k in deny_keywords if k and k in name):
                            continue
                        kept.append(it)
                    recs = kept
            elif typ == 'override' and not self.audit_only:
                field = a.get('field')
                if field and a.get('value') is not None:
                    parsed[field] = a.get('value')
        parsed['recommendations'] = recs
        return {"parsed": parsed, "audit_logs": logs}


def load_engine() -> RulesEngine:
    cfg = os.getenv('RULES_CONFIG_PATH') or str(Path(__file__).resolve().parents[2] / 'config' / 'rules_packs.json')
    return RulesEngine.from_file(cfg)

