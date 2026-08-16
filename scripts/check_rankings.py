"""Check whether the annual SCImago rankings need to be updated."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from pathlib import Path
import sys

try:
    from scripts.catalog import CatalogError, load_catalog
    from scripts.rankings import RankingsError, load_rankings
except ModuleNotFoundError:  # Direct execution from scripts/.
    from catalog import CatalogError, load_catalog
    from rankings import RankingsError, load_rankings


def stale_records(rankings: dict, *, as_of: date) -> list[dict]:
    """Return ranking records whose explicit refresh deadline has passed."""
    return sorted(
        (
            record
            for record in rankings["rankings"]
            if date.fromisoformat(str(record["refresh_due"])) < as_of
        ),
        key=lambda record: (
            str(record["refresh_due"]),
            record["journal_id"],
            record["source_id"],
            record["category"].casefold(),
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=root / "data" / "journals.yml")
    parser.add_argument("--rankings", type=Path, default=root / "data" / "rankings.yml")
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=datetime.now(timezone.utc).date(),
        help="check date in YYYY-MM-DD (defaults to today UTC)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        catalog = load_catalog(args.catalog)
        rankings = load_rankings(args.rankings, catalog)
    except (CatalogError, RankingsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    stale = stale_records(rankings, as_of=args.as_of)
    if stale:
        for record in stale:
            print(
                "update due: "
                f"{record['journal_id']} / {record['category']} "
                f"was due {record['refresh_due']}",
                file=sys.stderr,
            )
        print(
            "Refresh values manually from the cited SCImago pages; this command never scrapes or updates data.",
            file=sys.stderr,
        )
        return 1
    print(f"Ranking check passed for {len(rankings['rankings'])} journals.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
