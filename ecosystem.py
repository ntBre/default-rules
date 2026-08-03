import re
import argparse
import logging
import random
import polars as pl

from collections import Counter, defaultdict
from typing import Any, Self
from dataclasses import dataclass
import json
import subprocess
from pathlib import Path

REPOS = Path("/home/brent/astral/ruff/.repos")
RUFF = Path("./ruff.26230b1ed3").absolute()

logger = logging.getLogger(__name__)


@dataclass
class Diagnostic:
    code: str

    # I really only need the `code` for the current analysis, but it could be
    # interesting to render these somewhere later.
    filename: str
    line: int
    column: int

    @classmethod
    def from_dict(cls, root: Path, d: dict[str, Any]) -> Self:
        path = Path(d["filename"])
        return cls(
            code=d["code"],
            filename=str(path.relative_to(root)),
            line=d["location"]["row"],
            column=d["location"]["column"],
        )


def main():
    counts = Counter()
    hits = defaultdict(list)
    for repo in REPOS.iterdir():
        logger.info("Running ruff on %s", repo)
        data = json.loads(
            # I also tried this without --isolated because of the huge number
            # of E501 hits, but I think in general we do want to ignore the
            # config to avoid filtering out ignored rules. I want to know which
            # rules are triggering whether or not the project considers the
            # violations intentional.
            subprocess.run(
                [
                    RUFF,
                    "check",
                    "--isolated",
                    "--no-cache",
                    "--select",
                    "ALL",
                    "--output-format=json",
                    "--exit-zero",
                ],
                text=True,
                check=True,
                capture_output=True,
                cwd=repo,
            ).stdout
        )

        branch = re.search(
            r"HEAD branch: (.*)$",
            subprocess.run(
                ["git", "remote", "show", "origin"],
                check=True,
                capture_output=True,
                text=True,
                cwd=repo,
            ).stdout,
            flags=re.MULTILINE,
        )

        assert branch is not None

        branch = branch[1]

        gh_owner, gh_repo = repo.name.split(":")

        for rule in data:
            diag = Diagnostic.from_dict(repo, rule)
            counts[diag.code] += 1
            hits[diag.code].append((
                f"https://github.com/{gh_owner}/{gh_repo}/blob/{branch}/{diag.filename}#L{diag.line}",
                f"{repo.name}:{diag.filename}:{diag.line}",
            ))

    df = pl.from_dict({"code": counts.keys(), "ecosystem": counts.values()})

    df.write_csv("ecosystem.csv")

    with pl.Config(tbl_width_chars=100, tbl_rows=40):
        print(df.sort("ecosystem", descending=True))

    with open("docs/ecosystem.html", "w") as f:
        f.write("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body>
        """)

        for code, links in hits.items():
            f.write(f'<h2 id="{code}">{code}</h2>\n<ul>')
            n = min(20, len(links))
            sample = random.sample(links, n)
            for link, path in sample:
                f.write(f'<li><a href="{link}">{path}</a></li>\n')
            f.write("</ul>\n")

        f.write("""
        </body>
        </html>
        """)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    if args.verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(level=level)

    main()
