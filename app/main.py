"""FastAPI 라우트 — 페이지 + CRUD 액션 + SQL 콘솔."""
from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import quote, urlencode

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import auth, config, crud, db, meta, oci_storage
from .templating import register_filters


def _fmt_value(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8", errors="replace")
        except Exception:
            return repr(v)
    if hasattr(v, "isoformat"):
        return v.isoformat(sep=" ", timespec="seconds")
    return str(v)


app = FastAPI(title="SeSAC Admin", docs_url=None, redoc_url=None, openapi_url=None)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")
templates.env.filters["fmt"] = _fmt_value
register_filters(templates.env)


# ---------- 헬퍼 ----------

class HTTPSeeOther(Exception):
    def __init__(self, url: str):
        self.url = url


@app.exception_handler(HTTPSeeOther)
async def see_other_handler(request: Request, exc: HTTPSeeOther):
    return RedirectResponse(url=exc.url, status_code=303)


def current_user(request: Request) -> bool:
    token = request.cookies.get(config.SESSION_COOKIE, "")
    return bool(token) and auth.verify_session_token(token)


def require_login(request: Request) -> None:
    if not current_user(request):
        raise HTTPSeeOther("/login")


def set_flash(response: RedirectResponse, message: str, kind: str = "ok") -> None:
    # 쿠키는 latin-1 인코딩만 허용 → 한글 메시지를 URL 인코딩해서 담는다
    from urllib.parse import quote as _q
    response.set_cookie("flash", f"{kind}|{_q(message)}", max_age=30, httponly=True, samesite="lax")


def pop_flash(request: Request) -> tuple[str, str] | None:
    from urllib.parse import unquote as _uq
    raw = request.cookies.get("flash")
    if not raw or "|" not in raw:
        return None
    kind, _, msg = raw.partition("|")
    return (kind, _uq(msg))


def base_ctx(request: Request) -> dict[str, Any]:
    return {"request": request, "db_ok": db.check_connection(), "flash": pop_flash(request)}


def _back(owner: str, name: str) -> str:
    return f"/table/{quote(owner)}/{quote(name)}"


def _pk_from_form(table: meta.TableInfo, form: Any) -> dict[str, Any]:
    pk_vals: dict[str, Any] = {}
    for c in table.pk_columns():
        v = form.get(f"__pk__{c.name}")
        if v is None:
            raise HTTPSeeOther("/")
        pk_vals[c.name] = v
    return pk_vals


_TS_TYPES = ("TIMESTAMP", "DATE")
_NUM_TYPES = ("NUMBER", "FLOAT", "INTEGER")


def _coerce(col: meta.Column, raw: str) -> Any:
    raw = raw.strip()
    if raw == "":
        return None
    if col.data_type in _NUM_TYPES:
        return raw  # Oracle이 문자열 숫자 바인딩 허용
    return raw


def _collect_form_data(table: meta.TableInfo, form: Any, insertable_only: bool) -> dict[str, Any]:
    cols = table.insertable_columns() if insertable_only else table.updatable_columns()
    data: dict[str, Any] = {}
    for c in cols:
        raw = form.get(c.name)
        if raw is None:
            continue
        data[c.name] = _coerce(c, str(raw))
    return data


# ---------- 로그인 ----------

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if current_user(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login")
async def login_submit(request: Request, password: str = Form("")):
    if not auth.check_password(password):
        return templates.TemplateResponse(
            request, "login.html", {"error": "비밀번호가 올바르지 않습니다."}, status_code=401
        )
    token = auth.make_session_token()
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie(
        config.SESSION_COOKIE, token,
        max_age=config.SESSION_MAX_AGE, httponly=True, samesite="lax",
    )
    return resp


@app.post("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(config.SESSION_COOKIE)
    return resp


# ---------- 홈 ----------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    require_login(request)
    ctx = base_ctx(request)
    ctx.update(tables=meta.list_tables())
    return templates.TemplateResponse(request, "home.html", ctx)


# ---------- 테이블 행 조회 ----------

PAGE_SIZES = [10, 25, 50, 100]


@app.get("/table/{owner}/{name}", response_class=HTMLResponse)
async def table_view(
    request: Request, owner: str, name: str,
    page: int = 1, per_page: int = 25,
    search_col: str = "", search: str = "",
):
    require_login(request)
    table = meta.get_table(owner, name)
    if not table:
        raise HTTPSeeOther("/")
    page = max(1, page)
    per_page = per_page if per_page in PAGE_SIZES else 25

    rows, total = crud.select_rows(
        table, page=page, per_page=per_page,
        search=search.strip() or None, search_col=search_col or None,
    )

    colnames = [c.name for c in table.columns]
    pk_cols = [c.name for c in table.pk_columns()]
    fk_map = {c.name: c.fk_ref for c in table.columns if c.fk_ref}
    total_pages = max(1, (total + per_page - 1) // per_page)

    ctx = base_ctx(request)
    ctx.update(
        table=table, rows=rows, colnames=colnames, pk_cols=pk_cols, fk_map=fk_map,
        page=page, per_page=per_page, total=total, total_pages=total_pages,
        search=search, search_col=search_col, page_sizes=PAGE_SIZES,
        row_pk_query=lambda row: urlencode([(c.name, _fmt_value(row.get(c.name))) for c in table.pk_columns()]),
    )
    return templates.TemplateResponse(request, "table.html", ctx)


# ---------- 행 추가/수정 폼 ----------

@app.get("/table/{owner}/{name}/row/new", response_class=HTMLResponse)
async def row_new_form(request: Request, owner: str, name: str):
    require_login(request)
    table = meta.get_table(owner, name)
    if not table:
        raise HTTPSeeOther("/")
    ctx = base_ctx(request)
    ctx.update(table=table, mode="create", values={}, row_pk_query="")
    return templates.TemplateResponse(request, "row_form.html", ctx)


@app.get("/table/{owner}/{name}/row/edit", response_class=HTMLResponse)
async def row_edit_form(request: Request, owner: str, name: str):
    require_login(request)
    table = meta.get_table(owner, name)
    if not table:
        raise HTTPSeeOther("/")
    pk_vals: dict[str, Any] = {}
    for c in table.pk_columns():
        v = request.query_params.get(c.name)
        if v is None:
            raise HTTPSeeOther(_back(owner, name))
        pk_vals[c.name] = v
    row = crud.fetch_row_by_pk(table, pk_vals)
    if not row:
        raise HTTPSeeOther(_back(owner, name))
    ctx = base_ctx(request)
    ctx.update(
        table=table, mode="edit",
        values={k: _fmt_value(v) for k, v in row.items()},
        pk_query=urlencode([(c.name, _fmt_value(row.get(c.name))) for c in table.pk_columns()]),
    )
    return templates.TemplateResponse(request, "row_form.html", ctx)


# ---------- 행 추가/수정/삭제 액션 ----------

_IMAGE_RESOURCE_COLUMNS = ("IMAGE_FILE_PATH", "IMAGE_TAG_PATH", "IMAGE_HINT_PATH")
# 폼 필드명(multipart) → (필드명, kind)
_IMAGE_FILE_FIELDS = {
    "file": ("__file_image__", "IMAGE_FILE_PATH"),
    "tags": ("__file_tags__", "IMAGE_TAG_PATH"),
    "hint": ("__file_hint__", "IMAGE_HINT_PATH"),
}


def _res_rel_path(image_id: int, kind: str, ext: str) -> str:
    """OCI 저장 경로 (DB에는 base 미포함으로 저장). kind: file|tags|hint."""
    suffix = ext if kind == "file" else f"{kind}.json"
    return f"{image_id}/{image_id}.{suffix}"


def _insert_image_row_with_files(form: Any) -> int:
    """IMAGE_RESOURCE 행 생성 + 파일 업로드(트랜잭셔널).

    1) 이미지 파일 없으면 즉시 실패 (가짜 행 방지)
    2) INSERT ... RETURNING image_id 로 실제 ID 확보 (ID 부여의 유일한 지점)
    3) 이미지 본문을 OCI 최종 경로에 업로드 (실패 시 행 삭제 후 예외 상향)
    4) 태그/힌트 파일도 있으면 같이 업로드 — 하나라도 실패하면 전부 롤백
    5) 경로 컬럼 UPDATE
    """
    image_name = str(form.get("IMAGE_NAME", "")).strip()
    if not image_name:
        raise ValueError("IMAGE_NAME 은 필수입니다.")

    image_file = form.get("__file_image__")
    if image_file is None or not getattr(image_file, "filename", None):
        raise ValueError("이미지 파일은 필수입니다. 이미지를 선택한 뒤 추가하세요.")
    image_ext = oci_storage.extract_ext(image_file.filename or "")
    if not image_ext:
        raise ValueError("이미지는 jpg/jpeg/png/webp 형식만 지원합니다.")

    image_id = int(db.execute_dml_returning(
        "INSERT INTO SPEECHAPP_CONTENT.IMAGE_RESOURCE (IMAGE_NAME, IMAGE_FILE_PATH) "
        "VALUES (:image_name, :file_path) RETURNING IMAGE_ID INTO :out_id",
        {"image_name": image_name, "file_path": "__uploading__"},
        "out_id",
    ))

    saved: dict[str, str] = {}
    try:
        rel_file, _ = _store_upload(image_id, "file", image_file, image_ext)
        saved["IMAGE_FILE_PATH"] = rel_file
    except Exception:
        db.execute_dml("DELETE FROM SPEECHAPP_CONTENT.IMAGE_RESOURCE WHERE IMAGE_ID = :pk", {"pk": image_id})
        raise

    for kind, col in (("tags", "IMAGE_TAG_PATH"), ("hint", "IMAGE_HINT_PATH")):
        upload = form.get(f"__file_{kind}__")
        if upload is None or not getattr(upload, "filename", None):
            continue
        try:
            if not (upload.filename or "").lower().endswith(".json"):
                raise ValueError(f"{kind} 파일은 .json 이어야 합니다.")
            rel, _ = _store_upload(image_id, kind, upload, "json")
            saved[col] = rel
        except Exception:
            # 일관성 위해 전체 롤백: 업로드된 객체 삭제 + 행 삭제
            for rel in saved.values():
                try:
                    oci_storage.delete_object(oci_storage.build_key(rel))
                except Exception:
                    pass
            db.execute_dml("DELETE FROM SPEECHAPP_CONTENT.IMAGE_RESOURCE WHERE IMAGE_ID = :pk", {"pk": image_id})
            raise

    if saved:
        sets = ", ".join(f"{col} = :b_{col}" for col in saved)
        binds = {f"b_{c}": v for c, v in saved.items()}
        binds["pk"] = image_id
        db.execute_dml(
            f"UPDATE SPEECHAPP_CONTENT.IMAGE_RESOURCE SET {sets} WHERE IMAGE_ID = :pk",
            binds,
        )
    return image_id


def _store_upload(image_id: int, kind: str, upload: Any, default_ext: str = "json"):
    """단일 업로드 파일을 OCI 최종 경로에 저장. (rel_path, ext) 반환."""
    ext = (oci_storage.extract_ext(upload.filename or "") if kind == "file" else "json") or default_ext
    rel_path = _res_rel_path(image_id, kind, ext)
    upload.file.seek(0)
    data = upload.file.read()
    if not data:
        raise ValueError("비어 있는 파일입니다. 파일을 다시 선택하세요.")
    content_type = upload.content_type or "application/octet-stream"
    oci_storage.upload_object(oci_storage.build_key(rel_path), data, content_type)
    return rel_path, ext


@app.post("/table/{owner}/{name}/row/create")
async def row_create(request: Request, owner: str, name: str):
    require_login(request)
    table = meta.get_table(owner, name)
    if not table:
        raise HTTPSeeOther("/")
    form = await request.form()
    data = _collect_form_data(table, form, insertable_only=True)

    resp = RedirectResponse(_back(owner, name), status_code=303)

    if table.name != "IMAGE_RESOURCE":                                    # 일반 테이블
        try:
            n = crud.insert_row(table, data)
            set_flash(resp, f"{n}행이 추가되었습니다.")
        except Exception as e:
            set_flash(resp, meta.friendly_error(e), kind="err")
        return resp

    # IMAGE_RESOURCE: INSERT → RETURNING image_id → OCI 업로드 → 경로 UPDATE.
    # ID는 이 한 곳에서만 부여되므로 image_id ↔ 경로 불일치가 구조적으로 발생하지 않는다.
    try:
        image_id = _insert_image_row_with_files(form)
        set_flash(resp, f"1행이 추가되었습니다. (image_id={image_id})")
    except Exception as e:
        set_flash(resp, meta.friendly_error(e), kind="err")
    return resp


@app.post("/table/{owner}/{name}/row/update")
async def row_update(request: Request, owner: str, name: str):
    require_login(request)
    table = meta.get_table(owner, name)
    if not table:
        raise HTTPSeeOther("/")
    form = await request.form()
    pk_vals = _pk_from_form(table, form)
    data = _collect_form_data(table, form, insertable_only=False)
    resp = RedirectResponse(_back(owner, name), status_code=303)

    if table.name == "IMAGE_RESOURCE":
        # 경로 컬럼은 서버가 관리 — 사용자 입력 무시
        for col in _IMAGE_RESOURCE_COLUMNS:
            data.pop(col, None)

    try:
        n = crud.update_row(table, pk_vals, data)
        if table.name == "IMAGE_RESOURCE":
            image_id = int(str(pk_vals.get("IMAGE_ID", "")).strip() or 0)
            for kind, (field_name, col) in _IMAGE_FILE_FIELDS.items():
                upload = form.get(field_name)
                if upload is None or not getattr(upload, "filename", None):
                    continue  # 새 파일 없음 → 기존 경로 유지
                rel, _ = _store_upload(image_id, kind, upload)
                db.execute_dml(
                    f"UPDATE SPEECHAPP_CONTENT.IMAGE_RESOURCE SET {col} = :p WHERE IMAGE_ID = :pk",
                    {"p": rel, "pk": image_id},
                )
        set_flash(resp, f"{n}행이 수정되었습니다.")
    except Exception as e:
        set_flash(resp, meta.friendly_error(e), kind="err")
    return resp


def _delete_image_artifacts(row: dict[str, Any]) -> list[str]:
    """IMAGE_RESOURCE 행에 연결된 OCI 객체들을 삭제한다 (base 붙여 전체 키 생성). 실패해도 계속 진행."""
    deleted: list[str] = []
    for key in ("IMAGE_FILE_PATH", "IMAGE_TAG_PATH", "IMAGE_HINT_PATH"):
        rel = row.get(key)
        if not rel:
            continue
        try:
            oci_storage.delete_object(oci_storage.build_key(str(rel)))
            deleted.append(str(rel))
        except Exception:
            pass  # 이미 없거나 일시 오류 — DB 삭제는 진행
    return deleted


@app.post("/table/{owner}/{name}/row/delete")
async def row_delete(request: Request, owner: str, name: str):
    require_login(request)
    table = meta.get_table(owner, name)
    if not table:
        raise HTTPSeeOther("/")
    form = await request.form()
    pk_vals = _pk_from_form(table, form)
    resp = RedirectResponse(_back(owner, name), status_code=303)
    try:
        # OCI 정리: IMAGE_RESOURCE면 삭제 전에 행을 읽어 경로 확보
        oci_deleted: list[str] = []
        if table.name == "IMAGE_RESOURCE":
            row = crud.fetch_row_by_pk(table, pk_vals)
            if row:
                oci_deleted = _delete_image_artifacts(row)
        n = crud.delete_row(table, pk_vals)
        if oci_deleted:
            set_flash(resp, f"{n}행이 삭제되었습니다. (OCI 파일 {len(oci_deleted)}건도 삭제)")
        else:
            set_flash(resp, f"{n}행이 삭제되었습니다.")
    except Exception as e:
        set_flash(resp, meta.friendly_error(e), kind="err")
    return resp


# ---------- 이미지/JSON 업로드 (image_id 기반, base는 oci_storage.build_key) ----------
# (직접 폼 제출 방식으로 전환 — /upload-image, /upload-json AJAX 엔드포인트는 제거됨.
#  파일은 row_create/row_update가 multipart로 직접 받아 처리한다.)

@app.get("/image-preview")
async def image_preview(path: str):
    """rel_path(base 미포함, 예: 12/12.png)에 해당하는 객체의 presigned URL 을 생성해 리다이렉트한다."""
    url = oci_storage.generate_presigned_url(oci_storage.build_key(path), expiry_minutes=30)
    return RedirectResponse(url=url)


# ---------- SQL 콘솔 ----------

_SELECT_RE = None  # 아래에서 컴파일


@app.get("/sql", response_class=HTMLResponse)
async def sql_page(request: Request):
    require_login(request)
    ctx = base_ctx(request)
    ctx.update(sql="", columns=None, rows=None, error=None, dml_allowed=False, affected=None)
    return templates.TemplateResponse(request, "sql.html", ctx)


@app.post("/sql", response_class=HTMLResponse)
async def sql_run(
    request: Request,
    sql: str = Form(""),
    dml_allowed: str = Form(""),
):
    require_login(request)
    sql_text = sql.strip().rstrip(";").strip()
    ctx = base_ctx(request)
    ctx.update(sql=sql, columns=None, rows=None, error=None, affected=None,
               dml_allowed=bool(dml_allowed))

    if not sql_text:
        ctx["error"] = "SQL을 입력하세요."
        return templates.TemplateResponse(request, "sql.html", ctx)

    first_word = sql_text.split(None, 1)[0].upper() if sql_text else ""
    is_select = first_word == "SELECT" or first_word == "WITH"

    if not is_select and not ctx["dml_allowed"]:
        ctx["error"] = "SELECT만 허용됩니다. DML(INSERT/UPDATE/DELETE)을 실행하려면 'DML 허용'에 체크하세요."
        return templates.TemplateResponse(request, "sql.html", ctx)

    try:
        if is_select:
            rows = db.fetch_all(sql_text)
            ctx["rows"] = rows[:500]
            ctx["columns"] = list(rows[0].keys()) if rows else []
            if len(rows) > 500:
                ctx["error"] = f"결과가 500행을 초과해 앞 500행만 표시합니다. (전체 {len(rows)}행)"
        else:
            n = db.execute_dml(sql_text)
            ctx["affected"] = n
    except Exception as e:
        ctx["error"] = meta.friendly_error(e)
    return templates.TemplateResponse(request, "sql.html", ctx)