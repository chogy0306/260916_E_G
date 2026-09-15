from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app import db
from app.models.validation_rule import ValidationRule
from app.routes.auth import admin_required

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/rules")
@login_required
@admin_required
def rules():
    items = ValidationRule.query.order_by(ValidationRule.rule_code).all()
    return render_template("settings.html", rules=items)


@settings_bp.route("/rules/<int:rule_id>", methods=["POST"])
@login_required
@admin_required
def update_rule(rule_id):
    rule = ValidationRule.query.get_or_404(rule_id)
    threshold = request.form.get("threshold", type=float)
    severity = request.form.get("severity")
    is_active = request.form.get("is_active") == "on"

    if threshold is not None:
        rule.threshold = threshold
    if severity in {"ERROR", "WARNING", "REVIEW"}:
        rule.severity = severity
    rule.is_active = is_active

    db.session.commit()
    flash(f"'{rule.rule_name}' 기준이 저장되었습니다.", "success")
    return redirect(url_for("settings.rules"))
