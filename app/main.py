"""FastAPI 라우트 — 페이지 + CRUD 액션 + SQL 콘솔."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote, urlencode

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
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
    next_image_id = None
    if table.name == "IMAGE_RESOURCE":
        row = db.fetch_one("SELECT NVL(MAX(IMAGE_ID), 0) + 1 AS NEXT_ID FROM SPEECHAPP_CONTENT.IMAGE_RESOURCE")
        next_image_id = row["NEXT_ID"] if row else 1
    ctx = base_ctx(request)
    ctx.update(table=table, mode="create", values={}, row_pk_query="", next_image_id=next_image_id)
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

@app.post("/table/{owner}/{name}/row/create")
async def row_create(request: Request, owner: str, name: str):
    require_login(request)
    table = meta.get_table(owner, name)
    if not table:
        raise HTTPSeeOther("/")
    form = await request.form()
    data = _collect_form_data(table, form, insertable_only=True)

    resp = RedirectResponse(_back(owner, name), status_code=303)
    try:
        n = crud.insert_row(table, data)
        set_flash(resp, f"{n}행이 추가되었습니다.")
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
    try:
        n = crud.update_row(table, pk_vals, data)
        set_flash(resp, f"{n}행이 수정되었습니다.")
    except Exception as e:
        set_flash(resp, meta.friendly_error(e), kind="err")
    return resp


def _delete_image_artifacts(row: dict[str, Any]) -> list[str]:
    """IMAGE_RESOURCE 행에 연결된 OCI 객체들을 삭제한다. 실패해도 계속 진행."""
    deleted: list[str] = []
    for key in ("IMAGE_FILE_PATH", "IMAGE_TAG_PATH", "IMAGE_HINT_PATH"):
        path = row.get(key)
        if not path:
            continue
        try:
            oci_storage.delete_object(str(path))
            deleted.append(str(path))
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


# ---------- 이미지 업로드 / 미리보기 ----------

@app.post("/upload-image")
async def upload_image(request: Request, file: UploadFile):
    """이미지를 images/{image_id}/{image_id}.{ext} 규약으로 업로드한다.

    image_id 는 클라이언트가 사전에 생성(또는 DB max+1)해서 전달한다.
    """
    form = await request.form()
    image_id = str(form.get("image_id", "")).strip()
    if not image_id.isdigit():
        raise HTTPException(status_code=400, detail="image_id 가 필요합니다 (숫자).")
    data = await file.read()
    ext = oci_storage.extract_ext(file.filename or "")
    if not ext:
        ext = "png"
    object_key = f"images/{image_id}/{image_id}.{ext}"
    content_type = file.content_type or "application/octet-stream"
    oci_storage.upload_object(object_key, data, content_type)
    return {
        "bucket_path": object_key,
        "image_name": file.filename or object_key,
    }


@app.post("/upload-json")
async def upload_json(request: Request, file: UploadFile):
    """태그/힌트 JSON을 images/{image_id}/{image_id}.{kind}.json 규약으로 업로드한다.

    kind: tags | hint
    """
    form = await request.form()
    image_id = str(form.get("image_id", "")).strip()
    kind = str(form.get("kind", "")).strip()
    if not image_id.isdigit():
        raise HTTPException(status_code=400, detail="image_id 가 필요합니다 (숫자).")
    if kind not in ("tags", "hint"):
        raise HTTPException(status_code=400, detail="kind 는 tags 또는 hint 여야 합니다.")
    if not (file.filename or "").lower().endswith(".json"):
        raise HTTPException(status_code=400, detail=".json 파일만 허용됩니다.")
    data = await file.read()
    object_key = f"images/{image_id}/{image_id}.{kind}.json"
    oci_storage.upload_object(object_key, data, "application/json")
    return {
        "bucket_path": object_key,
        "image_name": file.filename or object_key,
    }


@app.get("/image-preview")
async def image_preview(path: str):
    """bucket_path 에 해당하는 객체의 presigned URL 을 생성해 리다이렉트한다."""
    url = oci_storage.generate_presigned_url(path, expiry_minutes=30)
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