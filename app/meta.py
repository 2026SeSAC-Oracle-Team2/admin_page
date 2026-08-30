"""테이블 메타데이터 (동적 조회 — Oracle 데이터 딕셔너리 기반).

speechapp_admin 은 SPEECHAPP_USER / SPEECHAPP_CONTENT 스키마의 테이블을
소유하지 않으므로 all_tab_columns 로 조회하고, 스키마.테이블 형태로 정규화한다.
"""
from dataclasses import dataclass, field

from . import config, db


@dataclass
class Column:
    name: str          # 대문자 컬럼명
    data_type: str     # NUMBER / VARCHAR2 / TIMESTAMP(6) ...
    nullable: bool
    data_default: str | None = None
    is_pk: bool = False
    is_identity: bool = False   # GENERATED ... IDENTITY → INSERT 시 입력 제외
    fk_ref: tuple[str, str] | None = None  # (참조스키마, 참조테이블) — FK


@dataclass
class TableInfo:
    owner: str
    name: str
    columns: list[Column] = field(default_factory=list)
    num_rows: int | None = None

    @property
    def fqn(self) -> str:
        return f'"{self.owner}"."{self.name}"'

    @property
    def display_name(self) -> str:
        return f"{self.owner}.{self.name}"

    def pk_columns(self) -> list[Column]:
        return [c for c in self.columns if c.is_pk]

    def insertable_columns(self) -> list[Column]:
        """INSERT 폼에 나올 컬럼: PK/제외 컬럼 빼고"""
        return [
            c for c in self.columns
            if not c.is_identity and not (c.is_pk and c.data_type == "NUMBER" and c.data_default is None)
        ]

    def updatable_columns(self) -> list[Column]:
        """UPDATE 폼에 나올 컬럼: PK/identity 제외, timestamp 자동컬럼 제외"""
        return [
            c for c in self.columns
            if not c.is_identity and not c.is_pk and c.data_type != "TIMESTAMP"
        ]


def list_tables() -> list[TableInfo]:
    """관리 대상 테이블 목록 (행 수 포함). 결과는 캐시 없이 매번 조회."""
    rows = db.fetch_all(
        f"""
        SELECT t.owner, t.table_name, t.num_rows
        FROM all_tables t
        WHERE t.owner LIKE :pfx ESCAPE '\\'
        ORDER BY t.owner, t.table_name
        """,
        {"pfx": config.OWNER_PREFIX + "%"},
    )
    tables = [TableInfo(owner=r["OWNER"], name=r["TABLE_NAME"], num_rows=r["NUM_ROWS"]) for r in rows]
    if tables:
        _attach_columns(tables)
    return tables


def get_table(owner: str, name: str) -> TableInfo | None:
    row = db.fetch_one(
        """
        SELECT owner, table_name, num_rows
        FROM all_tables
        WHERE owner = :o AND table_name = :t
        """,
        {"o": owner.upper(), "t": name.upper()},
    )
    if not row:
        return None
    t = TableInfo(owner=row["OWNER"], name=row["TABLE_NAME"], num_rows=row["NUM_ROWS"])
    _attach_columns([t])
    return t


