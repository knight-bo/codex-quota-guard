# Public-source evidence and limitations (0.5.0 candidate)

The default source is the public RSS linked by the
[ModelYard index](https://tibo.modelyard.dev/):
[feed.xml](https://tibo.modelyard.dev/feed.xml). It is an independent aggregator,
not an official OpenAI API or independently authenticated X evidence. Categories
never establish personal quota receipt. No access/login restriction is bypassed.

The parent reviewer reported a normal HTTP 200 at 2026-10-18 05:13 UTC,
15869 bytes, application/rss+xml, and supplied the exact header/first item as an
explicitly cropped fixture. The schema is RSS 2.0 with Atom self link; items have
title, description, event link/guid, pubDate and category. Description ends in a
Source line linking the original post. There are no products, checked_at,
updated_at or verification fields. The source supplies summaries/source text;
that text can be erroneous and is not independently authenticated.

The cropped sample's publication and lastBuildDate are October 17 16:21:13 UTC.
The parent observed that the feed omitted the separately public 21:12 completed
post. Therefore the latest-entry/build date cannot be a source-sync heartbeat or
a no-reset verdict. HTTP success is local retrieval evidence; completeness and
synchronization remain unknown. The code exposes fetched_at, latest entry/build
dates and newest-entry age without pretending to measure true source delay.

The development environment still received CONNECT 403 for the provider and for
one attempted Library byte materialization of the five-item sample. A subsequent
Library native-text read succeeded: exact 4351 bytes/SHA256 matched the reviewer
copy, and parsing all five items passed. This is data compatibility, not a live
provider fetch. Its browser tool
could read rendered public HTML but rejected RSS extraction by content type.
The actual directly supplied first-item fixture is exercised by the parser tests;
no successful live provider transport or complete-feed test is claimed here. The
five-item crop passed separately; parent review will retest the full feed and
adversarial variants. No forbidden API or
JSON path is requested. The original experimental HTML adapter was removed after
a template counterexample; there is no HTML fallback.

The parent reported robots allowing public/RSS paths and prohibiting admin/API/
cron/JSON paths. Robots is an access preference, **not a copyright or redistribution
licence**. No blanket licence, provider authorization or official affiliation is
claimed. MIT covers this project's code, not third-party content. Runtime persists
only factual metadata/URLs/types/provenance, not post bodies or summaries. Only the
explicitly supplied cropped fixture is retained for compatibility tests; do not
redistribute a full feed archive on this basis. Keep linked source attribution.
Provider terms and ongoing availability remain maintainer review obligations.

Original references include
[planned post](https://x.com/thsottiaux/status/2111492738025959922) and
[completed post](https://x.com/thsottiaux/status/2111566005684289735).
X browser reads returned 403; no direct X scraping or credential access is used.
[Codex Resets](https://codexresets.com/) was a cross-check lead, not an ingested
prediction or API; do not confuse it with codex-resets.com. Personal account quota
remains exclusively the existing explicit official account-read path.
