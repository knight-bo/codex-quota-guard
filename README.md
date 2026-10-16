# codex-quota-guard

Version 0.2.0 — plugin entry, explicit polling lifecycle and quota reporting.

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
no pip install is needed for the plugin. GitHub distribution is separate from
public plugin-directory approval. Installing the plugin does not start monitoring.

Examples: “查看 Codex 剩余额度”, “启动监控，保留 10%，缓冲 2 个百分点，每 30 秒检查”,
and “停止额度监控”. A one-shot request never starts a polling process.

## CLI install and test

Requires Python 3.10+ and POSIX (Linux/macOS). Live mode additionally requires an
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

Commands emit allowlisted JSON, never server payloads. `read`/`check` exit 0 only
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

`start` is an alias for `watch`, not a background daemon. Keep its foreground
process/session supervised. Stop that monitor cooperatively with
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
