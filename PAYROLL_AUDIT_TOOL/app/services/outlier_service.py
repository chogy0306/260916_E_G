import statistics

from app.services.mapping_service import field_label

MIN_SAMPLE_SIZE = 5


def detect(employees, values_by_employee):
    by_item = {}
    for emp in employees:
        for item, value in values_by_employee.get(emp.id, {}).items():
            if value is None:
                continue
            by_item.setdefault(item, []).append((emp, value))

    findings = []
    for item, pairs in by_item.items():
        values = sorted(v for _, v in pairs)
        n = len(values)
        if n < MIN_SAMPLE_SIZE:
            continue

        q1 = statistics.median(values[: n // 2])
        q3 = statistics.median(values[(n + 1) // 2 :])
        iqr = q3 - q1
        if iqr == 0:
            continue

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        for emp, value in pairs:
            if value < lower or value > upper:
                findings.append(
                    {
                        "employee_pk": emp.id,
                        "category": "통계적 이상치",
                        "severity": "REVIEW",
                        "field_name": item,
                        "current_value": value,
                        "message": (
                            f"'{emp.employee_name}'의 {field_label(item)}({value:,.0f}원)이 "
                            f"다른 직원들의 분포(IQR 기준 {lower:,.0f}~{upper:,.0f}원)에서 벗어난 값입니다."
                        ),
                        "rule_code": "STATISTICAL_OUTLIER",
                    }
                )
    return findings
