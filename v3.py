import sqlite3
import tomllib
from pathlib import Path

import polars as pl

from generate_html import generate_html_table, generate_index_page

severity = {
    "correctness": 0,
    "suspicious": 1,
    "style": 2,
    "complexity": 3,
    "perf": 4,
    "pedantic": 5,
    "restriction": 6,
}


def generate(df, title, path):
    generate_html_table(
        df.select(
            "rule",
            "name",
            "category",
            "accuracy",
            "severity",
            "fixability",
            "applicability",
            "configuration",
            "conflicts",
            "total",
            "ecosystem",
        ).sort("rule"),
        title,
        path,
    )


def load_categories(path="categories.db"):
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    codes, categories = zip(*cur.execute("SELECT code, category FROM rules").fetchall())
    categories = pl.from_dict({"rule": codes, "category": categories}).unique("rule")

    missing_categories = categories.filter(pl.col("category").is_null()).height
    assert missing_categories == 0, "non-default rule with missing category"

    return categories


def load_rules(path, categories: pl.DataFrame) -> pl.DataFrame:
    return (
        pl
        .read_csv(path)
        .with_columns(
            pl
            .col("category")
            .replace_strict(severity, return_dtype=pl.Int8)
            .alias("_severity")
        )
        .join(categories, on="rule", how="left")
        .with_columns(pl.col("category_right").alias("category"))
        .drop("category_right")
        .unique("rule")
        .sort("_severity", "rule")
    )


if __name__ == "__main__":
    data = tomllib.loads(Path("proposal.toml").read_text())

    categories = load_categories()
    initial = load_rules("proposed.csv", categories)
    non_default = load_rules("off_by_default.csv", categories)
    all_rules = pl.concat([initial, non_default], how="vertical")

    v3 = all_rules.filter(pl.col("rule").is_in(data['lint']['select']))

    generate(v3, "Default Rules v3", "docs/on_by_default_v3.html")
    generate_index_page()
