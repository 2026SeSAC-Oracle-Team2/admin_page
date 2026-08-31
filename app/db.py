"""Oracle DB 접속 풀 + 저수준 쿼리 헬퍼."""
import threading
from contextlib import contextmanager
from typing import Any

import oracledb

from . import config

_pool: oracledb.ConnectionPool | None = None
_lock = threading.Lock()


def get_pool() -> oracledb.ConnectionPool:
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                _pool = oracledb.create_pool(
                    user=config.DB_USER,
                    password=config.DB_PASSWORD,
                    dsn=config.DSN,
                    min=1,
                    max=4,
                    increment=1,
                    getmode=oracledb.POOL_GETMODE_WAIT,
                )
    return _pool


@contextmanager
def get_conn():
    pool = get_pool()
    conn = pool.acquire()
    try:
        yield conn
    finally:
        pool.release(conn)


def fetch_all(sql: str, binds: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """SELECT → list[dict]. 컬럼명은 대문자 그대로."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, binds or {})
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def fetch_one(sql: str, binds: dict[str, Any] | None = None) -> dict[str, Any] | None:
    rows = fetch_all(sql, binds)
    return rows[0] if rows else None


def execute_dml(sql: str, binds: dict[str, Any] | None = None) -> int:
    """INSERT/UPDATE/DELETE. 적용된 행 수 반환, 커밋 포함."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, binds or {})
            rowcount = cur.rowcount
        conn.commit()
        return rowcount


def execute_dml_returning(sql: str, binds: dict[str, Any] | None, out_name: str) -> Any:
    """DML + RETURNING INTO. 반환 컬럼 값을 커밋 후 돌려준다.

    binds에 out_name 키는 포함하지 않는다 (내부에서 OUT 바인드로 추가).
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            out_var = cur.var(oracledb.DB_TYPE_NUMBER)
            full_binds = dict(binds or {})
            full_binds[out_name] = out_var
            cur.execute(sql, full_binds)
            rowcount = cur.rowcount
            out_value = out_var.getvalue()
        conn.commit()
        if rowcount and out_var is not None:
            vals = out_var if isinstance(out_var, list) else out_var.getvalue()
            return vals[0] if isinstance(vals, list) and vals else vals
        return None


def check_connection() -> bool:
    try:
        fetch_one("SELECT 1 AS OK FROM dual")
        return True
    except Exception:
        return False