import polars as pl

from collections import Counter
from typing import Any, Self
from dataclasses import dataclass
import json
import subprocess
from pathlib import Path

REPOS = Path("/home/brent/astral/ruff/.repos")
RUFF = Path("./ruff.26230b1ed3").absolute()


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
    for repo in REPOS.iterdir():
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

        for rule in data:
            diag = Diagnostic.from_dict(repo, rule)
            counts[diag.code] += 1

    df = pl.from_dict({"code": counts.keys(), "ecosystem": counts.values()})

    df.write_csv("ecosystem.csv")

    with pl.Config(tbl_width_chars=100, tbl_rows=40):
        print(df.sort("ecosystem", descending=True))


if __name__ == "__main__":
    main()
