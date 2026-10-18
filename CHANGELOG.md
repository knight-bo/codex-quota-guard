# Changelog

## 0.5.0 (unreleased) — optional public reset announcements

- Add independent `resetwatch read/start/stop/status` commands with silent first-run
  baselines, durable post/state deduplication and planned-to-completed upgrades.
- Distinguish planned, completed, banked and manual-credit announcements; never
  treat public reports as personal quota restoration or task-control authority.
- Add a fixed ModelYard public RSS adapter and injectable provider integration,
  strict source/date validation, bounded fetching, persistent hourly cooldown,
  stale/error reporting and bounded backoff. Actual cropped RSS compatibility is tested; live transport remains
  blocked here. Source coverage is unknown and local status-observation times
  never masquerade as original edit dates. See docs/RESET-SOURCES.md.
- Add a local host-notification payload/callback adapter, event filters, timezone
  display, isolated offline fixtures and complete resetwatch help/errors/notices
  plus plugin usage in all nine existing languages. Machine JSON stays stable.
- Remove the superseded HTML adapter and arbitrary network endpoint flags; reject
  DTD/entity, hidden/nested XML, ambiguous categories/sources and recursive JSON.
- Preserve official account quota reads, arbitrary targets, confirmation events,
  managed-interruption boundaries and all prior offline regressions.

Earlier versions and their checks remain documented in docs/VALIDATION.md and git
history; 0.4.0 introduced arbitrary task targets and confirmation events.
