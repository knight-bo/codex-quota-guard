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
