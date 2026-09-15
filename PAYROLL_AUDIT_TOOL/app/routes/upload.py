from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models.audit_log import log_action
from app.models.payroll_upload import PayrollUpload
from app.routes.auth import admin_required
from app.services.excel_service import (
    ExcelValidationError,
    allowed_file,
    file_hash,
    parse_and_store,
    read_preview,
    read_upload,
)
from app.services.mapping_service import FIELD_LABELS, suggest_mapping
from app.services.validation_service import run_validation
from app.validators import schema_validator

upload_bp = Blueprint("upload", __name__, url_prefix="/upload")


@upload_bp.route("/", methods=["GET", "POST"])
@login_required
@admin_required
def new_upload():
    if request.method == "POST":
        file = request.files.get("file")
        year = request.form.get("payroll_year", type=int)
        month = request.form.get("payroll_month", type=int)

        if not file or file.filename == "":
            flash("파일을 선택해주세요.", "error")
            return redirect(url_for("upload.new_upload"))
        if not year or not month:
            flash("급여 귀속 연/월을 입력해주세요.", "error")
            return redirect(url_for("upload.new_upload"))
        if not allowed_file(file.filename, current_app.config["ALLOWED_EXTENSIONS"]):
            flash("xlsx 또는 xls 파일만 업로드할 수 있습니다.", "error")
            return redirect(url_for("upload.new_upload"))

        try:
            filename, file_bytes = read_upload(file)
            columns, preview_rows, row_count = read_preview(file_bytes)
        except ExcelValidationError as exc:
            flash(str(exc), "error")
            return redirect(url_for("upload.new_upload"))

        existing = PayrollUpload.query.filter_by(payroll_year=year, payroll_month=month).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()

        upload = PayrollUpload(
            file_name=filename,
            file_data=file_bytes,
            payroll_year=year,
            payroll_month=month,
            file_hash=file_hash(file_bytes),
            uploaded_by=current_user.id,
            status="UPLOADED",
        )
        db.session.add(upload)
        db.session.commit()
        log_action(current_user.id, "UPLOAD_FILE", "PayrollUpload", upload.id)
        db.session.commit()

        return redirect(url_for("upload.mapping", upload_id=upload.id))

    return render_template("upload.html")


@upload_bp.route("/<int:upload_id>/mapping", methods=["GET", "POST"])
@login_required
@admin_required
def mapping(upload_id):
    upload = PayrollUpload.query.get_or_404(upload_id)
    columns, preview_rows, row_count = read_preview(upload.file_data)

    if request.method == "POST":
        selected_mapping = {}
        for col in columns:
            field = request.form.get(f"map__{col}", "").strip()
            selected_mapping[col] = field or None

        try:
            schema_validator.check(selected_mapping)
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template(
                "mapping.html",
                upload=upload,
                columns=columns,
                preview_rows=preview_rows,
                suggested=selected_mapping,
                field_labels=FIELD_LABELS,
            )

        upload.status = "MAPPED"
        db.session.commit()

        created, errors = parse_and_store(upload, selected_mapping)
        for err in errors:
            flash(err, "error")
        flash(f"{created}명의 직원 데이터를 저장했습니다.", "success")

        return redirect(url_for("upload.select_previous", upload_id=upload.id))

    suggested = suggest_mapping(columns)
    return render_template(
        "mapping.html",
        upload=upload,
        columns=columns,
        preview_rows=preview_rows,
        suggested=suggested,
        field_labels=FIELD_LABELS,
    )


@upload_bp.route("/<int:upload_id>/validate", methods=["GET", "POST"])
@login_required
@admin_required
def select_previous(upload_id):
    upload = PayrollUpload.query.get_or_404(upload_id)
    other_uploads = (
        PayrollUpload.query.filter(PayrollUpload.id != upload.id)
        .filter(PayrollUpload.status == "VALIDATED")
        .order_by(PayrollUpload.payroll_year.desc(), PayrollUpload.payroll_month.desc())
        .all()
    )

    if request.method == "POST":
        previous_id = request.form.get("previous_upload_id", type=int)
        previous_upload = PayrollUpload.query.get(previous_id) if previous_id else None

        run_validation(upload, previous_upload)
        log_action(current_user.id, "RUN_VALIDATION", "PayrollUpload", upload.id)
        db.session.commit()

        flash("검증이 완료되었습니다.", "success")
        return redirect(url_for("validation.results", upload_id=upload.id))

    return render_template("select_previous.html", upload=upload, other_uploads=other_uploads)
