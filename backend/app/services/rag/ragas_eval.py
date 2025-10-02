import json
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def build_contexts_from_payload(payload: Dict[str, Any]) -> List[str]:
    contexts: List[str] = []
    for sc in payload.get("scenarios_with_recommendations") or []:
        desc = sc.get("scenario_description") or sc.get("description_zh")
        if desc:
            contexts.append(desc)
        for r in (sc.get("recommendations") or []):
            reason = r.get("reasoning_zh")
            if reason:
                contexts.append(reason)
    for sc in payload.get("scenarios") or []:
        desc = sc.get("description_zh")
        if desc:
            contexts.append(desc)
    return contexts


def format_answer_for_ragas(parsed: Dict[str, Any]) -> str:
    lines: List[str] = []
    for r in parsed.get("recommendations") or []:
        name = r.get("procedure_name", "")
        mod = r.get("modality", "")
        rating = r.get("appropriateness_rating", "")
        reason = r.get("recommendation_reason", "")
        t = f"{name} ({mod}) - 评分: {rating}"
        if reason:
            t += f"\n理由: {reason}"
        lines.append(t)
    if parsed.get("summary"):
        lines.append(f"总结: {parsed.get('summary')}")
    return "\n".join(lines) if lines else "无"


def compute_ragas_scores(user_input: str, answer: str, contexts: List[str], reference: str,
                         eval_context: Dict[str, Any]) -> Dict[str, float]:
    """Compute RAGAS metrics in-process with fallback to an isolated subprocess.

    Uses models from evaluation context to avoid leakage from inference settings.
    """
    try:
        import ragas  # type: ignore
        from datasets import Dataset  # type: ignore
        from ragas.metrics import (  # type: ignore
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        )
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # type: ignore

        api_key = os.getenv("SILICONFLOW_API_KEY") or os.getenv("OPENAI_API_KEY")
        base_url = (
            eval_context.get("base_url")
            or os.getenv("SILICONFLOW_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.siliconflow.cn/v1"
        )
        llm_model = eval_context.get("llm_model") or os.getenv("SILICONFLOW_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct")
        emb_model = eval_context.get("embedding_model") or os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3")
        temperature = eval_context.get("temperature", 0.1)
        top_p = eval_context.get("top_p", 0.7)

        llm = ChatOpenAI(model=llm_model, api_key=api_key, base_url=base_url, temperature=temperature, top_p=top_p)
        emb = OpenAIEmbeddings(model=emb_model, api_key=api_key, base_url=base_url)

        has_ref = bool(reference and str(reference).strip())
        if has_ref:
            data_dict = {
                "question": [user_input],
                "answer": [answer],
                "contexts": [contexts],
                "ground_truth": [reference],
            }
            metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
        else:
            data_dict = {"question": [user_input], "answer": [answer], "contexts": [contexts]}
            metrics = [faithfulness, answer_relevancy]

        data = Dataset.from_dict(data_dict)
        res = ragas.evaluate(dataset=data, metrics=metrics, llm=llm, embeddings=emb)
        if isinstance(res, dict):
            base = res
        elif hasattr(res, "scores") and isinstance(res.scores, dict):
            base = res.scores
        else:
            try:
                base = dict(res)
            except Exception:
                base = {}

        def clean(v):
            try:
                f = float(v)
                if f != f:
                    logger.warning(f"RAGAS评分为NaN: {v}")
                    return float("nan")
                return f
            except Exception as e:
                logger.warning(f"RAGAS评分转换失败: {v}, 错误: {e}")
                return 0.0

        # Only include metrics that were computed; avoid misleading 0.0 defaults
        result = {}
        if 'faithfulness' in base:
            result['faithfulness'] = clean(base.get('faithfulness'))
        if 'answer_relevancy' in base:
            result['answer_relevancy'] = clean(base.get('answer_relevancy'))
        if has_ref and 'context_precision' in base:
            result['context_precision'] = clean(base.get('context_precision'))
        if has_ref and 'context_recall' in base:
            result['context_recall'] = clean(base.get('context_recall'))
        return result
    except Exception as e:
        msg = str(e)
        if isinstance(e, ImportError) or "No module named" in msg or "uvloop" in msg or "nest_asyncio" in msg:
            logger.warning(f"RAGAS进程内评测失败，尝试子进程隔离执行: {e}")
            return compute_ragas_scores_isolated(user_input, answer, contexts, reference, eval_context)
        logger.error(f"RAGAS评测失败: {e}")
        raise


def compute_ragas_scores_isolated(user_input: str, answer: str, contexts: List[str], reference: str,
                                  eval_context: Dict[str, Any]) -> Dict[str, float]:
    payload = {
        "user_input": user_input,
        "answer": answer,
        "contexts": contexts,
        "reference": reference,
        "llm_model": eval_context.get("llm_model") or os.getenv("SILICONFLOW_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct"),
        "embedding_model": eval_context.get("embedding_model") or os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3"),
        "base_url": eval_context.get("base_url") or os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"),
    }
    code = r"""
import os, json, asyncio
try:
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
except Exception:
    pass
cfg = json.loads(os.environ.get('RAGAS_INPUT', '{}'))
user_input = cfg.get('user_input')
answer = cfg.get('answer')
contexts = cfg.get('contexts') or []
reference = cfg.get('reference')
import ragas
from datasets import Dataset
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
api_key = os.getenv('SILICONFLOW_API_KEY') or os.getenv('OPENAI_API_KEY')
base_url = os.getenv('SILICONFLOW_BASE_URL', cfg.get('base_url', 'https://api.siliconflow.cn/v1'))
llm_model = os.getenv('SILICONFLOW_LLM_MODEL', cfg.get('llm_model', 'Qwen/Qwen2.5-32B-Instruct'))
emb_model = os.getenv('SILICONFLOW_EMBEDDING_MODEL', cfg.get('embedding_model', 'BAAI/bge-m3'))
llm = ChatOpenAI(model=llm_model, api_key=api_key, base_url=base_url, temperature=0)
emb = OpenAIEmbeddings(model=emb_model, api_key=api_key, base_url=base_url)
has_ref = bool(reference and str(reference).strip())
if has_ref:
    data_dict = { 'question': [user_input], 'answer': [answer], 'contexts': [contexts], 'ground_truth': [reference] }
    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
else:
    data_dict = { 'question': [user_input], 'answer': [answer], 'contexts': [contexts] }
    metrics = [faithfulness, answer_relevancy]
data = Dataset.from_dict(data_dict)
res = ragas.evaluate(dataset=data, metrics=metrics, llm=llm, embeddings=emb)
if isinstance(res, dict):
    base = res
elif hasattr(res, 'scores') and isinstance(res.scores, dict):
    base = res.scores
elif hasattr(res, '_scores_dict') and isinstance(res._scores_dict, dict):
    base = {}
    for k, v in res._scores_dict.items():
        if isinstance(v, list) and len(v) > 0:
            base[k] = v[0]
        else:
            base[k] = v
else:
    try:
        base = dict(res)
    except Exception:
        base = {}
def clean(v):
    try:
        f = float(v)
        if f != f or f == float('inf') or f == float('-inf'):
            return 0.0
        return f
    except Exception:
        return 0.0
out = {}
if 'faithfulness' in base:
    out['faithfulness'] = clean(base.get('faithfulness'))
if 'answer_relevancy' in base:
    out['answer_relevancy'] = clean(base.get('answer_relevancy'))
if cfg.get('reference'):
    if 'context_precision' in base:
        out['context_precision'] = clean(base.get('context_precision'))
    if 'context_recall' in base:
        out['context_recall'] = clean(base.get('context_recall'))
print(json.dumps(out))
"""
    env = dict(os.environ)
    env["RAGAS_INPUT"] = json.dumps(payload, ensure_ascii=False)
    proc = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"ragas subprocess failed: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout.strip())
    except Exception as je:
        raise RuntimeError(f"invalid ragas subprocess output: {je}; raw={proc.stdout[:2000]}")
