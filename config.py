import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(basedir, "payroll_audit.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 20 * 1024 * 1024  # 20MB
    ALLOWED_EXTENSIONS = {"xlsx", "xls"}

    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin1234")

    AI_PROVIDER = os.environ.get("AI_PROVIDER", "openai")
    AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")
    AI_API_KEY = os.environ.get("AI_API_KEY", "")

    # Default validation thresholds (percent), overridable via ValidationRule rows
    DEFAULT_THRESHOLDS = {
        "base_salary": 10,
        "total_earnings": 20,
        "net_salary": 20,
        "allowance": 30,
    }
