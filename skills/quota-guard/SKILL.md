---
name: quota-guard
description: Watch public Tibo reset announcements independently on explicit request, or query Codex remaining quota or explicitly start/stop task-scoped confirmation monitoring at any remaining-quota target; retain separate reserve/buffer admission checks. 用于查询 Codex 剩余额度、查看缓存状态、设置保留额度和缓冲，以及明确启动或停止额度监控。
---

# Codex quota guard

Version 0.5.0. Desktop-only; distributed by GitHub download.

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
5. Reserve/admission-mode defaults: reserve 10%, buffer 2 percentage points, interval 30 seconds,
   maximum reading age 90 seconds. Apply the user's explicit settings. Explain
   that any applicable window at or below reserve + buffer denies new work.
   `--reserve` and `--threshold` are aliases. For `check`, repeat exactly the
   same bucket, reserve, buffer and max-age as the producing monitor/read.

## Commands

Below, SCRIPT is the resolved absolute bundled script path and STATE is the
chosen private absolute state directory. Substitute actual paths using argv or
safe shell quoting; never run these placeholder names literally.

- One-shot live query: `python3 SCRIPT read --bucket codex --state-dir STATE`
- Separate reserve/admission monitoring: `python3 SCRIPT start --bucket codex --reserve 10 --buffer 2 --interval 30 --max-age 90 --state-dir STATE`
- Task-target monitoring (only after resolving the task): `python3 SCRIPT start --bucket codex --target 80 --warn-margin 2 --confirm-margin 1 --task-key VERIFIED_STABLE_TASK_KEY --interval 30 --max-age 90 --state-dir STATE`
- Cached check: `python3 SCRIPT check --bucket codex --reserve 10 --buffer 2 --max-age 90 --state-dir STATE`
- Cooperative stop: `python3 SCRIPT stop --state-dir STATE`

`start` aliases `watch` and remains a foreground process. The host must run it in
a supervised background process session that can remain active and later be
observed, while keeping the conversation available to receive user replies. Record that session
and STATE for this task. Do not use nohup, daemonization, login hooks, cron,
automations or automatic startup. If the host cannot preserve both the process and interactive conversation,
explain that continuous monitoring would block interaction; provide a one-shot
read only, and never claim ongoing monitoring. Never kill processes by
name or search for unrelated PIDs.

Changing target, margins, reserve, buffer or polling interval requires a new
explicit monitoring agreement; it is not a hot configuration update. Request `stop` on the same state directory, confirm the old
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


## Languages and human reports

Use the user's requested language; supported bundled guides and human reports are
English (en), Simplified Chinese (zh), Russian (ru), Japanese (ja), Korean (ko),
Spanish (es), French (fr), German (de), and Portuguese (pt). Natural-language quota
questions in any of these languages still mean one read, never implicit monitoring.
Read `../../docs/LANGUAGES.md` relative to this skill directory for the guide index.
For machine interpretation keep default JSON; never translate JSON fields, reason
codes, state files or protocol parameters. If a human CLI report is wanted, add
`--format text --locale LANGUAGE`. Regional forms use the base language; unsupported
locales fall back to English. This does not change thresholds or permissions.
Describe invalid/stale values as unavailable/historical in every language and retain
all start/stop, approval, interruption and unconfirmed-checkpoint boundaries above.
Language support is not a claim of service availability in every country.


## Arbitrary targets and task-scoped confirmation

Use `--target` for an explicitly requested confirmation workflow such as “监控这项
任务，剩余额度到80%时先问我是否暂停”. Accept any finite 0–100 remaining percentage,
not just preset examples. Never confuse 80% remaining with 80% used. Resolve a
verified stable task identity and pass it as `--task-key`; if ambiguous, ask which
task. Do not guess a key, enumerate unrelated sessions or create a research task.
Only the hashed binding is persisted/emitted; do not echo raw task IDs in reports.

