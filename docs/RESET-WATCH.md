# Optional public reset announcements (0.5.0 candidate)

`resetwatch` watches public announcements attributed to Tibo (@thsottiaux),
independently of account quota. It never queries an account, restores quota,
redeems credit, clears target latches or pauses/resumes research. A public
completion report is not proof your personal quota arrived.

## Commands and lifecycle

Python 3.10+, POSIX/network and installed IANA timezone data are sufficient;
no Codex account/CLI, paid API, notification permission or dependency is needed.
Replace STATE with a private absolute parent outside the repository/plugin cache.
Public state/lock/stop token always live in STATE/public-reset-watch; existing
quota monitoring is independent.

```sh
python3 scripts/quota_guard.py resetwatch --help --locale en
python3 scripts/quota_guard.py resetwatch read --state-dir STATE
python3 scripts/quota_guard.py resetwatch start --state-dir STATE --provider modelyard --events planned,completed,banked,manual_credit --interval 3600 --timezone Asia/Shanghai
python3 scripts/quota_guard.py resetwatch stop --state-dir STATE
python3 scripts/quota_guard.py resetwatch status --state-dir STATE --format text --locale en
```

Natural-language requests work in all nine guides: a question means one `read`;
start only for explicit monitoring intent. The host must supervise the foreground
process and consume JSON. Stop/restart to change settings; verify the original
process exited before claiming a stop. A request acknowledgement is not exit.
Stopping public news does not stop research or the quota monitor. No daemon,
autostart, cron or cloud automation is installed. Sleep, exit and source/network
delays interrupt monitoring; no real-time or complete-delivery guarantee is made.
`status` is cached, not a new source fetch or proof of process liveness.

## Public RSS and source limits

Default `modelyard` makes one anonymous GET to the fixed, reviewed public address
`https://tibo.modelyard.dev/feed.xml`. No HTML parsing, X fetching, redirects,
API discovery, `/api/` or JSON endpoints are used. The unverified HTML adapter in
original candidate 0146949 was removed after a synthetic template counterexample.
There is no arbitrary network provider URL flag. Replacing a provider remains a
Python integration (`provider.fetch(now)`), requiring code/source review and an
explicit transport allowlist change; it is not an invitation to probe other APIs.

RSS 2.0 parsing validates the exact channel identity, canonical channel/self URL,
Atom namespace, item event/guid origin, singleton plain-text fields, exact category,
explicit-timezone RFC 822 date and unique trailing `Source:` original-post URL.
Only thsottiaux X/Twitter status paths are accepted; IDs must agree with publication
time within 120 seconds. These checks do not independently authenticate authorship.
DTD/entity declarations, nested/hidden/escaped HTML fields, namespace spoofing,
ambiguous fields/categories, unsupported XML and oversized bodies/entries fail
with no announcement events. Entire body: 1 MiB; each entry: 32 KiB; at most 500
entries. Category mapping is exact, never broad keyword inference of completion.
Known unrelated categories are skipped; an unknown category is unavailable.

| Type | Meaning |
|---|---|
| `planned` | A public plan; not completion |
| `completed` | Aggregator reports a completion category; individual receipt unknown |
| `banked` | Saved reset/card announcement; receipt and manual redemption unknown |
| `manual_credit` | Manual credit announcement; inspect original scope/conditions |

Every RSS record is `verification: third_party_reported`,
`source_verification: unverified`. A category is not official verification.
The supplied RSS has no products, checked_at, updated_at or verification fields.
`products` uses only explicitly named products in the aggregator-supplied source
text; otherwise it is `["unknown"]`. The title's product context is stored
separately as `reported_products`; it cannot authenticate scope. A ChatGPT-only
source text is retained/deduplicated but not sent as a Codex/Work alert. Unknown
scope notices explicitly say scope is unknown. Source text itself is not stored.

`fetched_at` is the local timestamp of a successful fetch attempt, separate from
`published_at`. `provider_checked_at` is null for RSS: no source synchronization
heartbeat was observed. `feed_last_build_at` and `source_latest_published_at` are
feed/event dates, never current verification times. `latest_entry_age_seconds`
is the age of the newest entry, not measured synchronization lag. `source_coverage`
remains `unknown`: HTTP success cannot prove every announcement was indexed.
Old but valid RSS can establish a silent baseline; latest-event age is not used to
permanently reject a normally served feed. See [source evidence](RESET-SOURCES.md).

## Baselines, deduplication and timing provenance

