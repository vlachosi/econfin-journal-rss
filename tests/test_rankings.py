from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from scripts.catalog import load_catalog
from scripts.check_rankings import stale_records
from scripts.rankings import RankingsError, load_rankings, validate_rankings


def test_repository_rankings_layer_has_complete_current_2025_coverage() -> None:
    root = Path(__file__).resolve().parents[1]
    catalog = load_catalog(root / "data" / "journals.yml")
    rankings = load_rankings(root / "data" / "rankings.yml", catalog)
    assert rankings["provider"]["name"] == "SCImago Journal & Country Rank"
    assert len(rankings["sources"]) == 3
    assert {source["ranking_year"] for source in rankings["sources"]} == {2025}
    assert {source["status"] for source in rankings["sources"]} == {"current"}
    assert all(source["sha256"] for source in rankings["sources"])
    assert len(rankings["rankings"]) == len(catalog["journals"]) == 30
    assert {record["journal_id"] for record in rankings["rankings"]} == {
        journal["id"] for journal in catalog["journals"]
    }


def test_valid_scimago_record_is_accepted(
    catalog_data: dict, rankings_data: dict
) -> None:
    assert validate_rankings(rankings_data, catalog_data) is rankings_data


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda data: data["policy"].update(main_catalog_columns="allowed"),
            "must be prohibited",
        ),
        (
            lambda data: data["policy"].update(main_catalog_ordering="alphabetical"),
            "must be latest_current_sjr_descending",
        ),
        (
            lambda data: data["policy"].update(update_mode="scrape"),
            "must be manual_only",
        ),
        (
            lambda data: data["rankings"][0].update(journal_id="missing"),
            "does not match data/journals.yml",
        ),
        (
            lambda data: data["rankings"][0].update(source_id="missing"),
            "does not match a declared rankings source",
        ),
        (
            lambda data: data["sources"][0].update(
                source_url="https://secondary.example/scimago.csv"
            ),
            "official scimagojr.com URL",
        ),
        (
            lambda data: data["sources"][0].update(
                source_url=(
                    "https://www.scimagojr.com/not-a-ranking.php?"
                    "category=2002&year=2024"
                )
            ),
            "official /journalrank.php path",
        ),
        (
            lambda data: data["sources"][0].update(category_code="20A2"),
            "four-digit SCImago category code",
        ),
        (
            lambda data: data["sources"][0].update(sha256="not-a-digest"),
            "64 lower-case hexadecimal",
        ),
        (
            lambda data: data["sources"][0].update(refresh_due="2100-01-01"),
            "must be within 400 days of retrieved_at",
        ),
        (
            lambda data: data["rankings"][0].update(category="Finance"),
            "must exactly match the declared source category",
        ),
        (
            lambda data: data["rankings"][0].update(sjr=3.125),
            "must be a string",
        ),
        (
            lambda data: data["rankings"][0].update(quartile="A"),
            "must be Q1",
        ),
        (
            lambda data: data["rankings"][0].update(scimago_id="SJR-123"),
            "stable numeric SCImago",
        ),
        (
            lambda data: data["rankings"][0].update(matched_issn="9999-9999"),
            "does not match the journal's print or online ISSN",
        ),
        (
            lambda data: data["rankings"][0].update(
                evidence_url="https://www.scimagojr.com/journalsearch.php?q=987654321"
            ),
            "q parameter must equal scimago_id",
        ),
        (
            lambda data: data["rankings"][0].update(
                evidence_url=(
                    "https://www.scimagojr.com/not-a-journal.php?"
                    "q=123456789&tip=sid"
                )
            ),
            "official /journalsearch.php path",
        ),
        (
            lambda data: data["rankings"][0].update(refresh_due="2026-08-16"),
            "must be later than retrieved_at",
        ),
        (
            lambda data: data.update(aggregate_rank="Q1"),
            "unknown key 'aggregate_rank'",
        ),
    ],
)
def test_rankings_reject_unsupported_or_untraceable_values(
    catalog_data: dict, rankings_data: dict, mutation, message: str
) -> None:
    mutation(rankings_data)
    with pytest.raises(RankingsError, match=message):
        validate_rankings(rankings_data, catalog_data)


def test_duplicate_journal_source_category_is_rejected(
    catalog_data: dict, rankings_data: dict
) -> None:
    rankings_data["rankings"].append(deepcopy(rankings_data["rankings"][0]))
    with pytest.raises(RankingsError, match="duplicates an earlier"):
        validate_rankings(rankings_data, catalog_data)


def test_annual_sjr_must_match_across_category_rows(
    catalog_data: dict, rankings_data: dict
) -> None:
    second_source = deepcopy(rankings_data["sources"][0])
    second_source.update(
        id="scimago-2024-finance",
        name="SCImago 2024 finance rankings",
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
        sha256="d" * 64,
    )
    second_ranking = deepcopy(rankings_data["rankings"][0])
    second_ranking.update(
        source_id="scimago-2024-finance",
        category="Finance",
        sjr="4.000",
    )
    rankings_data["sources"].append(second_source)
    rankings_data["rankings"].append(second_ranking)
    with pytest.raises(RankingsError, match="annual SJR must be identical"):
        validate_rankings(rankings_data, catalog_data)


def test_update_deadline_is_enforced_without_network(rankings_data: dict) -> None:
    assert stale_records(rankings_data, as_of=date(2027, 6, 30)) == []
    stale = stale_records(rankings_data, as_of=date(2027, 7, 1))
    assert [record["journal_id"] for record in stale] == ["example-journal"]
