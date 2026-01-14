import subprocess
import json
import warnings

from rich.console import Console
from rich.markdown import Markdown

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

results = {}
for rule, name in rules.iter_rows():
    console.clear()
    print(rule, name)

    console.print(Markdown(explanations[rule]))

    responses = {
        "c": "correctness",
        "s": "suspicious",
        "x": "complexity",
        "f": "perf",
        "y": "style",
        "p": "pedantic",
        "r": "restriction",
    }

    while True:
        response = input(
            "(c)orrectness, (s)uspicious, comple(x)ity, per(f), st(y)le, (p)edantic, (r)estriction\n"
        )
        if response in responses:
            break
        print(f"unknown response {response}")

    results[rule] = responses[response]

pl.from_dict({"rule": results.keys(), "category": results.values()}).write_csv(
    "out.csv"
)
