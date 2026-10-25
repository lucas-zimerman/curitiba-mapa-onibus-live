"""Inject data/curitiba_data.json into src/template.html and write index.html."""
import pathlib
root = pathlib.Path(__file__).resolve().parent.parent
tpl = (root / "src" / "template.html").read_text(encoding="utf-8")
data = (root / "data" / "curitiba_data.json").read_text(encoding="utf-8")
assert "</script" not in data
(root / "index.html").write_text(tpl.replace("__DATA__", data), encoding="utf-8")
print("wrote index.html")
