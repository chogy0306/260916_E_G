from io import BytesIO

import pandas as pd

SEVERITY_LABELS = {"ERROR": "오류", "WARNING": "경고", "REVIEW": "확인필요"}
STATUS_LABELS = {
    "NEW": "신규",
    "REVIEWING": "검토중",
    "CONFIRMED": "오류 확정",
    "FALSE_POSITIVE": "정상(오탐)",
    "RESOLVED": "해결됨",
}


def build_results_excel(results):
    rows = []
    for r in results:
        rows.append(
            {
                "직원ID": r.employee.employee_id if r.employee else "",
                "직원명": r.employee.employee_name if r.employee else "",
                "부서": r.employee.department if r.employee else "",
                "검증항목": r.category,
                "등급": SEVERITY_LABELS.get(r.severity, r.severity),
                "전월값": float(r.previous_value) if r.previous_value is not None else "",
                "이번달값": float(r.current_value) if r.current_value is not None else "",
                "변동률(%)": round(r.change_rate, 1) if r.change_rate is not None else "",
                "탐지사유": r.message,
                "AI 분석": r.ai_analysis.summary if r.ai_analysis else "",
                "처리상태": STATUS_LABELS.get(r.status, r.status),
                "메모": "; ".join(n.note for n in r.notes) if r.notes else "",
            }
        )

    df = pd.DataFrame(rows)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="검증결과")
        worksheet = writer.sheets["검증결과"]
        for col_letter in ("F", "G"):  # 전월값, 이번달값
            for cell in worksheet[col_letter][1:]:
                cell.number_format = "#,##0"
    buffer.seek(0)
    return buffer
