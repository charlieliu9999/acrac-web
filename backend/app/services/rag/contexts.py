import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _clean_context(ctx: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    if not ctx:
        return cleaned
    for key, value in ctx.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        cleaned[key] = value
    return cleaned


def _build_override_index(overrides: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    index: Dict[str, List[Dict[str, Any]]] = {"panel": [], "topic": [], "scenario": [], "custom": []}
    for item in overrides or []:
        scope_type = (item.get("scope_type") or "custom").lower()
        if scope_type not in index:
            scope_type = "custom"
        index[scope_type].append(item)
    return index


def _match_override(index: Dict[str, List[Dict[str, Any]]], scope: Dict[str, Optional[str]]):
    sid = (scope.get("scenario_id") or "").strip()
    if sid:
        for item in index.get("scenario", []):
            if (item.get("scope_id") or "").strip() == sid:
                return item
    tid = (scope.get("topic_id") or "").strip()
    if tid:
        for item in index.get("topic", []):
            if (item.get("scope_id") or "").strip() == tid:
                return item
    pid = (scope.get("panel_id") or "").strip()
    if pid:
        for item in index.get("panel", []):
            if (item.get("scope_id") or "").strip() == pid:
                return item
    custom = (scope.get("custom") or "").strip()
    if custom:
        for item in index.get("custom", []):
            if (item.get("scope_id") or "").strip() == custom:
                return item
    return None


class Contexts:
    """Model context loader with scenario overrides and mtime hot-reload."""

    def __init__(self, config_dir: Path) -> None:
        self.path = config_dir / "model_contexts.json"
        self.mtime = 0.0
        self.model_contexts: Dict[str, Any] = {}
        self.default_inference_context: Dict[str, Any] = {}
        self.default_evaluation_context: Dict[str, Any] = {}
        self.scenario_overrides: List[Dict[str, Any]] = []
        self.override_index: Dict[str, List[Dict[str, Any]]] = {
            "panel": [],
            "topic": [],
            "scenario": [],
            "custom": [],
        }
        self.reload()

    def reload(self) -> None:
        data: Dict[str, Any] = {}
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"读取模型上下文失败: {exc}")
            data = {}
        ctxs = data.get("contexts") or {}
        overrides = data.get("scenario_overrides") or []
        self.model_contexts = ctxs
        self.default_inference_context = _clean_context(ctxs.get("inference"))
        self.default_evaluation_context = _clean_context(ctxs.get("evaluation"))
        self.scenario_overrides = overrides
        self.override_index = _build_override_index(overrides)
        try:
            self.mtime = self.path.stat().st_mtime
        except Exception:
            self.mtime = 0.0

    def maybe_reload(self) -> bool:
        try:
            current_mtime = self.path.stat().st_mtime
        except Exception:
            current_mtime = 0.0
        if current_mtime != self.mtime:
            self.reload()
            return True
        return False

    def resolve_inference_context(self, scope: Dict[str, Optional[str]], base: Dict[str, Any]) -> Dict[str, Any]:
        ctx = dict(self.default_inference_context)
        ov = _match_override(self.override_index, scope)
        if ov and ov.get("inference"):
            ctx.update(_clean_context(ov.get("inference")))
        # fill base defaults if missing
        ctx.setdefault("llm_model", base.get("llm_model"))
        ctx.setdefault("embedding_model", base.get("embedding_model"))
        ctx.setdefault("base_url", base.get("base_url"))
        ctx.setdefault("reranker_model", base.get("reranker_model"))
        if "temperature" not in ctx and base.get("temperature") is not None:
            ctx["temperature"] = base.get("temperature")
        if "top_p" not in ctx and base.get("top_p") is not None:
            ctx["top_p"] = base.get("top_p")
        if "max_tokens" not in ctx and base.get("max_tokens") is not None:
            ctx["max_tokens"] = base.get("max_tokens")
        if "reasoning_model" not in ctx and base.get("reasoning_model") is not None:
            ctx["reasoning_model"] = base.get("reasoning_model")
        if "disable_thinking" not in ctx and base.get("disable_thinking") is not None:
            ctx["disable_thinking"] = base.get("disable_thinking")
        if "no_thinking_tag" not in ctx and base.get("no_thinking_tag") is not None:
            ctx["no_thinking_tag"] = base.get("no_thinking_tag")
        return ctx


def extract_scope_info(scenarios: List[Dict[str, Any]]) -> Dict[str, Optional[str]]:
    if not scenarios:
        return {}
    primary = scenarios[0] or {}
    return {
        "scenario_id": primary.get("semantic_id") or primary.get("scenario_id"),
        "topic_id": primary.get("topic_semantic_id") or primary.get("topic_id"),
        "panel_id": primary.get("panel_semantic_id") or primary.get("panel_id"),
    }

