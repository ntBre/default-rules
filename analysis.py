#!/usr/bin/env python
# coding: utf-8

# In[1]:


import warnings

warnings.filterwarnings("ignore", message=r".*GIL", category=RuntimeWarning)


# In[2]:


import json
import re
import subprocess

import polars as pl

pl.Config.set_tbl_rows(-1)
pl.Config.set_tbl_cols(-1)
pl.Config.set_fmt_str_lengths(1000);


# In[3]:


RUFF = "./ruff.26230b1ed3"
linter_data = json.loads(
    subprocess.run(
        [RUFF, "linter", "--output-format=json"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
)
linters = {linter["name"]: linter["prefix"] for linter in linter_data}
rule_data = json.loads(
    subprocess.run(
        [RUFF, "rule", "--all", "--output-format=json"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
)
rules = {rule["code"]: rule["name"] for rule in rule_data}
rule_to_linter = {rule["code"]: linters[rule["linter"]] for rule in rule_data}


# In[4]:


ecosystem = pl.read_csv("ecosystem.csv")


# ## Rule candidates

# In[5]:


full = (
    pl
    .read_csv("out.csv")
    .with_columns(
        (
            pl.col("accuracy")
            + 2 * pl.col("severity")
            + 0.5 * pl.col("fixability")
            + pl.col("applicability")
            + pl.col("configuration")
            + pl.col("conflicts")
        ).alias("total"),
        pl.col("rule").replace_strict(rule_to_linter).alias("linter"),
        pl.col("rule").replace_strict(rules).alias("name"),
    )
    .join(ecosystem.with_columns(pl.col("code").alias("rule")), on="rule", how="left")
    .with_columns(pl.col("ecosystem").fill_null(0))
    .drop("code")
)


# In[6]:


full.filter(
    pl.col("total") >= 9,
    pl.col("type") == "Stable",
).height


# In[7]:


full.filter(
    pl.col("accuracy") == 2,
    pl.col("total") >= 9,
    pl.col("type") == "Stable",
).height


# In[8]:


# Just requiring a total score >= 9 doesn't really narrow things down enough, even with
# a required accuracy of 2 and limiting to stable rules. Let's impose a few more constraints
# such as no conflicts or redundancy with other tools, a high applicability, and also a high
# severity. This actually requires a total score >= 10 so the >= 9 check is now redundant.
#
# Expanding the applicabilty range to >= 1 just pulls in the pytest rules. pytest was basically
# (maybe literally) the only library I considered widespread enough to warrant a 1.
#
# 197 seems like a pretty reasonable number of default rules (out of 938), just percentage-wise.
df = full.filter(
    pl.col("accuracy") == 2,
    pl.col("type") == "Stable",
    pl.col("conflicts") == 2,
    pl.col("applicability") == 2,
    pl.col("severity") == 2,
)
df.sort("rule")


# ## Comparison with current defaults

# In[9]:


# fmt: off
current_defaults = [
    "E401",	    "E742",	    "F504",	    "F602",	    "F811",
    "E712",	    "F404",	    "F521",	    "F634",	    "F901",
    "E741",	    "F503",	    "F601",	    "F722",	    "E711",
    "F403",	    "F509",	    "F633",	    "F842",	    "E731",
    "F502",	    "F541",	    "F707",	    "E703",	    "F402",
    "F508",	    "F632",	    "F841",	    "E722",	    "F501",
    "F525",	    "F706",	    "E702",	    "F401",	    "F507",
    "F631",	    "F823",	    "E721",	    "F407",	    "F524",
    "F704",	    "E701",	    "E902",	    "F506",	    "F622",
    "F822",	    "E714",	    "F406",	    "F523",	    "F702",
    "E402",	    "E743",	    "F505",	    "F621",	    "F821",
    "E713",	    "F405",	    "F522",	    "F701",
]
# fmt: on
len(current_defaults)


# In[10]:


in_defaults = pl.col("rule").is_in(current_defaults)
len(df.filter(in_defaults))


# In[11]:


missing_current_defaults = set(current_defaults) - set(df["rule"])
len(missing_current_defaults)


# In[12]:


# looks like these all got filtered out for severity == 1.
# I don't have any strong opposition to these and would probably lean toward
# including them to make the new default set a superset of the existing defaults.
full.filter(pl.col("rule").is_in(missing_current_defaults)).sort("rule")


# In[13]:


# looks like these were filtered out for accuracy = 1, I think I was
# probably too harsh here. There's an open bug report from dscorbett
# with a false negative, which is the only reason I can identify for this
full.filter(pl.col("rule").is_in(("A001", "A003")))


# In[14]:


# the ASYNC rules feel kind of out of place to me as defaults,
# not all projects are going to write any async code. I think
# we could consider revising the Applicability rubric to something like:
# - 2) widely used stdlib types
# - 1) "Niche" stdlib types or very widely used third-party
# - 0) Niche third-party
df.filter(pl.col("linter") == "ASYNC")


# In[15]:


# Similarly, the EXE rules probably shouldn't be default
# because they don't even do anything on Windows, and many
# projects may not have any executable Python scripts.
df.filter(pl.col("linter") == "EXE")


# ## Comparison with Dylan's rules

# In[16]:


# fmt: off
prefixes = [
    "YTT",		"SIM103",	"PLE01",	"E7",		"PLE0116",
    "B",		"D419",		"PLE0604",	"PLW0406",	"F701",
    "A",		"F541",		"PLE1310",	"F4",		"F702",
    "C4",		"F601",		"PLE25",	"ARG",		"F703",
    "UP",		"F602",		"PLR5501",	"F8",		"F704",
    "ISC004",	"F631",		"PLW0120",	"PLE0117",	"F705",
    "PIE794",	"F632",		"PLW0129",	"PLE0118",	"F706",
    "PIE796",	"PLC2801",	"PLW0245",	"PLE02",	"F707",
    "PYI",		"PLC1901",	"RUF047",	"PLE4703",	"F722",
]
# fmt: on


def expand_prefixes(prefixes):
    dylan_rules = []
    for prefix in prefixes:
        if prefix in rules:
            dylan_rules.append(prefix)
        else:
            pat = re.compile(rf"{prefix}\d+")
            expanded_prefix = [rule for rule in rules if pat.match(rule)]
            if len(expanded_prefix) == 0:
                print(f"skipping unknown prefix {prefix}")
            dylan_rules.extend(expanded_prefix)

    return dylan_rules


dylan_rules = set(expand_prefixes(prefixes))
len(dylan_rules)


# ### Rules we both included

# In[17]:


df.filter(pl.col("rule").is_in(dylan_rules))


# ### Rules I included but Dylan didn't

# In[18]:


df.filter(~pl.col("rule").is_in(dylan_rules))


# ### Rules Dylan included but I didn't
# 
# For a bit of stream-of-consciousness commentary here:
# 
# - I'm happy to include YTT202, it just has low applicability because it's an old third-party library
# - For most of the B rules with low Accuracy, I think I may have been overly harsh by focusing on open issues
#   - I don't think open bug reports are really inherent issues and these could be good in general
# - The B rules with low Severity seem accurate to me, but these may be unidiomatic enough to warrant defaults
# - The C4 rules, similarly, deal with idioms but probably highly preferable ones
# - I gave PYI low Applicability because most projects aren't stubs and many of them are stylistic
# - SIM103 was also low Severity but another style I like
# - E701-3 I filtered out for redundancy with the formatter, and the other E rules are stylistic
# - I gave D419 a very low severity, but it actually does seem like a potential mistake, I think I'll steal that one
# - F541 also seems like a potential error on second thought, as does PLE0237
# - PLR5501 is also an idiom but another good one
# - I filtered out many of the `UP` rules for being stylistic and depending on `target-version`, but like I note below,
#   I like these rules and would be happy to include them

# In[19]:


full.filter(pl.col("rule").is_in(dylan_rules)).join(df, on="rule", how="anti").filter(
    pl.col("type") == "Stable"
)


# ## Proposed defaults

# In[20]:


filter_out_linters = [
    # See above, not all projects use async
    "ASYNC",
    # Similarly, not all projects have executable files, and
    # these rules don't do anything on some systems (Windows)
    "EXE",
    # These are related to text translations, which also doesn't
    # seem relevant for most projects
    "INT",
]

filter_out_rules = [
    # ambiguous-unicode-character rules, these seem too noisy
    # for non-english text and possibly some mathematical code too
    "RUF001",
    "RUF002",
    "RUF003",
]

additional_rules = [
    # I was overly harsh on false negative reports, and I think
    # it makes sense to enable all of the A rules
    "A001",
    "A003",
    # An empty docstring does seem like a likely mistake
    "D419",
    # As does an f-string without placeholders
    "F541",
    # And invalid syntax in an annotation
    "F722",
    # Known false negatives, but a runtime error to violate
    "PLE0237",
]

# I haven't filtered these out yet, just flagging them for additional input
questionable_rules = [
    # This is pretty niche actually, not sure it's worth including
    "FURB163",
    # These have known false positives with the `loguru` library because
    # it uses `{}` for formatting instead of `%`. I'm not sure exactly how
    # common loguru is, but we get reports about it pretty often.
    "PLE1205",
    "PLE1206",
    # These two feel _kind of_ opinionated to me, I definitely wouldn't oppose
    # dropping them.
    "PLW1509",
    "PLW1510",
]

# I also haven't filtered these out yet, but they seem like they could be
# caught by a type checker (and probably should have Conflicts = 1)
typing_related = [
    "PLE1507",
    "RUF016",
    # ty actually doesn't flag this for some reason:
    # https://play.ty.dev/5d89172d-0df3-43de-a91a-1aa9d3d23516
    #
    # but I think it should trigger:
    # https://docs.astral.sh/ty/reference/rules/#positional-only-parameter-as-kwarg
    "RUF026",
]

# I think these are already in the list, but make sure to include them because
# they correspond to syntax errors. See the appendix for some additional notes.
syntax_errors = [
    "F404",
    "F407",
    "F622",
    "F701",
    "F702",
    "F704",
    "F706",
    "F707",
    "PLE0115",
    "PLE0116",
    "PLE0117",
    "PLE0118",
    "PLE1142",
    "PLE1700",
]

filtered = df.filter(
    ~pl.col("linter").is_in(filter_out_linters),
    ~pl.col("rule").is_in(filter_out_rules),
)

proposed = (
    pl
    .concat(
        [
            filtered,
            full.filter(pl.col("rule").is_in(missing_current_defaults)),
            full.filter(pl.col("rule").is_in(additional_rules)),
            full.filter(pl.col("rule").is_in(syntax_errors)),
        ],
        how="vertical",
    )
    .unique()
    .sort("rule")
)

proposed


# In[21]:


def to_url(rule: str) -> str:
    return f"[{rule}](https://docs.astral.sh/ruff/rules/{rule})"


def export_config():
    return pl.Config(
        tbl_formatting="MARKDOWN",
        tbl_hide_column_data_types=True,
        tbl_hide_dataframe_shape=True,
        tbl_width_chars=-1,
    )


with export_config(), open("rules.md", "w") as f:
    print(
        proposed.select("rule", pl.col("name").map_elements(to_url).alias("name")),
        file=f,
    )


# ## Off-by-default
# 
# This section covers the rules that are not enabled by default in the proposal above.
# To make it slightly more tractable, I also filtered out the 154 rules that are in preview.

# In[22]:


off_by_default = full.join(proposed, on="rule", how="anti")
total_off_by_default = off_by_default.height
stable_off_by_default = off_by_default.filter(pl.col("type") == "Stable")
print("Preview off by default", total_off_by_default - stable_off_by_default.height)

with export_config(), open("off_by_default.md", "w") as f:
    print(
        stable_off_by_default.select(
            "rule",
            pl.col("name").map_elements(to_url).alias("name"),
            "accuracy",
            "severity",
            "fixability",
            "applicability",
            "configuration",
            "conflicts",
        ).sort("rule"),
        file=f,
    )

stable_off_by_default.sort("rule")


# ## Appendix

# In[23]:


def by_linter(linter):
    return pl.col("linter").is_in((linter,)) & (pl.col("type") == "Stable")


# ### `FURB163`
# 
# I was curious why only this FURB rule appeared in my list of rule candidates.
# I guess it's because it had the only severity of 2, which I assigned based on
# the fact that manually providing the base can produce less accurate results,
# according to our docs.
# 
# The other FURB rules also scored highly but were filtered out for being less severe.
# 
# This feels fairly niche and unlikely to cause errors that are too substantial, so
# I definitely wouldn't be opposed to removing this from the set.

# In[24]:


full.filter(by_linter("FURB"))


# ### LOG001
# 
# Like `FURB163`, this is the only rule from its linter included, and I think the reason is the same.
# Our docs excerpt from the Python docs:
# 
# > Note that Loggers should _NEVER_ be instantiated directly
# 
# I considered the other LOG rules less severe.

# In[25]:


full.filter(by_linter("LOG"))


# ### Syntax Errors
# 
# As Dylan noted, we should just remove these rules and make them syntax errors at some point.
# Making them default may be a good step in that direction? 
# 
# `E999` is literally a syntax error obviously, but we removed it. `F722` is also literally a
# syntax error, but I consider it a bit different since it's not evaluated by CPython at runtime.

# In[26]:


def red(text):
    return f"\x1b[31;1m{text}\x1b[0m"


syntax_error = re.compile(r"syntax.*error", flags=re.IGNORECASE)
non_errors = ["B017", "PIE790", "E999", "F722", "FURB116"]
true_errors = [
    "F404",
    "F407",
    "F622",
    "F701",
    "F702",
    "F704",
    "F706",
    "F707",
    "PLE0115",
    "PLE0116",
    "PLE0117",
    "PLE0118",
    "PLE1142",
    "PLE1700",
]
for rule in (
    rule
    for rule in rule_data
    if syntax_error.search(rule["explanation"])
    and rule["code"] not in non_errors
    and rule["code"] not in true_errors
):
    print(rule["name"], "-", rule["code"])
    print(syntax_error.sub(red("SyntaxError"), rule["explanation"]))
    print("=" * 80)


# ### UP
# 
# It looks like I filtered the UP rules pretty aggressively, I think because
# many of them either won't work or won't work properly unless the `target-version` 
# is configured. I personally quite like these rules and would be happy enabling ~all 
# of them by default, but I was conservative with the scoring here.

# ## Categories
# 

# In[27]:


# code is outright wrong or useless, and you should try to fix it
correctness = [
    # This is essentially textbook correctness, ++x or --x are generally going to be useless
    # in Python
    "B002",
    # This one feels very borderline. The code might be working as written but I think
    # it's likely enough to be wrong to call it correctness
    "B004",
    # Useless, it's in the name
    "B015",
    # Runtime TypeError
    "B016",
    # Memory leak
    "B019",
    # I think this warrants correctness because it renders the docstring
    # mostly useless
    "B021",
    "B022",
    "B025",
    "B029",
    "B030",
    "B031",
    "B032",
    "B035",
    # Useless empty docstring (clippy calls this suspicious)
    "D419",
    # This one should probably not be a lint rule at all, just a separate io-error
    "E902",
    "F401",
    # Syntax errors
    "F404",
    "F407",
    # I think these are all runtime errors
    "F50",
    "F52",
    # Similar to B035
    "F601",
    "F602",
    "F621",
    # Syntax error
    "F622",
    "F631",
    "F633",
    "F634",
    # Syntax errors
    "F701",
    "F702",
    "F704",
    "F706",
    "F707",
    # Unused and undefined names
    "F8",
    # Useless? And the alternative is more precise
    "FURB163",
    # Python docs say you should "NEVER" do this
    "LOG001",
    "PIE794",
    "PIE796",
    "PLC0131",
    "PLC0132",
    "PLC0205",
    "PLE0100",
    "PLE0101",
    # Syntax errors
    "PLE0115",
    "PLE0116",
    "PLE0117",
    "PLE0118",
    # This is a runtime error but possibly not accurate enough
    # without access the parent classes
    "PLE0237",
    # Also covered more reliably by ty but still a runtime error
    "PLE0241",
    # These will cause runtime errors when using a star import, so I guess
    # they're either useless or wrong
    "PLE0604",
    "PLE0605",
    # analogous to clippy's out_of_bounds_indexing, also correctness
    "PLE0643",
    "PLE0704",
    "PLE1132",
    "PLE1142",
    "PLE1205",
    "PLE1206",
    "PLE1300",
    "PLE1307",
    "PLE1507",
    "PLE1700",
    # I'm going to mark these as correctness, like clippy's invisible_characters
    "PLE2510",
    "PLE2512",
    "PLE2513",
    "PLE2514",
    "PLE2515",
    "PLR0133",
    "PLR0206",
    "PLW0120",
    "PLW0127",
    "PLW0128",
    "PLW0129",
    "PLW0133",
    # this is a compiler warning in rust, not a lint
    "PLW0177",
    "PLW0245",
    "PLW0406",
    "PLW0602",
    "PLW0604",
    "PLW1501",
    "PLW2101",
    "PTH210",
    "PYI016",
    # unused private stuff
    "PYI018",
    "PYI046",
    "PYI047",
    "PYI049",
    "PYI062",
    "RUF016",
    "RUF026",
    "RUF028",
    "RUF030",
    "RUF033",
    "RUF034",
    "RUF040",
    "RUF049",
    "RUF053",
    "RUF059",
    "RUF100",
    "RUF101",
    "RUF200",
    "T100",
    "TC004",
    "TC007",
    "TC010",
    "W605",
]
# it might be possible that the linted code is intentionally written like it is
suspicious = [
    # I think it's possible to violate all of these without causing immediate errors,
    # so they are only suspicious
    "A",
    # Similar lints are from rustc rather than clippy in Rust, but in Python, I think
    # these are probably relegated to suspicious because it's always possible that
    # the arguments are needed for something that we can't detect, especially in Ruff
    "ARG",
    # Updating the env could be exactly what you want, it just looks suspicious
    "B003",
    "B005",
    # This could also be working correctly, even though this is a SyntaxWarning in 3.14+.
    # PEP 765 describes that making this a SyntaxError was rejected in PEP 601, which seems
    # like evidence to me that this is only suspicious.
    "B012",
    "B017",
    "B020",
    # I think these two could be more suspicious than the other E rules
    "E721",
    "E722",
    "F402",
    # Going with suspicious for now, but I can see it being lower
    "F541",
    "F632",
    # This is kind of a syntax error but not evaluated at runtime, possibly there
    # are cases where you want this
    "F722",
    # Not really sure where to put this, raising the wrong exception for the use case.
    # It doesn't really seem like a correctness or even suspicious lint, but style
    # doesn't feel right either.
    "F901",
    # I _think_ these are only suspicious and won't cause any outright errors
    # in general
    "PLE0302",
    "PLE0303",
    "PLE0305",
    "PLE0307",
    "PLE0308",
    "PLE0309",
    "PLE1310",
    "PLE2502",
    # only suspicious, unlike PLR0133 because there could be something weird
    # with __eq__
    "PLR0124",
    "PLR1704",
    "PLR1722",
    # this could arguably be style, but using := requires parens, which seems
    # to elevate the issue to me
    "PLW0131",
    "PLW0711",
    "PLW1507",
    "PLW1508",
    "PLW1509",
    "PLW1510",
    "PLW2901",
    "PYI006",
    # deprecation
    "PYI057",
    "PYI059",
    "RUF018",
    "RUF048",
    "SIM107",
    "TRY300",
    # more deprecations
    "UP005",
    "UP019",
    "UP021",
    "UP023",
    "UP024",
    "UP035",
    "UP036",
    "UP041",
    "YTT101",
    "YTT102",
    "YTT103",
    "YTT201",
    "YTT203",
    "YTT204",
    "YTT301",
    "YTT302",
    "YTT303",
]
# code that can be written in a shorter and more readable way, while preserving the semantics
complexity = []
# increase the performance of your code
perf = []
# mostly about writing idiomatic code
style = [
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
    # These are the ambiguous name rules, which might even go in a lower category
    # like pedantic or restriction
    "E741",
    "E742",
    "E743",
    # Arguably even lower in severity, but it is advised by PEP 8. These could also be
    # argued to a higher severity currently since Ruff really can't do much for
    # undefined variables in the presence of star imports without being able to
    # resolve them.
    "F403",
    "F405",
    "F406",
]
# Lints in this group are designed to be pedantic and false positives sometimes
# are intentional in order to prevent false negatives
pedantic = []
# restrict you from using certain parts of the language
restriction = []

covered = expand_prefixes(
    correctness + suspicious + complexity + perf + style + pedantic + restriction
)

assert len(set(covered)) == len(covered), "Duplicate rule found"

rest = proposed.filter(
    ~pl.col("linter").is_in(covered),
    ~pl.col("rule").is_in(covered),
)

assert len(covered) + rest.height == proposed.height, "Missing rules"


class Category:
    def __init__(
        self, correctness, suspicious, complexity, perf, style, pedantic, restriction
    ):
        self.correctness = expand_prefixes(correctness)
        self.suspicious = expand_prefixes(suspicious)
        self.complexity = expand_prefixes(complexity)
        self.perf = expand_prefixes(perf)
        self.style = expand_prefixes(style)
        self.pedantic = expand_prefixes(pedantic)
        self.restriction = expand_prefixes(restriction)

    def assign(self, rule: str) -> str:
        if rule in self.correctness:
            return "correctness"
        elif rule in self.suspicious:
            return "suspicious"
        elif rule in self.complexity:
            return "complexity"
        elif rule in self.perf:
            return "perf"
        elif rule in self.style:
            return "style"
        elif rule in self.pedantic:
            return "pedantic"
        elif rule in self.restriction:
            return "restriction"
        else:
            raise ValueError(f"rule {rule} not assigned to any category")


category = Category(
    correctness,
    suspicious,
    complexity,
    perf,
    style,
    pedantic,
    restriction,
)


# ## Export HTML

# In[28]:


# Generate HTML for off-by-default rules
from generate_html import generate_html_table, generate_index_page

generate_html_table(
    proposed.select(
        "rule",
        "name",
        pl
        .col("rule")
        .map_elements(category.assign, return_dtype=pl.String)
        .alias("category"),
        "accuracy",
        "severity",
        "fixability",
        "applicability",
        "configuration",
        "conflicts",
        "ecosystem",
    ).sort("rule"),
    "Proposed Default Ruff Rules",
    "docs/on_by_default.html",
)

generate_html_table(
    stable_off_by_default.select(
        "rule",
        "name",
        "accuracy",
        "severity",
        "fixability",
        "applicability",
        "configuration",
        "conflicts",
        "ecosystem",
    ).sort("rule"),
    "Off-by-Default Ruff Rules",
    "docs/off_by_default.html",
)

# Generate index page
generate_index_page()

