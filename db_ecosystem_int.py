"""Migrate ecosystem column from REAL to INTEGER."""

import sqlite3

conn = sqlite3.connect("categories.db")
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
        ecosystem INTEGER,
        notes TEXT
    )
""")
conn.execute("""
    INSERT INTO rules
    SELECT code, name, category, accuracy, severity, fixability,
           applicability, configuration, conflicts, total,
           CAST(ecosystem AS INTEGER), notes
    FROM rules_old
""")
conn.execute("DROP TABLE rules_old")
conn.commit()
conn.close()
print("Migrated ecosystem to INTEGER.")
