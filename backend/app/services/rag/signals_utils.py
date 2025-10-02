import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def extract_query_signals(query: str) -> Dict[str, Any]:
    """Minimal, safe signals extraction with negation guards."""
    q = query or ""
    signals: Dict[str, Any] = {}
    negs = ["非妊娠", "未孕", "否认妊娠", "备孕", "排除妊娠"]
    if any(k in q for k in ["孕", "妊娠", "孕妇", "围产", "产后"]) and not any(
        n in q for n in negs
    ):
        signals["pregnancy_status"] = "妊娠/围产"
    kws = []
    for k in ["急诊", "急性", "突发", "雷击样", "霹雳样", "TCH", "SAH", "蛛网膜下腔出血"]:
        if (k.lower() in q.lower()) or (k in q):
            kws.append(k)
    if kws:
        signals["keywords"] = kws
    return signals

