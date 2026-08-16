"""Generate the README catalog and OPML subscription files."""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

try:
    from scripts.catalog import CatalogError, load_catalog
    from scripts.rankings import RankingsError, load_rankings
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from catalog import CatalogError, load_catalog
    from rankings import RankingsError, load_rankings


START_MARKER = "<!-- catalog:start -->"
END_MARKER = "<!-- catalog:end -->"
SCOPE_LABELS = {
    "current_issue": "current issue",
    "advance_articles": "advance articles",
    "all_new_content": "all new content",
    "highlights": "highlights",
}
STATUS_LABELS = {
    "working": "working",
    "limited": "works with limits",
    "not_found": "not found",
}
GROUPS = (
    ("economics", "Economics"),
    ("finance", "Finance"),
    ("econometrics", "Econometrics"),
)


def _markdown(text: object) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _date_text(value: object) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _current_sjr_index(rankings: dict | None) -> dict[str, Decimal]:
    """Return each journal's SJR from its latest current source edition."""
    if not rankings:
        return {}
    source_map = {source["id"]: source for source in rankings["sources"]}
    latest: dict[str, tuple[int, Decimal]] = {}
    for record in rankings["rankings"]:
        source = source_map[record["source_id"]]
        if source["status"] != "current":
            continue
        candidate = (source["ranking_year"], Decimal(record["sjr"]))
        prior = latest.get(record["journal_id"])
        if prior is not None and candidate[0] == prior[0] and candidate[1] != prior[1]:
            raise ValueError(
                "Conflicting current SJR values for "
                f"{record['journal_id']} in {candidate[0]}"
            )
        if prior is None or candidate[0] > prior[0]:
            latest[record["journal_id"]] = candidate
    return {journal_id: value for journal_id, (_, value) in latest.items()}


def _journal_sjr_sort_key(journal: dict, sjr_index: dict[str, Decimal]) -> tuple:
    sjr = sjr_index.get(journal["id"])
    if sjr is None:
        return (1, Decimal(0), journal["name"].casefold(), journal["id"])
    return (0, -sjr, journal["name"].casefold(), journal["id"])


def _feed_cells(journal: dict) -> tuple[str, str, str]:
    feeds = sorted(journal["feeds"], key=lambda item: (item["scope"], item["id"]))
    if not feeds:
        return (
            "—",
            STATUS_LABELS["not_found"],
            _date_text(journal["discovery"]["checked_at"]),
        )
    scopes = "<br>".join(
        f"[{SCOPE_LABELS[feed['scope']]}]({feed['url']})" for feed in feeds
    )
    statuses = "<br>".join(
        dict.fromkeys(STATUS_LABELS[feed["status"]] for feed in feeds)
    )
    dates = "<br>".join(
        dict.fromkeys(_date_text(feed["last_checked"]) for feed in feeds)
    )
    return scopes, statuses, dates


def generate_catalog_table(
    catalog: dict,
    rankings: dict | None = None,
) -> str:
    """Build grouped, one-row-per-journal Markdown tables for README.md."""
    journals = catalog["journals"]
    sjr_index = _current_sjr_index(rankings)
    lines: list[str] = []
    for discipline, heading in GROUPS:
        group = sorted(
            (
                journal
                for journal in journals
                if journal["primary_discipline"] == discipline
            ),
            key=lambda journal: _journal_sjr_sort_key(journal, sjr_index),
        )
        lines.extend([f"### {heading}", ""])
        headers = ["Journal", "Tags", "Feed scope", "Status", "Last checked"]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for journal in group:
            journal_label = f"[{_markdown(journal['name'])}]({journal['journal_url']})"
            abbreviation = _markdown(journal["abbreviation"])
            if abbreviation:
                journal_label += f" ({abbreviation})"
            tags = ", ".join(_markdown(item) for item in journal["disciplines"])
            scopes, status, last_checked = _feed_cells(journal)
            cells = [journal_label, tags, scopes, status, last_checked]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines).rstrip()


