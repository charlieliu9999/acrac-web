Rules Engine for ACRAC RAG+LLM (Incremental, Default Off)

Overview
- A lightweight, file-driven rules engine that can adjust retrieval/rerank and post-LLM outputs without changing the core API or pipeline order. When disabled (default), it is a no-op.
- Scopes: pre (audit only by default), rerank (boost/filter), post_llm (warn/fix/override)
- Config: JSON rule packs (config/rules_packs.json)
- Audit: records rule hits into response debug_info.rules_audit when API debug is on

Enable
- .env or environment:
  - RULES_ENABLED=true (default: false)
  - RULES_AUDIT_ONLY=true (default: true; set false to allow filter/fix/override changes)
  - RULES_CONFIG_PATH=config/rules_packs.json (default path)

File Format (config/rules_packs.json)
Example:
{
  "packs": [
    {
      "id": "pregnancy_safety_post",
      "scope": "post_llm",
      "enabled": true,
      "priority": 10,
      "rules": [
        {
          "id": "warn_pregnancy_high_radiation",
          "enabled": true,
          "priority": 10,
          "condition": {"in": ["query_signals.pregnancy_status", ["妊娠/围产"]]},
          "action": {"type": "warn", "message": "Pregnancy case: review radiation and contrast choices."}
        },
        {
          "id": "filter_ct_in_pregnancy",
          "enabled": true,
          "priority": 20,
          "condition": {"in": ["query_signals.pregnancy_status", ["妊娠/围产"]]},
          "action": {"type": "fix", "field": "filter_procedures_by_keywords", "strategy": "deny_if_any_contains", "keywords": ["CT", "CTA", "CTV"]}
        }
      ]
    }
  ]
}

Condition Language
- Supported operators: and, or, not, eq, ne, gt, gte, lt, lte, in, any_in, all_in, contains, exists, regex
- Values resolve from context using dot-paths (e.g. "query_signals.pregnancy_status")

Actions
- boost (rerank): { "type":"boost", "by":0.15 } adds multiplicative bonus (1+by) during resort
- filter (rerank): { "type":"filter" } marks scenario as filtered (applied only if RULES_AUDIT_ONLY=false)
- warn (post): audit only
- fix (post): limited, safe mutators, e.g. { "type":"fix", "field":"filter_procedures_by_keywords", "strategy":"deny_if_any_contains", "keywords":["CT","CTA"] }
- override (post): set a field to value, e.g. { "type":"override", "field":"summary", "value":"..." }

Hooks in Pipeline
- rerank: after baseline re-ranking, rules_engine.apply_rerank can boost/filter scenarios
- post_llm: after LLM parsing, rules_engine.apply_post can warn/fix
- pre: reserved for later use (currently audit-only)

Context Passed to Rules
- query: original clinical query
- query_signals: lightweight signals extracted online (pregnancy_status, keywords)
- scenario (rerank only): current scenario dict (semantic_id, similarity, _rerank_score, etc.)
- scenarios (post): full list of scenarios used during this request
- llm_parsed (post): LLM parsed output (not exposed directly; actions operate via fix/override)

Auditing
- With API debug_mode=True, audit logs are included in response under debug_info.rules_audit.rerank / debug_info.rules_audit.post.
- File-level versioning/ownership is recommended via Git.

Extending
- Add new actions (e.g., harmonize scores, align ratings) in backend/app/services/rules_engine.py
- Add more signals: implement offline extractor to write semantic_signals table; online can read and merge
- For DB-managed rules: add a loader to fetch packs from DB instead of JSON (do not mix sources in one run)

Safety & Rollback
- Keep RULES_AUDIT_ONLY=true for an observation phase
- Flip to false to enforce filtering/fixes after confirming behavior in logs
- Set RULES_ENABLED=false to immediately revert to current behavior

Examples
- Boost thunderclap/SAH-like queries during rerank
- In pregnancy, warn and optionally filter CT-family procedures in post-LLM

Notes
- The engine intentionally avoids heavy dependencies and uses a minimal condition evaluator
- If you need JSONLogic compatibility, a converter can be added in a follow-up

