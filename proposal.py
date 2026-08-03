import tomli_w
import tomllib
from generate_html import generate_html_table, generate_index_page
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
STABLE_RULES = {
    rule["code"] for rule in RULE_DATA if next(iter(rule["status"])) == "Stable"
}
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
    # I marked these all as Correctness and still think that's accurate
    "B014",
    "B033",
    "EXE001",
    "EXE002",
    "EXE004",
    "EXE005",
    "FA102",
    "G101",
    "PGH005",
    "PT010",
    "PT014",
    "PT025",
    "PT026",
    "PYI010",
    "PYI035",
    # I'm including these mutable default rules somewhat tentatively. They are
    # definitely problems when detected accurately, but I think we may need
    # better type inference before we enable them by default.
    "B006",
    "B008",
    "B039",
    "RUF008",
    "RUF009",
    "RUF012",
    "RUF024",
    # This is kind of like a mutable default and also severe when detected
    # accurately, but it has some significant open issues
    "B023",
    # Miscellaneous Suspicious rules missing from the first draft
    "B011",
    "B018",
    "BLE001",
    "EXE003",
    "LOG002",
    "LOG009",
    "LOG014",
    "PLE1520",
    "PT012",
    "PT020",
    "PT028",
    "PT031",
    "PTH124",
    "PYI003",
    "PYI004",
    "PYI005",
    "PYI017",
    "PYI036",
    "PYI045",
    "PYI051",
    "S110",
    "S112",
    "SIM115",
    "SIM220",
    "SIM221",
    "UP026",
    "YTT202",
    # not sure about these, could be pedantic
    "RUF001",
    "RUF002",
    "RUF003",
    # Perf rules that seem reasonable. I don't think these are strictly Perf
    # and could fit into Complexity or Style as well if they don't improve
    # "performance" per se
    "PERF101",
    "PERF102",
    "PERF401",
    "PERF403",
    "PLC0208",
    "RUF015",
    "RUF017",
    # Complexity: I think these are all pretty clear simplifications
    "FURB116",
    "FURB161",
    "FURB162",
    "FURB166",
    "FURB168",
    "FURB169",
    "PERF402",
    "PLC0206",
    "PLC0414",
    "PLC3002",
    "PLR0402",
    "RUF046",
    "RUF051",
    "RUF057",
    "RUF058",
    "SIM101",
    "SIM102",
    "SIM103",
    "SIM110",
    "SIM113",
    "SIM114",
    "SIM117",
    "SIM118",
    "SIM201",
    "SIM202",
    "SIM208",
    "SIM210",
    "SIM211",
    "SIM222",
    "SIM223",
    "SIM401",
    "SIM905",
    "TRY201",
    "TRY203",
    "TRY301",
    "UP029",
    "UP034",
    "UP043",
    "UP044",
    "UP045",
    "UP046",
    "UP047",
    # I categorized these as Style lints and think they make sense to include
    "B009",
    "B010",
    "B013",
    "B026",
    "FA100",
    "FLY002",
    "FURB105",
    "FURB122",
    "FURB129",
    "FURB132",
    "FURB136",
    "FURB157",
    "FURB167",
    "FURB177",
    "FURB181",
    "FURB187",
    "FURB188",
    "G001",
    "G002",
    "G003",
    "G004",
    "G010",
    "G201",
    "G202",
    "I001",
    "LOG015",
    "N801",
    "N802",
    "N803",
    "N804",
    "N805",
    "N806",
    "N807",
    "N811",
    "N812",
    "N813",
    "N814",
    "N815",
    "N816",
    "N817",
    "N818",
    "N999",
    "PIE790",
    "PIE800",
    "PIE804",
    "PIE807",
    "PIE808",
    "PIE810",
    "PLC2401",
    "PLE1519",
    "PLR1711",
    "PLR1714",
    "PLR1716",
    "PLR1730",
    "PLR1733",
    "PLR1736",
    "PLR2044",
    "PLR5501",
    "PLW0211",
    "PLW0642",
    "PTH201",
    "PYI001",
    "PYI013",
    "PYI019",
    "PYI020",
    "PYI021",
    "PYI025",
    "PYI029",
    "PYI030",
    "PYI032",
    "PYI033",
    "PYI041",
    "PYI042",
    "PYI043",
    "PYI044",
    "PYI048",
    "PYI052",
    "PYI055",
    "PYI058",
    "PYI061",
    "PYI063",
    "PYI064",
    "PYI066",
    "RET501",
    "RET504",
    "RET505",
    "RET506",
    "RET507",
    "RET508",
    "RUF005",
    "RUF007",
    "RUF010",
    "RUF013",
    "RUF019",
    "RUF020",
    "RUF021",
    "RUF022",
    "RUF023",
    "RUF032",
    "RUF041",
    "SIM105",
    "TC005",
    "TID252",
    "TRY002",
    "TRY004",
    "TRY401",
    "UP001",
    "UP003",
    "UP004",
    "UP006",
    "UP007",
    "UP008",
    "UP009",
    "UP010",
    "UP011",
    "UP012",
    "UP013",
    "UP014",
    "UP015",
    "UP017",
    "UP018",
    "UP020",
    "UP022",
    "UP025",
    "UP028",
    "UP030",
    "UP031",
    "UP032",
    "UP033",
    "UP037",
    "UP039",
    "UP040",
    "UP049",
    "UP050",
])