Set `--warn-margin 2 --confirm-margin 1` unless the user chooses other margins.
Each must be finite in 0–100, warning >= confirmation, with trigger lines capped
at 100. Margins are percentage points, not fractions or percentages of the target.
For target 80, warning is at <=82, confirmation_required at <=81, and target_reached
at <=80. At 81 ask “到80%时暂停此项任务吗？” with clear task context. If the first
valid reading is already <=80, immediate confirmation and reached events mean
ask now: “当前已到或低于80%，现在暂停此项任务吗？”. Never auto-execute from an event.

The CLI emits versioned events in JSON for the host AI. It does not send or verify
user notification, collect approval, or confirm that a task has paused. Read the
JSON directly; do not use translated human text as the machine interface. Maintain
actual question, reply and task-state evidence separately. Silence is not consent.
Approval is limited to the specific verified task, target and accessible supported
control route. If the route is unavailable, explain that limitation. No arbitrary
cloud control is implied. Target mode rejects `--allow-interrupt`; do not remove
`--target` to bypass this safety boundary.

At/below target the top-level admission decision must be blocked even if the old
reserve policy allows it (`allow_new_work=false`, `confirmation_target_reached`).
The confirmation context retains the original policy result. This cooperative
admission block is not a real pause. The reached latch persists across quota rises,
resets and same-task/target restarts; never auto-resume work.

Stage deduplication persists for the same target/task across restarts. An absent
new event does not prove the user previously received or answered a question.
A new target/configuration requires a new explicit agreement: stop, verify exit,
then restart. A cancellation stops the watch, with verified exit. Use `--new-cycle`
only for an explicitly requested new monitoring cycle after the old monitor has
stopped; it clears the event ledger/admission latch, not user consent or task state.
Initial startup needs no such flag. Never use it to auto-resume after quota reset.

Reserve/admission mode remains independent: `--reserve` accepts finite 0–100 and
buffer is nonnegative with reserve + buffer <=100. An exact 80% admission line is
`--reserve 80 --buffer 0`; buffer 2 gates at 82%. Neither this nor target detection
can guarantee a stopping balance. Do not interpret an admission denial as proof
of paused research. No actual research should be started to demonstrate monitoring.

For cached target status, use `check --target X --task-key K` with the identical
margins, bucket and policy settings. `check` returns `events=[]`; inspect the
cached `confirmation.stage` and reconcile actual chat history to recover a
missed/pending question. Persisted at-most-once events do not guarantee delivery.
The confirmation object retains `quota_policy_allow_new_work` and
`quota_policy_reason`; `pause_authorized` and `task_paused` remain false because
the CLI does not verify external actions. Event `user_notified` is likewise false.
Target mode works with read/start/watch/check, not CLI simulate. Decimals such as
37.5 are valid; target 100 may ask immediately at 100%, while target 0 provides
no protection from exhaustion.

Read `../../docs/CONFIRMATION-WORKFLOW.md` for host questions, event handling and
lifecycle. Read `../../docs/MANAGED-INTERRUPT.md` for separate legacy managed-turn
limitations. Only the owning orchestrator with verified access and explicit
approval may use an appropriate control route; completion and saved progress
require separate evidence.


Target mode (`--target`) uses the exact chosen target as the admission threshold
with buffer 0; warning/confirmation margins do not move it. Do not combine
`--target` with `--reserve`, `--threshold`, or `--buffer` (rejected). The legacy
reserve/buffer mode remains available without `--target`. The prior default of
10% never replaces a selected task target, including a target below 10%.

## Separate public Tibo announcement watch (0.5.0)

Also use this skill for explicit public-reset requests in any of the nine supported
languages, including “每小时提醒 Tibo 重置公告”, “只看 completed 和 banked”, “停止公共
重置提醒”, “watch Tibo reset announcements”, or equivalent localized requests.
Read `../../docs/i18n/LOCALE.md` for the user's selected base locale (en fallback),
including localized examples, configuration and limitations. Read
`../../docs/RESET-WATCH.md` for the wire contract and
`../../docs/RESET-SOURCES.md` before claiming provider verification or readiness.

