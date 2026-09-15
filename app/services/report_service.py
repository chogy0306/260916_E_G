from io import BytesIO

import pandas as pd


def build_results_excel(results):
    rows = []
    for r in results:
        rows.append(
            {
                "직원ID": r.employee.employee_id if r.employee else "",
                "직원명": r.employee.employee_name if r.employee else "",
                "부서": r.employee.department if r.employee else "",
                "검증항목": r.category,
                "등급": r.severity,
                "전월값": float(r.previous_value) if r.previous_value is not None else "",
                "이번달값": float(r.current_value) if r.current_value is not None else "",
                "변동률(%)": round(r.change_rate, 1) if r.change_rate is not None else "",
                "탐지사유": r.message,
                "AI 분석": r.ai_analysis.summary if r.ai_analysis else "",
                "처리상태": r.status,
                "메모": "; ".join(n.note for n in r.notes) if r.notes else "",
            }
        )

    df = pd.DataFrame(rows)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="검증결과")
    buffer.seek(0)
    return buffer
