from datetime import datetime

from app import db


class PayrollEmployee(db.Model):
    __tablename__ = "payroll_employees"

    id = db.Column(db.Integer, primary_key=True)
    upload_id = db.Column(db.Integer, db.ForeignKey("payroll_uploads.id"), nullable=False)
    employee_id = db.Column(db.String(50), nullable=False)
    employee_name = db.Column(db.String(100))
    department = db.Column(db.String(100))
    position = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    values = db.relationship(
        "PayrollValue", backref="employee", lazy=True, cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.Index("ix_payroll_employees_upload_emp", "upload_id", "employee_id"),
    )