def render_readme(
    source: str,
    catalog: dict,
    rankings: dict | None = None,
) -> str:
    """Replace only the generated catalog block in README content."""
    normalized = source.replace("\r\n", "\n")
    if normalized.count(START_MARKER) != 1 or normalized.count(END_MARKER) != 1:
        raise ValueError("README must contain exactly one catalog marker pair")
    start = normalized.index(START_MARKER) + len(START_MARKER)
    end = normalized.index(END_MARKER)
    if start >= end:
        raise ValueError("README catalog markers are out of order")
    table = generate_catalog_table(catalog, rankings)
    return normalized[:start] + "\n" + table + "\n" + normalized[end:]


def render_opml(
    catalog: dict,
    *,
    scopes: set[str] | None = None,
    primary_disciplines: set[str] | None = None,
) -> str:
    """Render a stable OPML 2.0 subscription list."""
    root = ET.Element("opml", {"version": "2.0"})
    head = ET.SubElement(root, "head")
    ET.SubElement(head, "title").text = catalog["catalog"]["name"]
    body = ET.SubElement(root, "body")

    records: list[tuple[str, dict, dict]] = []
    for journal in catalog["journals"]:
        if (
            primary_disciplines is not None
            and journal["primary_discipline"] not in primary_disciplines
        ):
            continue
        for feed in journal["feeds"]:
            if scopes is None or feed["scope"] in scopes:
                records.append((journal["name"].casefold(), journal, feed))
    for _, journal, feed in sorted(records, key=lambda row: (row[0], row[2]["scope"], row[2]["id"])):
        label = journal["name"]
        if len(journal["feeds"]) > 1:
            label += f" — {SCOPE_LABELS[feed['scope']]}"
        ET.SubElement(
            body,
            "outline",
            {
                "text": label,
                "title": label,
                "type": "rss",
                "xmlUrl": feed["url"],
                "htmlUrl": journal["journal_url"],
                "category": ",".join(journal["disciplines"]),
            },
        )
    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
        root, encoding="unicode", short_empty_elements=True
    ) + "\n"


