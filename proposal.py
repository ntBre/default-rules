import re
import warnings
import json
import subprocess

with warnings.catch_warnings(action="ignore"):
    import polars as pl


RULE_DATA = json.loads(
    subprocess.run(
        ["ruff", "rule", "--all", "--output-format=json"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
)
RULES = {rule["code"]: rule["name"] for rule in RULE_DATA}


def expand_prefixes(prefixes: list[str]) -> list[str]:
    expanded_rules = []
    for prefix in prefixes:
        if prefix in RULES:
            expanded_rules.append(prefix)
        else:
            pat = re.compile(rf"{prefix}\d+")
            expanded_prefix = [rule for rule in RULES if pat.match(rule)]
            if len(expanded_prefix) == 0:
                print(f"skipping unknown prefix {prefix}")
            expanded_rules.extend(expanded_prefix)

    return expanded_rules


severity = {
    "correctness": 0,
    "suspicious": 1,
    "style": 2,
    "complexity": 3,
    "perf": 4,
    "pedantic": 5,
    "restriction": 6,
}


pl.Config.set_tbl_rows(-1)
pl.Config.set_tbl_cols(-1)
pl.Config.set_tbl_width_chars(-1)
pl.Config.set_fmt_str_lengths(1000)


def load_rules(path):
    return (
        pl
        .read_csv(path)
        .with_columns(
            pl
            .col("category")
            .replace_strict(severity, return_dtype=pl.Int8)
            .alias("_severity")
        )
        .sort("_severity", "rule")
    )


initial = load_rules("proposed.csv")
non_default = load_rules("off_by_default.csv")


# Potentially controversial rules that I suggest to keep in the proposed
# default set.
to_keep = expand_prefixes([
    # Some controversy on Discord, but I would lean toward keeping these, as I
    # commented on Notion.
    "F403",
    "F405",
    "F406",
    "F541",
])

# Rules in the initial proposal that we now want to remove.
to_remove = expand_prefixes([
    # I categorized these all as Style and there were various complaints about
    # them on Notion and Discord.
    "E401",
    "E402",
    "E701",
    "E702",
    "E703",
    "E711",
    "E712",
    "E713",
    "E714",
    "E731",
    "E741",
    "E742",
    "E743",
    # I categorized this as suspicious, but it has fairly severe known problems
    # in the docs
    "E721",
])

# Rules not in the initial proposal that we want to add in.
to_add = expand_prefixes([
    # These were all categorized as style or above
    "ASYNC100",
    "ASYNC105",
    "ASYNC115",
    "ASYNC116",
    "ASYNC210",
    "ASYNC220",
    "ASYNC221",
    "ASYNC222",
    "ASYNC230",
    "ASYNC251",
    # Suspicious
    "INT001",
    "INT002",
    "INT003",
    # Style/Complexity
    "C4",
    # Suspicious
    "DTZ",
])

# Rules not in the initial proposal that I think should stay that way.
to_exclude = expand_prefixes([
    # Third-party
    "AIR",
    "DJ",
    "FAST",
    "NPY",
    "PD",
    # I kind of like these personally, but they're divisive and annoying
    "EM101",
    "EM102",
    "EM103",
    # Documentation. I marked one of these (D418) as Style instead of Pedantic,
    # but on second thought I guess it's somewhat pedantic too, so just exclude
    # the whole set.
    "D",
    # Annotations
    "ANN",
    # Fixmes/todos
    "FIX",
    "TD",
    # I think ISC004 will be a better default rule, but the others felt
    # pedantic to me
    "ISC",
    # Doesn't do anything without configuring a list of imports
    "I002",
])

print("=== first draft ===")
# print(initial)

print("=== current non-default ===")

df = non_default.filter(
    pl.col("_severity") >= 5,
    ~pl.col("rule").is_in(to_add),
    ~pl.col("rule").is_in(to_exclude),
).sort("rule")

print(df)
