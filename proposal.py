import re
import warnings
import json
import subprocess
import sqlite3

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


# update any modified categories
categories = load_categories()
initial = load_rules("proposed.csv", categories)
non_default = load_rules("off_by_default.csv", categories)


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
    # I thought these were pedantic because they only matter if you run a type
    # checker, but I realize now that they're only applied in .pyi files, so I
    # think it's okay to include them by default (and bump them up to Style).
    "PYI002",
    "PYI007",
    "PYI008",
    "PYI009",
    "PYI011",
    "PYI012",
    "PYI014",
    "PYI015",
    "PYI026",
    # This actually seems like a Complexity lint on second thought
    "SIM911",
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
    # I think these are correctly categorized as Pedantic (or lower)
    "COM8",
    "ERA001",
    "FBT",
    "ICN",
    ## all the rules suggesting pathlib over os
    "PTH100",
    "PTH107",
    "PTH114",
    "PTH121",
    "PTH206",
    "PTH101",
    "PTH108",
    "PTH115",
    "PTH122",
    "PTH207",  # and this one, pathlib over glob
    "PTH102",
    "PTH109",
    "PTH116",
    "PTH123",  # except this one, pathlib over builtin open
    "PTH208",
    "PTH103",
    "PTH110",
    "PTH117",
    "PTH202",
    "PTH211",
    "PTH104",
    "PTH111",
    "PTH118",
    "PTH203",
    "PTH105",
    "PTH112",
    "PTH119",
    "PTH204",
    "PTH106",
    "PTH113",
    "PTH120",
    "PTH205",
    "Q",
    ## Stylistic but direct overlap or conflict with the formatter
    "E101",
    "E501",
    "W191",
    "W505",  # Except arguably this one since it's for doc lines
    ## I'm very suspicious of these but arguably at least some of them could be
    ## in a higher category
    "S101",
    "S102",
    "S103",
    "S104",
    "S105",
    "S106",
    "S107",
    "S108",
    "S113",
    "S201",
    "S202",
    "S301",
    "S302",
    "S303",
    "S304",
    "S305",
    "S306",
    "S307",
    "S308",
    "S310",
    "S311",
    "S312",
    "S313",
    "S314",
    "S315",
    "S316",
    "S317",
    "S318",
    "S319",
    "S321",
    "S323",
    "S324",
    "S501",
    "S502",
    "S503",
    "S504",
    "S505",
    "S506",
    "S507",
    "S508",
    "S509",
    "S601",
    "S602",
    "S603",
    "S604",
    "S605",
    "S606",
    "S607",
    "S608",
    "S609",
    "S610",
    "S611",
    "S612",
    "S701",
    "S702",
    "S704",
    "C901",
    "PGH003",
    "PGH004",
    "T201",
    "T203",
    "TC001",
    "TC002",
    "TC003",
    "TC006",
    "TID251",
    "TID253",
    # These both seem pedantic, especially now that Zsolt updated the docs for
    # ASYNC110
    "ASYNC109",
    "ASYNC110",
    # This _sounds_ like a good idea from the rule name and description, but we
    # don't check for usage of the loop variable after the loop, so in my
    # opinion the rule either has critical false positives or is very pedantic
    "B007",
    # I think these are also quite pedantic, unlike many of the other B rules
    "B024",
    "B027",
    "B028",
    "B034",
    "B904",
    "B905",
    "B911",
    # These feel pedantic to me but could arguably Style or even Perf
    "SLOT",
    # This obviously could be Perf, but the caveats around Python versions and
    # other considerations in the docs makes it feel overly Pedantic to me
    "PERF203",
    # Arguably Style, but the code will generally work fine
    "INP001",
    # Arguably Style, but I personally dislike this rule, or at least its
    # interaction with TRY400 (#4136)
    "LOG007",
    # Pedantic naming
    "PLC0105",
    # Technically in PEP 8, but I think there are enough legitimate cases to
    # consider this Pedantic
    "PLC0415",
    # Feels overly pedantic to me but could be Style
    "PLC1802",
    "PLC2403",
    # too-many-* rules
    "PLR09",
    # These all seem Pedantic
    "PLR2004",
    "PLW0603",
    "PLW1641",
    "PLW3301",
    # I'm open to including PT rules in general, but these all seem very
    # pedantic for defaults
    "PT001",
    "PT002",
    "PT003",
    "PT006",
    "PT007",
    "PT008",
    "PT011",
    "PT013",
    "PT018",
    "PT021",
    "PT023",
    "PT030",
    # I still think these PYI rules are pedantic because they apply to .py
    # files too
    "PYI024",
    "PYI034",
    "PYI050",
    "PYI056",
    # These two only apply to .pyi files but still seem very pedantic
    "PYI053",
    "PYI054",
    # These feel Pedantic to me but could be Style if we feel they're idiomatic
    # enough
    "RET502",
    "RET503",
    # Stylistic and also not very accurate without type inference
    "RSE102",
    # I think this one is pretty severe but our accuracy isn't high enough to
    # put it above Pedantic
    "RUF006",
    # This also feels Pedantic
    "RUF043",
    # These feel quite Pedantic, maybe SIM910 a little less so
    "SIM108",
    "SIM109",
    "SIM112",
    "SIM116",
    "SIM212",
    "SIM300",
    "SIM910",
    # Kind of reasonable but not accurate enough
    "SLF001",
    # Pedantic and very common in the ecosystem
    "TRY003",
    # Also kind of annoying (see LOG007 above)
    "TRY400",
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

df.write_csv("tmp.csv")
