---
name: quota-guard
description: Query Codex remaining quota, inspect cached quota state, or explicitly start/stop advisory quota polling with reserve, buffer and interval settings. 用于查询 Codex 剩余额度、查看缓存状态、设置保留额度和缓冲，以及明确启动或停止额度监控。
---

# Codex quota guard

Use this skill for “查看 Codex 额度”, “还有多少额度”, “保留 10% 额度”,
“启动/停止额度监控”, “每 30 秒检查”, “check remaining Codex quota”,
“start quota monitoring”, or “stop quota monitoring”. This is an independent,
local advisory guard. Do not promise a hard reserve or control of arbitrary cloud tasks.

## Resolve the request and execution context

1. A quota question means one `read`. A request for cached status means `check`.
   Neither starts monitoring. Start only on an explicit polling/monitoring request.
   A reserve preference alone does not authorize starting a process: ask whether
   the user wants one read or monitoring if intent is unclear.
2. For Codex quota, pass `--bucket codex` explicitly. For another bucket, obtain
   the exact identifier from the user or reliable task context. Never substitute
   another bucket or infer a universal model mapping. The runtime requires the
   selected map entry or matching legacy `limitId`; a mismatch is unavailable.
3. Resolve this SKILL.md's actual installed directory, then resolve
   `../../scripts/quota_guard.py` from it to an absolute path. Invoke that path
   with `python3`. Do not assume the shell's current directory is the plugin root.
   No pip install is required. Requires Python 3.10+, POSIX and a trusted installed
   official Codex CLI with an existing eligible authenticated account.
4. Always pass an absolute `--state-dir` in a private writable location outside
   the plugin cache and source repository, under a trusted parent. Use one
   directory per bucket/monitor. Keep it available for later `check` and `stop`.
   Do not write into installed skill files or assume a cache is writable.
   State must be owned by the current user with private 0700 permissions; the
   runtime creates its own state directory. Do not chmod an existing directory
   to evade rejection. Ask for a suitable location when none is authorized.
5. Defaults: reserve 10%, buffer 2 percentage points, interval 30 seconds,
   maximum reading age 90 seconds. Apply the user's explicit settings. Explain
   that any applicable window at or below reserve + buffer denies new work.
   `--reserve` and `--threshold` are aliases. For `check`, repeat exactly the
   same bucket, reserve, buffer and max-age as the producing monitor/read.

## Commands

Below, SCRIPT is the resolved absolute bundled script path and STATE is the
chosen private absolute state directory. Substitute actual paths using argv or
safe shell quoting; never run these placeholder names literally.

- One-shot live query: `python3 SCRIPT read --bucket codex --state-dir STATE`
- Explicit monitoring: `python3 SCRIPT start --bucket codex --reserve 10 --buffer 2 --interval 30 --max-age 90 --state-dir STATE`
- Cached check: `python3 SCRIPT check --bucket codex --reserve 10 --buffer 2 --max-age 90 --state-dir STATE`
- Cooperative stop: `python3 SCRIPT stop --state-dir STATE`

`start` aliases `watch` and remains a foreground process. Run it in a supervised
process session that can remain active and later be observed. Record that session
and STATE for this task. Do not use nohup, daemonization, login hooks, cron,
automations or automatic startup. If the host cannot preserve the process, report
that limitation rather than claiming ongoing monitoring. Never kill processes by
name or search for unrelated PIDs.

Changing reserve, buffer or polling interval on a running monitor is not a hot
configuration update. Request `stop` on the same state directory, confirm the old
process session exited, then `start` with the new settings. Preserve any unchanged
policy values. Do not stop an existing monitor merely because the user asks for
a one-shot balance. If its writer lock conflicts with `read`, explain that `check`
can report cached evidence, or use a separate private state directory for a new
one-shot live read. Never present the cached alternative as live.

`stop` requests shutdown through the same state directory. Observe the original
process session's exit before saying monitoring stopped; an accepted request is
not completion. Stopping polling does not stop the user's research work. Ctrl-C
on the exact owned foreground monitor is another supported way to stop it.

## Read results honestly

- Inspect `data_valid`, `stale`, `reported_at`, and `windows`; each window has
  `remaining_percent`, `window_duration_mins`, and `resets_at`. Report unavailable
  values as unknown, not zero. Report selected bucket, observation timestamp/timezone, stale/fresh status,
  reason, and each applicable window's remaining percentage and reset timestamp.
  Use returned window duration to describe a window; do not invent “daily” or
  “weekly”. Distinguish used from remaining (`100 - usedPercent`).
- `check` is cached evidence, not a new server query. Missing/invalid/expired or
  synthetic data never establish current quota or permission to work. Clearly
  say unavailable or stale when that is what the result means.
- Missing windows are unknown; explicit null windows are not applicable. A reset
  timestamp passing is not evidence of restored quota. Obtain a valid new read.
- Exit 0 from `read`/`check` means healthy; exit 2 means blocked or unavailable.
  Synthetic replay exit 0 only means replay completed, never live authentication.
- Threshold detection does not reserve quota. Concurrent clients, reporting delay
  and in-flight work can consume the remaining 10%. The cooperating orchestrator
  must check before each work unit; the guard does not enforce a platform limit.

## Safety and failures

Use the existing official app-server route. Never read credential files or session
logs directly; never change CODEX_HOME, authentication, filesystem permissions or
sandbox/security settings to make it work. No automatic login, purchase or credit
redemption. If a legitimate app-server operation needs host approval, request it
through the normal approval flow and honor denial. Distinguish a harmless stderr
PATH warning from actual failure: a successful handshake and valid matching quota
response take precedence. Do not expose raw server errors, account details or secrets.

Monitoring is read-only by default. Never add `--allow-interrupt`,
`--managed-thread` or `--managed-turn` just because the user requested a reserve.
Interruption additionally requires explicit authorization for the exact owned,
accessible thread/turn pair. This CLI uses its own app-server connection and
cannot stop arbitrary hosted cloud tasks. RPC acknowledgement is not confirmed
completion. Checkpoint requests are advisory: checkpoint_status remains
unconfirmed. Do not claim work was saved or all workers stopped without separate
verified evidence from the owning orchestrator.
