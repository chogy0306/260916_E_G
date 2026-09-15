from flask import Blueprint, redirect, render_template, url_for
from flask_login import login_required

from app.models.payroll_upload import PayrollUpload
from app.models.validation_result import ValidationResult
from app.services.validation_service import summarize

dashboard_bp = Blueprint("dashboard", __name__)


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
    )
