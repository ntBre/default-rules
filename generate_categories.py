# /// script
# requires-python = ">=3.12"
# dependencies = ["jinja2"]
# ///

"""Generate categories.html from categories.db using Jinja2 templates."""

import sqlite3
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

COLUMNS = [
    ("code", "Code"),
    ("name", "Name"),
    ("category", "Category"),
    ("accuracy", "Accuracy"),
    ("severity", "Severity"),
    ("fixability", "Fixability"),
    ("applicability", "Applicability"),
    ("configuration", "Configuration"),
    ("conflicts", "Conflicts"),
    ("total", "Total"),
    ("ecosystem", "Ecosystem"),
]

conn = sqlite3.connect("categories.db")
conn.row_factory = sqlite3.Row
rules = [dict(row) for row in conn.execute("SELECT * FROM rules ORDER BY code").fetchall()]
conn.close()

env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("categories.html")

html = template.render(
    title="Rule Categories",
    columns=[{"key": k, "label": v} for k, v in COLUMNS],
    rules=rules,
)

Path("docs/categories.html").write_text(html)
print("Generated docs/categories.html")
