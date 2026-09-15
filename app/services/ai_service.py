import json

import requests
from flask import current_app

SYSTEM_PROMPT = (
    "당신은 급여대장 이상치를 분석하는 보조 도구입니다. "
    "주어진 직원 급여 변동 데이터를 보고 왜 이상치로 감지되었는지 설명하세요. "
    "절대 오류라고 단정하지 말고 '가능성'으로만 표현하세요. "
    "최종 판단은 담당자가 합니다. "
    "다음 JSON 형식으로만 답변하세요: "
    '{"summary": str, "possible_causes": [str, ...], "recommended_action": str, "confidence": float(0~1)}'
)


def _fallback_analysis(payload):
    field = payload.get("field_name") or "해당 항목"
    rate = payload.get("change_rate")
    rate_text = f"{rate:+.1f}%" if rate is not None else "큰 폭으로"
    return {
        "summary": f"{field}이(가) 전월 대비 {rate_text} 변동하여 설정된 기준을 벗어났습니다.",
        "possible_causes": [
            "인사발령/직급 변경에 따른 정상적인 변경일 가능성",
            "급여 조건 변경 또는 성과급 반영 가능성",
            "데이터 입력 오류 가능성",
        ],
        "recommended_action": "인사발령 이력 및 원본 급여 산정 자료를 확인해주세요.",
        "confidence": 0.5,
        "model_name": "rule-based-fallback",
    }


def analyze(payload):
    """payload: minimal dict (employee_id, field, previous/current, detected_rules).
    Never include employee name or other PII."""
    provider = current_app.config.get("AI_PROVIDER")
    api_key = current_app.config.get("AI_API_KEY")
    model = current_app.config.get("AI_MODEL")

    if not api_key:
        return _fallback_analysis(payload)

    try:
        if provider == "openai":
            result = _call_openai(payload, api_key, model)
        else:
            return _fallback_analysis(payload)
        result["model_name"] = model
        return result
    except Exception:
        return _fallback_analysis(payload)


def _call_openai(payload, api_key, model):
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        },
        timeout=20,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(content)
