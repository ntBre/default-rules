import json
import sqlite3
import subprocess

conn = sqlite3.connect("categories.db")
conn.execute("ALTER TABLE rules RENAME TO rules_old")
conn.execute("""
    CREATE TABLE rules (
        code TEXT,
        name TEXT,
        category TEXT,
        notes TEXT
    )
""")
conn.execute("""
    INSERT INTO rules (code, category, notes)
    SELECT code, category, notes FROM rules_old
""")
conn.execute("DROP TABLE rules_old")


rules = {
    rule["code"]: rule["name"]
    for rule in json.loads(
        subprocess.run(
            ["ruff", "rule", "--all", "--output-format=json"],
            capture_output=True,
            check=True,
            text=True,
        ).stdout
    )
}

for code, name in rules.items():
    conn.execute("UPDATE rules SET name = ? WHERE code = ?", (name, code))

conn.commit()
conn.close()
