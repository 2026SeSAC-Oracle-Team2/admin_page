"""동적 CRUD — 바인딩 기반 안전 버전 (crud.py 대체).

타임스탬프 등은 SQL 리터럴 대신 바인딩 + TO_TIMESTAMP 로 처리.
"""
from typing import Any

from . import db
from .meta import TableInfo


def _qi(name: str) -> str:
    return f'"{name}"'


def select_rows(
    table: TableInfo,
    page: int = 1,
    per_page: int = 25,
    search: str | None = None,
    search_col: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    where = ""
    binds: dict[str, Any] = {}
    if search and search_col:
        col = next((c for c in table.columns if c.name == search_col.upper()), None)
        if col and col.data_type in ("VARCHAR2", "CHAR"):
            where = f'WHERE UPPER({_qi(col.name)}) LIKE :q'
            binds["q"] = f"%{search.upper()}%"

    total_row = db.fetch_one(f"SELECT COUNT(*) AS CNT FROM {table.fqn} {where}", binds)
    total = int(total_row["CNT"]) if total_row else 0

    offset = (page - 1) * per_page
    rows = db.fetch_all(
        f"""
        SELECT * FROM (
            SELECT t.*, ROWNUM AS rn FROM {table.fqn} t {where}
            ORDER BY {_qi(table.pk_columns()[0].name) if table.pk_columns() else 'ROWNUM'}
        ) WHERE rn > :off AND rn <= :off2
        """,
        {**binds, "off": offset, "off2": offset + per_page},
    )
    for r in rows:
        r.pop("rn", None)
    return rows, total


def fetch_row_by_pk(table: TableInfo, pk_vals: dict[str, Any]) -> dict[str, Any] | None:
    where = " AND ".join(f'{_qi(c)} = :pk_{c}' for c in pk_vals)
    binds = {f"pk_{k}": v for k, v in pk_vals.items()}
    sql = f"SELECT * FROM {table.fqn} WHERE {where} FETCH FIRST 1 ROWS ONLY"
    return db.fetch_one(sql, binds)


def insert_row(table: TableInfo, data: dict[str, Any]) -> int:
    cols = [c for c in table.columns if c.name in data]
    if not cols:
        raise ValueError("입력할 컬럼이 없습니다")
    col_sql = ", ".join(_qi(c.name) for c in cols)
    val_sql = ", ".join(f":b_{c.name}" for c in cols)
    sql = f"INSERT INTO {table.fqn} ({col_sql}) VALUES ({val_sql})"
    return db.execute_dml(sql, {f"b_{c.name}": data[c.name] for c in cols})


def update_row(table: TableInfo, pk_values: dict[str, Any], data: dict[str, Any]) -> int:
    set_parts, binds = [], {}
    for c in table.columns:
        if c.name in data:
            set_parts.append(f"{_qi(c.name)} = :b_{c.name}")
            binds[f"b_{c.name}"] = data[c.name]
    if not set_parts:
        raise ValueError("수정할 컬럼이 없습니다")
    where_parts = []
    for pk_col, pk_val in pk_values.items():
        where_parts.append(f"{_qi(pk_col)} = :pk_{pk_col}")
        binds[f"pk_{pk_col}"] = pk_val
    sql = f"UPDATE {table.fqn} SET {', '.join(set_parts)} WHERE {' AND '.join(where_parts)}"
    return db.execute_dml(sql, binds)


def delete_row(table: TableInfo, pk_values: dict[str, Any]) -> int:
    where_parts, binds = [], {}
    for pk_col, pk_val in pk_values.items():
        where_parts.append(f"{_qi(pk_col)} = :pk_{pk_col}")
        binds[f"pk_{pk_col}"] = pk_val
    sql = f"DELETE FROM {table.fqn} WHERE {' AND '.join(where_parts)}"
    return db.execute_dml(sql, binds)