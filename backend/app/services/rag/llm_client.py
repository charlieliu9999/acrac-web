from typing import Dict


def system_prompt() -> str:
    return (
        "你是一位专业的放射科医生，擅长影像检查推荐。"
        "必须仅输出有效JSON，不得包含解释、代码块(如```json)、或任何额外文字。"
        "JSON字段名必须与要求完全一致，且不得包含尾随逗号。"
    )


def chat_payload(model: str, user_prompt: str) -> Dict:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 3000,
    }

