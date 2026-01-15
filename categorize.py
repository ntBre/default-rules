import sqlite3
import subprocess
import json
import warnings

from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule

with warnings.catch_warnings(action="ignore"):
    import polars as pl

console = Console()

RUFF = "./ruff.26230b1ed3"
rule_data = json.loads(
    subprocess.run(
        [RUFF, "rule", "--all", "--output-format=json"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
)

explanations = {rule["code"]: rule["explanation"] for rule in rule_data}


rules = pl.read_csv("queue.csv").select("rule", "name")

conn = sqlite3.connect("categories.db")
conn.execute("""
CREATE TABLE IF NOT EXISTS rules (
    code TEXT,
    category TEXT
)
""")

rows = list(rules.iter_rows())
cur = 0
while cur < len(rows):
    rule, name = rows[cur]

    console.clear()
    print(rule, name, f"({cur}/{len(rows)})")

    console.print(Markdown(explanations[rule]))
    console.print(Rule())

    responses = {
        "c": "correctness",
        "s": "suspicious",
        "x": "complexity",
        "f": "perf",
        "y": "style",
        "p": "pedantic",
        "r": "restriction",
        # index manipulation
        "j": None,
        "k": None,
        "q": None,
    }

    cursor = conn.cursor()
    result = cursor.execute(
        "SELECT code, category FROM rules WHERE code = ?", (rule,)
    ).fetchone()

    while True:
        response = input(
            "\n(c)orrectness, (s)uspicious, comple(x)ity, per(f), st(y)le, (p)edantic, (r)estriction\n"
            "j: next, k: prev, q: quit\n"
            + (f"current value = {result[1]}\n" if result else "")
        )
        if response in responses:
            break
        print(f"unknown response {response}")

    if response == "j":
        cur = min(len(rows) - 1, cur + 1)
        continue
    elif response == "k":
        cur = max(0, cur - 1)
        continue
    elif response == "q":
        break

    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO rules (code, category) VALUES (?, ?)",
            (rule, responses[response]),
        )

    cur += 1
