# codex-quota-guard

Version 0.5.0 — optional public reset announcements, separate from personal quota.

[English · 简体中文 · Русский · 日本語 · 한국어 · Español · Français · Deutsch · Português](docs/LANGUAGES.md)

Experimental advisory plugin and CLI for conservative Codex quota monitoring.
Python runtime dependencies are limited to the standard library.
Not affiliated with OpenAI. [中文说明](README.zh-CN.md).

**Default behavior is read-only alerts.** Missing, invalid, stale or failed readings deny
new work. This is an advisory gate: an orchestrator must check it before each work unit.
It does not control existing hosted cloud research tasks, and cannot guarantee a
percentage reserve while other clients consume quota.

## Plugin installation

See the [Chinese installation guide](docs/PLUGIN-INSTALL.zh-CN.md). The package
includes a portable `plugin.json`, a compatibility manifest and a repository-local
marketplace catalog. Skills run the bundled `scripts/quota_guard.py` with Python;
no pip install is needed for the plugin. Distribution is by GitHub download only. The plugin remains desktop-only.
Installing the plugin does not start monitoring or research.

Examples: “查看 Codex 剩余额度”, “监控这项任务，剩余额度到 80% 时先问我是否暂停”,
and “停止额度监控”. Targets are arbitrary finite values from 0 to 100, not presets.
A one-shot request never starts a polling process.

## CLI install and test

Requires Python 3.10+ and POSIX (Linux/macOS). Personal-quota live mode additionally requires an
installed official `codex` CLI with an already configured, eligible account.
The runtime uses only the Python standard library. Packaging uses setuptools.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/codex-quota-guard --help
```

No login, token handling, purchases, credit redemption or security configuration
changes are performed. Credentials are handled only by the official Codex child.
The guard does not read credential files. Keep the official executable on a trusted PATH.

## Synthetic replay (no authentication, no inference)

```sh
codex-quota-guard simulate --bucket demo --fixture fixtures/demo.jsonl \
  --state-dir "$HOME/.local/state/codex-quota-guard-demo"
```

The fixture is invented. `at` is synthetic Unix time, and events are `read`,
`updated`, `error`, or `tick`. Replay never interrupts. Every persisted snapshot is marked `synthetic` and
denies real work from the first write, including during interruption. Replay
output uses `simulated_allow_new_work` for hypothetical decisions; `check` requires
explicit `live` provenance and rejects older snapshots without provenance. Never use fixture output as authenticated evidence.

## Live read and monitoring

```sh
codex-quota-guard read --bucket codex --state-dir "$HOME/.local/state/codex-quota-guard-live"
codex-quota-guard start --bucket codex --reserve 10 --buffer 2 \
  --interval 30 --max-age 90 --state-dir "$HOME/.local/state/codex-quota-guard-live"
