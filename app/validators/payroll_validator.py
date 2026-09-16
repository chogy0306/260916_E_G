from app.services.mapping_service import DEDUCTION_ITEMS, EARNING_ITEMS, field_label

TOLERANCE = 1.0  # allow up to 1 won rounding difference

# Absolute Won-amount ceilings, independent of any month-over-month or
# peer comparison - catches a value that's simply unreasonable on its own
# (e.g. a uniform data-entry mistake on the very first upload, before there's
# any previous month or outlier baseline to compare against).
ABS_MAX_RULE_FOR_FIELD = {
    "total_earnings": "ABS_MAX_TOTAL_EARNINGS",
    "net_salary": "ABS_MAX_NET_SALARY",
}


def check(employees, values_by_employee, rules_by_code=None):
    rules_by_code = rules_by_code or {}
    findings = []
    for emp in employees:
        items = values_by_employee.get(emp.id, {})

        total_earnings = items.get("total_earnings")
        total_deductions = items.get("total_deductions")
        net_salary = items.get("net_salary")

        earning_components = [items[k] for k in EARNING_ITEMS if items.get(k) is not None]
        deduction_components = [items[k] for k in DEDUCTION_ITEMS if items.get(k) is not None]

        if total_earnings is not None and earning_components:
            expected = sum(earning_components)
            diff = total_earnings - expected
            if abs(diff) > TOLERANCE:
                findings.append(
                    {
                        "employee_pk": emp.id,
                        "category": "합계 불일치",
                        "severity": "ERROR",
                        "field_name": "total_earnings",
                        "current_value": total_earnings,
                        "message": (
                            f"'{emp.employee_name}'의 총지급액({total_earnings:,.0f})이 "
                            f"지급 항목 합계({expected:,.0f})와 일치하지 않습니다. "
                            f"차이: {diff:,.0f}원"
                        ),
                        "rule_code": "SUM_MISMATCH_EARNINGS",
                    }
                )

        if total_deductions is not None and deduction_components:
            expected = sum(deduction_components)
            diff = total_deductions - expected
            if abs(diff) > TOLERANCE:
                findings.append(
                    {
                        "employee_pk": emp.id,
                        "category": "합계 불일치",
                        "severity": "ERROR",
                        "field_name": "total_deductions",
                        "current_value": total_deductions,
                        "message": (
                            f"'{emp.employee_name}'의 공제총액({total_deductions:,.0f})이 "
                            f"공제 항목 합계({expected:,.0f})와 일치하지 않습니다. "
                            f"차이: {diff:,.0f}원"
                        ),
                        "rule_code": "SUM_MISMATCH_DEDUCTIONS",
                    }
                )

        if total_earnings is not None and total_deductions is not None and net_salary is not None:
            expected_net = total_earnings - total_deductions
            diff = net_salary - expected_net
            if abs(diff) > TOLERANCE:
                findings.append(
                    {
                        "employee_pk": emp.id,
                        "category": "합계 불일치",
                        "severity": "ERROR",
                        "field_name": "net_salary",
                        "current_value": net_salary,
                        "message": (
                            f"'{emp.employee_name}'의 실지급액 계산이 맞지 않습니다. "
                            f"예상 실지급액: {expected_net:,.0f}원, "
                            f"실제: {net_salary:,.0f}원, 차이: {diff:,.0f}원"
                        ),
                        "rule_code": "SUM_MISMATCH_NET",
                    }
                )

        for field, rule_code in ABS_MAX_RULE_FOR_FIELD.items():
            value = items.get(field)
            rule = rules_by_code.get(rule_code)
            if rule and rule.is_active and value is not None and value > rule.threshold:
                findings.append(
                    {
                        "employee_pk": emp.id,
                        "category": "절대금액 초과",
                        "severity": rule.severity,
                        "field_name": field,
                        "current_value": value,
                        "message": (
                            f"'{emp.employee_name}'의 {field_label(field)}({value:,.0f}원)이 "
                            f"상한 기준({rule.threshold:,.0f}원)을 초과했습니다."
                        ),
                        "rule_code": rule_code,
                    }
                )
    return findings
