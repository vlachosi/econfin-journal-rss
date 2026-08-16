from __future__ import annotations

from copy import deepcopy
from datetime import date
from types import SimpleNamespace

from scripts.validate_feeds import make_session, validate_feed_response
from tests.conftest import response


TODAY = date(2026, 8, 16)


def test_valid_feed_passes(journal: dict, feed: dict, fixture_bytes) -> None:
    result = validate_feed_response(
        journal,
        feed,
        response(fixture_bytes("valid_rss.xml")),
        today=TODAY,
    )
    assert result.ok, result.errors
    assert result.item_count == 2
    assert result.latest_date == date(2026, 8, 15)
    assert result.date_source == "item"


def test_broken_springer_cookie_redirect_is_rejected(
    journal: dict, feed: dict, fixture_bytes
) -> None:
    redirect = SimpleNamespace(
        url="https://link.springer.com/search.rss?facet-journal-id=10551",
        headers={
            "Location": "https://idp.springer.com/authorize?client_id=springerlink"
        },
    )
    final = response(
        fixture_bytes("springer_pseudo_feed.xml"),
        url=(
            "https://link.springer.com/search.rss?facet-journal-id=10551"
            "&error=cookies_not_supported&code=test"
        ),
        history=[redirect],
    )
    result = validate_feed_response(journal, feed, final, today=TODAY)
    assert not result.ok
    assert any("authentication redirect" in error or "error-state" in error for error in result.errors)


def test_non_feed_xml_is_rejected(journal: dict, feed: dict, fixture_bytes) -> None:
    result = validate_feed_response(
        journal, feed, response(fixture_bytes("non_feed.xml")), today=TODAY
    )
    assert not result.ok
    assert any("non-feed XML" in error for error in result.errors)


def test_error_path_final_url_is_rejected(journal: dict, feed: dict, fixture_bytes) -> None:
    final = response(
        fixture_bytes("valid_rss.xml"),
        url="https://journal.example/error",
    )
    result = validate_feed_response(journal, feed, final, today=TODAY)
    assert any("error-state" in error for error in result.errors)


def test_literal_null_and_zero_items_are_rejected(
    journal: dict, feed: dict, fixture_bytes
) -> None:
    literal = validate_feed_response(
        journal,
        feed,
        response(b"null", content_type="application/xml"),
        today=TODAY,
    )
    empty = validate_feed_response(
        journal,
        feed,
        response(fixture_bytes("empty_rss.xml")),
        today=TODAY,
    )
    assert any("literal" in error for error in literal.errors)
    assert any("0 items" in error for error in empty.errors)


def test_wrong_channel_identity_is_rejected(
    journal: dict, feed: dict, fixture_bytes
) -> None:
    feed["expected"]["title_contains"] = "Different Journal"
    result = validate_feed_response(
        journal, feed, response(fixture_bytes("valid_rss.xml")), today=TODAY
    )
    assert any("channel title" in error for error in result.errors)


def test_stale_feed_is_rejected(journal: dict, feed: dict, fixture_bytes) -> None:
    result = validate_feed_response(
        journal, feed, response(fixture_bytes("stale_rss.xml")), today=TODAY
    )
    assert any("days old" in error for error in result.errors)


def test_misq_invalid_author_is_not_waivable(
    journal: dict, feed: dict, fixture_bytes
) -> None:
    invalid = validate_feed_response(
        journal,
        feed,
        response(fixture_bytes("misq_invalid_author.xml")),
        today=TODAY,
    )
    assert any("RSS author is not an email" in error for error in invalid.errors)

    feed["status"] = "limited"
    feed["compatibility"]["exception"] = {
        "code": "invalid_rss_author_email",
        "reason": "The official feed emits creator names in RSS author elements.",
    }
    still_rejected = validate_feed_response(
        journal,
        feed,
        response(fixture_bytes("misq_invalid_author.xml")),
        today=TODAY,
    )
    assert not still_rejected.ok
    assert any("RSS author is not an email" in error for error in still_rejected.errors)


def test_channel_date_can_be_used_when_item_dates_are_missing(
    journal: dict, feed: dict, fixture_bytes
) -> None:
    document = response(fixture_bytes("channel_date_only_rss.xml"))
    rejected = validate_feed_response(journal, feed, document, today=TODAY)
    assert any("set date_check to channel_if_needed" in error for error in rejected.errors)

    feed["expected"]["date_check"] = "channel_if_needed"
    accepted = validate_feed_response(journal, feed, document, today=TODAY)
    assert accepted.ok, accepted.errors
    assert accepted.latest_date == date(2026, 8, 15)
    assert accepted.date_source == "channel"
    assert any("date check uses the channel date" in note for note in accepted.notes)

    future = validate_feed_response(
        journal, feed, document, today=date(2026, 8, 10)
    )
    assert any("feed update date" in error for error in future.errors)

    feed["expected"]["max_age_days"] = 1
    stale = validate_feed_response(
        journal, feed, document, today=date(2026, 8, 20)
    )
    assert any("feed update is" in error for error in stale.errors)

    both_dates_xml = fixture_bytes("channel_date_only_rss.xml").replace(
        b"<lastBuildDate>",
        b"<pubDate>Wed, 01 Jul 2020 12:00:00 GMT</pubDate><lastBuildDate>",
    )
    both_dates = validate_feed_response(
        journal,
        feed,
        response(both_dates_xml),
        today=TODAY,
    )
    assert both_dates.latest_date == date(2026, 8, 15)
    assert both_dates.date_source == "channel"


def test_default_session_identifies_validator() -> None:
    session = make_session("https://github.com/example/catalog")
    assert "JournalRSSCatalogValidator" in session.headers["User-Agent"]
    assert "github.com/example/catalog" in session.headers["User-Agent"]
