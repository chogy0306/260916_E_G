from datetime import datetime

from app import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(50))
    target_id = db.Column(db.Integer)
    before_data = db.Column(db.JSON)
    after_data = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def log_action(user_id, action, target_type=None, target_id=None, before=None, after=None):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before_data=before,
        after_data=after,
    )
    db.session.add(entry)
