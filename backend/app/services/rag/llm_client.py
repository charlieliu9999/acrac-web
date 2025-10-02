import os
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def call_llm(prompt: str, context: Optional[Dict[str, Any]] = None, *, force_json: bool = True, default_max_tokens: int = 512, seed: Optional[int] = None) -> str:
    """Invoke an OpenAI-compatible chat completion with robust JSON output settings.

    - Respects Ollama base_url by using a placeholder API key if necessary.
    - Applies response_format=json_object when available and not using Ollama.
    - Supports optional reasoning suppression via disable_thinking and no_thinking_tag.
    """
    try:
        # Lazy import to avoid heavy import at module load time
        import openai  # type: ignore
    except Exception as e:  # pragma: no cover
        logger.error(f"openai SDK import failed: {e}")
        raise

    try:
        ctx = context or {}
        model_name = ctx.get("llm_model") or os.getenv("SILICONFLOW_LLM_MODEL", "Qwen/Qwen2.5-32B-Instruct")
        base_url = ctx.get("base_url") or os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        api_key = ctx.get("api_key") or os.getenv("SILICONFLOW_API_KEY") or os.getenv("OPENAI_API_KEY")
        client = openai.OpenAI(api_key=api_key, base_url=base_url)

        # Ollama usually doesn't need a real key, but OpenAI SDK requires some value
        if base_url and (("11434" in base_url) or ("ollama" in base_url.lower())):
            if not api_key:
                api_key = os.getenv("OLLAMA_API_KEY") or "ollama"
            client = openai.OpenAI(api_key=api_key, base_url=base_url)

        temperature = ctx.get("temperature")
        if temperature is None:
            temperature = 0.1
        top_p = ctx.get("top_p")
        if top_p is None:
            top_p = 0.7

        def _looks_reasoning(name: str) -> bool:
            n = (name or "").lower()
            for key in ["gpt-oss", "deepseek-r1", "qwq", "r1", "reason"]:
                if key in n:
                    return True
            return False

        reasoning_flag = bool(ctx.get("reasoning_model")) or _looks_reasoning(model_name)
        disable_thinking = bool(ctx.get("disable_thinking"))
        no_thinking_tag = (ctx.get("no_thinking_tag") or "").strip()

        sys_inst = (
            "你是一位专业的放射科医生，擅长影像检查推荐。"
            "必须仅输出有效JSON，不得包含解释、代码块(如```json)、或任何额外文字。"
            "JSON字段名必须与要求完全一致，且不得包含尾随逗号。"
            "严禁输出<think>、思维链、推理过程、系统提示或任何与JSON无关的内容。"
        )
        user_content = prompt
        if disable_thinking and no_thinking_tag:
            user_content = f"{prompt}\n{no_thinking_tag}"

        kwargs: Dict[str, Any] = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": sys_inst},
                {"role": "user", "content": user_content},
            ],
            "temperature": temperature,
            "top_p": top_p,
        }

        # Force JSON when service supports it (avoid for Ollama)
        is_ollama = bool(base_url and (("11434" in base_url) or ("ollama" in base_url.lower())))
        if force_json and not is_ollama:
            kwargs["response_format"] = {"type": "json_object"}

        max_out = ctx.get("max_tokens") if ctx.get("max_tokens") is not None else default_max_tokens
        try:
            max_out = int(max_out) if max_out is not None else None
        except Exception:
            max_out = None
        if reasoning_flag and (not max_out or max_out < 1024):
            max_out = 1024
        if max_out and max_out > 0:
            kwargs["max_tokens"] = max_out
        if disable_thinking:
            kwargs["stop"] = kwargs.get("stop") or ["</think>", "<think>"]
        if seed is not None:
            kwargs["seed"] = seed

        response = client.chat.completions.create(**kwargs)
        result = response.choices[0].message.content
        if result is None:
            return fallback_response()
        return result
    except Exception as e:
        logger.error(f"LLM调用失败: {e}")
        # Do not fabricate recommendations; let caller decide how to handle
        raise


def fallback_response() -> str:
    """Deterministic fallback JSON when LLM inference fails."""
    return (
        "{\n"
        "    \"recommendations\": [\n"
        "        {\n"
        "            \"rank\": 1,\n"
        "            \"procedure_name\": \"系统暂时无法生成推荐\",\n"
        "            \"modality\": \"N/A\",\n"
        "            \"appropriateness_rating\": \"N/A\",\n"
        "            \"recommendation_reason\": \"LLM服务暂时不可用，请稍后重试\",\n"
        "            \"clinical_considerations\": \"建议咨询专业医生\"\n"
        "        }\n"
        "    ],\n"
        "    \"summary\": \"系统暂时无法提供智能推荐，建议使用传统向量搜索功能\"\n"
        "}\n"
    )
