"""세션 기반 로그인. itsdangerous 서명 쿠키 하나로 끝."""
import hmac
from datetime import datetime, timedelta, timezone

from itsdangerous import BadSignature, SignatureExpired, TimestampSigner

from . import config


def _signer() -> TimestampSigner:
    return TimestampSigner(config.SESSION_SECRET, salt="sesac-admin")


def make_session_token() -> str:
    now = datetime.now(timezone.utc).isoformat()
    return _signer().sign(now.encode()).decode()


def verify_session_token(token: str) -> bool:
    try:
        _signer().unsign(token.encode(), max_age=config.SESSION_MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False


def check_password(submitted: str) -> bool:
    return hmac.compare_digest(submitted, config.ADMIN_PAGE_PASSWORD)