# In the cooperating orchestrator, before each work unit:
codex-quota-guard check --bucket codex --state-dir "$HOME/.local/state/codex-quota-guard-live"
```

Choose `--bucket` explicitly from the metered bucket appropriate to your work.
State paths above are examples: use a private location under a trusted writable
parent available in your execution environment.
`codex` above is an example, not automatic discovery or a universal model mapping.
Use separate state directories/guards for distinct buckets; all required guards
must allow work. The multi-bucket map is authoritative when present. A legacy
single bucket is accepted only when its `limitId` exactly matches. Unidentified
buckets deny work. Both applicable primary and secondary windows are checked;
explicit null means not applicable, omitted fields mean unknown.

`remaining = 100 - usedPercent`. With defaults, any window at **12% remaining or
less** denies new work (10% reserve + 2 percentage-point buffer). These are quota
windows, not conversation context usage or token counts. Invalid percentages,
server-classified reached limits, expired resets and missing windows deny work.
A reset time passing never grants quota: a new valid read is required.

Protocol writes are nonblocking and deadline-bounded. Response IDs must be exact
integers. Already-buffered and immediately readable notifications are processed
before returning a response; partial pending frames fail closed. Deadlines apply
even to buffered messages. Notifications arriving after that boundary remain an
unavoidable polling race, so a healthy read is not an atomic quota reservation.

Commands emit allowlisted JSON by default, never server payloads. Add
`--format text --locale en` for human reports; supported languages and fallback
rules are in [Languages](docs/LANGUAGES.md). Machine fields and state stay unchanged. `read`/`check` exit 0 only
when healthy, otherwise 2; `simulate` exits 0 for a completed replay regardless of
its quota decisions. Ctrl-C exits 130. Watch retries connection failures with
bounded exponential jitter (up to 60 seconds). Notifications invalidate cached
permission; the next poll re-reads. Decreasing usage within the same reset epoch,
older reset epochs, and disappearing windows remain blocked conservatively.
A legitimate quota adjustment in the same epoch may therefore stay blocked until
the next epoch; investigate manually instead of assuming an automatic reset.

State directory must be private (0700), owned by the current user, under a trusted
parent. Atomic snapshots permit `check` while a single monitor holds the writer
lock. `check` must use identical policy flags. No shell is executed by the guard.
The monitor revokes permission on normal shutdown; after abrupt death, a prior
healthy snapshot can remain usable until its short freshness deadline. For strict
liveness, the orchestrator must also supervise the monitor process. `check` is not
an atomic reservation: another client can spend quota immediately afterward.

## Monitoring lifecycle and status

`start` is an alias for `watch`, not a background daemon. The host must run its
foreground process in a supervised background session while remaining available
to receive the user’s replies. If the host cannot keep both the process and
conversation active, explain that continuous monitoring would block interaction
and offer a one-shot read only; do not promise continuous monitoring. Stop that monitor cooperatively with
`codex-quota-guard stop --state-dir YOUR_PRIVATE_STATE_DIR`, using
the same directory. A stop request is not proof the process has exited: observe
its session and final status. Ctrl-C is also supported. No login hooks, scheduled
startup or automatic reset/restart are installed.

Always supply `--state-dir`, outside the plugin cache and repository, under a
trusted writable parent. `check` reads cached state rather than querying the
server. Report its observation time, freshness/stale status and each applicable
window separately; a cached reading is not a current live query. Use the same
bucket, reserve, buffer and maximum age when checking. `--reserve` aliases
`--threshold`; reserve and buffer are percentages and percentage points respectively.

Do not change authentication, `CODEX_HOME`, permissions or sandbox rules to fix a
failed query. If the normal host approval flow is needed for app-server access,
request that approval. A PATH warning on stderr alone does not establish failure;
a valid handshake and matching quota response are the evidence. Never read
credential files or session logs to obtain quota.

## Explicit managed-turn interruption

Read-only monitoring never interrupts. Only opt in for a thread/turn your
orchestrator actually owns, on the app-server connection where it is available:

```sh
codex-quota-guard watch --bucket codex --state-dir "$HOME/.local/state/codex-quota-guard-managed" \
  --managed-thread YOUR_OWN_THREAD_ID --managed-turn YOUR_OWN_TURN_ID \
  --allow-interrupt
```

Omit `--allow-interrupt` for a `would_interrupt` simulation. Binding is an exact
thread/turn pair, with no enumeration, wildcard, PID search or arbitrary task
selection. This CLI starts its own stdio app-server; it does not attach to an
existing hosted cloud session. If that server cannot access the bound turn,
interruption cannot succeed. The reusable `ManagedStop` adapter can be integrated
into an orchestrator using its own initialized RPC session.

Before its single interrupt attempt it persists intent and writes an advisory
checkpoint request. This release does not implement checkpoint ACK verification
or save-before-interrupt waiting; `checkpoint_status` is always `unconfirmed`. A timeout/crash leaves `pending_unknown`, never automatic
retry. Successful RPC acknowledgement is `interrupt_acknowledged`, **not proof
of turn completion or checkpoint completion**. The owning orchestrator must
observe `turn/completed` on its session and verify its own workers. This release
does not perform that confirmation. See [checkpoint contract](docs/ARCHITECTURE.md).
`turn/interrupt` does not promise termination of detached subprocesses, nor control
over arbitrary hosted cloud tasks. No OS signals are sent to managed work; only
the guard's own transport child is cleaned up.

## Security, validation and license

See [security review](docs/SECURITY.md) and [validation](docs/VALIDATION.md).
Licensed under the [MIT License](LICENSE). Copyright (c) 2026 knight-bo.
Protocol reference: [official app-server documentation](https://learn.chatgpt.com/docs/app-server).


## Choose any remaining-quota target

“Ask me before pausing this task at 80% remaining” selects a real target of 80,
not a preset or 80% used. Resolve the specific task to a verified stable identity
before starting target-mode monitoring:

```sh
codex-quota-guard start --bucket codex --target 80 --warn-margin 2 --confirm-margin 1 \
  --task-key VERIFIED_STABLE_TASK_KEY --interval 30 --max-age 90 \
  --state-dir "$HOME/.local/state/codex-quota-guard-target"
