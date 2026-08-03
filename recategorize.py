#!/usr/bin/env -S uv run

"""Recategorize rules filtered by their current category."""

import json
import sqlite3
import subprocess
import sys
import termios
import tty
import warnings

from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule

with warnings.catch_warnings(action="ignore"):
    pass

console = Console()


def getch():
    """Read a single character without requiring Enter."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def position(it, p) -> int | None:
    return next((i for i, x in enumerate(it) if p(x)), None)


def main():
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument(
        "--category",
        required=True,
        help="Only show rules currently in this category",
    )
    parser.add_argument(
        "--ruff",
        default="./ruff.26230b1ed3",
        help="Path to the ruff executable",
    )
    parser.add_argument(
        "--database",
        default="categories.db",
        help="Path to the SQLite database",
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
    rows = conn.execute(
        "SELECT code, name FROM rules WHERE category = ? ORDER BY code",
        (args.category,),
    ).fetchall()

    if not rows:
        print(f"No rules found with category '{args.category}'")
        return

    responses = {
        "p": "pedantic",
        "s": "security",
        "d": "documentation",
        "f": "formatting",
        "t": "type-checking",
        "3": "third-party",
        # navigation
        "j": None,
        "k": None,
        "q": None,
        "/": None,
    }

    prompt = (
        "\n(p)edantic, (s)ecurity, (d)ocumentation, (f)ormatting, (t)ype-checking, (3)rd-party\n"
        "j: next, k: prev, q: quit, /<rule>: jump to rule\n"
    )

    cur = 0
    while cur < len(rows):
        code, name = rows[cur]

        console.clear()
        console.print(Rule(f"{code} {name} ({cur + 1}/{len(rows)})"))
        if code in explanations:
            console.print(Markdown(explanations[code]))
        console.print(Rule())

        result = conn.execute(
            "SELECT category FROM rules WHERE code = ?", (code,)
        ).fetchone()

        console.print(prompt + (f"current value = {result[0]}" if result else ""))
        while True:
            response = getch()
            if response == "/":
                # fall back to line input for rule search
                response = "/" + input("/")
                break
            if response in responses:
                break
            console.print(f"unknown response {response}")

        if response == "j":
            cur = min(len(rows) - 1, cur + 1)
            continue
        elif response == "k":
            cur = max(0, cur - 1)
            continue
        elif response[0] == "/":
            rest = response.removeprefix("/")
            cur = position(rows, lambda row: row[0].lower() == rest.lower()) or cur
            continue
        elif response == "q":
            break

        with conn:
            conn.execute(
                "UPDATE rules SET category = ? WHERE code = ?",
                (responses[response], code),
            )

        cur += 1


if __name__ == "__main__":
    main()
