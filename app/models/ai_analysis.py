from datetime import datetime

from app import db


class AIAnalysis(db.Model):
    __tablename__ = "ai_analysis"

    id = db.Column(db.Integer, primary_key=True)
    validation_result_id = db.Column(
        db.Integer, db.ForeignKey("validation_results.id"), nullable=False
    )
    summary = db.Column(db.Text)
    possible_causes = db.Column(db.JSON)
    recommended_action = db.Column(db.Text)
    confidence = db.Column(db.Float)
    model_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
