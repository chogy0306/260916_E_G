from datetime import datetime

from app import db


class ReviewNote(db.Model):
    __tablename__ = "review_notes"

    id = db.Column(db.Integer, primary_key=True)
    validation_result_id = db.Column(
        db.Integer, db.ForeignKey("validation_results.id"), nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")
