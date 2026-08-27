"""환경설정 — 모든 값은 환경변수(.env)에서만 읽는다. 시크릿은 커밋 금지."""
import os


def _req(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        raise RuntimeError(f"환경변수 {name} 이(가) 설정되지 않았습니다 (.env 확인)")
    return v


DB_USER = os.environ.get("DB_USER", "speechapp_admin")
DB_HOST = os.environ.get("DB_HOST", "sesac-oracle-db")
DB_PORT = os.environ.get("DB_PORT", "1521")
DB_SERVICE = os.environ.get("DB_SERVICE", "XEPDB1")
DB_PASSWORD = _req("DB_PASSWORD")

ADMIN_PAGE_PASSWORD = _req("ADMIN_PAGE_PASSWORD")
SESSION_SECRET = _req("SESSION_SECRET")

DSN = f"{DB_HOST}:{DB_PORT}/{DB_SERVICE}"
# 관리 대상 스키마 접두어
OWNER_PREFIX = "SPEECHAPP"

SESSION_COOKIE = "sesac_admin_session"
SESSION_MAX_AGE = 60 * 60 * 12  # 12시간