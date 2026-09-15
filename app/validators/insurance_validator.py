from app.services.mapping_service import INSURANCE_ITEMS, field_label

RATE_THRESHOLD = 20.0


def check(employees, values_by_employee, prev_values_by_employee_id):
    """prev_values_by_employee_id: {employee_id(business key): {item: value}}"""
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
    return findings
