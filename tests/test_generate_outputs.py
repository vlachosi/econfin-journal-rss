from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from scripts.generate_outputs import (
    END_MARKER,
    START_MARKER,
    generate_catalog_table,
    generate_rankings_document,
    generate_files,
    render_opml,
    render_readme,
)


def test_readme_replacement_preserves_surrounding_content(catalog_data: dict) -> None:
    source = f"# Before\n\n{START_MARKER}\nstale\n{END_MARKER}\n\nAfter\n"
    rendered = render_readme(source, catalog_data)
    assert rendered.startswith("# Before\n")
    assert rendered.endswith("\nAfter\n")
    assert "Example Journal" in rendered
    assert "stale" not in rendered


def test_catalog_table_is_deterministic(catalog_data: dict) -> None:
    first = generate_catalog_table(catalog_data)
    second = generate_catalog_table(catalog_data)
    assert first == second
    assert "[current issue](https://journal.example/feed.xml)" in first
    assert first.index("### Economics") < first.index("### Finance")
    assert first.index("### Finance") < first.index("### Econometrics")
    assert first.count("[Example Journal](https://journal.example)") == 1


def test_catalog_uses_plain_status_labels(catalog_data: dict) -> None:
    limited = deepcopy(catalog_data["journals"][0])
    limited.update(id="limited-journal", name="Limited Journal")
    limited["feeds"][0]["status"] = "limited"

    not_found = deepcopy(catalog_data["journals"][0])
    not_found.update(
        id="not-found-journal",
        name="Not Found Journal",
        discovery_status="not_found",
        feeds=[],
    )
    catalog_data["journals"].extend([limited, not_found])

    table = generate_catalog_table(catalog_data)
    assert "| Journal | Tags | Feed scope | Status | Last checked |" in table
    assert "Limited Journal" in table and "works with limits" in table
    assert "Not Found Journal" in table and "not found" in table


def test_scimago_rankings_render_only_in_separate_document(
    catalog_data: dict, rankings_data: dict
) -> None:
    main_catalog = generate_catalog_table(catalog_data, rankings=rankings_data)
    rankings_document = generate_rankings_document(catalog_data, rankings_data)
    assert "SCImago" not in main_catalog
    assert "SJR" not in main_catalog
    assert "| Journal | Tags | Feed scope | Status | Last checked |" in main_catalog
    assert "# SCImago journal rankings" in rankings_document
    assert "**License notice:**" in rankings_document
    assert "not covered by this repository's MIT License" in rankings_document
    assert "not relicensed here" in rankings_document
    assert "## Sources" in rankings_document
    assert "`" + "c" * 64 + "`" in rankings_document
    assert "### Economics" in rankings_document
    assert "3.125" in rankings_document
    assert "1234-567X" in rankings_document


