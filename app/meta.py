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
        """INSERT 폼에 나올 컬럼: PK/identity/timestamp 자동컬럼 제외

        TIMESTAMP 컬럼은 DEFAULT CURRENT_TIMESTAMP 자동 기록이 일반적 —
        폼에서 빈 값으로 바인딩되면 NOT NULL 위반(ORA-01400) 또는
        날짜 파싱 오류(ORA-01843)가 나므로 폼에서 아예 제외한다.
        """
        return [
            c for c in self.columns
            if not c.is_identity
            and not (c.is_pk and c.data_type == "NUMBER" and c.data_default is None)
            and not c.data_type.startswith("TIMESTAMP")
            and c.data_type != "DATE"
        ]

    def updatable_columns(self) -> list[Column]:
        """UPDATE 폼에 나올 컬럼: PK/identity 제외, timestamp 자동컬럼 제외

        data_type이 'TIMESTAMP(6)'처럼 precision을 붙고 있으므로
        정확히 'TIMESTAMP'와 비교하면 안 되고 startswith로 판정한다.
        (TIMESTAMP(6)가 폼에 포함되어 ORA-01843이 나던 버그 수정)
        """
        return [
            c for c in self.columns
            if not c.is_identity and not c.is_pk and not c.data_type.startswith("TIMESTAMP")
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


def check_options(owner: str, name: str) -> dict[str, list[str]]:
    """CHECK 제약이 IN ('A','B',...) 형태인 컬럼의 허용값 목록.

    반환: {컬럼명(대문자): ["A", "B", ...]}
    - all_constraints(constraint_type='C') + all_cons_columns에서 조건을 읽어
      "col IN ('X','Y')" 패턴만 파싱. 그 외 조건식(IS NOT NULL, !=, OR 결합 등)은 무시.
    - 행 추가/수정 폼에서 해당 컬럼을 드롭다운으로 렌더링하는 데 사용.
    """
    rows = db.fetch_all(
        """
        SELECT cc.column_name, c.search_condition_vc
        FROM all_constraints c
        JOIN all_cons_columns cc
          ON c.owner = cc.owner AND c.constraint_name = cc.constraint_name
        WHERE c.constraint_type = 'C' AND c.owner = :o AND c.table_name = :t
          AND c.status = 'ENABLED'
        """,
        {"o": owner.upper(), "t": name.upper()},
    )
    out: dict[str, list[str]] = {}
    import re as _re
    pat = _re.compile(r"^\s*\"?([A-Za-z0-9_]+)\"?\s+IN\s*\((.*)\)\s*$", _re.IGNORECASE | _re.DOTALL)
    val_re = _re.compile(r"'([^']*)'")
    for r in rows:
        cond = r["SEARCH_CONDITION_VC"] or ""
        m = pat.match(cond.replace("\n", " "))
        if not m:
            continue
        col, body = m.group(1).upper(), m.group(2)
        vals = val_re.findall(body)
        if vals:
            # 같은 컬럼에 여러 IN 제약이 있으면 병합 (중복 제거, 순서 유지)
            merged = list(dict.fromkeys(out.get(col, []) + vals))
            out[col] = merged
    return out


def fk_options(owner: str, name: str) -> list[dict]:
    """FK 드롭다운용 옵션 목록. PK 오름차순 정렬.

    반환: [{"value": pk값, "label": "pk — 라벨", "image_path": 경로|None}, ...]
    - 라벨: PK 제외 VARCHAR2 컬럼(경로 제외) 최대 2개를 " / "로 연결
    - IMAGE_RESOURCE 참조 시 image_path에 IMAGE_FILE_PATH 포함 (미리보기용)
    - 복합 PK 테이블은 드롭다운 불가 → 빈 리스트 (폼이 텍스트 입력으로 폴백)
    """
    t = get_table(owner, name)
    if not t:
        return []
    pk_cols = t.pk_columns()
    if len(pk_cols) != 1:
        return []
    pk = pk_cols[0].name

    label_cols = [
        c.name for c in t.columns
        if c.name != pk and c.data_type in ("VARCHAR2", "CHAR")
        and not c.name.endswith("_PATH")
    ][:2]

    wanted = list(dict.fromkeys([pk] + label_cols + (
        ["IMAGE_FILE_PATH"] if any(c.name == "IMAGE_FILE_PATH" for c in t.columns) else []
    )))
    cols_sql = ", ".join(f'"{c}"' for c in wanted)
    try:
        rows = db.fetch_all(f'SELECT {cols_sql} FROM "{owner}"."{name}" ORDER BY "{pk}" ASC')
    except Exception:
        return []

    opts: list[dict] = []
    for r in rows[:1000]:
        parts = [str(r[c]) for c in label_cols if r.get(c) is not None]
        opts.append({
            "value": "" if r[pk] is None else r[pk],
            "label": f"{r[pk]}" + (f" — {' / '.join(parts)}" if parts else ""),
            "image_path": r.get("IMAGE_FILE_PATH"),
        })
    return opts


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
            ("HINT_TYPE", "HINT_TYPE 은 'CHOSUNG' 또는 'ASSOCIATION' 만 허용됩니다."),
        ]:
            if col_hint in cname.upper():
                return msg
        return f"허용되지 않는 값입니다. (CHECK 제약{': ' + cname if cname else ''})"
    return s