"""Load and check the SCImago journal rankings."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import math
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import yaml


SOURCE_STATUSES = {"current", "superseded", "pending_verification"}
QUARTILES = {"Q1", "Q2", "Q3", "Q4"}
_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ISSN_RE = re.compile(r"^\d{4}-[\dX]{4}$", re.IGNORECASE)
_SCIMAGO_ID_RE = re.compile(r"^\d+$")
_SJR_RE = re.compile(r"^\d+(?:\.\d{1,6})?$")
_CATEGORY_CODE_RE = re.compile(r"^\d{4}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class RankingsError(ValueError):
    """Raised when rankings data does not match the documented format."""


def _is_scimago_host(hostname: str | None) -> bool:
    host = (hostname or "").lower().rstrip(".")
    return host == "scimagojr.com" or host.endswith(".scimagojr.com")


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

    def keys(self, value: dict[str, Any], path: str, required: set[str]) -> None:
        for key in sorted(required - value.keys()):
            self.error(path, f"missing required key {key!r}")
        for key in sorted(value.keys() - required):
            self.error(path, f"unknown key {key!r}")

    def string(self, value: Any, path: str) -> str:
        if not isinstance(value, str):
            self.error(path, "must be a string")
            return ""
        if not value.strip():
            self.error(path, "must not be empty")
        return value

    def url(self, value: Any, path: str) -> str:
        text = self.string(value, path)
        parsed = urlparse(text)
        if text and (parsed.scheme != "https" or not parsed.hostname):
            self.error(path, "must be an absolute HTTPS URL")
        return text

    def iso_date(self, value: Any, path: str) -> date | None:
        if isinstance(value, date):
            return value
        text = self.string(value, path)
        if not text:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            self.error(path, "must use YYYY-MM-DD")
            return None

    def integer(self, value: Any, path: str, *, minimum: int, maximum: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            self.error(path, "must be an integer")
            return minimum
        if not minimum <= value <= maximum:
            self.error(path, f"must be between {minimum} and {maximum}")
        return value


def _validate_source(validator: _Validator, raw: Any, path: str, ids: set[str]) -> dict:
    source = validator.mapping(raw, path)
    validator.keys(
        source,
        path,
        {
            "id",
            "name",
            "ranking_year",
            "status",
            "category",
            "category_code",
            "source_url",
            "artifact_url",
            "sha256",
            "retrieved_at",
            "refresh_due",
            "usage_terms",
            "usage_url",
            "notes",
        },
    )
    source_id = validator.string(source.get("id"), f"{path}.id")
    if source_id and not _ID_RE.fullmatch(source_id):
        validator.error(f"{path}.id", "must be a lower-case hyphenated identifier")
    if source_id in ids:
        validator.error(f"{path}.id", "must be unique")
    ids.add(source_id)
    for field in ("name", "category", "usage_terms", "notes"):
        if field in source:
            validator.string(source[field], f"{path}.{field}")
    category_code = validator.string(source.get("category_code"), f"{path}.category_code")
    if category_code and not _CATEGORY_CODE_RE.fullmatch(category_code):
        validator.error(f"{path}.category_code", "must be a four-digit SCImago category code")
    ranking_year = source.get("ranking_year")
    if "ranking_year" in source:
        ranking_year = validator.integer(
            source["ranking_year"], f"{path}.ranking_year", minimum=1999, maximum=2100
        )
    if "status" in source:
        status = validator.string(source["status"], f"{path}.status")
        if status and status not in SOURCE_STATUSES:
            validator.error(f"{path}.status", f"must be one of {', '.join(sorted(SOURCE_STATUSES))}")
    if "source_url" in source:
        source_url = validator.url(source["source_url"], f"{path}.source_url")
        parsed_source = urlparse(source_url)
        if source_url and not _is_scimago_host(parsed_source.hostname):
            validator.error(f"{path}.source_url", "must be an official scimagojr.com URL")
        if source_url and parsed_source.path != "/journalrank.php":
            validator.error(f"{path}.source_url", "must use the official /journalrank.php path")
        source_query = parse_qs(parsed_source.query)
        if category_code and source_query.get("category", [None])[0] != category_code:
            validator.error(f"{path}.source_url", "category query must equal category_code")
        if isinstance(ranking_year, int) and source_query.get("year", [None])[0] != str(ranking_year):
            validator.error(f"{path}.source_url", "year query must equal ranking_year")
    if "artifact_url" in source:
        artifact_url = validator.url(source["artifact_url"], f"{path}.artifact_url")
        parsed_artifact = urlparse(artifact_url)
        if artifact_url and not _is_scimago_host(parsed_artifact.hostname):
            validator.error(f"{path}.artifact_url", "must be an official scimagojr.com URL")
        if artifact_url and parsed_artifact.path != "/journalrank.php":
            validator.error(f"{path}.artifact_url", "must use the official /journalrank.php path")
        artifact_query = parse_qs(parsed_artifact.query)
        if category_code and artifact_query.get("category", [None])[0] != category_code:
            validator.error(f"{path}.artifact_url", "category query must equal category_code")
        if artifact_query.get("out", [None])[0] != "xls":
            validator.error(f"{path}.artifact_url", "must identify the official CSV export with out=xls")
    if "sha256" in source:
        digest = validator.string(source["sha256"], f"{path}.sha256")
        if digest and not _SHA256_RE.fullmatch(digest):
            validator.error(f"{path}.sha256", "must be 64 lower-case hexadecimal characters")
    source_retrieved = None
    source_refresh_due = None
    if "retrieved_at" in source:
        source_retrieved = validator.iso_date(
            source["retrieved_at"], f"{path}.retrieved_at"
        )
    if "refresh_due" in source:
        source_refresh_due = validator.iso_date(
            source["refresh_due"], f"{path}.refresh_due"
        )
    if source_retrieved and source_refresh_due:
        if source_refresh_due <= source_retrieved:
            validator.error(f"{path}.refresh_due", "must be later than retrieved_at")
        elif source_refresh_due > source_retrieved + timedelta(days=400):
            validator.error(
                f"{path}.refresh_due", "must be within 400 days of retrieved_at"
            )
    if "usage_url" in source:
        usage_url = validator.url(source["usage_url"], f"{path}.usage_url")
        if usage_url and not _is_scimago_host(urlparse(usage_url).hostname):
            validator.error(f"{path}.usage_url", "must be an official scimagojr.com URL")
    return source


def _validate_ranking(
    validator: _Validator,
    raw: Any,
    path: str,
    *,
    journals: dict[str, dict],
    sources: dict[str, dict],
    keys: set[tuple[str, str, str]],
    scimago_owners: dict[str, str],
    journal_year_sjr: dict[tuple[str, int], str],
) -> None:
    ranking = validator.mapping(raw, path)
    validator.keys(
        ranking,
        path,
        {
            "journal_id",
            "source_id",
            "category",
            "sjr",
            "quartile",
            "scimago_id",
            "matched_issn",
            "evidence_url",
            "retrieved_at",
            "refresh_due",
            "notes",
        },
    )
    journal_id = validator.string(ranking.get("journal_id"), f"{path}.journal_id")
    source_id = validator.string(ranking.get("source_id"), f"{path}.source_id")
    category = validator.string(ranking.get("category"), f"{path}.category")
    journal = journals.get(journal_id)
    if journal_id and journal is None:
        validator.error(f"{path}.journal_id", "does not match data/journals.yml")
    if source_id and source_id not in sources:
        validator.error(f"{path}.source_id", "does not match a declared rankings source")
    source = sources.get(source_id)
    if source and category and category != source.get("category"):
        validator.error(f"{path}.category", "must exactly match the declared source category")
    unique_key = (journal_id, source_id, category.casefold())
    if unique_key in keys:
        validator.error(path, "duplicates an earlier journal/source/category record")
    keys.add(unique_key)

    sjr = validator.string(ranking.get("sjr"), f"{path}.sjr")
    if sjr and not _SJR_RE.fullmatch(sjr):
        validator.error(f"{path}.sjr", "must be a non-negative decimal string with at most 6 places")
    elif sjr and not math.isfinite(float(sjr)):
        validator.error(f"{path}.sjr", "must be finite")
    if source and sjr:
        annual_key = (journal_id, source["ranking_year"])
        prior_sjr = journal_year_sjr.get(annual_key)
        if prior_sjr is not None and prior_sjr != sjr:
            validator.error(
                f"{path}.sjr",
                "annual SJR must be identical across category rows for a journal",
            )
        journal_year_sjr[annual_key] = sjr
    quartile = validator.string(ranking.get("quartile"), f"{path}.quartile")
    if quartile and quartile not in QUARTILES:
        validator.error(f"{path}.quartile", "must be Q1, Q2, Q3, or Q4")

    scimago_id = validator.string(ranking.get("scimago_id"), f"{path}.scimago_id")
    if scimago_id and not _SCIMAGO_ID_RE.fullmatch(scimago_id):
        validator.error(f"{path}.scimago_id", "must be the stable numeric SCImago source ID")
    prior_owner = scimago_owners.get(scimago_id)
    if prior_owner and prior_owner != journal_id:
        validator.error(f"{path}.scimago_id", "is already assigned to a different journal")
    scimago_owners[scimago_id] = journal_id

    matched_issn = validator.string(ranking.get("matched_issn"), f"{path}.matched_issn")
    if matched_issn and not _ISSN_RE.fullmatch(matched_issn):
        validator.error(f"{path}.matched_issn", "must use canonical NNNN-NNNN format")
    if journal and matched_issn and matched_issn.casefold() not in {
        str(value).casefold()
        for value in journal.get("issn", {}).values()
        if value is not None
    }:
        validator.error(f"{path}.matched_issn", "does not match the journal's print or online ISSN")

    evidence_url = validator.url(ranking.get("evidence_url"), f"{path}.evidence_url")
    parsed_evidence = urlparse(evidence_url)
    if evidence_url and not _is_scimago_host(parsed_evidence.hostname):
        validator.error(f"{path}.evidence_url", "must be an official scimagojr.com journal page")
    if evidence_url and parsed_evidence.path != "/journalsearch.php":
        validator.error(
            f"{path}.evidence_url", "must use the official /journalsearch.php path"
        )
    query_id = parse_qs(parsed_evidence.query).get("q", [None])[0]
    if scimago_id and query_id != scimago_id:
        validator.error(f"{path}.evidence_url", "q parameter must equal scimago_id")
    if evidence_url and parse_qs(parsed_evidence.query).get("tip", [None])[0] != "sid":
        validator.error(f"{path}.evidence_url", "tip parameter must be sid")

    retrieved = validator.iso_date(ranking.get("retrieved_at"), f"{path}.retrieved_at")
    refresh_due = validator.iso_date(ranking.get("refresh_due"), f"{path}.refresh_due")
    if source and retrieved:
        source_retrieved = source.get("retrieved_at")
        source_retrieved_text = (
            source_retrieved.isoformat()
            if isinstance(source_retrieved, date)
            else str(source_retrieved)
        )
        if retrieved.isoformat() != source_retrieved_text:
            validator.error(
                f"{path}.retrieved_at", "must equal the declared source retrieval date"
            )
    if source and refresh_due:
        source_refresh = source.get("refresh_due")
        source_refresh_text = (
            source_refresh.isoformat()
            if isinstance(source_refresh, date)
            else str(source_refresh)
        )
        if refresh_due.isoformat() != source_refresh_text:
            validator.error(
                f"{path}.refresh_due", "must equal the declared source refresh deadline"
            )
    if retrieved and refresh_due and refresh_due <= retrieved:
        validator.error(f"{path}.refresh_due", "must be later than retrieved_at")
    elif retrieved and refresh_due and refresh_due > retrieved + timedelta(days=400):
        validator.error(
            f"{path}.refresh_due", "must be within 400 days of retrieved_at"
        )
    if "notes" in ranking:
        validator.string(ranking["notes"], f"{path}.notes")


def validate_rankings(data: Any, catalog: dict[str, Any]) -> dict[str, Any]:
    """Validate SCImago source editions and annual journal ranking records."""
    validator = _Validator()
    root = validator.mapping(data, "rankings")
    validator.keys(
        root,
        "rankings",
        {"schema_version", "policy", "provider", "sources", "rankings"},
    )
    if root.get("schema_version") != 1:
        validator.error("rankings.schema_version", "must be the integer 1")

    policy = validator.mapping(root.get("policy"), "rankings.policy")
    validator.keys(
        policy,
        "rankings.policy",
        {"display", "main_catalog_columns", "main_catalog_ordering", "update_mode"},
    )
    if policy.get("display") != "separate_document":
        validator.error("rankings.policy.display", "must be separate_document")
    if policy.get("main_catalog_columns") != "prohibited":
        validator.error("rankings.policy.main_catalog_columns", "must be prohibited")
    if policy.get("main_catalog_ordering") != "latest_current_sjr_descending":
        validator.error(
            "rankings.policy.main_catalog_ordering",
            "must be latest_current_sjr_descending",
        )
    if policy.get("update_mode") != "manual_only":
        validator.error("rankings.policy.update_mode", "must be manual_only")

    provider = validator.mapping(root.get("provider"), "rankings.provider")
    validator.keys(
        provider,
        "rankings.provider",
        {"name", "homepage_url", "methodology_url", "update_frequency"},
    )
    if provider.get("name") != "SCImago Journal & Country Rank":
        validator.error("rankings.provider.name", "must identify SCImago Journal & Country Rank")
    for field in ("homepage_url", "methodology_url"):
        if field in provider:
            provider_url = validator.url(provider[field], f"rankings.provider.{field}")
            if provider_url and not _is_scimago_host(urlparse(provider_url).hostname):
                validator.error(
                    f"rankings.provider.{field}", "must be an official scimagojr.com URL"
                )
    if provider.get("update_frequency") != "annual":
        validator.error("rankings.provider.update_frequency", "must be annual")

    source_list = validator.sequence(root.get("sources"), "rankings.sources")
    source_ids: set[str] = set()
    sources: dict[str, dict] = {}
    for index, raw_source in enumerate(source_list):
        source = _validate_source(validator, raw_source, f"rankings.sources[{index}]", source_ids)
        if isinstance(source.get("id"), str):
            sources[source["id"]] = source

    journal_map = {
        journal["id"]: journal
        for journal in catalog.get("journals", [])
        if isinstance(journal, dict) and isinstance(journal.get("id"), str)
    }
    ranking_list = validator.sequence(root.get("rankings"), "rankings.rankings")
    keys: set[tuple[str, str, str]] = set()
    scimago_owners: dict[str, str] = {}
    journal_year_sjr: dict[tuple[str, int], str] = {}
    for index, raw_ranking in enumerate(ranking_list):
        _validate_ranking(
            validator,
            raw_ranking,
            f"rankings.rankings[{index}]",
            journals=journal_map,
            sources=sources,
            keys=keys,
            scimago_owners=scimago_owners,
            journal_year_sjr=journal_year_sjr,
        )

    if validator.errors:
        details = "\n".join(f"- {error}" for error in validator.errors)
        raise RankingsError(f"Rankings validation failed:\n{details}")
    return root


def load_rankings(path: str | Path, catalog: dict[str, Any]) -> dict[str, Any]:
    """Safely load rankings YAML and validate catalog references."""
    rankings_path = Path(path)
    try:
        with rankings_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        raise RankingsError(f"Could not read {rankings_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise RankingsError(f"Could not parse {rankings_path}: {exc}") from exc
    return validate_rankings(data, catalog)
