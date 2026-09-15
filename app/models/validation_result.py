from datetime import datetime

from app import db


class ValidationResult(db.Model):
    __tablename__ = "validation_results"

    id = db.Column(db.Integer, primary_key=True)
    upload_id = db.Column(db.Integer, db.ForeignKey("payroll_uploads.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("payroll_employees.id"), nullable=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("validation_rules.id"), nullable=True)

    category = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(20), nullable=False)
    # ERROR | WARNING | REVIEW
    field_name = db.Column(db.String(100))
    previous_value = db.Column(db.Numeric(18, 2))
    current_value = db.Column(db.Numeric(18, 2))
    change_rate = db.Column(db.Float)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="NEW")
    # NEW -> REVIEWING -> CONFIRMED | FALSE_POSITIVE -> RESOLVED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship("PayrollEmployee")
    rule = db.relationship("ValidationRule")
    ai_analysis = db.relationship(
        "AIAnalysis", backref="result", uselist=False, cascade="all, delete-orphan"
    )
    notes = db.relationship(
        "ReviewNote", backref="result", lazy=True, cascade="all, delete-orphan"
    )
