import os, sys
os.environ.setdefault("DB_PASSWORD", "x")
os.environ.setdefault("ADMIN_PAGE_PASSWORD", "x")
os.environ.setdefault("SESSION_SECRET", "x")
sys.path.insert(0, "/workspace/admin_page")
os.chdir("/workspace/admin_page")
from app import config, oci_storage
assert config.IMAGE_PATH_BASE == "images/", config.IMAGE_PATH_BASE
assert oci_storage.build_key("12/12.png") == "images/12/12.png"
assert oci_storage.build_key("images/12/12.png") == "images/12/12.png"
assert oci_storage.build_key("/12/12.png") == "images/12/12.png"
from app import main
assert main._final_rel_path(12, "tmp/abc123.png") == "12/12.png"
assert main._final_rel_path(12, "tmp/abc123.tags.json") == "12/12.tags.json"
assert main._final_rel_path(12, "tmp/abc123.hint.json") == "12/12.hint.json"
assert main._final_rel_path(33, "tmp/deadbeef.jpg") == "33/33.jpg"
print("build_key + _final_rel_path: OK")
from app.main import app
routes = {r.path for r in app.routes}
for p in ["/upload-image", "/upload-json", "/image-preview",
          "/table/{owner}/{name}/row/create", "/table/{owner}/{name}/row/update",
          "/table/{owner}/{name}/row/delete"]:
    assert p in routes, p
print("routes: OK", len(routes))
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader("app/templates"))
env.filters["fmt"] = lambda v: "" if v is None else str(v)
env.filters["querystring"] = lambda d: "&".join(f"{k}={v}" for k, v in d.items())
env.filters["urlencode"] = lambda s: s
env.globals.setdefault("querystring", env.filters["querystring"])
for t in ["row_form.html", "table.html", "base.html", "home.html", "login.html", "sql.html"]:
    env.get_template(t)
print("templates: OK")