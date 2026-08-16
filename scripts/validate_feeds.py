"""Check every live feed in the journal catalog."""

from __future__ import annotations

import argparse
import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import re
from pathlib import Path
import sys
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlparse
import xml.etree.ElementTree as ET

import feedparser
import requests

try:
    from scripts.catalog import CatalogError, iter_feeds, load_catalog
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from catalog import CatalogError, iter_feeds, load_catalog


_XML_CONTENT_TYPES = {
    "application/atom+xml",
    "application/rdf+xml",
    "application/rss+xml",
    "application/xml",
    "text/xml",
}
_LITERAL_FAILURES = {b"null", b"none", b"0", b"{}", b"[]"}
_ERROR_VALUES = {
    "authentication_failed",
    "cookies_not_supported",
    "invalid_request",
    "login_required",
    "server_error",
}
_EMAIL_RE = re.compile(
    r"(?i)(?:^|[\s<(])"
    r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+"
    r"(?:$|[\s>)])"
)


@dataclass
class ValidationResult:
    journal_id: str
    feed_id: str
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    title: str | None = None
    item_count: int = 0
    latest_date: date | None = None
    date_source: str | None = None

    @property
    def ok(self) -> bool:
        return not self.errors


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _host_allowed(host: str | None, allowed: list[str]) -> bool:
    if not host:
        return False
    normalized = host.rstrip(".").lower()
    return any(
        normalized == candidate.lower()
        or normalized.endswith("." + candidate.lower())
        for candidate in allowed
    )


def _url_has_error_state(url: str) -> bool:
    parsed = urlparse(url)
    final_path_part = parsed.path.rstrip("/").rsplit("/", 1)[-1].casefold()
    if final_path_part in {"error", "failure"}:
        return True
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        key_lower = key.casefold()
        value_lower = value.casefold()
        if key_lower == "error" or key_lower.startswith("error_"):
            return True
        if any(token in value_lower for token in _ERROR_VALUES):
            return True
    return False


def _url_has_auth_state(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    path_parts = {part.casefold() for part in parsed.path.split("/") if part}
    return (
        host.startswith("idp.")
        or "authorize" in path_parts
        or "login" in path_parts
        or "signin" in path_parts
        or "oauth" in path_parts
    )


def _redirect_urls(response: requests.Response) -> list[str]:
    urls: list[str] = []
    for hop in response.history:
        urls.append(hop.url)
        location = hop.headers.get("Location")
        if location:
            urls.append(urljoin(hop.url, location))
    urls.append(response.url)
    return urls


def _detect_feed_format(content: bytes) -> tuple[str | None, ET.Element | None, str | None]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        return None, None, str(exc)
    local = _local_name(root.tag)
    if local == "rss":
        if not any(_local_name(child.tag) == "channel" for child in root):
            return None, root, "RSS document has no channel"
        return "rss", root, None
    if local == "feed":
        return "atom", root, None
    if local == "rdf":
        return "rdf", root, None
    return None, root, f"root element {local!r} is not RSS, Atom, or RDF"


def _rss_author_errors(root: ET.Element) -> list[str]:
    if _local_name(root.tag) != "rss":
        return []
    errors: list[str] = []
    item_index = 0
    for element in root.iter():
        if _local_name(element.tag) != "item":
            continue
        item_index += 1
        for child in element:
            if _local_name(child.tag) != "author":
                continue
            author = "".join(child.itertext()).strip()
            if not _EMAIL_RE.search(author):
                errors.append(f"item {item_index} RSS author is not an email address: {author!r}")
    return errors


def _entry_date(entry: Any) -> datetime | None:
    for field_name in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(field_name)
        if parsed:
            try:
                return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
            except (OverflowError, TypeError, ValueError):
                continue
    for field_name in ("published", "updated", "created"):
        raw = entry.get(field_name)
        if raw:
            try:
                parsed_date = parsedate_to_datetime(raw)
            except (TypeError, ValueError):
                continue
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            return parsed_date.astimezone(timezone.utc)
    return None


def _channel_date(channel: Any) -> datetime | None:
    """Return the channel update date, preferring RSS lastBuildDate."""
    for field_name in ("updated_parsed", "published_parsed", "created_parsed"):
        parsed = channel.get(field_name)
        if parsed:
            try:
                return datetime.fromtimestamp(calendar.timegm(parsed), tz=timezone.utc)
            except (OverflowError, TypeError, ValueError):
                continue
    for field_name in ("updated", "published", "created"):
        raw = channel.get(field_name)
        if raw:
            try:
                parsed_date = parsedate_to_datetime(raw)
            except (TypeError, ValueError):
                continue
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=timezone.utc)
            return parsed_date.astimezone(timezone.utc)
    return None


