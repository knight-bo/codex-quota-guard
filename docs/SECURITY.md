# Security and limitations

The default is read-only monitoring. Only explicit managed-thread/managed-turn
binding plus allow-interrupt enables an interrupt request. No task enumeration,
PID search, arbitrary shell command or research-process signaling is performed.
Only the transport child created by the guard is cleaned up.

The runtime does not parse credentials, invoke login, purchase credits, redeem
resets, change security settings or call private endpoints. An installed official
Codex CLI handles its own configured authentication. Keep executable PATH and the
state directory parent trusted. State is private, atomic and single-writer, but
is not a boundary against same-user attackers.

Logs use allowlisted fields and omit raw server errors, notifications, prompts
and task identifiers. Input framing is bounded. Nonblocking writes and reads
share deadlines. IDs are strictly typed, buffered responses expire and pending
notifications are handled before returning a read. Incomplete frames fail closed.

Missing, invalid, stale, reset-expired or ambiguous readings deny new work.
Synthetic snapshots always deny real work, and check requires live provenance.
Interrupt intent is persisted before sending; ambiguous outcomes never retry
automatically. Interrupt acknowledgement is not completion confirmation.
Checkpoint status is always unconfirmed: the feature only requests a save.

Residual risks include future notification arrivals after the snapshot boundary,
concurrent external quota consumption, stale snapshots after abrupt monitor death
until their TTL, legitimate same-epoch quota adjustments conservatively blocked,
unsupported protocol revisions and unavailable authenticated integration evidence.
An orchestrator must supervise monitor liveness and verify its own worker and
checkpoint completion. No atomic reservation, detached-process termination or
arbitrary hosted-cloud control is promised. POSIX only.

Automated tests and source review reduce risk but are not proof of security.
No third-party security certification is claimed.


## Plugin lifecycle and state

Version 0.2.0 packages a skill and a foreground CLI, with no autostart hooks or
daemon. Monitoring requires an explicit request. Cooperative stop is scoped to
the selected private state directory; observing the monitor's exit is still
required. Stop requests do not signal research processes or establish cloud-task
termination. Keep writable state outside the plugin cache and repository.

Read quota only through the existing official app-server route. Never parse
credentials or session logs directly, change CODEX_HOME, or relax permissions
and security settings to bypass a startup failure. Use normal host approval for
a legitimate operation when needed, and honor denial.

Localization is presentation-only. Locale identifiers select from a fixed list,
not arbitrary filesystem paths. Human reports never display raw server messages,
exception strings or prompts. Machine reason codes, state and permission behavior
are not translated. Language support does not bypass eligibility or regional policy.


Target confirmation mode never calls ManagedStop and rejects --allow-interrupt
and managed bindings. Every generated event explicitly leaves user notification,
pause authorization and task-paused status unconfirmed/false. These fields do not
attempt to reflect external host actions. Hashing a task key is identification,
not authentication. The host must verify the task, ask the user, remain available
for replies, and use only an already-authorized supported route. A reached target
closes admission but is not proof a running task stopped. No automatic resume is
triggered by quota resets, rises, or an event-ledger reset.

## Optional public-announcement boundary (0.5.0)

Public monitoring is independent of account reads and starts only explicitly.
Anonymous public HTTPS GETs send no user/account identifiers, request body, cookies
or authentication; no credentials/session logs are read. X/Twitter destinations
and redirects are rejected. Public content cannot invoke commands or task control:
only bounded factual IDs, URLs, dates and enumerated types/claims are retained;
raw posts, summaries, scripts and instruction text are not consumed or emitted.
Default network transport only permits the reviewed fixed RSS address. Arbitrary
network endpoint flags were removed; provider replacement requires code/source
review. Host/URL allowlists are not a security boundary against malicious same-user
code/configuration or DNS. Offline JSON remains bounded and handles recursion errors.

A provider may be mistaken, incomplete or dishonest. Original URL/author-path and
snowflake consistency checks are not independent X authentication. Provider
verification never becomes an official API claim or personal quota receipt.
Missing/stale/malformed/unavailable data remain unknown. Public events cannot
clear quota targets, restore admission, redeem credits, pause or resume work.
No notification permissions are requested; a host may use its existing local
adapter. Emission does not establish delivery. Persistence precedes output, so a
crash can lose an alert. Sleep and process/network/provider failures can leave
coverage gaps. The parser is tested against the parent-supplied actual cropped RSS item; live
transport/full-feed success is not claimed in this blocked environment. Robots
permission is not a redistribution licence; source terms remain a review obligation.
