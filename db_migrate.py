"""Add scoring and ecosystem columns to categories.db from out.csv and ecosystem.csv.

Also reorders columns so notes is last.
"""

import csv
import sqlite3

conn = sqlite3.connect("categories.db")

# Recreate table with notes at the end
conn.execute("ALTER TABLE rules RENAME TO rules_old")
conn.execute("""
    CREATE TABLE rules (
        code TEXT,
        name TEXT,
        category TEXT,
        accuracy REAL,
        severity REAL,
        fixability REAL,
        applicability REAL,
        configuration REAL,
        conflicts REAL,
        total REAL,
        ecosystem REAL,
        notes TEXT
    )
""")
conn.execute("""
    INSERT INTO rules (code, name, category, notes)
    SELECT code, name, category, notes FROM rules_old
""")
conn.execute("DROP TABLE rules_old")

# Populate scoring from out.csv
with open("out.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        conn.execute(
            """UPDATE rules SET
                accuracy = ?, severity = ?, fixability = ?,
                applicability = ?, configuration = ?, conflicts = ?, total = ?
            WHERE code = ?""",
            (
                float(row["accuracy"]) if row["accuracy"] else None,
                float(row["severity"]) if row["severity"] else None,
                float(row["fixability"]) if row["fixability"] else None,
                float(row["applicability"]) if row["applicability"] else None,
                float(row["configuration"]) if row["configuration"] else None,
                float(row["conflicts"]) if row["conflicts"] else None,
                float(row["total"]) if row["total"] else None,
                row["rule"],
            ),
        )

# Populate ecosystem from ecosystem.csv
with open("ecosystem.csv") as f:
    reader = csv.DictReader(f)
    for row in reader:
        conn.execute(
            "UPDATE rules SET ecosystem = ? WHERE code = ?",
            (float(row["ecosystem"]) if row["ecosystem"] else None, row["code"]),
        )

conn.commit()
conn.close()
print("Migration complete.")