```

The task key is supplied from verified host context, not a guessed name; only its
hashed binding is persisted or emitted. Do not echo raw task IDs in reports.
The CLI emits versioned advisory events; the host AI reads the JSON and handles
user-facing messages. At or below 82% it emits a warning, at or below 81% a
`confirmation_required` event, and at or below 80% `target_reached`. At 81% the
host asks “到80%时暂停此项任务吗？” (“Pause this task when it reaches 80%?”).
If the first valid read is already at or below 80%, confirmation and target-reached
events are emitted immediately; ask whether to pause now, not at a future crossing.
Never execute a pause just because either event occurred.

Targets accept any finite 0–100 value. Margins are finite percentage points in
0–100, with warning margin >= confirmation margin; effective trigger lines are
capped at 100. A zero margin is allowed. All percentages describe remaining quota.
Events do not prove a message was delivered, seen or approved, nor that work paused.
`--allow-interrupt` is rejected with `--target`; events cannot bypass confirmation.
Any later action requires approval for this specific verified task and target,
plus an accessible, supported control route. Monitoring alone neither starts
research nor grants control over arbitrary cloud tasks.

Warning/confirmation deduplication persists for the same target/task across
restarts. A quota rise or reset never resumes work automatically or renews
approval. Changing the target or other monitoring configuration requires a new
explicit monitoring agreement: stop the monitor, verify its process exited, then
restart. A user cancellation stops the watch; verify exit before reporting success.
See the [host confirmation workflow](docs/CONFIRMATION-WORKFLOW.md).

## Separate reserve/admission mode

The existing `--reserve` / `--threshold` and `--buffer` controls remain a separate
cooperative new-work admission policy. Reserve accepts 0–100; buffer is
nonnegative and reserve + buffer must not exceed 100. For an exact 80% admission
line use `--reserve 80 --buffer 0`; with buffer 2 it gates at 82% or less. These
flags do not express target-mode confirmation or grant permission to stop work.
Neither mode guarantees an exact stopping balance: polling, RPC/retry delays,
in-flight work and concurrent clients can consume quota after detection.
See [managed scope](docs/MANAGED-INTERRUPT.md) for the separate opt-in legacy route
and its unverified live-turn limitations.

Reached targets also latch cooperative admission closed across quota rises and
restarts (`allow_new_work=false`, `confirmation_target_reached`); this is not proof
of a paused task. `--new-cycle` clears the event ledger/admission latch only for
an explicitly requested new cycle after the previous monitor has stopped. It
does not approve or resume work, and is unnecessary for initial startup.

Decimal targets such as 37.5 are supported. Target 100 can ask immediately even
at 100% remaining; target 0 offers no protection from exhaustion. Target flags
work with read/start/watch/check, not CLI simulate. Cached target checks must
repeat the same task key, target and margins; `events=[]` is normal for check.
The host recovers pending questions from cached stage plus actual conversation
history, because persisted at-most-once events do not guarantee user delivery.


Target mode (`--target`) uses the exact chosen target as the admission threshold
with buffer 0; warning/confirmation margins do not move it. Do not combine
`--target` with `--reserve`, `--threshold`, or `--buffer` (rejected). The legacy
reserve/buffer mode remains available without `--target`. The prior default of
10% never replaces a selected task target, including a target below 10%.

## Optional public Tibo reset announcements

`resetwatch` is an independent, opt-in public announcement watch; it needs no
account or API key. It distinguishes `planned`, `completed`, `banked`, and
`manual_credit`, retaining original post/source URLs and provider verification
claims. A public completion announcement never confirms personal quota restoration
or authorizes resuming/pausing research. It never changes quota/confirmation state.

```sh
python3 scripts/quota_guard.py resetwatch --help --locale en
python3 scripts/quota_guard.py resetwatch read --state-dir PUBLIC_STATE
python3 scripts/quota_guard.py resetwatch start --state-dir PUBLIC_STATE --events completed,banked --interval 3600 --timezone UTC
python3 scripts/quota_guard.py resetwatch stop --state-dir PUBLIC_STATE
```

Replace PUBLIC_STATE with a private absolute parent outside the repository/cache.
First success silently builds a baseline; subsequent post/state events deduplicate
across restarts. Polling is hourly by default, with persisted cooldown and bounded
backoff. Failures/stale/invalid sources mean unknown. The host consumes JSON and
uses its existing local notification adapter; CLI events do not prove delivery.
Sleep, exit and network/provider delay interrupt monitoring; no real-time guarantee.
The default reads ModelYard's fixed public RSS; HTML and arbitrary endpoint flags
were removed. Fetch time is separate from feed publication dates; source coverage
remains unknown. Same-post classification updates have local observation provenance.
The supplied real cropped RSS sample is tested; live transport remains blocked here.
[Full configuration, JSON contract and limitations](docs/RESET-WATCH.md) ·
[Source inspection/permission limits](docs/RESET-SOURCES.md) ·
[Nine-language help and plugin guides](docs/LANGUAGES.md).