This route needs Python/POSIX/network, but NO authenticated Codex CLI/account.
The account prerequisites and bucket rules above apply only to personal quota.
Never read credentials, host session logs or unrelated task state for public news.
Resolve SCRIPT exactly as above. A public-news question means `resetwatch read`,
not account `read`, research or continuous watching. An explicit public watch
request authorizes `resetwatch start` in an observed supervised process session;
installation alone does not. Never substitute a hosted automation or autostart.

Use a private absolute STATE outside the plugin cache/repository. Runtime isolates
public monitoring in STATE/public-reset-watch. Record the process session and STATE.
These commands never call account/rateLimits/read, turn/interrupt or modify the
quota monitor's state, stop token, confirmation target or reached latch:

- Once: `python3 SCRIPT resetwatch read --state-dir STATE`
- Start: `python3 SCRIPT resetwatch start --state-dir STATE --events planned,completed,banked,manual_credit --interval 3600 --timezone UTC`
- Stop: `python3 SCRIPT resetwatch stop --state-dir STATE`
- Cache: `python3 SCRIPT resetwatch status --state-dir STATE`
- Localized help: `python3 SCRIPT resetwatch --help --locale LOCALE`

Apply explicit event filters, interval and IANA timezone. Keep JSON for the host;
text/help use all nine existing locales and the usual fallback. Stop, verify the
original process has exited and restart to change settings; retain STATE for
deduplication. Never stop research or quota monitoring when stopping public news.
A cooperative stop acknowledgement is not process exit. If the host cannot keep
a supervised process available, explain the limitation and offer a one-shot read;
do not claim a continuing watch. Sleep, exit, network and provider latency affect
coverage; no real-time guarantee. Minimum persisted polling interval is one hour.

Inspect the version-1 `events` and source metadata. `planned` is only a plan;
`completed` is a third-party report of a public completion announcement;
`banked` means saved reset/card credit with personal receipt and manual redemption
unknown; `manual_credit` announces manual credit whose scope must be checked in
the original. Preserve original post URL/ID, publication date, provider source URL
and provider verification claim. Never re-label `third_party_reported` as official
API data, independently authenticated evidence or personal quota restoration.
The default reads only the fixed public RSS. HTML and arbitrary endpoint flags
were removed. Be candid about docs/RESET-SOURCES.md source/transport limitations.
RSS has no source heartbeat/update timestamp: provider_checked_at and updated_at
are null. fetched_at is local retrieval evidence; feed lastBuildDate/latest entry
is not synchronization. Report source_coverage unknown even after HTTP success.
Same-post classification upgrades are aggregation_status_update with local
first_observed_status_at, never a new post or verified edit time. Products are
from supplied source text or unknown; reported title/context is only a provider
claim. ChatGPT-only records are not sent as Codex/Work announcements.
Never bypass a 403/login restriction or scrape X credentials. Do not guess another
site's JSON schema, infer completion from dates, or ingest forecast probabilities.

First success only establishes a silent historical baseline. New states are
persistently deduplicated; a planned-to-completed upgrade can notify only the new
state. Network/HTTP failure, stale provider check time, parse/date/source errors
and cooldown are not reset/no-reset verdicts. Read `status`, `last_poll_status`,
`last_success_at`, `provider_checked_at` and `next_poll_at`. `status` is cached,
never a live source query or proof of liveness. Absence of new events is not proof
that no reset happened. No failures may fabricate announcement events.

For each genuinely new event, use the host's existing LOCAL notification route,
keeping source URL and original post link, translated into the user's language.
`quota_guard.notifications.notification_payload(event, locale, timezone)` builds
the title/body; `deliver_local(event, host_callback, locale, timezone)` is the
callback adapter. No OS sender, new permission or external messaging account is
installed. If the host cannot send a local notification, explain the blocker;
do not claim delivery. Do not email or post to others. Record actual delivery
separately. `user_notified` remains false in emitted records; persistence precedes
emission and a crash may lose delivery. Never treat an event as consent to act.

Every notice must say public news does not establish personal quota receipt and
does not automatically resume or pause work. A separate explicit personal-quota
request may use the existing official read path, but a public announcement alone
must never invoke it, clear a target latch, redeem credit or touch research tasks.