def _attach_columns(tables: list[TableInfo]) -> None:
    owners = [t.owner for t in tables]
    names = [t.name for t in tables]
    by_key = {(t.owner, t.name): t for t in tables}

    # 컬럼
    col_rows = db.fetch_all(
        """
        SELECT owner, table_name, column_name, data_type, data_length,
               nullable, data_default, char_length
        FROM all_tab_columns
        WHERE owner = :o AND table_name = :t
        ORDER BY column_id
        """,
        # IN 절 바인딩은 단순화 위해 테이블별 호출 대신 아래 루프
        {"o": owners[0], "t": names[0]},
    )
    # ↑ 위 쿼리는 1개 테이블만 커버하므로, 테이블별로 조회한다
    col_rows = []
    for t in tables:
        col_rows += db.fetch_all(
            """
            SELECT owner, table_name, column_name, data_type, data_length,
                   nullable, data_default, char_length
            FROM all_tab_columns
            WHERE owner = :o AND table_name = :t
            ORDER BY column_id
            """,
            {"o": t.owner, "t": t.name},
        )

    # PK 컬럼
    pk_rows = db.fetch_all(
        """
        SELECT c.owner, c.table_name, cc.column_name
        FROM all_constraints c
        JOIN all_cons_columns cc ON c.owner = cc.owner AND c.constraint_name = cc.constraint_name
        WHERE c.owner = :o AND c.constraint_type = 'P'
        """,
        {"o": config.OWNER_PREFIX + "%"},
    )
    # LIKE 바인딩이 안 되므로 아래에서 직접 필터
    pk_rows = db.fetch_all(
        """
        SELECT c.owner, c.table_name, cc.column_name
        FROM all_constraints c
        JOIN all_cons_columns cc ON c.owner = cc.owner AND c.constraint_name = cc.constraint_name
        WHERE c.owner LIKE :pfx AND c.constraint_type = 'P'
        """,
        {"pfx": config.OWNER_PREFIX + "%"},
    )

    # FK 매핑
    fk_rows = db.fetch_all(
        """
        SELECT ac.owner, ac.table_name, acc.column_name,
               rc.owner AS r_owner, rc.table_name AS r_table
        FROM all_constraints ac
        JOIN all_cons_columns acc ON ac.owner = acc.owner AND ac.constraint_name = acc.constraint_name
        JOIN all_constraints rc ON ac.r_constraint_name = rc.constraint_name AND ac.r_owner = rc.owner
        WHERE ac.owner LIKE :pfx AND ac.constraint_type = 'R'
        """,
        {"pfx": config.OWNER_PREFIX + "%"},
    )

    # identity 여부
    id_rows = db.fetch_all(
        """
        SELECT table_name, column_name
        FROM all_tab_identity_cols
        WHERE owner LIKE :pfx
        """,
        {"pfx": config.OWNER_PREFIX + "%"},
    )

    for r in col_rows:
        key = (r["OWNER"], r["TABLE_NAME"])
        if key not in by_key:
            continue
        default = r["DATA_DEFAULT"]
        if default is not None and hasattr(default, "read"):
            default = default.read()
        by_key[key].columns.append(
            Column(
                name=r["COLUMN_NAME"],
                data_type=r["DATA_TYPE"],
                nullable=(r["NULLABLE"] == "Y"),
                data_default=default,
                is_identity=(r["COLUMN_NAME"],) in {(i["COLUMN_NAME"],) for i in id_rows if i["TABLE_NAME"] == r["TABLE_NAME"]},
                fk_ref=next(
                    (
                        (f["R_OWNER"], f["R_TABLE"])
                        for f in fk_rows
                        if f["OWNER"] == r["OWNER"] and f["TABLE_NAME"] == r["TABLE_NAME"] and f["COLUMN_NAME"] == r["COLUMN_NAME"]
                    ),
                    None,
                ),
            )
        )

    # PK 마킹
    for r in pk_rows:
        key = (r["OWNER"], r["TABLE_NAME"])
        if key not in by_key:
            continue
        for col in by_key[key].columns:
            if col.name == r["COLUMN_NAME"]:
                col.is_pk = True


def friendly_error(exc: Exception) -> str:
    """Oracle 에러코드 → 사람이 읽는 메시지."""
    s = str(exc)
    if "ORA-02292" in s:
        return "다른 테이블이 이 행을 참조하고 있어서 삭제할 수 없습니다. (FK 제약)"
    if "ORA-00001" in s:
        return "이미 존재하는 키입니다. (UNIQUE 제약)"
    if "ORA-01400" in s:
        return "필수 컬럼이 비어 있습니다. (NOT NULL)"
    if "ORA-02291" in s:
        return "참조하는 부모 행이 없습니다. (FK 제약 — 부모를 먼저 만드세요)"
    if "ORA-12899" in s:
        return "값이 컬럼 길이를 초과했습니다."
    if "ORA-02290" in s:
        # CHECK 제약 위반 — 제약 이름에서 컬럼을 유추해 안내
        import re as _re
        m = _re.search(r"constraint \((\S+)\)", s)
        cname = m.group(1) if m else ""
        for col_hint, msg in [
            ("PROBLEM_TYPE", "PROBLEM_TYPE 은 'DESCRIBE' 또는 'CHOOSE' 만 허용됩니다."),
            ("HINT_TYPE", "HINT_TYPE 은 'CHOSUNG' 또는 'ASSOCIATION' 만 허용됩니다."),
        ]:
            if col_hint in cname.upper():
                return msg
        return f"허용되지 않는 값입니다. (CHECK 제약{': ' + cname if cname else ''})"
    return s