def validate_feed_response(
    journal: dict[str, Any],
    feed: dict[str, Any],
    response: requests.Response,
    *,
    today: date | None = None,
) -> ValidationResult:
    """Validate a completed HTTP response without performing network I/O."""
    result = ValidationResult(journal_id=journal["id"], feed_id=feed["id"])
    today = today or datetime.now(timezone.utc).date()

    if response.status_code != 200:
        result.errors.append(f"HTTP status is {response.status_code}, expected 200")
        return result

    for redirect_url in _redirect_urls(response):
        if _url_has_error_state(redirect_url):
            result.errors.append(f"error-state redirect or final URL: {redirect_url}")
        elif _url_has_auth_state(redirect_url):
            result.errors.append(f"authentication redirect is not reader-safe: {redirect_url}")
    if result.errors:
        return result

    content = bytes(response.content)
    if content.strip().lower() in _LITERAL_FAILURES:
        result.errors.append("response is a literal null/empty sentinel, not a feed")
        return result
    if not content.strip():
        result.errors.append("response body is empty")
        return result

    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type not in _XML_CONTENT_TYPES:
        result.errors.append(f"content type {content_type or '<missing>'!r} is not XML syndication")

    detected_format, xml_root, xml_error = _detect_feed_format(content)
    if xml_error:
        result.errors.append(f"non-feed XML: {xml_error}")
        return result
    if detected_format != feed["format"]:
        result.errors.append(
            f"declared format {feed['format']!r} does not match {detected_format!r} document"
        )

    parsed = feedparser.parse(content)
    if parsed.bozo:
        result.errors.append(f"feedparser rejected the document: {parsed.bozo_exception}")
    entries = list(parsed.entries)
    result.item_count = len(entries)
    minimum = feed["expected"]["min_items"]
    if len(entries) < minimum:
        result.errors.append(f"feed has {len(entries)} items; expected at least {minimum}")
        return result

    title = str(parsed.feed.get("title", "")).strip()
    result.title = title or None
    expected_title = feed["expected"]["title_contains"]
    if expected_title.casefold() not in title.casefold():
        result.errors.append(
            f"channel title {title!r} does not contain expected identity {expected_title!r}"
        )

    allowed_hosts = feed["expected"]["item_hosts"]
    for index, entry in enumerate(entries, start=1):
        link = str(entry.get("link", "")).strip()
        host = urlparse(link).hostname
        if not _host_allowed(host, allowed_hosts):
            result.errors.append(
                f"item {index} link host {host or '<missing>'!r} is outside expected hosts"
            )

    dated_entries = [item_date for entry in entries if (item_date := _entry_date(entry))]
    freshness_dates = dated_entries
    if dated_entries:
        result.date_source = "item"
    if not dated_entries:
        channel_date = _channel_date(parsed.feed)
        date_check = feed["expected"].get("date_check", "items")
        if date_check == "channel_if_needed" and channel_date:
            freshness_dates = [channel_date]
            result.date_source = "channel"
            result.notes.append(
                "item dates are not supplied; the date check uses the channel date"
            )
        elif date_check == "channel_if_needed":
            result.errors.append(
                "items have no usable dates and the channel has no usable date"
            )
        elif channel_date:
            result.errors.append(
                "items have no usable dates; set date_check to channel_if_needed only "
                "when the official feed is documented to use a channel date"
            )
        else:
            result.errors.append("neither the items nor the channel has a usable date")
    if freshness_dates:
        newest = max(freshness_dates).date()
        result.latest_date = newest
        age_days = (today - newest).days
        date_label = "feed update" if result.date_source == "channel" else "newest item"
        if age_days < -2:
            result.errors.append(
                f"{date_label} date {newest.isoformat()} is implausibly in the future"
            )
        elif age_days > feed["expected"]["max_age_days"]:
            result.errors.append(
                f"{date_label} is {age_days} days old; maximum is "
                f"{feed['expected']['max_age_days']}"
            )

    assert xml_root is not None
    author_errors = _rss_author_errors(xml_root)
    # Invalid RSS author fields are a structural interoperability failure.
    # They cannot be accepted even when a feed has another documented limit.
    result.errors.extend(author_errors)
    return result


def make_session(repository_url: str, user_agent: str | None = None) -> requests.Session:
    session = requests.Session()
    identity = user_agent or f"JournalRSSCatalogValidator/1.0 (+{repository_url})"
    session.headers.update(
        {
            "User-Agent": identity,
            "Accept": (
                "application/rss+xml, application/atom+xml, application/rdf+xml, "
                "application/xml;q=0.9, text/xml;q=0.8"
            ),
        }
    )
    return session


def fetch_and_validate(
    session: requests.Session,
    journal: dict[str, Any],
    feed: dict[str, Any],
    *,
    timeout: float,
    today: date | None = None,
) -> ValidationResult:
    try:
        response = session.get(feed["url"], timeout=timeout, allow_redirects=True)
    except requests.RequestException as exc:
        return ValidationResult(
            journal_id=journal["id"],
            feed_id=feed["id"],
            errors=[f"request failed: {exc}"],
        )
    return validate_feed_response(journal, feed, response, today=today)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--catalog",
        type=Path,
        default=root / "data" / "journals.yml",
        help="catalog YAML path",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="per-feed timeout")
    parser.add_argument("--user-agent", help="identifying RSS-reader user agent")
    parser.add_argument("--journal", action="append", help="validate only this journal id")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="run all feed checks (this is already the default)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        print("error: --timeout must be positive", file=sys.stderr)
        return 2
    try:
        catalog = load_catalog(args.catalog)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    selected = set(args.journal or [])
    known = {journal["id"] for journal in catalog["journals"]}
    unknown = selected - known
    if unknown:
        print(f"error: unknown journal id(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    session = make_session(catalog["catalog"]["repository_url"], args.user_agent)
    results: list[ValidationResult] = []
    for journal, feed in iter_feeds(catalog):
        if selected and journal["id"] not in selected:
            continue
        print(f"checking {journal['name']} [{feed['id']}] ...", flush=True)
        result = fetch_and_validate(
            session,
            journal,
            feed,
            timeout=args.timeout,
        )
        results.append(result)
        if result.ok:
            latest = result.latest_date.isoformat() if result.latest_date else "unknown"
            date_label = "feed updated" if result.date_source == "channel" else "newest item"
            print(f"  PASS: {result.item_count} items; {date_label} {latest}")
            for note in result.notes:
                print(f"  INFO: {note}")
        else:
            for error in result.errors:
                print(f"  FAIL: {error}")

    failures = [result for result in results if not result.ok]
    print(f"Validated {len(results)} feeds: {len(results) - len(failures)} passed, {len(failures)} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
