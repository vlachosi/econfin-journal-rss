from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest


FIXTURES = Path(__file__).parent / "fixtures"


def sample_feed() -> dict:
    return {
        "id": "example-current-issue",
        "url": "https://journal.example/feed.xml",
        "format": "rss",
        "scope": "current_issue",
        "official_source_url": "https://journal.example/rss-information",
        "status": "working",
        "last_checked": "2026-08-16",
        "expected": {
            "title_contains": "Example Journal",
            "item_hosts": ["journal.example"],
            "min_items": 1,
            "max_age_days": 30,
        },
        "compatibility": {
            "requires_identifying_user_agent": False,
            "w3c_validation": "valid",
            "notes": "Direct standards-compliant feed.",
        },
    }


def sample_journal() -> dict:
    return {
        "id": "example-journal",
        "name": "Example Journal",
        "abbreviation": "EJ",
        "disciplines": ["economics"],
        "primary_discipline": "economics",
        "publisher": "Example Publisher",
        "issn": {"print": "1234-567X", "online": None},
        "journal_url": "https://journal.example",
        "discovery_status": "working",
        "discovery": {
            "checked_at": "2026-08-16",
            "source_urls": ["https://journal.example/rss-information"],
            "notes": "Publisher documents the feed.",
        },
        "feeds": [sample_feed()],
    }


def sample_catalog() -> dict:
    return {
        "schema_version": 1,
        "catalog": {
            "name": "Example catalog",
            "description": "Test catalog.",
            "repository_url": "https://github.com/example/catalog",
            "default_max_age_days": 30,
        },
        "journals": [sample_journal()],
    }


def sample_rankings() -> dict:
    return {
        "schema_version": 1,
        "policy": {
            "display": "separate_document",
            "main_catalog_columns": "prohibited",
            "main_catalog_ordering": "latest_current_sjr_descending",
            "update_mode": "manual_only",
        },
        "provider": {
            "name": "SCImago Journal & Country Rank",
            "homepage_url": "https://www.scimagojr.com/",
            "methodology_url": "https://www.scimagojr.com/SCImagoJournalRank.pdf",
            "update_frequency": "annual",
        },
        "sources": [
            {
                "id": "scimago-2024",
                "name": "SCImago 2024 journal rankings",
                "ranking_year": 2024,
                "status": "current",
                "category": "Economics and Econometrics",
                "category_code": "2002",
                "source_url": (
                    "https://www.scimagojr.com/journalrank.php?"
                    "category=2002&year=2024"
                ),
                "artifact_url": (
                    "https://www.scimagojr.com/journalrank.php?"
                    "category=2002&out=xls"
                ),
                "sha256": "c" * 64,
                "retrieved_at": "2026-08-16",
                "refresh_due": "2027-06-30",
                "usage_terms": "Non-commercial use with citation.",
                "usage_url": "https://www.scimagojr.com/",
                "notes": "Test-only dated source.",
            }
        ],
        "rankings": [
            {
                "journal_id": "example-journal",
                "source_id": "scimago-2024",
                "category": "Economics and Econometrics",
                "sjr": "3.125",
                "quartile": "Q1",
                "scimago_id": "123456789",
                "matched_issn": "1234-567X",
                "evidence_url": (
                    "https://www.scimagojr.com/journalsearch.php?"
                    "q=123456789&tip=sid"
                ),
                "retrieved_at": "2026-08-16",
                "refresh_due": "2027-06-30",
                "notes": "Matched by ISSN in the test fixture.",
            }
        ],
    }


@pytest.fixture
def catalog_data() -> dict:
    return deepcopy(sample_catalog())


@pytest.fixture
def journal() -> dict:
    return deepcopy(sample_journal())


@pytest.fixture
def feed() -> dict:
    return deepcopy(sample_feed())


@pytest.fixture
def rankings_data() -> dict:
    return deepcopy(sample_rankings())


@pytest.fixture
def fixture_bytes():
    def load(name: str) -> bytes:
        return (FIXTURES / name).read_bytes()

    return load


def response(
    content: bytes,
    *,
    url: str = "https://journal.example/feed.xml",
    status: int = 200,
    content_type: str = "application/rss+xml; charset=utf-8",
    history: list | None = None,
):
    return SimpleNamespace(
        content=content,
        url=url,
        status_code=status,
        headers={"Content-Type": content_type},
        history=history or [],
    )
