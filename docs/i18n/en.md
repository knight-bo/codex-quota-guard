# English — install and use (0.4.0)

[Languages](../LANGUAGES.md) · [Full README](../../README.md)

Requires Python 3.10+, macOS/Linux and the official Codex CLI with an already
configured, eligible account. This is an independent advisory tool, not an
OpenAI product. Language support does not expand account or regional eligibility.

## Install

```sh
codex plugin marketplace add knight-bo/codex-quota-guard
```

Restart the desktop app, select “Codex Quota Guard Local” in the plugin directory,
then install and enable “Codex Quota Guard”. GitHub distribution is not approval
for the public plugin directory. Installation does not start monitoring. If you
already installed it, refresh the marketplace and verify the installed version.

Try “Check my Codex quota”, “Watch this task and ask me at 81% remaining whether
to pause it at 80%”, or “Stop quota monitoring”. A quota question means
one read. The assistant must verify the original monitor has exited after stopping.

## Explicit CLI use

From the repository root, replace STATE with your chosen private absolute path
outside the repository/plugin cache, under a trusted writable parent:

```sh
python3 scripts/quota_guard.py read --bucket codex --state-dir STATE --format text --locale en
python3 scripts/quota_guard.py read --bucket codex --target 80 --task-key TASK --warn-margin 2 --confirm-margin 1 --state-dir STATE --format text --locale en
# Only when the host can supervise the background session and consume JSON:
python3 scripts/quota_guard.py start --bucket codex --target 80 --task-key TASK --warn-margin 2 --confirm-margin 1 --interval 30 --state-dir STATE
# From another supervised terminal/session:
python3 scripts/quota_guard.py stop --state-dir STATE --format text --locale en
```

`start` is a foreground monitor. No daemon or automatic startup is installed.
Keep its session supervised; a stop request alone does not prove exit. JSON remains
the default for machines. Invalid/stale data must not be presented as current quota.

The old `--reserve 10 --buffer 2` example is a separate compatibility mode:
its 12% detection line does not guarantee a hard 10% reserve. It is not a preset
for your task target. Other clients can spend quota. Arbitrary cloud tasks cannot be controlled. Managed interruption needs
explicit authorization for the exact accessible thread/turn; checkpoint status is
always unconfirmed. Use normal permission approval; never change permissions,
CODEX_HOME or authentication to bypass failures, or read credentials/session logs.

## Choose any remaining-percentage target

Say “Ask before pausing this task at 37.5% remaining” or “Watch this task; at 81%
remaining, ask whether to pause it at 80%.” Targets can be any finite number from
0 to 100, including decimals; they refer to **remaining**, not used quota. The
assistant must first read the actual quota and resolve the exact task. Replace
TASK above with that verified stable task identity, not a secret or an invented
ID. The monitor stores its hash. A task binding does not grant control access.

For target 80, default margins are 2 and 1 percentage points: at or below 82%,
create a warning; at or below 81%, request confirmation; at or below 80%, deny
new-work admission. The host asks “Pause this task when it reaches 80% remaining?”
If the first valid reading is already at or below 80%, ask immediately whether
to pause now. Target 100 asks immediately even at 100%; target 0 does not protect
against exhaustion. Polling and concurrent usage can skip a line or overshoot it.

`--target` uses exactly the chosen admission threshold with buffer 0. Do not
combine it with `--reserve`, `--threshold`, or `--buffer`; those combinations
are rejected. Change `--target 80` to `--target 37.5` for that exact value. Warning
and confirmation margins do not move the target itself.

The CLI only emits events. An event is not proof of notification delivery, user
authorization, or a paused task. Before starting continuous monitoring, the host
must support a supervised background session, consume its events, and keep the
conversation available for your reply. Otherwise explain the limitation and use
one-shot reads only. The host must actually ask you and obtain approval for the
specific task and supported control route. Without such a route, it can only
alert you and request manual action; it must not pretend to pause arbitrary tasks.

Events are deduplicated across restarts. A quota rise/reset never clears a reached
target or automatically resumes a task. A missed event does not mean you were
already asked or approved anything. See the [host workflow](../CONFIRMATION-WORKFLOW.md)
for recovery, explicit new cycles, and the unverified real-host integration limits.
