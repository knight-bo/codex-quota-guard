# English — install and use (0.3.0)

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

Try “Check my Codex quota”, “Start quota monitoring with a 10% reserve, 2-point
buffer and 30-second interval”, or “Stop quota monitoring”. A quota question means
one read. The assistant must verify the original monitor has exited after stopping.

## Explicit CLI use

From the repository root, replace STATE with your chosen private absolute path
outside the repository/plugin cache, under a trusted writable parent:

```sh
python3 scripts/quota_guard.py read --bucket codex --state-dir STATE --format text --locale en
python3 scripts/quota_guard.py start --bucket codex --reserve 10 --buffer 2 --interval 30 --state-dir STATE --format text --locale en
# From another supervised terminal/session:
python3 scripts/quota_guard.py stop --state-dir STATE --format text --locale en
```

`start` is a foreground monitor. No daemon or automatic startup is installed.
Keep its session supervised; a stop request alone does not prove exit. JSON remains
the default for machines. Invalid/stale data must not be presented as current quota.

The 12% alert threshold does not guarantee a hard 10% reserve. Other clients can
spend quota. Arbitrary cloud tasks cannot be controlled. Managed interruption needs
explicit authorization for the exact accessible thread/turn; checkpoint status is
always unconfirmed. Use normal permission approval; never change permissions,
CODEX_HOME or authentication to bypass failures, or read credentials/session logs.
