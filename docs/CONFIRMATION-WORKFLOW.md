# Host confirmation workflow

Version 0.4.0. This is a host integration contract, not a claim that the CLI can
send confirmations or pause arbitrary tasks. Distribution is by GitHub download.
The desktop-only plugin remains read-only by default.

## 1. Establish the monitoring agreement

A request for remaining quota is one `read`; a reserve preference alone is not a
request to monitor. Parse any finite remaining-quota target in 0–100, including
80, rather than mapping natural language to preset values. Distinguish remaining
from used quota. Resolve the intended task to a verified stable identity. If the
task is ambiguous, ask; do not invent an ID, enumerate unrelated sessions, or
start research to manufacture a target.

Record the specific task, bucket, target, warning/confirmation margins, polling
interval and freshness limit in the host's task context. Target-mode requires
`--task-key` from that verified context. Persisted state and emitted records use
only the hashed binding, never the raw task ID. This binding identifies the
agreement; it is neither authentication nor authorization to control the task.

Example (substitute verified values and a private absolute state path):

```sh
python3 SCRIPT start --bucket codex --target 80 --warn-margin 2 --confirm-margin 1 \
  --task-key VERIFIED_STABLE_TASK_KEY --interval 30 --max-age 90 --state-dir STATE
```

The target is a remaining percentage. Margins are percentage points, each finite
in 0–100, with warning margin >= confirmation margin. Each trigger line is capped
at 100. Thus target 80 with margins 2/1 gives lines 82/81/80. Zero margins are valid.
The legacy reserve/buffer mode remains separate. In target mode the effective
admission threshold is exactly target with buffer 0; do not mix both modes.

## 2. Keep the user able to answer

`start` / `watch` is a foreground CLI, not a daemon. The host must put it in a
supervised background session and keep the conversation available. Preserve the
session handle and private state directory so status and exit can be verified.
Do not block the host indefinitely waiting on a foreground loop. If the host
cannot maintain both monitoring and interactive replies, explain that limitation
and provide a one-shot read only. Do not claim continuous monitoring is running.
No nohup, hidden daemon, login hook, scheduled startup or research task is needed.

## 3. Interpret events, then ask

Read the CLI's default JSON and versioned event records. Use valid live readings
from the selected bucket and each applicable window. Missing, stale, synthetic or
invalid readings are not evidence that a threshold has been reached or cleared.
Explain unavailable readings honestly. Polling can miss an exact crossing.

| Condition in an applicable valid window | CLI event | Host behavior |
| --- | --- | --- |
| remaining <= min(100, target + warn-margin) | warning | Tell the user the task is nearing the target when useful. |
| remaining <= min(100, target + confirm-margin) | confirmation_required | Ask for the task-specific decision. |
| remaining <= target | target_reached | Check approval and supported control access; never treat the event itself as approval or a completed pause. |

At 81% for target 80, ask “到80%时暂停此项任务吗？” (“Pause this task when it
reaches 80% remaining?”), with enough context to identify the exact task. If the
first valid read is already at or below target, confirmation and target-reached
events are immediate. Ask “当前已到或低于80%，现在暂停此项任务吗？” (“It is already
at or below 80%; pause this task now?”). Do not describe a future crossing that
has already happened. With equal/zero margins, several stages may occur on one
read; consolidate the user message rather than asking duplicate questions.

An emitted event proves neither user notification nor delivery, awareness, consent,
or task completion. The host must track its actual question and the user's reply
separately. Silence is not approval. A repeated JSON record is not a repeated
approval. `--target` rejects `--allow-interrupt` to prevent a confirmation bypass.

### JSON contract and missed delivery

The top-level `confirmation` object has `schema_version: 1`, `task_binding`,
`target_percent`, `warn_margin`, `confirm_margin`, `stage`,
`target_reached_latched`, `quota_policy_allow_new_work`, `quota_policy_reason`,
`pause_authorized: false`, and `task_paused: false`. Stage is `observing`,
`warning`, `confirmation_required`, `target_reached`, or `unavailable`.

