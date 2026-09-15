from functools import wraps

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.models.user import User

auth_bp = Blueprint("auth", __name__)


def ensure_admin_user():
    username = current_app.config["ADMIN_USERNAME"]
    if User.query.filter_by(username=username).first():
        return
    user = User(username=username, role="admin", is_active_user=True)
    user.set_password(current_app.config["ADMIN_PASSWORD"])
    db.session.add(user)
    db.session.commit()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash("관리자 권한이 필요합니다.", "error")
            return redirect(url_for("dashboard.index"))
        return view(*args, **kwargs)

    return wrapped


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if not user.is_active_user:
                return render_template("login.html", error="비활성화된 계정입니다. 관리자에게 문의하세요.")
            login_user(user)
            return redirect(url_for("dashboard.index"))
        return render_template("login.html", error="아이디 또는 비밀번호가 올바르지 않습니다.")
    return render_template("login.html")


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
