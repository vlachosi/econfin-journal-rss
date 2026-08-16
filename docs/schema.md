# Catalog Schema

`data/journals.yml` stores the journal and feed information. `data/rankings.yml` stores the annual SCImago rankings. The generated Markdown and OPML files use only these two data files.

Annual SCImago rankings are shown in the generated `RANKINGS.md`, as described in [rankings.md](rankings.md). They are used to order journals but are not displayed as a main-catalog column.

## Top-level fields

- `schema_version`: Current schema version; presently `1`.
- `catalog`: Repository information and the default maximum feed age.
- `journals`: Ordered list of journal records.

## Journal records

Each journal contains:

- `id`: Stable lowercase, hyphenated identifier.
- `name` and `abbreviation`.
- `disciplines`: One or more of `economics`, `finance`, and `econometrics`.
- `primary_discipline`: Exactly one of the journal's discipline tags, used to place the journal in one generated README group without duplication.
- `publisher`.
- `issn.print` and `issn.online`, with `null` when unavailable.
- `journal_url`: Canonical official journal page.
- `discovery_status`: `working`, `limited`, or `not_found`.
- `discovery`: Date checked, official pages searched, and concise notes.
- `feeds`: Zero or more feed records. This list may be empty only for `not_found`.

## Feed records

Each feed contains:

- `id`: Stable identifier unique within the catalog.
- `url`: Exact official endpoint.
- `format`: `rss`, `atom`, or `rdf`.
- `scope`: `current_issue`, `advance_articles`, `all_new_content`, or `highlights`.
- `official_source_url`: Publisher or journal page that documents the feed.
- `status`: `working` or `limited`.
- `last_checked`: ISO date.
- `expected`: Channel-title fragment, allowed item hosts, minimum item count, maximum age, and an optional date-check rule.
- `compatibility`: Reader requirement, W3C result, notes, and an optional documented limit.

Multiple feed records are required when a publisher separately exposes current-issue and advance-article feeds. A highlights feed must never substitute for a journal publication feed.

`expected.date_check` is optional. The default, `items`, requires a usable date on at least one item. Use `channel_if_needed` only when an official feed omits item dates but supplies a usable channel update date such as `lastBuildDate`. This confirms feed activity rather than article age; it does not make a feed `limited`.

## Status invariants

- `working` requires at least one `working` feed.
- `limited` requires at least one feed with a documented reader-access or standards limitation.
- `not_found` requires an empty `feeds` list and at least one official source URL documenting the completed search.
- Every feed must contain at least one item when validated.
- Redirects ending in authentication or error-state URLs always fail, regardless of HTTP status.
- Malformed XML and invalid RSS author fields are structural failures and cannot be waived.

Generated OPML includes a flat all-feeds file, scope-specific files, and one file per `primary_discipline`. A journal appears in exactly one discipline-specific OPML file even when it has multiple discipline tags.

## Annual ranking records

The ranking file records the annual SCImago source, category, official links, file checksum, date checked, next update date, and usage terms. Each journal record includes its SJR, quartile, SCImago ID, matched ISSN, evidence link, dates, and notes. The latest current SJR orders journals from highest to lowest within each subject. Ties are alphabetical, and journals without a current ranking appear last. Invalid sources, conflicting values, duplicate records, mismatched IDs or ISSNs, and overdue updates fail the checks.

Unknown fields, duplicate journal/source pairs, unsupported category values, invented aggregate fields, and unresolved journal or source IDs fail schema validation.
