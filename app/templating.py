""" Jinja2 필터/전역 헬퍼 등록. main.py 보다 먼저 import 되어야 함."""
from jinja2 import pass_context
from markupsafe import Markup
from urllib.parse import urlencode as _urlencode


@pass_context
def querystring(ctx, params: dict) -> str:
    """딕셔너리 → 쿼리스트링 (빈 값 제외)."""
    return _urlencode({k: v for k, v in params.items() if v not in (None, "")})


def register_filters(env):
    env.filters["querystring"] = querystring