# App-server startup troubleshooting

Use the bundled script with a trusted official Codex CLI, an already configured
eligible account, and a private state directory under a trusted writable parent.
A failed read must remain unavailable; never infer remaining quota from a startup
error or from an earlier successful query.

## Interpret the evidence

- A PATH warning on stderr alone is not fatal. The relevant evidence is a
  completed app-server handshake and a valid response for the requested quota
  bucket. Do not classify an otherwise successful read as failed from that warning.
- EOF only means the transport closed. It does not establish that authentication
  is missing, expired or invalid. Report the observed failure without guessing its
  cause or printing raw server messages.
- A successful handshake without a valid matching quota response does not establish
  quota availability. Missing, malformed, stale and mismatched data remain blocked.
- An old cached snapshot is not a live diagnostic. Report its timestamp and stale
  status explicitly, or perform a fresh authorized one-shot read.

## Permission failures

In supported environments, app-server startup may need access to its normal
storage. If the host blocks that legitimate operation, request approval using the
host's normal approval mechanism for the same operation and environment. Respect
any denial. Approval is not a reason to relax the sandbox or broaden access.

Keep runtime quota state outside the plugin cache and source repository. If the
chosen directory is unavailable or rejected, choose an authorized private writable
location under a trusted parent. Do not change an existing directory's permissions
to circumvent rejection.

## Do not bypass the failure

Do not read credentials, authentication tokens or session logs directly. Do not
copy authentication data, change CODEX_HOME, redirect internal storage, override
logging/database paths, alter security settings, or relax filesystem permissions.
Use only the existing official app-server route and normal approval flow. If that
route remains unavailable, report quota as unavailable and the verified blocker.
Do not claim monitoring started until its foreground process is running and its
state can be observed. Never report a hard percentage reserve or arbitrary cloud
work termination from local monitoring.
