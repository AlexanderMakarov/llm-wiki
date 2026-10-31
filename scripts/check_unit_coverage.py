#!/usr/bin/env python3
"""Enforce the unit-suite line coverage floor after a pytest-cov run (#271).

Coverage.py ``fail_under`` uses the combined line+branch total when branches
are measured. CI enables ``--cov-branch`` for visibility, so this script gates
on **line** coverage only (the #280 baseline) and prints branch totals for the
log/artifact consumers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LINE_FLOOR = 87


def main() -> int:
    path = Path("coverage.json")
    if not path.is_file():
        print("coverage.json missing — run pytest with --cov-report=json:coverage.json", file=sys.stderr)
        return 1
    totals = json.loads(path.read_text(encoding="utf-8"))["totals"]
    stmts = totals["num_statements"]
    line_pct = 100.0 * totals["covered_lines"] / stmts if stmts else 100.0
    branches = totals["num_branches"]
    branch_pct = 100.0 * totals["covered_branches"] / branches if branches else 100.0
    print(
        f"Unit line coverage: {line_pct:.2f}% "
        f"({totals['covered_lines']}/{stmts}); "
        f"branch: {branch_pct:.2f}% ({totals['covered_branches']}/{branches})"
    )
    if line_pct + 1e-9 < LINE_FLOOR:
        print(
            f"ERROR: line coverage {line_pct:.2f}% is below the {LINE_FLOOR}% floor",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
