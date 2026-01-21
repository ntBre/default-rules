from textwrap import dedent
from argparse import ArgumentParser, RawTextHelpFormatter, ArgumentDefaultsHelpFormatter
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


class HelpFormatter(RawTextHelpFormatter, ArgumentDefaultsHelpFormatter): ...


def main():
    parser = ArgumentParser(formatter_class=HelpFormatter)
    parser.add_argument(
        "--ruff",
        help="The path to the ruff executable used to extract rule information",
        default="./ruff.26230b1ed3",
    )
    parser.add_argument(
        "--rules",
        help="The path to a CSV file with rules to categorize (default: %(default)s)"
        + dedent("""

        The file needs to have at least `rule` and `name` columns and a header
        so that it can be loaded by polars. For example:

        ```csv
        rule,name
        B009,get-attr-with-constant
        B010,set-attr-with-constant
        ```

        If omitted, the list of all rules will be extracted from the ruff
        executable instead.
        """),
        default=None,
    )
    parser.add_argument(
        "--database",
        help="The path to the output SQLite database",
        default="categories.db",
    )

    args = parser.parse_args()

    rule_data = json.loads(
        subprocess.run(
            [args.ruff, "rule", "--all", "--output-format=json"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout
    )

    explanations = {rule["code"]: rule["explanation"] for rule in rule_data}

    conn = sqlite3.connect(args.database)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS rules (
        code TEXT,
        category TEXT
    )
    """)

    if args.rules is None:
        rows = [(rule["code"], rule["name"]) for rule in rule_data]
    else:
        rules = pl.read_csv(args.rules).select("rule", "name")
        rows = list(rules.iter_rows())

    cur = 0
    while cur < len(rows):
        rule, name = rows[cur]

        console.clear()
        print(rule, name, f"({cur + 1}/{len(rows)})")

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


if __name__ == "__main__":
    main()