First successful fetch silently records the baseline and original metadata.
Failures never establish a baseline. New old posts, repeated IDs/types, restarts,
filtered types and downgraded states do not replay history. Switching provider
identity builds a new silent baseline while preserving global post/type dedup.
Separate completion posts are distinct, with their own IDs/publication dates.

RSS has no modification date, so its `updated_at` is null and
`update_time_source` is `unavailable`. A previously seen planned post changing to
completed can emit exactly one `announcement_kind: aggregation_status_update`,
with `status_time_provenance: local_observation` and
`first_observed_status_at` from the local durable ledger. The original publication
date is unchanged. This means a new observed aggregator classification, not a new
original post or a verified edit/completion time. The observer cannot tell whether
a delayed cache or a later provider correction caused the change. Old completion
states already seen do not replay. Age limits still apply to the original post
when no source update date is available. Providers with explicit source update
times keep that separate provenance instead.

Durable intent precedes output: delivery is at most once, and a crash can lose an
alert. Corrupt/full state fails rather than silently rebuilding. Event fields
`user_notified: false`, `personal_quota_verified: false`, `task_action: none` never
claim consent, receipt or task control. Metadata includes original URL/ID,
publication, observed status date, attribution and verification provenance.

## Configuration and errors

`--events` selects comma-separated planned,completed,banked,manual_credit (all by
default). `--interval` is 3600..86400 seconds, default hourly. Minimum cooldown is
persisted before I/O and survives one-shot reads/restarts. Errors back off with
jitter up to 24 hours and bounded Retry-After. `--timeout` is 1..30 seconds, default
10, shared across the snapshot; one additional socket timeout can overrun it.
`--max-age` bounds cached fetch/check evidence (default 172800 seconds, at least
the interval and at most 604800), not source coverage. With RSS cached status uses
`fetched_at`; offline version-1 JSON can provide its own explicit `checked_at`.
`--event-age` bounds new-post age (default 604800, range 3600..2592000).
`--timezone` selects IANA human display; wire dates remain UTC. Nine-language help,
notices, errors and configuration text use the existing locale/fallback rules.
JSON keys, enum values and exit codes never translate.

Network/HTTP, stale cached evidence, parse/source, clock and state failures mean
unknown, with events empty, never reset/no-reset. A success without new events is
not proof no reset occurred. A cooldown makes no request; inspect last_poll_status
and last_success_at. `read` exits 0 for success/baseline/cooldown, 2 for unavailable
or invalid results; SIGINT/SIGTERM exits 130. Stop exits 0 only for accepted intent.

## Local notification integration

The CLI emits events and does not install an OS notification sender.
`quota_guard.notifications.notification_payload(event, locale, timezone)` builds
a localized payload; `deliver_local(event, host_callback, locale, timezone)` calls
the host's existing LOCAL adapter. A concrete integration consumes each JSON line,
iterates its new events, and invokes that callback, retaining the original/source
links and scope/provenance warnings. The callback is supplied by the host, not
implemented by a platform sender in this package. Without such a host route only
text/JSON output is available. No email/Slack/network messaging is sent. Real-host
notification delivery remains unverified; callback invocation is not proof a user
received anything. The host records actual delivery separately.

## Offline and replaceable providers

`--fixture FILE` works only with `read`, uses separate synthetic state, never
fetches URLs or calls an account, and emits `synthetic: true`. The original two
known October 17 IDs are dedup/baseline fixtures, never new alerts.
`fixtures/modelyard-rss-item-124.xml` is an explicitly cropped real header/first
item supplied by the parent review, with closing tags added; it is not a complete
feed capture. Provenance is stored next to it. Tests pass that RSS through the real
parser with mock transport; a separate native Library text read of the five-item
real crop matched its 4351-byte SHA256 and passed parser compatibility checks; the CLI's offline fixture contract remains JSON:

```json
{"schema_version":1,"checked_at":"2026-10-18T00:00:00Z","events":[{"post_id":"2111492738025959922","post_url":"https://x.com/thsottiaux/status/2111492738025959922","published_at":"2026-10-17T16:21:00Z","event_type":"planned","products":["unknown"],"source_url":"https://tibo.modelyard.dev/events/124","source_verification":"unverified"}]}
```

A provider integration returns `(source_checked_at_or_null, events)`. Null check
time requires `source_check_available=False`; optional `snapshot_metadata` holds
latest publication/build dates. It must never invent source timestamps. Runtime
normalizes/validates every injected record. JSON parsing catches deep-recursion
errors as unavailable/backoff, with recovery tests. Hostile same-user configuration
or DNS is not a security boundary; default transport only permits the fixed RSS.