def test_journals_are_ordered_by_current_sjr_with_missing_last(
    catalog_data: dict, rankings_data: dict
) -> None:
    higher = deepcopy(catalog_data["journals"][0])
    higher.update(id="higher-sjr-journal", name="Higher SJR Journal")
    tied = deepcopy(catalog_data["journals"][0])
    tied.update(id="a-tied-sjr-journal", name="A Tied SJR Journal")
    first_missing = deepcopy(catalog_data["journals"][0])
    first_missing.update(id="a-missing-sjr-journal", name="A Missing SJR Journal")
    missing = deepcopy(catalog_data["journals"][0])
    missing.update(id="missing-sjr-journal", name="Missing SJR Journal")
    catalog_data["journals"].extend([missing, tied, first_missing, higher])

    higher_ranking = deepcopy(rankings_data["rankings"][0])
    higher_ranking.update(
        journal_id="higher-sjr-journal",
        sjr="9.000",
        scimago_id="987654321",
        evidence_url=(
            "https://www.scimagojr.com/journalsearch.php?"
            "q=987654321&tip=sid"
        ),
    )
    tied_ranking = deepcopy(rankings_data["rankings"][0])
    tied_ranking.update(
        journal_id="a-tied-sjr-journal",
        scimago_id="987654322",
        evidence_url=(
            "https://www.scimagojr.com/journalsearch.php?"
            "q=987654322&tip=sid"
        ),
    )
    superseded_source = deepcopy(rankings_data["sources"][0])
    superseded_source.update(
        id="scimago-2026-superseded",
        name="Superseded SCImago 2026 test rankings",
        ranking_year=2026,
        status="superseded",
        source_url=(
            "https://www.scimagojr.com/journalrank.php?"
            "category=2002&year=2026"
        ),
    )
    superseded_ranking = deepcopy(rankings_data["rankings"][0])
    superseded_ranking.update(
        source_id="scimago-2026-superseded",
        sjr="99.000",
    )
    older_current_source = deepcopy(rankings_data["sources"][0])
    older_current_source.update(
        id="scimago-2023-current",
        name="Older current SCImago 2023 test rankings",
        ranking_year=2023,
        source_url=(
            "https://www.scimagojr.com/journalrank.php?"
            "category=2002&year=2023"
        ),
    )
    older_current_ranking = deepcopy(rankings_data["rankings"][0])
    older_current_ranking.update(
        source_id="scimago-2023-current",
        sjr="100.000",
    )
    rankings_data["sources"].extend([superseded_source, older_current_source])
    rankings_data["rankings"].extend(
        [higher_ranking, tied_ranking, superseded_ranking, older_current_ranking]
    )

    table = generate_catalog_table(catalog_data, rankings=rankings_data)
    rankings_document = generate_rankings_document(catalog_data, rankings_data)
    for rendered in (table, rankings_document):
        assert rendered.index("Higher SJR Journal") < rendered.index("Example Journal")
        assert rendered.index("A Tied SJR Journal") < rendered.index("Example Journal")
        assert rendered.index("Example Journal") < rendered.index("A Missing SJR Journal")
        assert rendered.index("A Missing SJR Journal") < rendered.index("Missing SJR Journal")
    assert "| not recorded | not recorded |" in rankings_document


def test_conflicting_current_sjr_values_fail_generation(
    catalog_data: dict, rankings_data: dict
) -> None:
    conflicting_source = deepcopy(rankings_data["sources"][0])
    conflicting_source.update(
        id="scimago-2024-conflict",
        name="Conflicting test source",
        category="Finance",
        category_code="2003",
        source_url=(
            "https://www.scimagojr.com/journalrank.php?"
            "category=2003&year=2024"
        ),
        artifact_url=(
            "https://www.scimagojr.com/journalrank.php?"
            "category=2003&out=xls"
        ),
    )
    conflicting_ranking = deepcopy(rankings_data["rankings"][0])
    conflicting_ranking.update(
        source_id="scimago-2024-conflict",
        category="Finance",
        sjr="4.000",
    )
    rankings_data["sources"].append(conflicting_source)
    rankings_data["rankings"].append(conflicting_ranking)
    with pytest.raises(ValueError, match="Conflicting current SJR values"):
        generate_catalog_table(catalog_data, rankings=rankings_data)


def test_opml_is_valid_and_scope_filtered(catalog_data: dict) -> None:
    all_opml = render_opml(catalog_data)
    current = render_opml(catalog_data, scopes={"current_issue"})
    advance = render_opml(catalog_data, scopes={"advance_articles"})
    economics = render_opml(catalog_data, primary_disciplines={"economics"})
    finance = render_opml(catalog_data, primary_disciplines={"finance"})
    assert ET.fromstring(all_opml).tag == "opml"
    assert "Example Journal" in current
    assert "Example Journal" not in advance
    assert "Example Journal" in economics
    assert "Example Journal" not in finance


def test_generation_then_check_is_clean(
    tmp_path: Path, catalog_data: dict, rankings_data: dict
) -> None:
    (tmp_path / "README.md").write_text(
        f"# Catalog\n\n{START_MARKER}\nplaceholder\n{END_MARKER}\n",
        encoding="utf-8",
    )
    changed = generate_files(
        tmp_path,
        catalog_data,
        check=False,
        rankings=rankings_data,
    )
    assert {path.name for path in changed} == {
        "README.md",
        "all.opml",
        "current-issues.opml",
        "advance-articles.opml",
        "economics.opml",
        "finance.opml",
        "econometrics.opml",
        "RANKINGS.md",
    }
    assert generate_files(
        tmp_path,
        catalog_data,
        check=True,
        rankings=rankings_data,
    ) == []

    (tmp_path / "feeds" / "all.opml").write_text("stale", encoding="utf-8")
    stale = generate_files(
        tmp_path,
        catalog_data,
        check=True,
        rankings=rankings_data,
    )
    assert stale == [tmp_path / "feeds" / "all.opml"]
