# Languages / 语言

Version 0.4.0 provides optional human-readable reports and updated target-workflow
guides in nine languages. The default
JSON output, protocol fields, reason codes, state files, thresholds and exit codes
stay unchanged. Language support does not imply service availability in every
country or override account eligibility, regional restrictions or administrator policy.

| Language | Locale | Installation and usage |
|---|---|---|
| English | en | [English](i18n/en.md) |
| 简体中文 | zh | [简体中文](i18n/zh.md) |
| Русский | ru | [Русский](i18n/ru.md) |
| 日本語 | ja | [日本語](i18n/ja.md) |
| 한국어 | ko | [한국어](i18n/ko.md) |
| Español | es | [Español](i18n/es.md) |
| Français | fr | [Français](i18n/fr.md) |
| Deutsch | de | [Deutsch](i18n/de.md) |
| Português | pt | [Português](i18n/pt.md) |

From the repository root, replace STATE with a private absolute writable directory:

```sh
python3 scripts/quota_guard.py read --bucket codex --state-dir STATE --format text --locale ja
```

`--format json` is the default and should be used by automation. `--locale` only
changes `--format text`; it never changes policy, RPC parameters, persisted data
or process exit codes. Regional variants select their base language (for example,
`pt-BR` → `pt`, `zh-CN` → `zh`). Matching ignores case and accepts underscores.
Unsupported locales fall back to English; absent or invalid individual translations
also fall back to English. The default locale is English, independent of environment
variables. Chinese text is Simplified Chinese; regional variants do not add a
separate Traditional Chinese translation.

Dates in human reports use ISO 8601 UTC. Numeric percentages and durations retain
their values, with `.` as the decimal separator. UTF-8 terminals display translated
characters; legacy encodings use escaped characters rather than crashing.
Core status and runtime failure messages are translated. CLI option names, `--help`,
argument-parser usage errors, protocol identifiers and synthetic fixture data remain
English/machine-oriented. Translate neither JSON fields nor state files.

The plugin skill can answer in the user's chosen language while using JSON for
reliable interpretation. A one-shot query does not start monitoring. Explicit
start/stop and normal permission approval remain required. See each guide and
[security](SECURITY.md) for safety boundaries.

## 0.4.0 guide coverage

All nine linked guides cover installation, one-shot reads, a natural-language
task request, and the same explicit `--target 80 --task-key TASK --warn-margin 2
--confirm-margin 1` workflow. Each explains arbitrary 0–100 remaining-percentage
values including 37.5; 82/81/80 warning/confirmation/admission stages; immediate
confirmation when already at/below target; and 0/100 endpoints. Legacy reserve
examples are compatibility mode, not fixed task presets.

Every guide also explains the supervised background and interactive-host
requirements, event delivery versus authorization and actual task control, the
unsupported-route limitation, and no automatic resume after quota resets. The
CLI itself does not ask the user or pause a task. These documentation translations
do not establish real-host end-to-end notification or pause validation. Machine
event identifiers remain untranslated, and automation should consume JSON.
