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

SEVERITY_RANK = {"ERROR": 0, "WARNING": 1, "REVIEW": 2, "NORMAL": 3}


def _group_by_employee(items, normal_employees):
    """Groups findings by business employee_id so duplicate PayrollEmployee
    rows (e.g. a flagged duplicate-employee-id case) merge into one group."""
    groups_by_key = {}
    unassigned = []

    for r in items:
        if not r.employee:
            unassigned.append(r)
            continue
        key = r.employee.employee_id
        group = groups_by_key.setdefault(
            key,
            {
                "employee_id": r.employee.employee_id,
                "employee_name": r.employee.employee_name,
                "department": r.employee.department,
                "results": [],
                "rank": SEVERITY_RANK["NORMAL"],
            },
        )
        group["results"].append(r)
        group["rank"] = min(group["rank"], SEVERITY_RANK.get(r.severity, 9))

    for e in normal_employees:
        groups_by_key.setdefault(
            e.employee_id,
            {
                "employee_id": e.employee_id,
                "employee_name": e.employee_name,
                "department": e.department,
                "results": [],
                "rank": SEVERITY_RANK["NORMAL"],
            },
        )

    groups = sorted(groups_by_key.values(), key=lambda g: (g["rank"], g["employee_name"] or ""))
    return groups, unassigned


@validation_bp.route("/uploads/<int:upload_id>/results")
@login_required
def results(upload_id):
    upload = PayrollUpload.query.get_or_404(upload_id)

    query = ValidationResult.query.filter_by(upload_id=upload.id)

    severity = request.args.get("severity")
    status = request.args.get("status")
    keyword = request.args.get("q")

    if severity and severity != "NORMAL":
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
    # "정상" isn't stored as a row per employee (that would bloat the table for
    # zero information); it's derived here as employees with no findings at all.
    items = [] if severity == "NORMAL" else query.order_by(severity_order).all()

    normal_employees = []
    if not status and severity in (None, "", "NORMAL"):
        flagged_ids = {
            r.employee_id
            for r in ValidationResult.query.filter_by(upload_id=upload.id).all()
            if r.employee_id
        }
        normal_query = PayrollEmployee.query.filter_by(upload_id=upload.id)
        if flagged_ids:
            normal_query = normal_query.filter(~PayrollEmployee.id.in_(flagged_ids))
        normal_employees = normal_query.order_by(PayrollEmployee.employee_name).all()

        if keyword:
            kw = keyword.lower()
            normal_employees = [
                e
                for e in normal_employees
                if kw in (e.employee_name or "").lower() or kw in (e.department or "").lower()
            ]

    groups, unassigned = _group_by_employee(items, normal_employees)

    return render_template(
        "results.html",
        upload=upload,
        groups=groups,
        unassigned=unassigned,
        severity=severity,
        status=status,
        q=keyword or "",
    )


@validation_bp.route("/validation-results/<int:result_id>")
@login_required
def detail(result_id):
    result = ValidationResult.query.get_or_404(result_id)

    employee_results = []
    position = None
    prev_employee_group = None
    next_employee_group = None

    if result.employee:
        upload_results = ValidationResult.query.filter_by(upload_id=result.upload_id).all()
        groups, _ = _group_by_employee(upload_results, [])
        group_index = next(
            (i for i, g in enumerate(groups) if any(r.id == result.id for r in g["results"])),
            None,
        )
        if group_index is not None:
            employee_results = groups[group_index]["results"]
            position = next(i for i, r in enumerate(employee_results) if r.id == result.id)
            if group_index > 0 and groups[group_index - 1]["results"]:
                prev_employee_group = groups[group_index - 1]
            if group_index + 1 < len(groups) and groups[group_index + 1]["results"]:
                next_employee_group = groups[group_index + 1]

    return render_template(
        "detail.html",
        result=result,
        employee_results=employee_results,
        position=position,
        prev_employee_group=prev_employee_group,
        next_employee_group=next_employee_group,
    )


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

    flagged_ids = {r.employee_id for r in items if r.employee_id}
    normal_query = PayrollEmployee.query.filter_by(upload_id=upload.id)
    if flagged_ids:
        normal_query = normal_query.filter(~PayrollEmployee.id.in_(flagged_ids))
    normal_employees = normal_query.order_by(PayrollEmployee.employee_name).all()

    groups, unassigned = _group_by_employee(items, normal_employees)
    buffer = build_results_excel(groups, unassigned)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"급여대장_검증결과_{upload.payroll_year}년_{upload.payroll_month:02d}월.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
