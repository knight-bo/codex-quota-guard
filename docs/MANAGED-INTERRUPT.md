# Managed interruption evidence / 受管中断的证据边界

## What the implementation establishes / 当前实现能证明什么

- `quota_guard/rpc.py` launches a **new** `codex app-server` child, completes
  `initialize` / `initialized`, and allows only `initialize`,
  `account/rateLimits/read` and `turn/interrupt` requests.
- It exposes no attach, resume, task-start or task-list route. Supplying IDs to the
  CLI does not establish that its new connection owns or can access those tasks.
- `ManagedStop` in `quota_guard/state.py` binds one exact thread/turn pair. Real
  interruption requires explicit authorization for that pair and an RPC session
  that can actually reach it. Never guess IDs or target unrelated work.
- Offline tests exercise fake RPC responses, durable attempt tracking and
  unconfirmed checkpoint reporting. They do not demonstrate live interruption.

`rpc.py` 会启动新的 `codex app-server` 子进程并完成握手，只允许初始化、额度读取和
`turn/interrupt` 请求。没有连接既有会话、恢复、启动任务或列举任务的接口。
给 CLI 填入任务标识，不代表新连接拥有或能访问该任务。
`ManagedStop` 绑定精确的 thread/turn；真实中断需要对此目标的明确授权及确实可访问
它的 RPC 会话。离线测试使用假 RPC，不能证明真实中断已成功。

The currently inspected CLI offers no verified route to interrupt an existing
external task. This is a limit of the verified integration, not a claim that such
integration is universally impossible. Hosted tasks and detached workers require
their own supported control and completion evidence.

当前检查的 CLI 没有已验证的路径来中断既有外部任务。这仅说明当前集成的证据边界，
并非断言所有集成都不可能做到。托管任务和独立工作进程需要各自支持的控制路径及
完成证据。

## Result meanings / 结果含义

- `would_interrupt`: dry-run intention; no interrupt request was sent.
- `pending_unknown`: durable intent exists; delivery or response may be unknown.
  The attempt ledger prevents automatic retry, including after restart. Inspect
  the owning session; do not erase the ledger merely to retry.
- `interrupt_acknowledged`: the RPC returned a successful response. Independently
  observe the matching `turn/completed` and check worker completion.
- `checkpoint_status: unconfirmed`: always unconfirmed in this package, even after
  an interrupt acknowledgement. `checkpoint.json` requests a cooperative save;
  it is neither proof of a saved checkpoint nor a pause/resume facility.

`would_interrupt` 仅表示演练意图；`pending_unknown` 表示已记录意图，但发送或响应
可能不明，不自动重试。`interrupt_acknowledged` 仅表示 RPC 返回成功，仍需分别观察
匹配的 `turn/completed` 及工作进程完成情况。`checkpoint_status` 始终为
`unconfirmed`；检查点请求不是保存证明，也不是暂停/恢复功能。

The guard sends the interrupt immediately after writing the checkpoint request;
it does not wait for a save acknowledgement. Work needing save-before-interrupt
must use a separate two-phase coordinator. No task automatically restarts after
quota resets, and polling cannot guarantee a hard quota reserve.

守卫写入检查点请求后即尝试中断，不等待保存确认。需要“先保存再中断”的任务应使用
独立的两阶段协调器。额度恢复后不会自动重启任务；轮询不能保证硬性额度保留。

## Smallest next validation / 最小下一步验证

Only after explicit user authorization, use one disposable local task whose owning
orchestrator retains its initialized RPC session. Integrate the existing
`ManagedStop` adapter with **that same session**, bind only its authorized exact
thread/turn, then verify the interrupt response, matching `turn/completed` and
worker shutdown separately. Any durable save requires its own evidence. This is a
proposed integration test, not an existing CLI attach feature. No real model task
is created or interrupted as part of this documentation work.

取得用户明确授权后，才使用一个可丢弃的本地测试任务。由任务所属协调器保留已初始化
的 RPC 会话，在同一会话复用现有 `ManagedStop` 适配器，仅绑定已授权的精确目标。
分别确认中断响应、匹配的 `turn/completed` 和工作进程退出；持久化保存另需证据。
这是待实施的集成验证方案，不是 CLI 已有的连接功能。本次文档工作不创建或中断真实
模型任务。

See [architecture](ARCHITECTURE.md), [validation](VALIDATION.md),
[startup diagnostics](STARTUP-DIAGNOSTIC.md), and the implementation in
[`rpc.py`](../quota_guard/rpc.py), [`state.py`](../quota_guard/state.py) and
[`cli.py`](../quota_guard/cli.py).
