# Codex Quota Guard: Installation und Nutzung

Voraussetzungen: Python 3.10 oder neuer, ein POSIX-System und die offizielle Codex-CLI mit einem angemeldeten, zur Kontingentabfrage berechtigten Konto. Verwenden Sie den regulären Genehmigungs- und Anmeldevorgang. Umgehen Sie keine Berechtigungen oder Authentifizierung. Ändern Sie `CODEX_HOME` nicht zur Umgehung von Einschränkungen und lesen Sie keine Zugangsdaten oder Sitzungsdateien direkt aus.

## Installation

Führen Sie Folgendes aus:

```sh
codex plugin marketplace add knight-bo/codex-quota-guard
```

Starten Sie die Desktop-App neu, wählen Sie **Codex Quota Guard Local**, installieren und aktivieren Sie das Plugin. Eine Veröffentlichung auf GitHub bedeutet keine Zulassung im öffentlichen Plugin-Verzeichnis. Die Installation startet keine Überwachung und richtet keinen automatischen Start ein.

## Abfragen, starten und stoppen

Beispielanfragen:
- „Zeige mein verbleibendes Codex-Kontingent.“
- „Starte die Überwachung mit 10 % Reserve, 2 Prozentpunkten Puffer und einer Prüfung alle 30 Sekunden.“
- „Stoppe die Kontingentüberwachung.“

Eine einmalige Abfrage startet keine regelmäßigen Prüfungen. Im Stammverzeichnis des Pakets:

```sh
python3 scripts/quota_guard.py read --bucket codex --state-dir STATE --format text --locale de
python3 scripts/quota_guard.py start --bucket codex --reserve 10 --buffer 2 --interval 30 --state-dir STATE --format text --locale de
# In einem anderen Terminal, während start im Vordergrund läuft:
python3 scripts/quota_guard.py stop --state-dir STATE --format text --locale de
```

Ersetzen Sie `STATE` durch den absoluten Pfad eines privaten Verzeichnisses (0700), das Ihrem Benutzer gehört und außerhalb des Repositorys sowie des Plugin-Caches unter einem vertrauenswürdigen, beschreibbaren übergeordneten Verzeichnis liegt. Umgehen Sie keine Zugriffsbeschränkungen mit `chmod`. Verwenden Sie zum Stoppen genau dasselbe Verzeichnis. `codex` ist eine beispielhafte Kontingentgruppe; wählen Sie ausdrücklich die für Ihre Arbeit passende Gruppe.

`start` läuft im Vordergrund. Behalten Sie die Sitzung unter Aufsicht. Prüfen Sie nach der Stoppanforderung, ob der Prozess tatsächlich beendet wurde. Die Anforderung allein ist kein Nachweis. Verwenden Sie für verschiedene Kontingentgruppen getrennte Zustandsverzeichnisse.

## Grenzen

Die Erkennung greift bei höchstens 12 % Restkontingent: 10 % Reserve plus 2 Prozentpunkte Puffer. Sie garantiert keine feste Reserve von 10 %. Andere Clients können weiterhin Kontingent verbrauchen. Ungültige oder veraltete Werte zeigen keinen aktuellen Restbestand an. Das Plugin steuert keine beliebigen Cloud-Aufgaben. Sein Feld `checkpoint_status` bleibt immer `unconfirmed`; nur der zuständige Orchestrator prüft Speicherung und Abschluss unabhängig. Eine verwaltete Unterbrechung erfordert eine ausdrückliche Genehmigung für den genauen zugänglichen Thread und Turn. Eine bestätigte Unterbrechung bestätigt keinen Aufgabenabschluss. Bei fehlenden aktuellen Daten sollte keine neue Arbeit aufgrund alter Freigaben gestartet werden.

Weitere Informationen: [README](../../README.md) · [Sprachen](../LANGUAGES.md).
