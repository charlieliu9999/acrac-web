"""
Configurable, negation-aware query signals extractor.

Reads patterns from a JSON file so domain rules don't need to be hardcoded.
Default path can be overridden via env `QUERY_SIGNALS_CONFIG_PATH`.

JSON schema (sample at backend/config/query_signals.sample.json):
{
  "signals": {
    "pregnancy_status": {
      "value": "妊娠/围产",
      "positive": ["孕", "妊娠", "孕妇", "围产", "产后"],
      "negative": ["非妊娠", "未孕", "否认妊娠", "备孕", "排除妊娠"]
    }
  },
  "keywords": ["急诊", "急性", "突发", "雷击样", "霹雳样", "TCH", "SAH", "蛛网膜下腔出血"]
}
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import os
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class _SignalRule:
    value: str
    positive: List[str]
    negative: List[str]


class QuerySignalExtractor:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.getenv("QUERY_SIGNALS_CONFIG_PATH")
        self._cfg: Dict[str, Any] = {}
        self._compiled: Dict[str, Dict[str, List[re.Pattern]]] = {}
        self._keywords: List[str] = []
        self._load_config()

    def _load_config(self) -> None:
        # Resolve path priority: env path -> repo config -> sample -> built-in defaults
        paths: List[Path] = []
        if self.config_path:
            paths.append(Path(self.config_path))
        repo_base = Path(__file__).resolve().parents[2]
        paths.append(repo_base / "config" / "query_signals.json")
        paths.append(repo_base / "config" / "query_signals.sample.json")

        cfg: Dict[str, Any] = {}
        for p in paths:
            try:
                if p.exists():
                    cfg = json.loads(p.read_text(encoding="utf-8"))
                    logger.info(f"Loaded query signals config: {p}")
                    break
            except Exception as e:
                logger.warning(f"Failed to read query signals config {p}: {e}")

        if not cfg:
            # Built-in default
            cfg = {
                "signals": {
                    "pregnancy_status": {
                        "value": "妊娠/围产",
                        "positive": ["孕", "妊娠", "孕妇", "围产", "产后"],
                        "negative": ["非妊娠", "未孕", "否认妊娠", "备孕", "排除妊娠"],
                    }
                },
                "keywords": ["急诊", "急性", "突发", "雷击样", "霹雳样", "TCH", "SAH", "蛛网膜下腔出血"],
            }
            logger.info("Using built-in query signals defaults")

        self._cfg = cfg
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        comp: Dict[str, Dict[str, List[re.Pattern]]] = {}
        for name, rule in (self._cfg.get("signals") or {}).items():
            pos = [re.compile(re.escape(s), re.I) for s in rule.get("positive") or []]
            neg = [re.compile(re.escape(s), re.I) for s in rule.get("negative") or []]
            comp[name] = {"positive": pos, "negative": neg}
        self._compiled = comp
        self._keywords = list(self._cfg.get("keywords") or [])

    def extract(self, query: str) -> Dict[str, Any]:
        q = query or ""
        out: Dict[str, Any] = {}

        # Signals with positive/negative lists
        for name, rule in (self._cfg.get("signals") or {}).items():
            pats = self._compiled.get(name) or {"positive": [], "negative": []}
            has_pos = any(p.search(q) for p in pats["positive"]) if pats["positive"] else False
            has_neg = any(n.search(q) for n in pats["negative"]) if pats["negative"] else False
            if has_pos and not has_neg:
                out[name] = str(rule.get("value") or name)

        # Keyword hits (flat list)
        kws: List[str] = []
        if self._keywords:
            for k in self._keywords:
                try:
                    if re.search(re.escape(k), q, re.I):
                        kws.append(k)
                except Exception:
                    pass
        if kws:
            out["keywords"] = kws

        return out

