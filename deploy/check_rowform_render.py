"""row_form.html 렌더 스모크: IMAGE_RESOURCE 생성/수정 폼에 pending hidden 이 있는지 확인."""
import os, sys
os.environ.setdefault("DB_PASSWORD", "x")
os.environ.setdefault("ADMIN_PAGE_PASSWORD", "x")
os.environ.setdefault("SESSION_SECRET", "x")
sys.path.insert(0, "/workspace/admin_page")
os.chdir("/workspace/admin_page")

from jinja2 import Environment, FileSystemLoader, DictLoader

base = open("app/templates/base.html", encoding="utf-8").read()
# base.html 의 block 구조가 있어도 렌더 가능하도록 그대로 사용
env = Environment(loader=FileSystemLoader("app/templates"))
env.filters["fmt"] = lambda v: "" if v is None else str(v)

class FakeCol:
    def __init__(self, name, data_type, nullable=True, is_pk=False, is_identity=False, fk_ref=None, data_default=None):
        self.name, self.data_type, self.nullable = name, data_type, nullable
        self.is_pk, self.is_identity, self.fk_ref, self.data_default = is_pk, is_identity, fk_ref, data_default

class FakeTable:
    owner = "SPEECHAPP_CONTENT"
    name = "IMAGE_RESOURCE"
    display_name = "SPEECHAPP_CONTENT.IMAGE_RESOURCE"
    columns = [
        FakeCol("IMAGE_ID", "NUMBER", is_pk=True, is_identity=True),
        FakeCol("IMAGE_NAME", "VARCHAR2", nullable=False),
        FakeCol("IMAGE_FILE_PATH", "VARCHAR2", nullable=False),
        FakeCol("IMAGE_TAG_PATH", "VARCHAR2"),
        FakeCol("IMAGE_HINT_PATH", "VARCHAR2"),
        FakeCol("HINT_TYPE", "VARCHAR2"),
        FakeCol("CREATED_AT", "TIMESTAMP(6)"),
    ]
    def pk_columns(self):
        return [c for c in self.columns if c.is_pk]
    def insertable_columns(self):
        return [c for c in self.columns if not c.is_identity]
    def updatable_columns(self):
        return [c for c in self.columns if not c.is_identity and not c.is_pk and not c.data_type.startswith("TIMESTAMP")]

tpl = env.get_template("row_form.html")

class FakeURL:
    path = "/"

class FakeRequest:
    url = FakeURL()

def render(mode, values):
    return tpl.render(
        request=FakeRequest(), table=FakeTable(), mode=mode, values=values,
        db_ok=True, flash=None, row_pk_query="", pk_query="",
    )

# create mode
html = render("create", {})
assert 'name="__pending_file"' in html, "missing __pending_file"
assert 'name="__pending_tags"' in html, "missing __pending_tags"
assert 'name="__pending_hint"' in html, "missing __pending_hint"
assert "next_image_id" not in html and "nextId" not in html, "nextId logic should be gone"
assert 'name="image_id"' not in html, "no image_id form field"
# edit mode: hidden path inputs carry rel_path values
html_edit = render("edit", {"IMAGE_ID": "12", "IMAGE_FILE_PATH": "12/12.png", "IMAGE_NAME": "rabbit"})
assert 'value="12/12.png"' in html_edit
assert 'name="__pk__IMAGE_ID"' in html_edit
print("row_form.html smoke: OK")
print("- create form has 3 pending hidden inputs, no image_id prefill")
print("- edit form carries rel_path values (12/12.png)")