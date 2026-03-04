"""
Update the categories of a number of Style rules to Complexity based on
Micha's feedback.
"""

import sqlite3

rules = [
    "unnecessary-literal-set",
    "multiple-starts-ends-with",
    "redundant-literal-union",
    "slice-to-remove-prefix-or-suffix",
    "unnecessary-list-comprehension-set",
    "unnecessary-double-cast-or-process",
    "unnecessary-dict-comprehension-for-iterable",
    "logging-string-format",
    "unnecessary-generator-dict",
    "utf8-encoding-declaration",
    "unnecessary-spread",
    "unnecessary-future-import",
    "empty-type-checking-block",
    "unicode-kind-prefix",
]

conn = sqlite3.connect("categories.db")
for rule in rules:
    conn.execute(
        "UPDATE rules SET category = 'complexity' WHERE name = ? AND category = 'style'",
        (rule,),
    )
conn.commit()
conn.close()
