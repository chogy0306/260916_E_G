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


# Ordered most-decisive-first: when several categories are merged into one
# finding (e.g. "비정상 데이터 · 통계적 이상치 · 급여 변동"), the first match
# here picks the recommended action; every match contributes its causes.
CATEGORY_INSIGHTS = [
    ("중복 직원", {
        "causes": ["동일 직원이 두 행으로 중복 입력되었을 가능성", "퇴사/재입사 처리 중 직원ID가 재사용되었을 가능성"],
        "action": "인사 시스템에서 해당 직원ID의 등록 이력을 확인하고 중복 행을 제거해주세요.",
    }),
    ("비정상 데이터", {
        "causes": ["입력 과정에서 부호가 반대로 입력되었을 가능성", "원본 급여 산정 자료의 계산 오류 가능성"],
        "action": "원본 급여 산정 자료를 확인해 음수로 입력된 값을 정정해주세요.",
    }),
    ("합계 불일치", {
        "causes": ["항목 합산 공식 또는 서식이 잘못되었을 가능성", "일부 지급/공제 항목이 누락되어 합계에 반영되지 않았을 가능성"],
        "action": "지급/공제 항목별 값과 합계 셀의 수식을 다시 확인해주세요.",
    }),
    ("4대보험", {
        "causes": ["신고된 요율과 다른 요율이 적용되었을 가능성", "기준소득월액(기본급) 변경이 아직 반영되지 않았을 가능성"],
        "action": "4대보험 신고 내역과 이번 달 적용 요율이 일치하는지 확인해주세요.",
    }),
    ("통계적 이상치", {
        "causes": ["다른 직원 대비 특이한 근무/직급 조건일 가능성", "데이터 입력 시 자릿수 오류(예: 0 하나 추가)가 있을 가능성"],
        "action": "해당 직원의 근로 조건과 입력 값의 자릿수를 다시 확인해주세요.",
    }),
    ("직원 누락", {
        "causes": ["퇴사 또는 휴직으로 급여 대상에서 제외되었을 가능성", "급여대장 작성 시 해당 직원이 실수로 빠졌을 가능성"],
        "action": "퇴사/휴직 처리 이력을 확인하고, 실수 누락이라면 급여대장에 다시 반영해주세요.",
    }),
    ("신규 직원", {
        "causes": ["이번 달 신규 입사자일 가능성", "직원ID가 변경되어 새로운 직원으로 인식되었을 가능성"],
        "action": "인사기록에서 신규 입사 여부를 확인해주세요.",
    }),
    ("신규 항목", {
        "causes": ["이번 달부터 새로 지급/공제되는 항목일 가능성", "항목명이 변경되어 새로운 항목으로 인식되었을 가능성"],
        "action": "해당 항목이 신규 지급 항목인지, 기존 항목명이 바뀐 것인지 확인해주세요.",
    }),
    ("항목 소멸", {
        "causes": ["해당 항목의 지급/공제가 이번 달부터 중단되었을 가능성", "항목명이 변경되어 이전 항목이 인식되지 않았을 가능성"],
        "action": "해당 항목의 지급 중단 여부와 항목명 변경 여부를 확인해주세요.",
    }),
    ("필수값 누락", {
        "causes": ["엑셀 원본에서 해당 셀이 비어 있을 가능성", "컬럼 매핑이 잘못되어 값이 인식되지 않았을 가능성"],
        "action": "원본 엑셀 파일에서 해당 값이 실제로 입력되어 있는지 확인해주세요.",
    }),
    ("급여 변동", {
        "causes": ["인사발령/직급 변경에 따른 정상적인 변경일 가능성", "급여 조건 변경 또는 성과급 반영 가능성", "데이터 입력 오류 가능성"],
        "action": "인사발령 이력 및 원본 급여 산정 자료를 확인해주세요.",
    }),
]


def _fallback_analysis(payload):
    category = payload.get("category") or payload.get("detected_rule") or ""
    matched = [key for key, info in CATEGORY_INSIGHTS if key in category]

    causes = []
    for key in matched:
        for cause in dict(CATEGORY_INSIGHTS)[key]["causes"]:
            if cause not in causes:
                causes.append(cause)

    default = dict(CATEGORY_INSIGHTS)["급여 변동"]
    action = dict(CATEGORY_INSIGHTS)[matched[0]]["action"] if matched else default["action"]
    if not causes:
        causes = default["causes"]

    message = payload.get("message")
    if message:
        summary = message.strip().splitlines()[0].lstrip("- ").strip()
        if len(message.strip().splitlines()) > 1:
            summary += " 등 여러 조건이 함께 감지되었습니다."
    else:
        field = payload.get("field_name") or "해당 항목"
        rate = payload.get("change_rate")
        rate_text = f"{rate:+.1f}%" if rate is not None else "설정된 기준을"
        summary = f"{field}이(가) 전월 대비 {rate_text} 변동하여 기준을 벗어났습니다."

    return {
        "summary": summary,
        "possible_causes": causes[:3],
        "recommended_action": action,
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
