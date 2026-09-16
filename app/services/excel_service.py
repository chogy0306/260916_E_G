import hashlib
import re
from io import BytesIO

import pandas as pd
from werkzeug.utils import secure_filename

from app import db
from app.models.payroll_employee import PayrollEmployee
from app.models.payroll_value import PayrollValue
from app.services.mapping_service import IDENTITY_FIELDS, field_label


class ExcelValidationError(Exception):
    pass


def allowed_file(filename, allowed_extensions):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def read_upload(file_storage):
    """Validates and reads the uploaded file into memory. Nothing is written
    to local disk: on a serverless deployment the filesystem isn't shared or
    persistent between requests, so the file bytes are kept in the database
    instead (see PayrollUpload.file_data)."""
    filename = secure_filename(file_storage.filename)
    if not filename:
        raise ExcelValidationError("올바르지 않은 파일명입니다.")

    file_bytes = file_storage.read()
    if not file_bytes:
        raise ExcelValidationError("빈 파일은 업로드할 수 없습니다.")

    return filename, file_bytes


def file_hash(file_bytes):
    return hashlib.sha256(file_bytes).hexdigest()


def read_preview(file_bytes, n_rows=5):
    try:
        df = pd.read_excel(BytesIO(file_bytes), dtype=object)
    except Exception as exc:
        raise ExcelValidationError(f"Excel 파일을 읽을 수 없습니다: {exc}")

    if df.empty or len(df.columns) == 0:
        raise ExcelValidationError("Excel에 데이터가 없습니다.")

    columns = [str(c).strip() for c in df.columns]
    preview_rows = df.head(n_rows).fillna("").values.tolist()
    return columns, preview_rows, len(df)


def _to_number(value):
    """Returns (number_or_None, is_format_error). is_format_error is True only
    when the cell had non-blank content that couldn't be read as a number -
    a blank cell is just missing data, not a format error."""
    if value is None or value == "":
        return None, False
    if isinstance(value, (int, float)):
        return float(value), False
    text = str(value).strip()
    text = re.sub(r"[,\s원₩]", "", text)
    if text in ("", "-"):
        return None, False
    try:
        return float(text), False
    except ValueError:
        return None, True


def parse_and_store(upload, mapping):
    """mapping: {excel_column: system_field_name_or_custom_label_or_None}."""
    df = pd.read_excel(BytesIO(upload.file_data), dtype=object)
    df.columns = [str(c).strip() for c in df.columns]

    errors = []
    format_errors = []
    created_employees = 0

    for idx, row in df.iterrows():
        row_no = idx + 2  # header is row 1

        identity = {"employee_id": None, "employee_name": None, "department": None, "position": None}
        items = {}

        for col, field in mapping.items():
            if not field or col not in df.columns:
                continue
            raw = row.get(col)
            if field in IDENTITY_FIELDS:
                value = "" if raw is None else str(raw).strip()
                identity[field] = value or None
            else:
                value, is_format_error = _to_number(raw)
                items[field] = value
                if is_format_error:
                    format_errors.append(
                        f"{row_no}행: {field_label(field)} 값 '{raw}'을 숫자로 인식할 수 없어 빈 값으로 처리했습니다."
                    )

        if not identity["employee_id"] or not identity["employee_name"]:
            errors.append(f"{row_no}행: 직원ID 또는 직원명이 비어 있습니다.")
            continue

        employee = PayrollEmployee(
            upload_id=upload.id,
            employee_id=identity["employee_id"],
            employee_name=identity["employee_name"],
            department=identity["department"],
            position=identity["position"],
        )
        db.session.add(employee)
        db.session.flush()
        created_employees += 1

        for item_name, value in items.items():
            db.session.add(
                PayrollValue(
                    upload_id=upload.id,
                    employee_id=employee.id,
                    item_name=item_name,
                    item_value=value,
                )
            )

    db.session.commit()
    return created_employees, errors, format_errors
