from datetime import datetime

from app import db


class PayrollValue(db.Model):
    """EAV-style storage: one row per (employee, item). Keeps the schema
    flexible since payroll item names differ across companies."""

    __tablename__ = "payroll_values"

    id = db.Column(db.Integer, primary_key=True)
    upload_id = db.Column(db.Integer, db.ForeignKey("payroll_uploads.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("payroll_employees.id"), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    item_value = db.Column(db.Numeric(18, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index("ix_payroll_values_upload_item", "upload_id", "item_name"),
    )
