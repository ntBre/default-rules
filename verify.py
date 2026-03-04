"""
Verify that the rules enabled in our preview defaults match the categories
in the database.
"""

import re
import sqlite3
import subprocess

# Get enabled rules from ruff
result = subprocess.run(
    ["uvx", "ruff@0.15.2", "check", "--isolated", "--preview", "--show-settings"],
    capture_output=True,
    check=True,
    text=True,
)

# Parse enabled rule codes: lines like "\tname (CODE),"
in_enabled = False
ruff_enabled = set()
for line in result.stdout.splitlines():
    if line.startswith("linter.rules.enabled"):
        in_enabled = True
        continue
    if in_enabled:
        if line.strip() == "]":
            break
        m = re.search(r"\((\w+)\)", line)
        if m:
            ruff_enabled.add(m.group(1))

# Get rules that should be enabled by default from the DB
conn = sqlite3.connect("categories.db")
on_by_default = {"correctness", "suspicious", "complexity", "perf", "style"}
rows = conn.execute(
    "SELECT code, category FROM rules WHERE category IN (?, ?, ?, ?, ?)",
    tuple(on_by_default),
).fetchall()
db_enabled = {code for code, _ in rows}
conn.close()

# Compare
only_in_ruff = ruff_enabled - db_enabled
only_in_db = db_enabled - ruff_enabled

print(f"Enabled in ruff: {len(ruff_enabled)}")
print(f"Enabled in DB:   {len(db_enabled)}")

if only_in_ruff:
    print(f"\nIn ruff but not in DB ({len(only_in_ruff)}):")
    for code in sorted(only_in_ruff):
        print(f"  {code}")

if only_in_db:
    print(f"\nIn DB but not in ruff ({len(only_in_db)}):")
    for code in sorted(only_in_db):
        print(f"  {code}")

assert ruff_enabled == db_enabled
