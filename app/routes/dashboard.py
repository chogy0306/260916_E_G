from flask import Blueprint, redirect, render_template, url_for
from flask_login import login_required

from app.models.payroll_employee import PayrollEmployee
from app.models.payroll_upload import PayrollUpload
from app.models.validation_result import ValidationResult
from app.services.validation_service import summarize

dashboard_bp = Blueprint("dashboard", __name__)


def _employee_count_change(latest, uploads):
    """Compares the latest upload's employee roster to the one immediately
    before it chronologically (not necessarily the one picked for
    rate-of-change comparison), so this still shows up even for an upload
    that was validated without a previous-month comparison."""
    later_uploads = [u for u in uploads if (u.payroll_year, u.payroll_month) < (latest.payroll_year, latest.payroll_month)]
    if not later_uploads:
        return None
    previous = max(later_uploads, key=lambda u: (u.payroll_year, u.payroll_month))

    current_ids = {e.employee_id for e in PayrollEmployee.query.filter_by(upload_id=latest.id).all()}
    previous_ids = {e.employee_id for e in PayrollEmployee.query.filter_by(upload_id=previous.id).all()}
    if not previous_ids:
        return None

    new_count = len(current_ids - previous_ids)
    missing_count = len(previous_ids - current_ids)
    return {
        "previous_label": previous.period_label,
        "delta": len(current_ids) - len(previous_ids),
        "new_count": new_count,
        "missing_count": missing_count,
    }


@dashboard_bp.route("/")
@login_required
def index():
    uploads = PayrollUpload.query.order_by(
        PayrollUpload.payroll_year.desc(), PayrollUpload.payroll_month.desc()
    ).all()

    if not uploads:
        return render_template("dashboard.html", has_data=False)

    latest = uploads[0]
    summary = summarize(latest) if latest.status == "VALIDATED" else None
    employee_change = _employee_count_change(latest, uploads) if summary else None

    top_errors = []
    if summary:
        top_errors = (
            ValidationResult.query.filter_by(upload_id=latest.id)
            .order_by(
                ValidationResult.severity.asc(),  # ERROR < REVIEW < WARNING alphabetically; reorder below
            )
            .all()
        )
        severity_order = {"ERROR": 0, "WARNING": 1, "REVIEW": 2}
        top_errors = sorted(top_errors, key=lambda r: severity_order.get(r.severity, 9))

    return render_template(
        "dashboard.html",
        has_data=True,
        latest=latest,
        uploads=uploads,
        summary=summary,
        top_errors=top_errors,
        employee_change=employee_change,
    )
