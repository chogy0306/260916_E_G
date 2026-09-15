from collections import defaultdict


def check(employees):
    """employees: list of PayrollEmployee for one upload."""
    by_id = defaultdict(list)
    for emp in employees:
        by_id[emp.employee_id].append(emp)

    findings = []
    for emp_id, group in by_id.items():
        if len(group) > 1:
            for emp in group:
                findings.append(
                    {
                        "employee_pk": emp.id,
                        "category": "중복 직원",
                        "severity": "ERROR",
                        "field_name": "employee_id",
                        "message": f"직원ID '{emp_id}'가 {len(group)}건 중복 발견되었습니다.",
                        "rule_code": "DUPLICATE_EMPLOYEE",
                    }
                )
    return findings
