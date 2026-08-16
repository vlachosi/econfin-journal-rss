from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from scripts.catalog import (
    DISCOVERY_STATUSES,
    FEED_STATUSES,
    CatalogError,
    load_catalog,
    validate_catalog,
)


def test_repository_catalog_matches_schema() -> None:
    root = Path(__file__).resolve().parents[1]
    catalog = load_catalog(root / "data" / "journals.yml")
    assert catalog["schema_version"] == 1
    assert catalog["journals"]


def test_valid_catalog_is_accepted(catalog_data: dict) -> None:
    assert validate_catalog(catalog_data) is catalog_data


def test_loader_uses_yaml_and_validates(tmp_path: Path, catalog_data: dict) -> None:
    path = tmp_path / "journals.yml"
    path.write_text(yaml.safe_dump(catalog_data, sort_keys=False), encoding="utf-8")
    assert load_catalog(path)["journals"][0]["id"] == "example-journal"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data.update(schema_version=2), "schema_version"),
        (
            lambda data: data["journals"][0].update(feeds=[]),
            "must contain a feed",
        ),
        (
            lambda data: data["journals"][0]["feeds"][0]["expected"].update(min_items=0),
            "must be at least 1",
        ),
        (
            lambda data: data["journals"][0]["feeds"][0]["expected"].update(
                date_check="publisher"
            ),
            "must be one of channel_if_needed, items",
        ),
        (
            lambda data: data["journals"][0]["feeds"][0].update(url="javascript:bad"),
            "absolute HTTP",
        ),
        (
            lambda data: data["journals"][0].update(disciplines=["accounting"]),
            "must be one of econometrics, economics, finance",
        ),
        (
            lambda data: data["journals"][0].update(primary_discipline="finance"),
            "must also appear in disciplines",
        ),
    ],
)
def test_schema_rejects_unsafe_or_inconsistent_data(
    catalog_data: dict, mutation, message: str
) -> None:
    mutation(catalog_data)
    with pytest.raises(CatalogError, match=message):
        validate_catalog(catalog_data)


def test_no_feed_status_requires_empty_feed_list(catalog_data: dict) -> None:
    journal = catalog_data["journals"][0]
    journal["discovery_status"] = "not_found"
    journal["feeds"] = []
    validate_catalog(catalog_data)

    invalid = deepcopy(catalog_data)
    invalid["journals"][0]["feeds"] = [
        {
            "id": "unexpected-feed",
            "url": "https://journal.example/feed.xml",
        }
    ]
    with pytest.raises(CatalogError, match="must be empty"):
        validate_catalog(invalid)


def test_status_names_are_plain_and_complete() -> None:
    assert DISCOVERY_STATUSES == {"working", "limited", "not_found"}
    assert FEED_STATUSES == {"working", "limited"}
