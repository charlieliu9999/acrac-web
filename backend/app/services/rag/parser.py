import json
import re
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


def parse_llm_response(llm_response: str) -> Dict[str, Any]:
    """Parse LLM output into a normalized JSON object.

    Always returns a dict; never raises, to keep pipeline resilient.

    - Strips code fences
    - Normalizes curly quotes
    - Extracts the first balanced JSON object
    - Tolerates relaxed JSON: single-quotes and unquoted keys
    - Validates and normalizes via Pydantic
    - Falls back to minimal structure when JSON cannot be found
    """
    original_text = (llm_response or "").strip()
    try:
        text = original_text
        if text.startswith("```"):
            lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
            text = "\n".join(lines)

        text = (
            text.replace("“", '\\"')
            .replace("”", '\\"')
            .replace("’", "'")
            .replace("‘", "'")
        )

        def extract_balanced_json(s: str) -> Optional[str]:
            start = s.find("{")
            if start == -1:
                return None
            depth = 0
            in_str = False
            esc = False
            for i in range(start, len(s)):
                ch = s[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                else:
                    if ch == '"':
                        in_str = True
                    elif ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            return s[start : i + 1]
            return None

        candidate = extract_balanced_json(text)
        if not candidate:
            # Fallback: return minimal dict with summary snippet
            return {
                "recommendations": [],
                "summary": (original_text[:200] if original_text else "解析失败: 未找到有效的JSON对象"),
                "no_rag": True,
                "rag_note": "LLM未输出JSON，已回退最小结构",
            }

        # remove trailing commas
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)

        try:
            data = json.loads(candidate)
        except Exception:
            relaxed = candidate
            relaxed = re.sub(r"([\{,]\s*)'([^'\n\r]+?)'(\s*:)", r'\1"\2"\3', relaxed)
            relaxed = re.sub(r"(:\s*)'([^'\n\r]*?)'", r'\1"\2"', relaxed)
            relaxed = re.sub(
                r"([\{,]\s*)([A-Za-z_][A-Za-z0-9_\-]*)(\s*:)", r'\1"\2"\3', relaxed
            )
            relaxed = re.sub(r",\s*([}\]])", r"\1", relaxed)
            try:
                data = json.loads(relaxed)
            except Exception:
                import ast

                data_py = ast.literal_eval(relaxed)
                data = json.loads(json.dumps(data_py, ensure_ascii=False))

        if not isinstance(data, dict):
            data = {"recommendations": data}
        if "recommendations" not in data or not isinstance(data["recommendations"], list):
            data["recommendations"] = []
        if "summary" not in data:
            data["summary"] = ""

        class _RecItem(BaseModel):
            rank: Optional[int] = None
            procedure_name: str = Field(default_factory=str)
            modality: str = Field(default_factory=str)
            appropriateness_rating: Union[str, int, float] = Field(default_factory=str)
            recommendation_reason: str = Field(default_factory=str)
            clinical_considerations: str = Field(default_factory=str)

        class _LLMOut(BaseModel):
            recommendations: List[_RecItem] = Field(default_factory=list)
            summary: str = Field(default_factory=str)
            no_rag: Optional[bool] = None
            rag_note: Optional[str] = None

        fixed_recs = []
        for i, rec in enumerate(data.get("recommendations", []), start=1):
            if not isinstance(rec, dict):
                continue
            rec = dict(rec)
            # Key alias mapping (incl. log_* variants some models emit)
            alias_map = {
                "procedure": "procedure_name",
                "log_procedure_name": "procedure_name",
                "method": "procedure_name",
                "mathod": "procedure_name",
                "log_modality": "modality",
                "method_modality": "modality",
                "mathodality": "modality",
                "log_appropriateness_rating": "appropriateness_rating",
                "rating": "appropriateness_rating",
                "mathp": "appropriateness_rating",
                "log_rank": "rank",
                "log_recommendation_reason": "recommendation_reason",
                "log_reason": "recommendation_reason",
                "reason": "recommendation_reason",
                "math_reason": "recommendation_reason",
                "log_clinical_considerations": "clinical_considerations",
                "considerations": "clinical_considerations",
                "math_considerations": "clinical_considerations",
                "math": "rank",
            }
            for src, dst in alias_map.items():
                if src in rec and not rec.get(dst):
                    rec[dst] = rec.pop(src)
            # More generic aliases for reason field
            for alt in ["reason", "reasoning", "clinical_reasoning"]:
                if alt in rec and not rec.get("recommendation_reason"):
                    rec["recommendation_reason"] = rec.pop(alt)
            if "rank" not in rec or rec["rank"] in (None, ""):
                rec["rank"] = i
            try:
                ar = rec.get("appropriateness_rating")
                if isinstance(ar, (int, float)):
                    rec["appropriateness_rating"] = f"{int(ar)}/9"
                elif isinstance(ar, str):
                    s = ar.strip()
                    if s and not s.endswith("/9"):
                        if s.isdigit():
                            rec["appropriateness_rating"] = f"{s}/9"
                # ensure rank is int
                if isinstance(rec.get("rank"), str):
                    try:
                        rec["rank"] = int(rec["rank"].strip())
                    except Exception:
                        pass
            except Exception:
                pass
            fixed_recs.append(rec)

        try:
            obj = _LLMOut(recommendations=fixed_recs, summary=data.get("summary") or "")
        except Exception:
            obj = _LLMOut(recommendations=[], summary=data.get("summary") or "")
        # Normalize minor formatting issues (e.g., unmatched parentheses)
        def _fix_name(name: str) -> str:
            s = (name or "").strip()
            if not s:
                return s
            # balance ASCII parentheses
            if s.count('(') > s.count(')'):
                s += ')'
            if s.count('（') > s.count('）'):
                s += '）'
            return s

        norm_recs = []
        for r in obj.recommendations:
            rr = {
                "rank": r.rank,
                "procedure_name": _fix_name(r.procedure_name),
                "modality": r.modality,
                "appropriateness_rating": r.appropriateness_rating,
                "recommendation_reason": r.recommendation_reason,
                "clinical_considerations": r.clinical_considerations,
            }
            norm_recs.append(rr)

        out = {
            "recommendations": norm_recs,
            "summary": obj.summary,
        }
        if isinstance(data, dict):
            if data.get("no_rag") is not None:
                out["no_rag"] = bool(data.get("no_rag"))
            if data.get("rag_note") is not None:
                out["rag_note"] = data.get("rag_note")
        return out
    except Exception as e:
        # ultimate fallback: never raise
        return {
            "recommendations": [],
            "summary": f"解析LLM响应失败: {e}",
            "no_rag": True,
            "rag_note": "解析异常，已回退最小结构",
        }
