from app.services.mapping_service import INSURANCE_ITEMS, field_label

RATE_THRESHOLD = 20.0

RATE_RULE_FOR_ITEM = {
    "pension": "INSURANCE_RATE_NATIONAL_PENSION",
    "health_insurance": "INSURANCE_RATE_HEALTH",
    "long_term_care": "INSURANCE_RATE_LONG_TERM_CARE",
    "employment_insurance": "INSURANCE_RATE_EMPLOYMENT",
}

# Most items are a % of base salary, but 장기요양보험료 is legally defined as a
# % of the *건강보험료* itself (13.14% of the health-insurance premium as of
# 2026), not of salary directly.
RATE_BASE_FOR_ITEM = {
    "pension": "base_salary",
    "health_insurance": "base_salary",
    "employment_insurance": "base_salary",
    "long_term_care": "health_insurance",
}


def check(employees, values_by_employee, prev_values_by_employee_id, rules_by_code=None):
    """prev_values_by_employee_id: {employee_id(business key): {item: value}}"""
    rules_by_code = rules_by_code or {}
    findings = []
    for emp in employees:
        items = values_by_employee.get(emp.id, {})
        prev_items = prev_values_by_employee_id.get(emp.employee_id, {})

        mapped_insurance_items = [i for i in INSURANCE_ITEMS if i in items or i in prev_items]
        if not mapped_insurance_items:
            continue

        for item in INSURANCE_ITEMS:
            if item not in items and item not in prev_items:
                continue
            current = items.get(item)
            previous = prev_items.get(item)
            label = field_label(item)

            if current is None and previous is not None:
                findings.append(
                    {
                        "employee_pk": emp.id,
                        "category": "4대보험",
                        "severity": "REVIEW",
                        "field_name": item,
                        "previous_value": previous,
                        "message": f"'{emp.employee_name}'의 {label} 데이터가 이번 달에 누락되었습니다.",
                        "rule_code": "INSURANCE_MISSING",
                    }
                )
                continue

            if current is not None and current < 0:
                findings.append(
                    {
                        "employee_pk": emp.id,
                        "category": "4대보험",
                        "severity": "ERROR",
                        "field_name": item,
                        "current_value": current,
                        "message": f"'{emp.employee_name}'의 {label} 금액이 음수입니다.",
                        "rule_code": "INSURANCE_NEGATIVE",
                    }
                )

            if previous and current is not None:
                rate = (current - previous) / previous * 100
                if abs(rate) > RATE_THRESHOLD:
                    findings.append(
                        {
                            "employee_pk": emp.id,
                            "category": "4대보험",
                            "severity": "REVIEW",
                            "field_name": item,
                            "previous_value": previous,
                            "current_value": current,
                            "change_rate": rate,
                            "message": (
                                f"'{emp.employee_name}'의 {label}이(가) 전월 대비 "
                                f"{rate:+.1f}% 변동했습니다."
                            ),
                            "rule_code": "INSURANCE_RATE_CHANGE",
                        }
                    )

            rate_rule = rules_by_code.get(RATE_RULE_FOR_ITEM.get(item))
            base_amount = items.get(RATE_BASE_FOR_ITEM.get(item, "base_salary"))
            if rate_rule and rate_rule.is_active and base_amount and current is not None:
                expected = base_amount * rate_rule.threshold / 100
                tolerance = max(1000, expected * 0.02)
                if abs(current - expected) > tolerance:
                    findings.append(
                        {
                            "employee_pk": emp.id,
                            "category": "4대보험",
                            "severity": rate_rule.severity,
                            "field_name": item,
                            "current_value": current,
                            "message": (
                                f"'{emp.employee_name}'의 {label} 공제액({current:,.0f}원)이 "
                                f"신고된 요율({rate_rule.threshold}%) 기준 예상액({expected:,.0f}원)과 "
                                f"{abs(current - expected):,.0f}원 차이가 납니다."
                            ),
                            "rule_code": rate_rule.rule_code,
                        }
                    )
    return findings
