from app.services.mapping_service import INSURANCE_ITEMS, field_label

RATE_RULE_FOR_FIELD = {
    "base_salary": "RATE_BASE_SALARY",
    "total_earnings": "RATE_TOTAL_EARNINGS",
    "net_salary": "RATE_NET_SALARY",
}


def _rule_for_field(field, rules_by_code):
    code = RATE_RULE_FOR_FIELD.get(field, "RATE_OTHER_ITEM")
    return rules_by_code.get(code)


def compare_employees(current_employees, previous_employees):
    current_ids = {e.employee_id for e in current_employees}
    previous_ids = {e.employee_id for e in previous_employees}

    new_ids = current_ids - previous_ids
    missing_ids = previous_ids - current_ids

    findings = []
    for emp in current_employees:
        if emp.employee_id in new_ids:
            findings.append(
                {
                    "employee_pk": emp.id,
                    "category": "신규 직원",
                    "severity": "REVIEW",
                    "field_name": None,
                    "message": f"'{emp.employee_name}'({emp.employee_id})은(는) 이번 달에 새로 나타난 직원입니다.",
                    "rule_code": "NEW_EMPLOYEE",
                }
            )

    for emp in previous_employees:
        if emp.employee_id in missing_ids:
            findings.append(
                {
                    "employee_pk": None,
                    "category": "직원 누락",
                    "severity": "REVIEW",
                    "field_name": None,
                    "message": (
                        f"'{emp.employee_name}'({emp.employee_id})은(는) 전월 급여대장에는 "
                        f"있었으나 이번 달 급여대장에서는 확인되지 않습니다. 퇴사/휴직 여부를 확인하세요."
                    ),
                    "rule_code": "MISSING_EMPLOYEE",
                }
            )
    return findings, new_ids, missing_ids


def compare_values(
    current_employees, values_by_employee, prev_values_by_employee_id, rules_by_code
):
    findings = []
    for emp in current_employees:
        current_items = values_by_employee.get(emp.id, {})
        prev_items = prev_values_by_employee_id.get(emp.employee_id)
        if prev_items is None:
            continue

        all_items = set(current_items) | set(prev_items)
        for item in all_items:
            if item in INSURANCE_ITEMS:
                continue  # handled by insurance_validator

            current = current_items.get(item)
            previous = prev_items.get(item)

            if current is not None and previous is not None and previous not in (0, None):
                rate = (current - previous) / previous * 100
                rule = _rule_for_field(item, rules_by_code)
                threshold = rule.threshold if rule else 30.0
                severity = rule.severity if rule else "REVIEW"
                if abs(rate) > threshold:
                    findings.append(
                        {
                            "employee_pk": emp.id,
                            "category": "급여 변동",
                            "severity": severity,
                            "field_name": item,
                            "previous_value": previous,
                            "current_value": current,
                            "change_rate": rate,
                            "message": (
                                f"'{emp.employee_name}'의 {field_label(item)}이(가) 전월 대비 "
                                f"{rate:+.1f}% 변동했습니다 ({previous:,.0f} → {current:,.0f})."
                            ),
                            "rule_code": rule.rule_code if rule else "RATE_OTHER_ITEM",
                        }
                    )
            elif current and (previous is None or previous == 0):
                findings.append(
                    {
                        "employee_pk": emp.id,
                        "category": "신규 항목",
                        "severity": "REVIEW",
                        "field_name": item,
                        "current_value": current,
                        "message": f"'{emp.employee_name}'에게 이번 달 새로 발생한 항목 '{field_label(item)}'({current:,.0f}원)이 있습니다.",
                        "rule_code": "NEW_ITEM",
                    }
                )
            elif current is None and previous:
                findings.append(
                    {
                        "employee_pk": emp.id,
                        "category": "항목 소멸",
                        "severity": "REVIEW",
                        "field_name": item,
                        "previous_value": previous,
                        "message": f"'{emp.employee_name}'의 전월 항목 '{field_label(item)}'({previous:,.0f}원)이 이번 달에는 없습니다.",
                        "rule_code": "ITEM_DISAPPEARED",
                    }
                )
    return findings
