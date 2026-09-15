from app.services.mapping_service import field_label

NEGATIVE_NOT_ALLOWED = {"base_salary", "total_earnings", "net_salary"}


def check(employees, values_by_employee):
    findings = []
    for emp in employees:
        if not emp.employee_name:
            findings.append(
                {
                    "employee_pk": emp.id,
                    "category": "필수값 누락",
                    "severity": "ERROR",
                    "field_name": "employee_name",
                    "message": f"직원ID '{emp.employee_id}'의 직원명이 비어 있습니다.",
                    "rule_code": "MISSING_REQUIRED",
                }
            )

        items = values_by_employee.get(emp.id, {})
        if "base_salary" not in items or items.get("base_salary") is None:
            findings.append(
                {
                    "employee_pk": emp.id,
                    "category": "필수값 누락",
                    "severity": "WARNING",
                    "field_name": "base_salary",
                    "message": f"'{emp.employee_name}'의 기본급 데이터가 없습니다.",
                    "rule_code": "MISSING_BASE_SALARY",
                }
            )

        for field in NEGATIVE_NOT_ALLOWED:
            value = items.get(field)
            if value is not None and value < 0:
                findings.append(
                    {
                        "employee_pk": emp.id,
                        "category": "비정상 데이터",
                        "severity": "ERROR",
                        "field_name": field,
                        "current_value": value,
                        "message": f"'{emp.employee_name}'의 {field_label(field)} 값이 음수({value:,.0f})입니다.",
                        "rule_code": "NEGATIVE_AMOUNT",
                    }
                )
    return findings
