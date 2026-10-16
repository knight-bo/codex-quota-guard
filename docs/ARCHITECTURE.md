# Architecture and cooperative checkpoint contract

core.py validates quota snapshots and evaluates every applicable window in one
explicitly selected bucket. No token/context metric enters this policy.
rpc.py starts a dedicated official stdio child, sends initialize, waits for its
response, then sends initialized. Frames are newline-delimited JSON. Requests are
correlated by exact integer ID and bounded by a monotonic deadline and 1 MiB
frame limit. Nonblocking stdin writes share the request deadline. The deadline
is checked before/after buffered parsing. Responses are returned only after
already-buffered/readable notifications have been handled. A partial pending
frame fails closed; future arrivals after the drain boundary remain possible.
Unknown server requests are rejected. Only initialize, rateLimits/read and
turn/interrupt are permitted. Raw stderr and unrelated notifications are discarded.

Notifications account/rateLimits/updated and account/updated revoke cached
permission. They never authorize work. A notification received during a read
invalidates even that response to avoid notification/response races. Reconnect
creates a new transport and repeats initialization; local ordering evidence is
retained within the monitor lifetime. Cached healthy readings are never loaded
into a new monitor. Backoff limits retries to <=60 seconds plus RPC duration.

State writes use private temporary files, fsync, atomic replace and directory
fsync. One writer owns flock; readers consume whole snapshots. Persistent data
contains numeric decisions, policy, hashed binding identities and attempt states;
no raw account data, prompts, authentication material or original task IDs.
The state belongs to one cooperating user; it is not a security boundary against
that same user, a compromised Codex executable or a mutable/untrusted parent path.

## Version 1 checkpoint contract

1. The orchestrator owns an exact thread/turn pair and explicitly grants
   interruption. It supplies the same pair to its checkpoint worker and guard.
2. The identity is SHA-256 of Python json.dumps([thread_id, turn_id]).encode().
3. When blocked, ManagedStop durably marks pending_unknown and atomically writes
   checkpoint.json: {binding_sha256, requested: true, contract_version: 1,
   checkpoint_status: "unconfirmed"}.
4. The worker periodically reads this file, verifies its own binding hash, finishes
   an atomic checkpoint in its own application directory, stops starting work and
   reports checkpoint completion to its orchestrator. Repeated requests are harmless.
5. The guard immediately attempts turn/interrupt after the request file is written;
   it does not wait for checkpoint completion. Work needing guaranteed save-before-
   interrupt must implement a two-phase coordinator externally before opting in.
6. An acknowledged RPC marks interrupt_acknowledged. The orchestrator separately
   observes turn/completed and worker completion. A missing acknowledgement remains
   pending_unknown, preventing duplicate requests across restarts. Investigate on
   the owning session; do not delete the ledger to blindly retry.

No exactly-once network delivery claim is made: durable intent gives at-most-one
attempt, which may be lost before send. Safety is preferred over automatic retry.
No automatic restarts follow quota reset. Polling cannot guarantee a reserve;
a short interval, buffer and small work units reduce exposure. Concurrent spending,
network latency and reported quota granularity remain external limitations.

The checkpoint feature is explicitly request-only. This package has no ACK
consumer and cannot verify durable application saves. Every managed-action
report includes checkpoint_status=unconfirmed, including interrupt_acknowledged.
Never interpret transport acknowledgement as checkpoint success.