Each `events` item has `schema_version: 1`, `id`, `type`, `task_binding`,
`remaining_percent`, `target_percent`, `observed_at`, `target_already_reached`,
`requires_user_confirmation`, `requires_task_authorization`, `user_notified: false`, `pause_authorized: false`,
and `task_paused: false`. Types are `warning`, `confirmation_required`,
`target_reached`, and `quota_changed`. These false fields deliberately make no
claim about actions outside the CLI.

Events are persisted at-most-once, not guaranteed-delivery messages. Cached
`check --target X --task-key K` must also match the target margins; it returns
`events=[]` with cached confirmation stage. If a stream event was missed, the
host must reconcile stage with its actual conversation history and recover any
pending question. Never infer consent from the lack of a new event.

Target flags are supported for `read`, `watch` / `start`, and `check`, not CLI
`simulate`. Decimal targets such as 37.5 are supported. Target 100 may require an
immediate question even with 100% remaining; target 0 warns near exhaustion and
does not protect against running out of quota.

## 4. Apply only a specific, supported decision

A user decision covers only the identified task, target and accessible supported
control route explained to them. Verify ownership and control access before any
action. If no supported route exists, explain the blocker and request the user's
manual action; do not invent arbitrary hosted-cloud control. CLI events do not
initiate a control request. The separate legacy managed-turn adapter is not a
shortcut around this workflow or proof of a resumable pause.

At/below target, target-mode denies new work at the user-selected detection line: `allow_new_work=false`, reason
`confirmation_target_reached`. This is a cooperative admission decision, not a
real task pause. The original reserve-policy decision remains in the confirmation
context for inspection. Once reached, the target admission latch remains blocked
across quota rises, resets and same-task/target restarts. Neither a later healthy
quota read nor a reset automatically resumes work.

If the host has explicit approval and a verified route, it may perform only that
approved action using that route. Observe the task's actual state before saying it
paused/stopped. An RPC acknowledgement is not completion, a checkpoint request is
not a saved checkpoint, and a turn interrupt does not terminate all detached
workers or promise resumability. No guarantee can be made about stopping exactly
at the target: reporting delay, polling, retries and concurrent usage remain.

## 5. Restart, change, cancel

The stage ledger persists deduplication for the same task/target across restarts.
Reusing a state directory does not establish a new agreement or a fresh user
approval. Do not reset state merely to repeat warnings. If the host restarts,
recover actual question/approval context separately; absence of a new CLI event
is not proof that the user has already been asked.

Changing target or other monitoring configuration requires a new explicit
monitoring agreement. Request `stop` using the same state directory, observe the
original process's confirmed exit, then start with the agreed values. Never hot
swap a running target. User cancellation means stop the watch and verify exit;
stopping a watch does not stop the task it was observing.

Use `--new-cycle` only when the user explicitly requests a new monitoring cycle,
after the prior monitor has stopped. Initial normal startup does not need it.
This explicitly clears the confirmation event ledger and admission latch for the
new cycle; it does not mean the user approved a pause, approved a resume, or that
a task resumed. Do not use it to silently clear a reached target on reset/rise.

## Safety boundaries

Never read credentials or session logs, alter authentication, CODEX_HOME,
permissions or security settings, or bypass a denied app-server operation. Use the
normal host approval route if access requires it. Monitoring does not start real
research, purchase quota, make country-availability claims or confer new task
control. Keep raw task identifiers out of persisted/output monitoring records.


Target mode (`--target`) uses the exact chosen target as the admission threshold
with buffer 0; warning/confirmation margins do not move it. Do not combine
`--target` with `--reserve`, `--threshold`, or `--buffer` (rejected). The legacy
reserve/buffer mode remains available without `--target`. The prior default of
10% never replaces a selected task target, including a target below 10%.
