"""테이블 CRUD — 동적 SQL (컬럼명은 메타데이터에서 검증된 값만 사용)."""
from typing import Any

from . import db, meta
from .meta import TableInfo


def _quote_ident(name: str) -> str:
    """식별자 인용 — 메타데이터에서 온 값만 들어옴."""
    return f'"{name}"'


def select_rows(
    table: TableInfo,
    page: int = 1,
    per_page: int = 25,
    search: str | None = None,
    search_col: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """행 조회 + 전체 행 수. search 가 있으면 LIKE 검색."""
    where = ""
    binds: dict[str, Any] = {}
    if search and search_col:
        col = next((c for c in table.columns if c.name == search_col.upper()), None)
        if col:
            where = f"WHERE UPPER({_quote_ident(col.name)}) LIKE :q"
            binds["q"] = f"%{search.upper()}%"

    offset = (page - 1) * per_page
    total_row = db.fetch_one(
        f"SELECT COUNT(*) AS CNT FROM {table.fqn} {where}", binds
    )
    total = total_row["CNT"] if total_row else 0

    rows = db.fetch_all(
        f"""
        SELECT * FROM (
            SELECT t.*, ROWNUM AS _rn FROM {table.fqn} t {where} ORDER BY ROWNUM
        ) WHERE _rn > :off AND _rn <= :off2
        """,
        {**binds, "off": offset, "off2": offset + per_page},
    )
    for r in rows:
        r.pop("_rn", None)
    return rows, total


def insert_row(table: TableInfo, data: dict[str, Any]) -> int:
    cols = [c for c in table.columns if c.name in data]
    if not cols:
        raise ValueError("입력할 컬럼이 없습니다")
    col_sql = ", ".join(_quote_ident(c.name) for c in cols)
    val_sql = ", ".join(f":{c.name}" for c in cols)
    sql = f"INSERT INTO {table.fqn} ({col_sql}) VALUES ({val_sql})"
    return db.execute_dml(sql, {c.name: data[c.name] for c in cols})


def update_row(table: TableInfo, pk_values: dict[str, Any], data: dict[str, Any]) -> int:
    set_parts = []
    binds: dict[str, Any] = {}
    for c in table.columns:
        if c.name in data:
            set_parts.append(f"{_quote_ident(c.name)} = :{c.name}")
            binds[c.name] = data[c.name]
    if not set_parts:
        raise ValueError("수정할 컬럼이 없습니다")
    where_parts = []
    for pk_col, pk_val in pk_values.items():
        where_parts.append(f"{_quote_ident(pk_col)} = :pk_{pk_col}")
        binds[f"pk_{pk_col}"] = pk_val
    sql = f"UPDATE {table.fqn} SET {', '.join(set_parts)} WHERE {' AND '.join(where_parts)}"
    return db.execute_dml(sql, binds)


def delete_row(table: TableInfo, pk_values: dict[str, Any]) -> int:
    where_parts = []
    binds: dict[str, Any] = {}
    for pk_col, pk_val in pk_values.items():
        where_parts.append(f"{_quote_ident(pk_col)} = :pk_{pk_col}")
        binds[f"pk_{pk_col}"] = pk_val
    sql = f"DELETE FROM {table.fqn} WHERE {' AND '.join(where_parts)}"
    return db.execute_dml(sql, binds)