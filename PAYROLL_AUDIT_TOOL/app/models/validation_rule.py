from datetime import datetime

from app import db


class ValidationRule(db.Model):
    __tablename__ = "validation_rules"

    id = db.Column(db.Integer, primary_key=True)
    rule_code = db.Column(db.String(50), unique=True, nullable=False)
    rule_name = db.Column(db.String(200), nullable=False)
    threshold = db.Column(db.Float)
    severity = db.Column(db.String(20), nullable=False, default="REVIEW")
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
