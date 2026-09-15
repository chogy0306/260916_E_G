from flask import Flask
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "로그인이 필요합니다."
csrf = CSRFProtect()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        user = User.query.get(int(user_id))
        # A deactivated account must be force-logged-out on its very next
        # request, not just blocked from a future login.
        if user and not user.is_active_user:
            return None
        return user

    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.upload import upload_bp
    from app.routes.validation import validation_bp
    from app.routes.settings import settings_bp
    from app.routes.users import users_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(upload_bp)
    app.register_blueprint(validation_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(users_bp)

    from app.services.validation_service import ensure_default_rules
    from app.routes.auth import ensure_admin_user

    with app.app_context():
        db.create_all()
        ensure_default_rules()
        ensure_admin_user()

    return app
