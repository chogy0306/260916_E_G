from datetime import datetime

from app import db


class PayrollUpload(db.Model):
    __tablename__ = "payroll_uploads"

    id = db.Column(db.Integer, primary_key=True)
    file_name = db.Column(db.String(255), nullable=False)
    file_data = db.Column(db.LargeBinary, nullable=False)
    payroll_year = db.Column(db.Integer, nullable=False)
    payroll_month = db.Column(db.Integer, nullable=False)
    file_hash = db.Column(db.String(64))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="UPLOADED")
    # UPLOADED -> MAPPED -> VALIDATED

    employees = db.relationship(
        "PayrollEmployee", backref="upload", lazy=True, cascade="all, delete-orphan"
    )
    values = db.relationship(
        "PayrollValue", backref="upload", lazy=True, cascade="all, delete-orphan"
    )
    results = db.relationship(
        "ValidationResult", backref="upload", lazy=True, cascade="all, delete-orphan"
    )

    __table_args__ = (
        db.UniqueConstraint("payroll_year", "payroll_month", name="uq_upload_year_month"),
    )

    @property
    def period_label(self):
        return f"{self.payroll_year}년 {self.payroll_month:02d}월"
