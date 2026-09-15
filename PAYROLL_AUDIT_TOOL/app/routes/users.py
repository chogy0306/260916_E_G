from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models.user import User
from app.routes.auth import admin_required

users_bp = Blueprint("users", __name__, url_prefix="/settings/users")


@users_bp.route("/")
@login_required
@admin_required
def index():
    all_users = User.query.order_by(User.created_at).all()
    return render_template("users.html", users=all_users)


@users_bp.route("/", methods=["POST"])
@login_required
@admin_required
def create():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "viewer")

    if role not in {"admin", "viewer"}:
        role = "viewer"

    if not username or not password:
        flash("아이디와 비밀번호를 입력해주세요.", "error")
    elif User.query.filter_by(username=username).first():
        flash("이미 사용 중인 아이디입니다.", "error")
    else:
        user = User(username=username, role=role, is_active_user=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f"'{username}' 계정을 생성했습니다.", "success")

    return redirect(url_for("users.index"))


def _active_admin_count():
    return User.query.filter_by(role="admin", is_active_user=True).count()


@users_bp.route("/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_active(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash("본인 계정은 여기서 비활성화할 수 없습니다.", "error")
        return redirect(url_for("users.index"))

    if user.is_active_user and user.is_admin() and _active_admin_count() <= 1:
        flash("마지막 남은 관리자 계정은 비활성화할 수 없습니다.", "error")
        return redirect(url_for("users.index"))

    user.is_active_user = not user.is_active_user
    db.session.commit()
    flash(f"'{user.username}' 계정을 {'활성화' if user.is_active_user else '비활성화'}했습니다.", "success")
    return redirect(url_for("users.index"))


@users_bp.route("/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def change_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get("role")

    if new_role not in {"admin", "viewer"}:
        return redirect(url_for("users.index"))

    if user.id == current_user.id and new_role != "admin":
        flash("본인 권한은 여기서 낮출 수 없습니다.", "error")
        return redirect(url_for("users.index"))

    if user.is_admin() and new_role == "viewer" and _active_admin_count() <= 1:
        flash("마지막 남은 관리자 계정의 권한은 낮출 수 없습니다.", "error")
        return redirect(url_for("users.index"))

    user.role = new_role
    db.session.commit()
    flash(f"'{user.username}'의 권한을 변경했습니다.", "success")
    return redirect(url_for("users.index"))
