# SCImago Rankings

SCImago Journal Rank (SJR) is the catalog's ranking measure. SJR values and annual, category-specific quartiles are stored in `data/rankings.yml` and shown in `RANKINGS.md`. Within each subject, journals are ordered from highest to lowest current SJR. Ties are alphabetical, and journals without a current ranking appear last. SJR is not displayed as a column in the main catalog.

## How rankings are updated

This repository does not update rankings automatically. A contributor checks the cited SCImago pages and records the values and source details. The automatic check only reports when an update is due.

## Information recorded

Each annual source records its year, subject category and code, official page and export link, date checked, next update date, file checksum, usage terms, status, and notes. Every journal record includes:

- Journal and annual source identifiers
- SCImago subject category
- SJR as a quoted decimal string and category quartile (`Q1`–`Q4`)
- Stable numeric SCImago source ID
- The print or online ISSN used to match the journal
- A link to the official SCImago journal page
- Date checked, next update date, and a short note

A journal may appear in more than one category for the same year. Duplicate records and conflicting SJR values are rejected.

## Annual update

Run:

```bash
python scripts/check_rankings.py
```

If an update is due, check the new annual SCImago source, update the values and links, set the next update date, and regenerate `RANKINGS.md`. The check does not access the internet or change any data.
