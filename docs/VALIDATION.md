# Validation

## Version 0.1.1 baseline

Run `python3 -m unittest discover -s tests -v` from the source root.
All 35 automated tests passed. Wheel build, isolated installation, and CLI
synthetic-replay smoke testing passed. Tests use synthetic data and fake child
processes; these are not authenticated integration tests.

Regression coverage includes concurrent checks during simulation, interrupted
simulation, missing provenance, multiple quota windows, missing/stale/invalid
readings, reset ordering, exact bucket selection, response-plus-notification in
one write, buffered-response deadlines, strict integer response IDs, blocked
stdin writes with an outer watchdog, partial frames, persistent at-most-one
interrupt attempts and unconfirmed checkpoint reporting.

Real authenticated quota reads and real managed-turn interruption are unverified.
No guarantee is made for controlling hosted cloud tasks or detached processes.
Checkpoint requests do not verify that application data was saved. This release
is experimental advisory software, not an atomic quota reservation service.


## Version 0.2.0 validation

The development validation run passed 48 offline unittest cases and compileall.
These results validate the exercised implementation and synthetic protocol paths,
not live account access. Actual plugin installation in the client UI, authenticated
quota reads, and managed-turn interruption have not been verified for this release.
Manifest JSON parsing is checked separately; it is not proof of client acceptance.

Version 0.2.0 also passed a no-dependency/no-build-isolation wheel build,
installation into a fresh isolated virtual environment, synthetic CLI replay,
and rejection of that replay by `check` (exit 2). The wheel contains the Python
CLI; plugin installation uses the complete repository package and manifests.

The 0.2.0 review regression covers a stop accepted during an in-flight read:
healthy, low-quota and transport-error outcomes all exit without a new interrupt
or healthy report; stopped state and subsequent cached checks deny admission.

## Version 0.3.0 multilingual validation

All 60 offline unittest cases passed, including the original protocol, cancellation,
cleanup and fail-closed regressions. New tests cover nine complete UTF-8 catalogs,
explicit locale selection and regional/unsupported fallback, missing translation
fallback, UTC/numeric presentation, stale/invalid data, unconfirmed checkpoints,
ASCII-terminal escaping, unchanged machine JSON and persisted policy, identical
read exit codes, localized runtime failures and stop-request wording.

Compileall, wheel build and installation into an isolated virtual environment
passed. Rendering from outside the source tree verified that the installed wheel
contains and loads all nine locale catalogs. Relative links in the multilingual
entry and guides resolve. Tests use synthetic data, not personal quota readings.
This release has not undergone a new live authenticated/client-UI integration test.
Translations received an editorial pass; they are not certified translations.


## Version 0.4.0 task confirmation events

All 78 offline tests passed. Added cases cover arbitrary decimal targets, 0/100
endpoints, rejected nonfinite/out-of-range targets and invalid margins, 82/81/80
warning/confirmation/reached events, first reads already below target, skipped
crossings, no implicit authorization or interruption, persisted deduplication,
reset/rise latch preservation, explicit new-cycle behavior, hashed task binding,
cached policy/task mismatch rejection and stop-during-read cancellation.
Target mode uses exactly the chosen target and buffer 0, rejects mixed legacy
reserve/buffer flags, and does not substitute the old default for low targets.
A supervised fake app-server process exercised event streaming and cooperative stop.
The legacy 5/10/20/30% reserve and exact/default-buffer boundary tests remain.

Tests create no real model task, send no real user notification and pause no user
task. Events are pending host work, not evidence of delivery, consent or completion.
Real end-to-end host event handling, interactive confirmation and an authorized
supported task-control route remain integration checks, not established by tests.
This release is distributed by GitHub only. Official-directory submission work was
canceled; no submission ZIP, portal upload or identity verification is part of it.

## Original 0.5.0 HTML candidate 0146949 (superseded, not for release)

All 125 offline unittest cases passed: the original 78 quota/protocol/target tests
and 47 new public-watch cases. New coverage includes silent baselines (the two
known October 17 posts), durable original metadata/deduplication, planned-to-
completed upgrades, new completion posts, old/late/edited posts, reversed state
ordering, duplicate conflicts, filtered states, provider changes, corrupt/empty/
oversized state, source/date forgery, stale checks, clock rollback, persisted
cooldown, bounded backoff/rate limits, failure recovery and strict JSON contracts.
Mock HTTP tests cover anonymous GETs, rejected redirects/X targets, deadlines,
size/content-type/encoding limits, 403/429/timeouts and Retry-After. No real account
or quota is required. Fake-provider subprocesses verify cooperative stop, SIGTERM,
lock release and independent public/quota state; cleanup failures are redacted.

All nine catalogs have identical keys and format placeholders, valid UTF-8 and
localized public-watch help, event payloads, errors and configuration text. Tests
exercise all nine CLI help/text paths, ASCII terminal fallback, regional/unsupported
fallback, UTC/IANA date display, identical machine JSON and guide coverage.
Compilation and relative Markdown link checks passed. A no-dependency, no-build-
isolation wheel build and isolated virtual-environment installation passed;
installed entry-point/help/catalog smoke checks run outside the source tree.

The actual public-source CLI returned exit 2 / reset_network_error on this
network, with no baseline, no announcement events, unknown last success and a
persisted next-poll deadline. It did not query a Codex account or touch research.
Rendered source pages were browser-inspected; raw provider RSS/JSON and real
urllib HTML transport/DOM were not validated. Synthetic markup tests are not
captured production payloads. See RESET-SOURCES.md for this release blocker and
provider terms/robots review. Real-host notification delivery and the default
provider's live success path remain unverified. A callback/payload test is not
proof a user received a notification. Nothing was published as part of validation.


## Revised 0.5.0 RSS candidate

The default HTML adapter was removed after a synthetic template counterexample.
The new parser uses the exact first-item RSS fixture supplied by parent review,
explicitly cropped and provenance-marked, plus adversarial/synthetic cases.
The parent five-item Library sample could not be downloaded through this
environment's proxy (one normal byte-transfer attempt, CONNECT 403). A subsequent
native Library text read matched the exact 4351-byte SHA256 and passed five-item
parser compatibility checks. That is not a successful live provider fetch.
Tests cover namespaces, original author/host/guid, exact/ambiguous/unknown categories,
missing/multiple/trailing sources, nested/hidden/escaped HTML, DTD/entities, size
limits and dates. Old valid feeds build baselines without invented heartbeats.
Same-post upgrades retain publication and first local observation separately;
ChatGPT-only scope is filtered and unknown scope stays explicit. Deep JSON fails
as reset_parse_error/backoff and subsequently recovers without a false baseline.
All nine locales cover fetch/coverage/scope and local status-change provenance.
The local notification callback is only an integration interface, not a platform
sender or demonstrated user delivery. Full parent real-feed retest remains separate.

The revised run passed all 131 offline tests (78 retained quota tests plus 53
public-watch cases), compileall, relative links and diff checks. A new wheel
build/isolated install passed outside the source tree, including all nine help,
coverage reports and offline CLI paths plus the real five-item crop. The exact
4351-byte cropped input was SHA256-verified via native Library text, not fetched
live by this environment. Full verbose output is included in the review package.
