import os

basedir = os.path.abspath(os.path.dirname(__file__))


def _resolve_database_uri():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url
    if os.environ.get("VERCEL"):
        # Vercel's serverless filesystem is read-only outside /tmp, so the
        # sqlite fallback silently breaks every request in production while
        # still looking fine locally. Fail loudly instead of falling back.
        raise RuntimeError(
            "DATABASE_URL 환경변수가 설정되지 않았습니다. "
            "Vercel 프로젝트 Settings > Environment Variables 에서 DATABASE_URL을 "
            "추가한 뒤 다시 배포하세요 (SQLite는 Vercel의 읽기 전용 파일시스템에서 동작하지 않습니다)."
        )
    return "sqlite:///" + os.path.join(basedir, "payroll_audit.db")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = _resolve_database_uri()
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
