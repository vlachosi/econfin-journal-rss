# Economics, Finance, and Econometrics Journal RSS

A maintained directory of official journal RSS and Atom feeds for economics, finance, and econometrics.

## What this repository provides

- Journal and feed information in `data/journals.yml`
- Annual [SCImago rankings](RANKINGS.md) in `data/rankings.yml`
- Separate feed scopes for current issues, advance articles, and all new content
- OPML subscriptions: [all feeds](feeds/all.opml), [economics](feeds/economics.opml), [finance](feeds/finance.opml), and [econometrics](feeds/econometrics.opml)
- A catalog generator that keeps the files consistent
- Automatic feed checks
- Scheduled checks through GitHub Actions

## How feeds are checked

A feed is marked `working` only when it passes all applicable checks:

1. An official publisher or journal page links to or documents the feed.
2. The feed opens in a normal RSS reader without a login or error redirect.
3. It contains valid RSS or Atom data and at least one item.
4. Its items belong to the correct journal.
5. Dated items are recent enough, or an undated feed has been updated recently.
6. Any known reader limitation is documented.

Empty feeds, error pages, and publisher-wide feeds that do not represent the journal are rejected.

If no suitable official feed is found, the journal is marked `not_found`. The catalog does not guess feed addresses from publisher URL patterns.

## Catalog

Within each subject, journals are ordered from highest to lowest current SCImago SJR. Ties are alphabetical, and journals without a current ranking appear last. SJR values and category-specific quartiles are shown in the separate [rankings report](RANKINGS.md).

<!-- catalog:start -->
### Economics

