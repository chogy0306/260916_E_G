from app import db
from app.models.payroll_employee import PayrollEmployee
from app.models.payroll_value import PayrollValue
from app.models.validation_result import ValidationResult
from app.models.validation_rule import ValidationRule
from app.validators import (
    duplicate_validator,
    insurance_validator,
    missing_validator,
    payroll_validator,
)
from app.services import comparison_service, outlier_service

DEFAULT_RULES = [
    ("RATE_BASE_SALARY", "기본급 변동 기준", 10.0, "REVIEW"),
    ("RATE_TOTAL_EARNINGS", "총지급액 변동 기준", 20.0, "WARNING"),
    ("RATE_NET_SALARY", "실지급액 변동 기준", 20.0, "WARNING"),
    ("RATE_OTHER_ITEM", "기타 급여 항목 변동 기준", 30.0, "REVIEW"),
    ("INSURANCE_RATE_NATIONAL_PENSION", "국민연금 요율(%, 기본급 대비)", 4.75, "REVIEW"),
    ("INSURANCE_RATE_HEALTH", "건강보험 요율(%, 기본급 대비)", 3.595, "REVIEW"),
    ("INSURANCE_RATE_LONG_TERM_CARE", "장기요양보험 요율(%, 건강보험료 대비)", 13.14, "REVIEW"),
    ("INSURANCE_RATE_EMPLOYMENT", "고용보험 요율(%, 기본급 대비)", 0.9, "REVIEW"),
]


def ensure_default_rules():
    existing = {r.rule_code for r in ValidationRule.query.all()}
    for code, name, threshold, severity in DEFAULT_RULES:
        if code not in existing:
            db.session.add(
                ValidationRule(
                    rule_code=code,
                    rule_name=name,
                    threshold=threshold,
                    severity=severity,
                    is_active=True,
                )
            )
    db.session.commit()


def _values_by_employee(employees):
    result = {}
    for emp in employees:
        result[emp.id] = {
            v.item_name: float(v.item_value) for v in emp.values if v.item_value is not None
        }
    return result


def _prev_values_by_business_id(previous_employees):
    result = {}
    for emp in previous_employees:
        result[emp.employee_id] = {
            v.item_name: float(v.item_value) for v in emp.values if v.item_value is not None
        }
    return result


def run_validation(upload, previous_upload=None):
    # Delete via the ORM (not a bulk Query.delete()) so the
    # cascade="all, delete-orphan" on ai_analysis/notes actually fires.
    # A bulk delete bypasses cascades, orphans those child rows, and lets
    # SQLite recycle the freed ids for new unrelated results.
    for old_result in ValidationResult.query.filter_by(upload_id=upload.id).all():
        db.session.delete(old_result)
    db.session.commit()

    employees = PayrollEmployee.query.filter_by(upload_id=upload.id).all()
    values_by_employee = _values_by_employee(employees)

    rules_by_code = {r.rule_code: r for r in ValidationRule.query.filter_by(is_active=True).all()}

    findings = []
    findings += duplicate_validator.check(employees)
    findings += missing_validator.check(employees, values_by_employee)
    findings += payroll_validator.check(employees, values_by_employee)
    findings += outlier_service.detect(employees, values_by_employee)

    new_ids, missing_ids = set(), set()
    prev_values = {}
    if previous_upload:
        previous_employees = PayrollEmployee.query.filter_by(upload_id=previous_upload.id).all()
        prev_values = _prev_values_by_business_id(previous_employees)

        emp_findings, new_ids, missing_ids = comparison_service.compare_employees(
            employees, previous_employees
        )
        findings += emp_findings
        findings += comparison_service.compare_values(
            employees, values_by_employee, prev_values, rules_by_code
        )

    # Runs even without a previous upload: the legal-rate check needs only
    # this month's data, unlike INSURANCE_MISSING/INSURANCE_RATE_CHANGE
    # which naturally no-op when prev_values is empty.
    findings += insurance_validator.check(employees, values_by_employee, prev_values, rules_by_code)

    rule_lookup = {r.rule_code: r for r in ValidationRule.query.all()}

    for f in findings:
        rule = rule_lookup.get(f.get("rule_code"))
        result = ValidationResult(
            upload_id=upload.id,
            employee_id=f.get("employee_pk"),
            rule_id=rule.id if rule else None,
            category=f["category"],
            severity=f["severity"],
            field_name=f.get("field_name"),
            previous_value=f.get("previous_value"),
            current_value=f.get("current_value"),
            change_rate=f.get("change_rate"),
            message=f["message"],
            status="NEW",
        )
        db.session.add(result)

    upload.status = "VALIDATED"
    db.session.commit()

    return {
        "total_findings": len(findings),
        "new_employees": len(new_ids),
        "missing_employees": len(missing_ids),
    }


def summarize(upload):
    results = ValidationResult.query.filter_by(upload_id=upload.id).all()
    total_employees = PayrollEmployee.query.filter_by(upload_id=upload.id).count()

    counts = {"ERROR": 0, "WARNING": 0, "REVIEW": 0}
    flagged_employees = set()
    for r in results:
        counts[r.severity] = counts.get(r.severity, 0) + 1
        if r.employee_id:
            flagged_employees.add(r.employee_id)

    normal = max(total_employees - len(flagged_employees), 0)
    return {
        "total_employees": total_employees,
        "normal": normal,
        "error": counts.get("ERROR", 0),
        "warning": counts.get("WARNING", 0),
        "review": counts.get("REVIEW", 0),
    }
