from flask import Blueprint, flash, redirect, request, render_template, send_file, url_for
from flask_login import current_user, login_required

from app import db
from app.models.ai_analysis import AIAnalysis
from app.models.audit_log import log_action
from app.models.payroll_employee import PayrollEmployee
from app.models.payroll_upload import PayrollUpload
from app.models.review_note import ReviewNote
from app.models.validation_result import ValidationResult
from app.routes.auth import admin_required
from app.services import ai_service
from app.services.report_service import build_results_excel

validation_bp = Blueprint("validation", __name__)


@validation_bp.route("/uploads/<int:upload_id>/results")
@login_required
def results(upload_id):
    upload = PayrollUpload.query.get_or_404(upload_id)

    query = ValidationResult.query.filter_by(upload_id=upload.id)

    severity = request.args.get("severity")
    status = request.args.get("status")
    keyword = request.args.get("q")

    if severity:
        query = query.filter(ValidationResult.severity == severity)
    if status:
        query = query.filter(ValidationResult.status == status)
    if keyword:
        query = query.outerjoin(
            PayrollEmployee, ValidationResult.employee_id == PayrollEmployee.id
        ).filter(
            db.or_(
                ValidationResult.message.ilike(f"%{keyword}%"),
                PayrollEmployee.employee_name.ilike(f"%{keyword}%"),
                PayrollEmployee.department.ilike(f"%{keyword}%"),
            )
        )

    severity_order = db.case(
        (ValidationResult.severity == "ERROR", 0),
        (ValidationResult.severity == "WARNING", 1),
        (ValidationResult.severity == "REVIEW", 2),
        else_=9,
    )
    items = query.order_by(severity_order).all()

    return render_template("results.html", upload=upload, items=items, severity=severity, status=status, q=keyword or "")


@validation_bp.route("/validation-results/<int:result_id>")
@login_required
def detail(result_id):
    result = ValidationResult.query.get_or_404(result_id)
    return render_template("detail.html", result=result)


@validation_bp.route("/validation-results/<int:result_id>/status", methods=["POST"])
@login_required
@admin_required
def update_status(result_id):
    result = ValidationResult.query.get_or_404(result_id)
    new_status = request.form.get("status")
    if new_status in {"NEW", "REVIEWING", "CONFIRMED", "FALSE_POSITIVE", "RESOLVED"}:
        before = result.status
        result.status = new_status
        log_action(
            current_user.id,
            "UPDATE_STATUS",
            "ValidationResult",
            result.id,
            before={"status": before},
            after={"status": new_status},
        )
        db.session.commit()
        flash("상태가 변경되었습니다.", "success")
    return redirect(url_for("validation.detail", result_id=result.id))


@validation_bp.route("/validation-results/<int:result_id>/notes", methods=["POST"])
@login_required
@admin_required
def add_note(result_id):
    result = ValidationResult.query.get_or_404(result_id)
    note_text = request.form.get("note", "").strip()
    if note_text:
        db.session.add(ReviewNote(validation_result_id=result.id, user_id=current_user.id, note=note_text))
        db.session.commit()
        flash("메모가 저장되었습니다.", "success")
    return redirect(url_for("validation.detail", result_id=result.id))


@validation_bp.route("/validation-results/<int:result_id>/ai-analysis", methods=["POST"])
@login_required
@admin_required
def ai_analysis(result_id):
    result = ValidationResult.query.get_or_404(result_id)

    payload = {
        "employee_id": result.employee.employee_id if result.employee else None,
        "field_name": result.field_name,
        "previous_value": float(result.previous_value) if result.previous_value is not None else None,
        "current_value": float(result.current_value) if result.current_value is not None else None,
        "change_rate": result.change_rate,
        "detected_rule": result.rule.rule_code if result.rule else result.category,
    }

    analysis = ai_service.analyze(payload)

    if result.ai_analysis:
        db.session.delete(result.ai_analysis)
        db.session.flush()

    db.session.add(
        AIAnalysis(
            validation_result_id=result.id,
            summary=analysis.get("summary"),
            possible_causes=analysis.get("possible_causes"),
            recommended_action=analysis.get("recommended_action"),
            confidence=analysis.get("confidence"),
            model_name=analysis.get("model_name"),
        )
    )
    db.session.commit()
    flash("AI 분석이 완료되었습니다.", "success")
    return redirect(url_for("validation.detail", result_id=result.id))


@validation_bp.route("/uploads/<int:upload_id>/results/download")
@login_required
def download_results(upload_id):
    upload = PayrollUpload.query.get_or_404(upload_id)
    items = ValidationResult.query.filter_by(upload_id=upload.id).all()
    buffer = build_results_excel(items)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"validation_result_{upload.payroll_year}_{upload.payroll_month:02d}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
