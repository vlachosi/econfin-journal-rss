"""Load and validate the journal catalog schema."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

import yaml


DISCOVERY_STATUSES = {
    "working",
    "limited",
    "not_found",
}
DISCIPLINES = {"economics", "finance", "econometrics"}
FEED_FORMATS = {"rss", "atom", "rdf"}
FEED_SCOPES = {
    "current_issue",
    "advance_articles",
    "all_new_content",
    "highlights",
}
FEED_STATUSES = {"working", "limited"}
DATE_CHECKS = {"items", "channel_if_needed"}
W3C_STATUSES = {"valid", "caveat"}

_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ISSN_RE = re.compile(r"^\d{4}-[\dX]{4}$", re.IGNORECASE)
_HOST_RE = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$",
    re.IGNORECASE,
)


class CatalogError(ValueError):
    """Raised when the catalog does not match the documented schema."""


class _Validator:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, path: str, message: str) -> None:
        self.errors.append(f"{path}: {message}")

    def mapping(self, value: Any, path: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            self.error(path, "must be a mapping")
            return {}
        return value

    def sequence(self, value: Any, path: str) -> list[Any]:
        if not isinstance(value, list):
            self.error(path, "must be a list")
            return []
        return value

    def allowed_keys(
        self,
        value: dict[str, Any],
        path: str,
        *,
        required: set[str],
        optional: set[str] | None = None,
    ) -> None:
        optional = optional or set()
        missing = sorted(required - value.keys())
        extra = sorted(value.keys() - required - optional)
        for key in missing:
            self.error(path, f"missing required key {key!r}")
        for key in extra:
            self.error(path, f"unknown key {key!r}")

    def string(self, value: Any, path: str, *, allow_empty: bool = False) -> str:
        if not isinstance(value, str):
            self.error(path, "must be a string")
            return ""
        if not allow_empty and not value.strip():
            self.error(path, "must not be empty")
        return value

    def integer(self, value: Any, path: str, *, minimum: int = 0) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            self.error(path, "must be an integer")
            return minimum
        if value < minimum:
            self.error(path, f"must be at least {minimum}")
        return value

    def boolean(self, value: Any, path: str) -> bool:
        if not isinstance(value, bool):
            self.error(path, "must be true or false")
            return False
        return value

    def enum(self, value: Any, path: str, allowed: set[str]) -> str:
        text = self.string(value, path)
        if text and text not in allowed:
            self.error(path, f"must be one of {', '.join(sorted(allowed))}")
        return text

    def url(self, value: Any, path: str) -> str:
        text = self.string(value, path)
        parsed = urlparse(text)
        if text and (parsed.scheme not in {"http", "https"} or not parsed.hostname):
            self.error(path, "must be an absolute HTTP(S) URL")
        return text

    def iso_date(self, value: Any, path: str) -> str:
        if isinstance(value, date):
            return value.isoformat()
        text = self.string(value, path)
        if text:
            try:
                date.fromisoformat(text)
            except ValueError:
                self.error(path, "must use YYYY-MM-DD")
        return text


def _validate_exception(validator: _Validator, value: Any, path: str) -> None:
    """Accept prose evidence or a rule-specific structured exception."""
    if isinstance(value, str):
        validator.string(value, path)
        return
    exception = validator.mapping(value, path)
    validator.allowed_keys(
        exception,
        path,
        required={"code", "reason"},
    )
    if "code" in exception:
        code = validator.string(exception["code"], f"{path}.code")
        if code and not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", code):
            validator.error(f"{path}.code", "must be a lower-case underscore identifier")
    if "reason" in exception:
        validator.string(exception["reason"], f"{path}.reason")


def _validate_expected(validator: _Validator, value: Any, path: str) -> None:
    expected = validator.mapping(value, path)
    validator.allowed_keys(
        expected,
        path,
        required={"title_contains", "item_hosts", "min_items", "max_age_days"},
        optional={"date_check"},
    )
    if "title_contains" in expected:
        validator.string(expected["title_contains"], f"{path}.title_contains")
    hosts = validator.sequence(expected.get("item_hosts"), f"{path}.item_hosts")
    if not hosts:
        validator.error(f"{path}.item_hosts", "must contain at least one host")
    seen_hosts: set[str] = set()
    for index, host_value in enumerate(hosts):
        host_path = f"{path}.item_hosts[{index}]"
        host = validator.string(host_value, host_path).lower()
        if host and not _HOST_RE.fullmatch(host):
            validator.error(host_path, "must be a hostname, not a URL")
        if host in seen_hosts:
            validator.error(host_path, "duplicates an earlier hostname")
        seen_hosts.add(host)
    if "min_items" in expected:
        validator.integer(expected["min_items"], f"{path}.min_items", minimum=1)
    if "max_age_days" in expected:
        validator.integer(expected["max_age_days"], f"{path}.max_age_days", minimum=1)
    if "date_check" in expected:
        validator.enum(expected["date_check"], f"{path}.date_check", DATE_CHECKS)


def _validate_compatibility(validator: _Validator, value: Any, path: str) -> None:
    compatibility = validator.mapping(value, path)
    validator.allowed_keys(
        compatibility,
        path,
        required={"requires_identifying_user_agent", "w3c_validation", "notes"},
        optional={"exception"},
    )
    if "requires_identifying_user_agent" in compatibility:
        validator.boolean(
            compatibility["requires_identifying_user_agent"],
            f"{path}.requires_identifying_user_agent",
        )
    if "w3c_validation" in compatibility:
        validator.enum(
            compatibility["w3c_validation"],
            f"{path}.w3c_validation",
            W3C_STATUSES,
        )
    if "notes" in compatibility:
        validator.string(compatibility["notes"], f"{path}.notes")
    if "exception" in compatibility:
        _validate_exception(validator, compatibility["exception"], f"{path}.exception")


def _validate_feed(
    validator: _Validator,
    value: Any,
    path: str,
    *,
    feed_ids: set[str],
) -> None:
    feed = validator.mapping(value, path)
    validator.allowed_keys(
        feed,
        path,
        required={
            "id",
            "url",
            "format",
            "scope",
            "official_source_url",
            "status",
            "last_checked",
            "expected",
            "compatibility",
        },
    )
    feed_id = validator.string(feed.get("id"), f"{path}.id")
    if feed_id and not _ID_RE.fullmatch(feed_id):
        validator.error(f"{path}.id", "must be a lower-case hyphenated identifier")
    if feed_id in feed_ids:
        validator.error(f"{path}.id", "must be globally unique")
    feed_ids.add(feed_id)
    if "url" in feed:
        validator.url(feed["url"], f"{path}.url")
    if "format" in feed:
        validator.enum(feed["format"], f"{path}.format", FEED_FORMATS)
    if "scope" in feed:
        validator.enum(feed["scope"], f"{path}.scope", FEED_SCOPES)
    if "official_source_url" in feed:
        validator.url(feed["official_source_url"], f"{path}.official_source_url")
    status = ""
    if "status" in feed:
        status = validator.enum(feed["status"], f"{path}.status", FEED_STATUSES)
    if "last_checked" in feed:
        validator.iso_date(feed["last_checked"], f"{path}.last_checked")
    if "expected" in feed:
        _validate_expected(validator, feed["expected"], f"{path}.expected")
    if "compatibility" in feed:
        _validate_compatibility(validator, feed["compatibility"], f"{path}.compatibility")
        compatibility = feed["compatibility"]
        if (
            status == "working"
            and isinstance(compatibility, dict)
            and compatibility.get("exception")
        ):
            validator.error(
                f"{path}.status",
                "must be limited when an exception is documented",
            )
        if status == "limited" and isinstance(compatibility, dict):
            has_evidence = bool(compatibility.get("requires_identifying_user_agent"))
            has_evidence = has_evidence or compatibility.get("w3c_validation") == "caveat"
            has_evidence = has_evidence or bool(compatibility.get("exception"))
            if not has_evidence:
                validator.error(
                    f"{path}.compatibility",
                "a limited feed must explain its known limitation",
                )


def _validate_journal(
    validator: _Validator,
    value: Any,
    path: str,
    *,
    journal_ids: set[str],
    feed_ids: set[str],
) -> None:
    journal = validator.mapping(value, path)
    validator.allowed_keys(
        journal,
        path,
        required={
            "id",
            "name",
            "abbreviation",
            "disciplines",
            "primary_discipline",
            "publisher",
            "issn",
            "journal_url",
            "discovery_status",
            "discovery",
            "feeds",
        },
    )
    journal_id = validator.string(journal.get("id"), f"{path}.id")
    if journal_id and not _ID_RE.fullmatch(journal_id):
        validator.error(f"{path}.id", "must be a lower-case hyphenated identifier")
    if journal_id in journal_ids:
        validator.error(f"{path}.id", "must be unique")
    journal_ids.add(journal_id)
    for key in ("name", "abbreviation", "publisher"):
        if key in journal:
            validator.string(journal[key], f"{path}.{key}")

    disciplines = validator.sequence(journal.get("disciplines"), f"{path}.disciplines")
    if not disciplines:
        validator.error(f"{path}.disciplines", "must contain at least one discipline")
    seen_disciplines: set[str] = set()
    for index, discipline_value in enumerate(disciplines):
        item_path = f"{path}.disciplines[{index}]"
        discipline = validator.string(discipline_value, item_path).lower()
        if discipline and discipline not in DISCIPLINES:
            validator.error(
                item_path,
                f"must be one of {', '.join(sorted(DISCIPLINES))}",
            )
        if discipline in seen_disciplines:
            validator.error(item_path, "duplicates an earlier discipline")
        seen_disciplines.add(discipline)
    primary_discipline = validator.string(
        journal.get("primary_discipline"), f"{path}.primary_discipline"
    ).lower()
    if primary_discipline and primary_discipline not in DISCIPLINES:
        validator.error(
            f"{path}.primary_discipline",
            f"must be one of {', '.join(sorted(DISCIPLINES))}",
        )
    if primary_discipline and primary_discipline not in seen_disciplines:
        validator.error(
            f"{path}.primary_discipline",
            "must also appear in disciplines",
        )

    issn = validator.mapping(journal.get("issn"), f"{path}.issn")
    validator.allowed_keys(issn, f"{path}.issn", required={"print", "online"})
    for kind in ("print", "online"):
        if kind not in issn or issn[kind] is None:
            continue
        value_text = validator.string(issn[kind], f"{path}.issn.{kind}")
        if value_text and not _ISSN_RE.fullmatch(value_text):
            validator.error(f"{path}.issn.{kind}", "must use the NNNN-NNNN ISSN format")
    if issn and issn.get("print") is None and issn.get("online") is None:
        validator.error(f"{path}.issn", "at least one ISSN must be present")

    if "journal_url" in journal:
        validator.url(journal["journal_url"], f"{path}.journal_url")
    discovery_status = ""
    if "discovery_status" in journal:
        discovery_status = validator.enum(
            journal["discovery_status"],
            f"{path}.discovery_status",
            DISCOVERY_STATUSES,
        )

    discovery = validator.mapping(journal.get("discovery"), f"{path}.discovery")
    validator.allowed_keys(
        discovery,
        f"{path}.discovery",
        required={"checked_at", "source_urls", "notes"},
    )
    if "checked_at" in discovery:
        validator.iso_date(discovery["checked_at"], f"{path}.discovery.checked_at")
    source_urls = validator.sequence(
        discovery.get("source_urls"), f"{path}.discovery.source_urls"
    )
    if not source_urls:
        validator.error(
            f"{path}.discovery.source_urls", "must cite at least one official source"
        )
    for index, source_url in enumerate(source_urls):
        validator.url(source_url, f"{path}.discovery.source_urls[{index}]")
    if "notes" in discovery:
        validator.string(discovery["notes"], f"{path}.discovery.notes")

    feeds = validator.sequence(journal.get("feeds"), f"{path}.feeds")
    for index, feed in enumerate(feeds):
        _validate_feed(
            validator,
            feed,
            f"{path}.feeds[{index}]",
            feed_ids=feed_ids,
        )

    if discovery_status == "not_found" and feeds:
        validator.error(f"{path}.feeds", "must be empty when no official RSS was found")
    if discovery_status != "not_found" and not feeds:
        validator.error(f"{path}.feeds", "must contain a feed for this discovery status")
    if discovery_status == "working" and any(
        isinstance(feed, dict) and feed.get("status") != "working" for feed in feeds
    ):
        validator.error(
            f"{path}.discovery_status",
            "must be limited when any feed is limited",
        )
    if discovery_status == "limited" and feeds and not any(
        isinstance(feed, dict) and feed.get("status") == "limited"
        for feed in feeds
    ):
        validator.error(
            f"{path}.discovery_status",
            "requires at least one limited feed",
        )


def validate_catalog(data: Any) -> dict[str, Any]:
    """Validate an already parsed catalog and return it unchanged."""
    validator = _Validator()
    root = validator.mapping(data, "catalog")
    validator.allowed_keys(
        root,
        "catalog",
        required={"schema_version", "catalog", "journals"},
    )
    if root.get("schema_version") != 1:
        validator.error("catalog.schema_version", "must be the integer 1")

    metadata = validator.mapping(root.get("catalog"), "catalog.catalog")
    validator.allowed_keys(
        metadata,
        "catalog.catalog",
        required={"name", "description", "repository_url", "default_max_age_days"},
    )
    for key in ("name", "description"):
        if key in metadata:
            validator.string(metadata[key], f"catalog.catalog.{key}")
    if "repository_url" in metadata:
        validator.url(metadata["repository_url"], "catalog.catalog.repository_url")
    if "default_max_age_days" in metadata:
        validator.integer(
            metadata["default_max_age_days"],
            "catalog.catalog.default_max_age_days",
            minimum=1,
        )

    journals = validator.sequence(root.get("journals"), "catalog.journals")
    if not journals:
        validator.error("catalog.journals", "must contain at least one journal")
    journal_ids: set[str] = set()
    feed_ids: set[str] = set()
    for index, journal in enumerate(journals):
        _validate_journal(
            validator,
            journal,
            f"catalog.journals[{index}]",
            journal_ids=journal_ids,
            feed_ids=feed_ids,
        )

    if validator.errors:
        details = "\n".join(f"- {error}" for error in validator.errors)
        raise CatalogError(f"Catalog schema validation failed:\n{details}")
    return root


def load_catalog(path: str | Path) -> dict[str, Any]:
    """Load a YAML catalog with safe parsing and strict schema validation."""
    catalog_path = Path(path)
    try:
        with catalog_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        raise CatalogError(f"Could not read {catalog_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise CatalogError(f"Could not parse {catalog_path}: {exc}") from exc
    return validate_catalog(data)


def iter_feeds(catalog: dict[str, Any]):
    """Yield (journal, feed) pairs in stable catalog order."""
    for journal in catalog["journals"]:
        for feed in journal["feeds"]:
            yield journal, feed
