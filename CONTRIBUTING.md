# Contributing

Contributions should improve the reliability of the directory, not merely increase its size.

## Adding or changing a journal

1. Edit `data/journals.yml`.
2. Link an official publisher or journal page that exposes or documents the feed.
3. Record the feed scope precisely: `current_issue`, `advance_articles`, `all_new_content`, or `highlights`.
4. Regenerate the files and check the feed.
5. Include the validation result and the date checked in the pull request.

If no acceptable feed exists, use `not_found` and record the official pages searched. Do not guess an endpoint from another journal on the same platform.

## Required feed checks

- Follow the full redirect chain without relying on a browser login or stored cookies.
- Reject redirects or final URLs that indicate authentication, cookie failure, or another error state.
- Require a recognized RSS/Atom root and at least one item.
- Confirm the channel title and item hosts belong to the intended journal.
- Check the newest item date against the journal's publication cadence. If item dates are absent, use `date_check: channel_if_needed` only when the official feed provides a reliable channel update date. This checks feed activity, not article age.
- Run W3C Feed Validation, record `valid` or `caveat`, and explain any specific limit.
- Test any limitation with named, ordinary RSS-reader user agents.

An endpoint that returns XML but contains zero items, literal error text, or cross-journal content is not a working journal feed.

## Feeds with limits

Use `limited` only for a reader-access or standards problem. Missing item dates alone are not a reader limitation when a usable channel date is available. Any accepted limit must be narrow and reproducible. Record:

- The exact standards or transport defect
- The reader identities tested
- Evidence that the endpoint is publisher-supported
- Why the feed remains useful despite the problem

Publisher login redirects, empty feeds, the wrong journal, malformed XML, and invalid RSS author fields are not accepted.

## Generated files

Do not hand-edit generated catalog or OPML content. Run:

```bash
python scripts/generate_outputs.py
python scripts/generate_outputs.py --check
```

Commit the source-data change and regenerated outputs together.

## Updating SCImago rankings

SCImago SJR is the catalog's ranking measure. Values belong in `data/rankings.yml` and the generated `RANKINGS.md`. The main catalog uses current SJR to order journals but does not display it as a column. Record the annual source, category, SJR, quartile, SCImago ID, matched ISSN, evidence URL, date checked, and next update date.

Updates are manual. Do not add a scraper or automatic updater. Run `python scripts/check_rankings.py`, then regenerate the files after changing the ranking data. See [docs/rankings.md](docs/rankings.md).