# Rules not in the initial proposal that I think should stay that way.
to_exclude = expand_prefixes([
    # Third-party
    "AIR",
    "DJ",
    "FAST",
    "NPY",
    "PD002",
    "PD003",
    "PD004",
    "PD007",
    "PD008",
    "PD009",
    "PD010",
    "PD011",
    "PD012",
    "PD013",
    "PD015",
    "PD101",
    # I kind of like these personally, but they're divisive and annoying
    "EM101",
    "EM102",
    "EM103",
    # Documentation. I marked one of these (D418) as Style instead of Pedantic,
    # but on second thought I guess it's somewhat pedantic too, so just exclude
    # the whole set. We do have to be slightly careful to avoid D419, which I
    # proposed including in the default set
    "D1",
    "D2",
    "D3",
    "D40",
    "D410",
    "D411",
    "D412",
    "D413",
    "D414",
    "D415",
    "D416",
    "D417",
    "D418",
    # Annotations
    "ANN001",
    "ANN002",
    "ANN003",
    "ANN201",
    "ANN202",
    "ANN204",
    "ANN205",
    "ANN206",
    "ANN401",
    # Fixmes/todos
    "FIX",
    "TD",
    # I think ISC004 will be a better default rule, but the others felt
    # pedantic to me
    "ISC001",
    "ISC002",
    "ISC003",
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
    "W291",
    "W292",
    "W293",
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
    "PLR0911",
    "PLR0912",
    "PLR0913",
    "PLR0915",
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
    # Recategorized these from Style to Pedantic at the last minute. I don't
    # think they even check that pytest is imported, and PT015, for example,
    # triggers on any falsey assertion, even just a top-level `assert False`
    "PT009",
    "PT015",
    "PT016",
    "PT017",
    "PT019",
    "PT022",
    "PT024",
    "PT027",
])

# print("=== first draft ===")
# print(initial)

# print("=== current non-default ===")


# df = non_default.filter(
#     pl.col("_severity") == 2,
#     ~pl.col("rule").is_in(to_add),
#     ~pl.col("rule").is_in(to_exclude),
#     # pl.col("name").str.contains(r"mutable-.*-default.*"),
# ).sort("_severity", "rule")

# check that we haven't ignored too many rules and that everything still adds
# up to the total
# S = set(to_add) | set(to_exclude)
# non_default_rules = set(non_default.select("rule").to_series().to_list())
# missing_entirely = sorted(S - non_default_rules)
# if missing_entirely:
#     print(missing_entirely)
# assert non_default.height == len(to_add) + len(to_exclude) + df.height

# print(df)

# df.write_csv("tmp.csv")

assert initial.height + non_default.height == len(STABLE_RULES)

all_rules = pl.concat([initial, non_default], how="vertical")
assert all_rules.height == len(STABLE_RULES)

# Initial rules to keep (this is a no-op for consistency)
to_keep = all_rules.filter(pl.col("rule").is_in(to_keep))
# Initial rules to remove
to_remove = all_rules.filter(pl.col("rule").is_in(to_remove))
# Rules to add
to_add = all_rules.filter(pl.col("rule").is_in(to_add))
# Rules to continue excluding
to_exclude = all_rules.filter(pl.col("rule").is_in(to_exclude))


def to_url(rule: str) -> str:
    return f"[{rule}](https://docs.astral.sh/ruff/rules/{rule})"


def print_df(df):
    with pl.Config(
        tbl_formatting="MARKDOWN",
        tbl_hide_column_data_types=True,
        tbl_hide_dataframe_shape=True,
        tbl_width_chars=-1,
    ):
        print(df.height)
        print(
            df
            .drop("_severity")
            .with_columns(pl.col("name").map_elements(to_url))
            .sort("rule")
        )


# print_df(to_remove)

initial_minus_removed = initial.join(to_remove, on="rule", how="anti")
# print_df(initial_minus_removed)

added_correctness = to_add.filter(pl.col("category") == "correctness")
# print_df(added_correctness)

added_suspicious = to_add.filter(pl.col("category") == "suspicious")
# print_df(added_suspicious)

added_complexity = to_add.filter(pl.col("category") == "complexity")
# print_df(added_complexity)

added_perf = to_add.filter(pl.col("category") == "perf")
# print_df(added_perf)

added_style = to_add.filter(pl.col("category") == "style")
# print_df(added_style)

new_proposal = pl.concat(
    [
        initial_minus_removed,
        added_correctness,
        added_suspicious,
        added_complexity,
        added_perf,
        added_style,
    ],
    how="vertical",
)

excluded_pedantic = to_exclude.filter(pl.col("category") == "pedantic")
# print_df(excluded_pedantic)

excluded_restriction = to_exclude.filter(pl.col("category") == "restriction")
# print_df(excluded_restriction)

all_excluded = pl.concat(
    [
        to_remove,
        excluded_pedantic,
        excluded_restriction,
    ],
    how="vertical",
)

print(len(RULES), "total rules")
print(len(STABLE_RULES), "stable rules")
print(new_proposal.height, "proposed default rules")
print(all_excluded.height, "proposed non-default rules")
print(new_proposal.height + all_excluded.height)

df = pl.concat([new_proposal, all_excluded], how="vertical")

assert df.height == len(STABLE_RULES), df.height


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


generate(new_proposal, "Default Rules v2", "docs/on_by_default_v2.html")
generate(all_rules, "All Rules", "docs/all_rules.html")
generate_index_page()


with open("proposal.toml", "wb") as f:
    tomli_w.dump(
        {"lint": {"select": sorted([row[0] for row in new_proposal.iter_rows()])}}, f
    )