def generate_rankings_document(catalog: dict, rankings: dict) -> str:
    """Render annual SCImago rankings separately from feed metadata."""
    provider = rankings["provider"]
    journal_map = {journal["id"]: journal for journal in catalog["journals"]}
    source_map = {source["id"]: source for source in rankings["sources"]}
    records_by_journal: dict[str, list[dict]] = {}
    for record in rankings["rankings"]:
        records_by_journal.setdefault(record["journal_id"], []).append(record)
    sjr_index = _current_sjr_index(rankings)

    lines = [
        "# SCImago journal rankings",
        "",
        (
            "**License notice:** The SCImago ranking data in this report is "
            "third-party material. It is not covered by this repository's MIT "
            "License and is not relicensed here; see the linked SCImago sources "
            "and usage terms."
        ),
        "",
        (
            f"Source: [{provider['name']}]({provider['homepage_url']}); "
            f"[methodology]({provider['methodology_url']})."
        ),
        "",
        (
            "SCImago SJR is the catalog's ranking measure. SJR values and "
            "category-specific quartiles are shown in this report. The data is updated "
            "manually; this repository does not scrape SCImago."
        ),
        "",
        (
            "Within each subject, journals are ordered from highest to lowest current SJR. "
            "Ties are alphabetical, and journals without a current ranking appear last."
        ),
        "",
        "## Sources",
        "",
        "| Year | Category | Source file | Checked | File checksum | Usage terms |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for source in sorted(
        rankings["sources"],
        key=lambda item: (-item["ranking_year"], item["category"].casefold()),
    ):
        lines.append(
            "| "
            + " | ".join(
                [
                    f"[{source['ranking_year']}]({source['source_url']})",
                    _markdown(source["category"]),
                    f"[CSV]({source['artifact_url']})",
                    _date_text(source["retrieved_at"]),
                    f"`{source['sha256']}`",
                    f"[{_markdown(source['usage_terms'])}]({source['usage_url']})",
                ]
            )
            + " |"
        )
    lines.extend(["", "## Journal rankings", ""])
    for discipline, heading in GROUPS:
        lines.extend(
            [
                f"### {heading}",
                "",
                (
                    "| Journal | Source year | Category | SJR | Quartile | "
                    "SCImago ID | Matched ISSN | Checked | Next update |"
                ),
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        journals = sorted(
            (
                journal
                for journal in catalog["journals"]
                if journal["primary_discipline"] == discipline
            ),
            key=lambda journal: _journal_sjr_sort_key(journal, sjr_index),
        )
        for journal in journals:
            journal_link = f"[{_markdown(journal['name'])}]({journal['journal_url']})"
            records = sorted(
                records_by_journal.get(journal["id"], []),
                key=lambda record: (
                    -source_map[record["source_id"]]["ranking_year"],
                    record["category"].casefold(),
                ),
            )
            if not records:
                lines.append(
                    f"| {journal_link} | not recorded | not recorded | not recorded | "
                    "not recorded | not recorded | not recorded | not recorded | not recorded |"
                )
                continue
            for record in records:
                source = source_map[record["source_id"]]
                year_link = (
                    f"[{source['ranking_year']}]({source['source_url']}) "
                    f"({source['status'].replace('_', ' ')})"
                )
                scimago_link = f"[{record['scimago_id']}]({record['evidence_url']})"
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            journal_link,
                            year_link,
                            _markdown(record["category"]),
                            record["sjr"],
                            record["quartile"],
                            scimago_link,
                            record["matched_issn"],
                            _date_text(record["retrieved_at"]),
                            _date_text(record["refresh_due"]),
                        ]
                    )
                    + " |"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def expected_outputs(
    root: Path,
    catalog: dict,
    rankings: dict | None = None,
) -> dict[Path, str]:
    readme_path = root / "README.md"
    source = readme_path.read_text(encoding="utf-8")
    outputs = {
        readme_path: render_readme(source, catalog, rankings),
        root / "feeds" / "all.opml": render_opml(catalog),
        root / "feeds" / "current-issues.opml": render_opml(
            catalog, scopes={"current_issue"}
        ),
        root / "feeds" / "advance-articles.opml": render_opml(
            catalog, scopes={"advance_articles"}
        ),
        root / "feeds" / "economics.opml": render_opml(
            catalog, primary_disciplines={"economics"}
        ),
        root / "feeds" / "finance.opml": render_opml(
            catalog, primary_disciplines={"finance"}
        ),
        root / "feeds" / "econometrics.opml": render_opml(
            catalog, primary_disciplines={"econometrics"}
        ),
    }
    if rankings is not None:
        outputs[root / "RANKINGS.md"] = generate_rankings_document(catalog, rankings)
    return outputs


def generate_files(
    root: Path,
    catalog: dict,
    *,
    check: bool,
    rankings: dict | None = None,
) -> list[Path]:
    """Write outputs, or return paths that differ in check mode."""
    changed: list[Path] = []
    for path, expected in expected_outputs(root, catalog, rankings).items():
        actual = ""
        if path.exists():
            actual = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if actual == expected:
            continue
        changed.append(path)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(expected, encoding="utf-8", newline="\n")
    return changed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the parent of scripts/)",
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        help="catalog path (defaults to ROOT/data/journals.yml)",
    )
    parser.add_argument(
        "--rankings",
        type=Path,
        help="rankings path (defaults to ROOT/data/rankings.yml)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if generated files are absent or out of date",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    catalog_path = args.catalog or root / "data" / "journals.yml"
    rankings_path = args.rankings or root / "data" / "rankings.yml"
    try:
        catalog = load_catalog(catalog_path)
        rankings = load_rankings(rankings_path, catalog)
        changed = generate_files(
            root,
            catalog,
            check=args.check,
            rankings=rankings,
        )
    except (CatalogError, RankingsError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.check and changed:
        for path in changed:
            print(f"out of date: {path.relative_to(root)}", file=sys.stderr)
        print("Run python scripts/generate_outputs.py to update generated files.", file=sys.stderr)
        return 1
    if changed:
        for path in changed:
            print(f"generated: {path.relative_to(root)}")
    else:
        print("Generated files are up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