| Journal | Tags | Feed scope | Status | Last checked |
| --- | --- | --- | --- | --- |
| [Quarterly Journal of Economics](https://academic.oup.com/qje) (QJE) | economics | [advance articles](https://academic.oup.com/rss/site_5504/advanceAccess_3365.xml)<br>[current issue](https://academic.oup.com/rss/site_5504/3365.xml) | works with limits | 2026-08-16 |
| [The Review of Economic Studies](https://academic.oup.com/restud) (REStud) | economics | [advance articles](https://academic.oup.com/rss/site_5508/advanceAccess_3369.xml) | works with limits | 2026-08-16 |
| [American Economic Review](https://www.aeaweb.org/journals/aer) (AER) | economics | [all new content](https://pubs.aeaweb.org/action/showFeed?type=etoc&feed=rss&jc=aer) | working | 2026-08-16 |
| [Journal of Economic Literature](https://www.aeaweb.org/journals/jel) (JEL) | economics | [all new content](https://pubs.aeaweb.org/action/showFeed?type=etoc&feed=rss&jc=jel) | working | 2026-08-16 |
| [Journal of Political Economy](https://www.journals.uchicago.edu/toc/jpe/current) (JPE) | economics | [all new content](https://www.journals.uchicago.edu/action/showFeed?type=etoc&feed=rss&jc=jpe) | working | 2026-08-16 |
| [American Economic Journal: Macroeconomics](https://www.aeaweb.org/journals/mac) (AEJ Macro) | economics | [all new content](https://pubs.aeaweb.org/action/showFeed?type=etoc&feed=rss&jc=mac) | working | 2026-08-16 |
| [American Economic Journal: Applied Economics](https://www.aeaweb.org/journals/app) (AEJ Applied) | economics | [all new content](https://pubs.aeaweb.org/action/showFeed?type=etoc&feed=rss&jc=app) | working | 2026-08-16 |
| [Journal of Economic Perspectives](https://www.aeaweb.org/journals/jep) (JEP) | economics | [all new content](https://pubs.aeaweb.org/action/showFeed?type=etoc&feed=rss&jc=jep) | working | 2026-08-16 |
| [American Economic Journal: Economic Policy](https://www.aeaweb.org/journals/pol) (AEJ Policy) | economics | [all new content](https://pubs.aeaweb.org/action/showFeed?type=etoc&feed=rss&jc=pol) | working | 2026-08-16 |
| [Journal of Monetary Economics](https://www.sciencedirect.com/journal/journal-of-monetary-economics) (JME) | economics | [all new content](https://rss.sciencedirect.com/publication/science/03043932) | working | 2026-08-16 |
| [American Economic Journal: Microeconomics](https://www.aeaweb.org/journals/mic) (AEJ Micro) | economics | [all new content](https://pubs.aeaweb.org/action/showFeed?type=etoc&feed=rss&jc=mic) | working | 2026-08-16 |
| [Journal of Public Economics](https://www.sciencedirect.com/journal/journal-of-public-economics) (JPubE) | economics | [all new content](https://rss.sciencedirect.com/publication/science/00472727) | working | 2026-08-16 |
| [Journal of Economic Theory](https://www.sciencedirect.com/journal/journal-of-economic-theory) (JET) | economics | [all new content](https://rss.sciencedirect.com/publication/science/00220531) | working | 2026-08-16 |

### Finance

| Journal | Tags | Feed scope | Status | Last checked |
| --- | --- | --- | --- | --- |
| [The Journal of Finance](https://onlinelibrary.wiley.com/journal/15406261) (JF) | finance | [all new content](https://onlinelibrary.wiley.com/action/showFeed?jc=15406261&type=etoc&feed=rss) | working | 2026-08-16 |
| [Journal of Financial Economics](https://www.sciencedirect.com/journal/journal-of-financial-economics) (JFE) | finance | [all new content](https://rss.sciencedirect.com/publication/science/0304405X) | working | 2026-08-16 |
| [Review of Financial Studies](https://academic.oup.com/rfs) (RFS) | finance | [current issue](https://academic.oup.com/rss/site_5511/3372.xml) | works with limits | 2026-08-16 |
| [Review of Finance](https://academic.oup.com/rof) (RF) | finance | [current issue](https://academic.oup.com/rss/site_5510/3371.xml) | works with limits | 2026-08-16 |
| [Journal of Financial and Quantitative Analysis](https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis) (JFQA) | finance | [current issue](https://www.cambridge.org/core/rss/product/id/FB35548FF614F4556E96D01FA2CB412E) | works with limits | 2026-08-16 |
| [Financial Management](https://onlinelibrary.wiley.com/journal/1755053x) (FM) | finance | [all new content](https://onlinelibrary.wiley.com/action/showFeed?jc=1755053x&type=etoc&feed=rss) | working | 2026-08-16 |
| [The Review of Asset Pricing Studies](https://academic.oup.com/raps) (RAPS) | finance | [current issue](https://academic.oup.com/rss/site_5506/3367.xml) | works with limits | 2026-08-16 |
| [Journal of Corporate Finance](https://www.sciencedirect.com/journal/journal-of-corporate-finance) (JCF) | finance | [all new content](https://rss.sciencedirect.com/publication/science/09291199) | working | 2026-08-16 |
| [Journal of Financial Intermediation](https://www.sciencedirect.com/journal/journal-of-financial-intermediation) (JFI) | finance | [all new content](https://rss.sciencedirect.com/publication/science/10429573) | working | 2026-08-16 |
| [Journal of Banking & Finance](https://www.sciencedirect.com/journal/journal-of-banking-and-finance) (JBF) | finance | [all new content](https://rss.sciencedirect.com/publication/science/03784266) | working | 2026-08-16 |
| [Mathematical Finance](https://onlinelibrary.wiley.com/journal/14679965) (MF) | finance | [all new content](https://onlinelibrary.wiley.com/action/showFeed?jc=14679965&type=etoc&feed=rss) | working | 2026-08-16 |
| [Finance Research Letters](https://www.sciencedirect.com/journal/finance-research-letters) (FRL) | finance | [all new content](https://rss.sciencedirect.com/publication/science/15446123) | working | 2026-08-16 |
| [Journal of Financial Stability](https://www.sciencedirect.com/journal/journal-of-financial-stability) (JFS) | finance | [all new content](https://rss.sciencedirect.com/publication/science/15723089) | working | 2026-08-16 |
| [Journal of Financial Markets](https://www.sciencedirect.com/journal/journal-of-financial-markets) (JFM) | finance | [all new content](https://rss.sciencedirect.com/publication/science/13864181) | working | 2026-08-16 |
| [Journal of Empirical Finance](https://www.sciencedirect.com/journal/journal-of-empirical-finance) (JEF) | finance | [all new content](https://rss.sciencedirect.com/publication/science/09275398) | working | 2026-08-16 |

### Econometrics

| Journal | Tags | Feed scope | Status | Last checked |
| --- | --- | --- | --- | --- |
| [Econometrica](https://onlinelibrary.wiley.com/journal/14680262) (Econometrica) | economics, econometrics | [all new content](https://onlinelibrary.wiley.com/feed/14680262/most-recent) | working | 2026-08-16 |
| [Journal of Econometrics](https://www.sciencedirect.com/journal/journal-of-econometrics) (JoE) | econometrics | [all new content](https://rss.sciencedirect.com/publication/science/03044076) | working | 2026-08-16 |
<!-- catalog:end -->

## Journal rankings

SCImago SJR is the catalog's ranking measure. The values and category-specific quartiles are kept in the separate [rankings report](RANKINGS.md). They are [checked and updated manually](docs/rankings.md); the repository does not scrape SCImago.

## Status meanings

| Status | Meaning |
| --- | --- |
| `working` | The official feed passes the checks. |
| `limited` (shown as “works with limits”) | The feed works but requires a compatible RSS reader. |
| `not_found` (shown as “not found”) | No suitable official journal feed was found. |

## Local use

```bash
python -m pip install -e .[dev]
python scripts/generate_outputs.py --check
python scripts/validate_feeds.py --strict
python scripts/check_rankings.py
python -m pytest
```

Run `python scripts/generate_outputs.py` without `--check` after intentionally changing any source file under `data/`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Contributions must cite an official source page and include a recent feed-check result.

## Acknowledgements

This project was inspired by [yexner/rss-feeds-academic-journals](https://github.com/yexner/rss-feeds-academic-journals) and [AndyGreenPhD/journal-rss-feeds](https://github.com/AndyGreenPhD/journal-rss-feeds). Every entry in this catalog is independently checked against official sources.

## License

Except for the SCImago-derived material described below, original material in this repository is licensed under the [MIT License](LICENSE).

SCImago ranking data, including `data/rankings.yml`, [RANKINGS.md](RANKINGS.md), and the SJR-derived ordering of the journal catalog, is third-party material. It is not covered by the MIT License and is not relicensed by this repository; see the linked SCImago sources and usage terms.
