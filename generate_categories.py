# /// script
# requires-python = ">=3.12"
# dependencies = ["jinja2"]
# ///

"""Generate categories.html from categories.db.

Links rule codes to the corresponding line in the categories.md PR diff for
commenting.
"""

import hashlib
import sqlite3
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

REPO = "ntBre/default-rules"
PR_NUMBER = 3
CATEGORIES_MD = "categories.md"

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

# Build code -> GitHub diff line URL map
file_hash = hashlib.sha256(CATEGORIES_MD.encode()).hexdigest()
pr_url_base = f"https://github.com/{REPO}/pull/{PR_NUMBER}/files#diff-{file_hash}"

# Line 1 = header, line 2 = separator, line 3+ = rules
code_to_pr_url = {}
for i, rule in enumerate(rules):
    line_num = i + 3
    code_to_pr_url[rule["code"]] = f"{pr_url_base}R{line_num}"

for rule in rules:
    rule["pr_url"] = code_to_pr_url.get(rule["code"])

# Generate HTML
env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("categories.html")

html = template.render(
    title="Rule Categories",
    columns=[{"key": k, "label": v} for k, v in COLUMNS],
    rules=rules,
)

Path("docs/categories.html").write_text(html)
print("Generated docs/categories.html")
