# Codex Quota Guard 0.5.0: Installation und Nutzung

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
- „Überwache das Kontingent für diese Aufgabe alle 30 Sekunden. Warne mich bei 82 % Restkontingent und frage mich bei 81 %, ob du die Aufgabe bei 80 % pausieren sollst.“
- „Stoppe die Kontingentüberwachung.“

Eine einmalige Abfrage startet keine regelmäßigen Prüfungen. Vor dem Start einer laufenden Überwachung muss der ausführende Assistent die konkrete Aufgabe identifizieren, die CLI in einer beaufsichtigten Hintergrundsitzung ausführen und ihre Ereignisse verarbeiten können. Die Unterhaltung muss dabei für Ihre Antworten verfügbar bleiben. Falls das nicht möglich ist, muss der Assistent diese Einschränkung erklären und nur eine einmalige Abfrage anbieten. Er darf dann keine laufende Überwachung behaupten.

Im Stammverzeichnis des Pakets:

```sh
# Manuelle Abfrage auf Deutsch:
python3 scripts/quota_guard.py read --bucket codex --state-dir STATE --format text --locale de
python3 scripts/quota_guard.py read --bucket codex --target 80 --task-key TASK --warn-margin 2 --confirm-margin 1 --state-dir STATE --format text --locale de
# Der Assistent muss diese Sitzung im Hintergrund beaufsichtigen und die standardmäßige JSON-Ausgabe verarbeiten:
python3 scripts/quota_guard.py start --bucket codex --target 80 --task-key TASK --warn-margin 2 --confirm-margin 1 --interval 30 --state-dir STATE
# In einer anderen Sitzung mit demselben Zustandsverzeichnis:
python3 scripts/quota_guard.py stop --state-dir STATE --format text --locale de
```

Ersetzen Sie `TASK` durch die überprüfte, stabile Identität der konkret zu überwachenden Aufgabe. Erfinden Sie keine Identität und verwenden Sie keine Geheimnisse. Die gespeicherte und ausgegebene Zuordnung verwendet einen Hash statt der ursprünglichen Kennung und erteilt keine Berechtigung zur Steuerung der Aufgabe. Ersetzen Sie `STATE` durch den absoluten Pfad eines privaten Verzeichnisses (0700), das Ihrem Benutzer gehört und außerhalb des Repositorys sowie des Plugin-Caches unter einem vertrauenswürdigen, beschreibbaren übergeordneten Verzeichnis liegt. Umgehen Sie keine Zugriffsbeschränkungen mit `chmod`. Verwenden Sie zum Stoppen genau dasselbe Verzeichnis. `codex` ist eine beispielhafte Kontingentgruppe; wählen Sie ausdrücklich die für Ihre Arbeit passende Gruppe. Verwenden Sie für verschiedene Kontingentgruppen getrennte Zustandsverzeichnisse.

`start` bleibt ein Vordergrundprozess und ist kein eigenständiger Hintergrunddienst. Der Assistent muss die zugehörige Hintergrundsitzung behalten und beaufsichtigen. Prüfen Sie nach der Stoppanforderung, ob der Prozess tatsächlich beendet wurde. Die Anforderung allein ist kein Nachweis. Das Stoppen der Überwachung stoppt nicht die beobachtete Aufgabe.

## Restkontingent als Zielwert und Bestätigung

`--target` akzeptiert jeden endlichen Prozentwert des **verbleibenden** Kontingents von 0 bis einschließlich 100, auch Dezimalwerte wie `37.5`. Gemeint ist nicht der verbrauchte Anteil. Standardmäßig beträgt der Warnabstand 2 Prozentpunkte und der Bestätigungsabstand 1 Prozentpunkt. Bei Zielwert 80 gilt:
- Bei höchstens 82 % Restkontingent wird `warning` ausgegeben.
- Bei höchstens 81 % wird `confirmation_required` ausgegeben. Der Assistent muss die konkrete Aufgabe nennen und fragen: „Soll ich diese Aufgabe bei 80 % Restkontingent pausieren?“
- Bei höchstens 80 % wird `target_reached` ausgegeben und die Zulassung neuer Arbeit verweigert (`allow_new_work=false`). Diese kooperative Zulassungsentscheidung pausiert die Aufgabe nicht tatsächlich.

Die Abstände werden in Prozentpunkten angegeben und müssen endliche Werte von 0 bis 100 sein. Der Warnabstand muss mindestens so groß wie der Bestätigungsabstand sein. Jede Auslöseschwelle wird auf 100 % begrenzt. Die Abstände verschieben die Zulassungsschwelle nicht: Sie entspricht genau dem Zielwert, mit einem effektiven Puffer von 0.

Liegt der erste gültige Messwert bereits am oder unter dem Zielwert, muss der Assistent sofort fragen: „Es sind bereits nur noch 80 % oder weniger verfügbar. Soll ich diese Aufgabe jetzt pausieren?“ Bei Zielwert 100 ist die Frage selbst bei 100 % Restkontingent sofort fällig. Zielwert 0 garantiert keinen Schutz vor vollständigem Verbrauch. Fallen mehrere Stufen auf denselben Messwert, sollen sie in einer Nachricht zusammengefasst werden, ohne die Frage mehrfach zu stellen.

Ein Ereignis beweist weder, dass der Nutzer benachrichtigt wurde, noch dass eine Aktion genehmigt wurde oder die Aufgabe pausiert ist. Der Assistent muss die Frage tatsächlich stellen und die Antwort prüfen. Schweigen ist keine Zustimmung. Jede Aktion erfordert eine ausdrückliche Genehmigung für die konkrete Aufgabe und einen unterstützten, überprüften Steuerungsweg. Fehlt dieser, muss der Assistent das Hindernis erklären und den Nutzer um manuelles Eingreifen bitten. Beliebige Aufgaben dürfen nicht einfach pausiert oder beendet werden. Bevor eine Pause oder ein Stopp als erfolgt gemeldet wird, muss der tatsächliche Aufgabenstatus überprüft werden.

Nach Erreichen des Zielwerts bleibt neue Arbeit gesperrt, auch wenn das Kontingent steigt oder zurückgesetzt wird oder die Überwachung derselben Aufgabe mit demselben Zielwert neu startet. Arbeit wird niemals automatisch wieder aufgenommen. Für eine Konfigurationsänderung müssen die neuen Werte vereinbart, die Überwachung gestoppt und das Prozessende überprüft werden, bevor sie neu startet. Verwenden Sie `--new-cycle` nur bei einem ausdrücklichen Nutzerwunsch nach einem neuen Überwachungszyklus und erst nach dem Stopp des vorherigen. Das genehmigt weder eine Pause noch eine Wiederaufnahme. Ereignisse werden höchstens einmal protokolliert. Geht eines verloren, müssen der Zustand und der tatsächliche Gesprächsverlauf abgeglichen werden. Ein fehlendes neues Ereignis beweist nicht, dass bereits gefragt oder zugestimmt wurde.

## Kompatibilität mit dem Reservemodus

Der bisherige Modus `--reserve 10 --buffer 2` bleibt ausschließlich als Kompatibilitätsoption verfügbar. In diesem Modus greift die Erkennung bei höchstens 12 % Restkontingent und garantiert keine feste Reserve von 10 %. Kombinieren Sie `--target` nicht mit `--reserve`, `--threshold` oder `--buffer`; die CLI weist diese Kombinationen zurück. Eine bisherige Reserve von 10 % ersetzt niemals den gewählten Zielwert, auch wenn dieser unter 10 % liegt.

## Grenzen

Die regelmäßige Abfrage kann eine Schwellenüberschreitung verspätet erkennen oder den exakten Prozentwert verpassen. Verzögerte Daten und Verbrauch durch andere Clients verhindern eine Garantie für einen Stopp genau am Zielwert. Fehlende, ungültige, synthetische oder veraltete Werte zeigen keinen aktuellen Restbestand an und belegen keine erreichte oder überschrittene Schwelle. Bei fehlenden aktuellen Daten sollte keine neue Arbeit aufgrund alter Freigaben gestartet werden. Das Plugin steuert keine beliebigen Cloud-Aufgaben. Sein Feld `checkpoint_status` bleibt immer `unconfirmed`; nur der zuständige Orchestrator prüft Speicherung und Abschluss unabhängig. Eine verwaltete Unterbrechung erfordert eine ausdrückliche Genehmigung für den genauen zugänglichen Thread und Turn. Eine bestätigte Unterbrechung bestätigt weder Aufgabenabschluss noch gespeicherten Checkpoint oder Wiederaufnehmbarkeit. Dieser ältere Mechanismus darf die Bestätigung im Zielmodus nicht umgehen; `--target` weist `--allow-interrupt` zurück.

Weitere Informationen: [Bestätigungsablauf für den ausführenden Assistenten (Englisch)](../CONFIRMATION-WORKFLOW.md) · [README](../../README.md) · [Sprachen](../LANGUAGES.md).


## Optionale öffentliche Tibo-Meldungen

Sagen Sie „Überwache Tibos öffentliche Reset-Meldungen stündlich“, „Melde nur completed und banked in Asia/Shanghai“, „Prüfe öffentliche Meldungen einmal“ oder „Stoppe öffentliche Reset-Meldungen“. Dafür dient der getrennte Befehl `resetwatch`. Eine Frage bedeutet einen `read`; Start nur bei ausdrücklichem Überwachungswunsch. Der Host muss den Vordergrundprozess beaufsichtigen, JSON lesen und seinen vorhandenen lokalen Benachrichtigungsadapter nutzen. Fehlt dieser Weg, muss er erklären, dass nur Text/JSON verfügbar ist. Installation startet nichts.

`planned` ist ein Plan, kein Abschluss; `completed` ist ein Drittanbieterbericht über eine Abschlussmeldung; `banked` ist gespeichertes Zurücksetzen ohne bestätigten Erhalt oder manuelle Einlösung; `manual_credit` kündigt manuelle Gutschrift an, deren Originalbedingungen zu prüfen sind. Eine Meldung bestätigt kein persönliches Kontingent, löst nichts ein und setzt Forschung nicht automatisch fort oder pausiert sie. Auch „direkt geprüft“ ist eine Anbieterbehauptung, keine unabhängige Bestätigung oder offizielle API.

Ersetzen Sie PUBLIC_STATE durch ein privates absolutes Elternverzeichnis außerhalb von Repository/Cache. `PUBLIC_STATE/public-reset-watch`, Sperre und Stopptoken sind getrennt und ändern keinen Kontingentzustand. Der erste erfolgreiche Abruf erstellt still einen Anfangsbestand. Historische Beiträge, Duplikate, Neustarts und alte ungeordnete Zustände wiederholen keine Warnungen. Ein Wechsel planned→completed kann nur den neuen Zustand melden. Filterwechsel spielt keine Historie ab. Zum Ändern stoppen, Ende prüfen und neu starten; Forschung und Kontingentmonitor bleiben unberührt.

`--events` wählt planned,completed,banked,manual_credit (Standard alle). `--interval`: 3600..86400 Sekunden, Standard 3600. Wartezeiten überstehen Neustarts; Rückzug nach Fehlern ist auf 24 Stunden begrenzt. `--max-age` begrenzt das Alter gespeicherter Abruf-/Prüfbelege (172800 Sekunden, mindestens Intervall, höchstens 604800); `--event-age` das neuer Beiträge (604800, Bereich 3600..2592000). Gemeinsames `--timeout`: 1..30 Sekunden (10), höchstens ein zusätzliches Socket-Zeitlimit. `--timezone` nutzt eine installierte IANA-Zone, Standard UTC; Maschinendaten bleiben UTC. `--locale` behält die Ausweichregeln bei; JSON-Felder und -Werte werden nicht übersetzt.

Standardmäßig liest `--provider modelyard` nur den festen öffentlichen RSS `/feed.xml`. HTML und beliebige `--provider-url` wurden entfernt; Quellenwechsel erfordert Codeprüfung. RSS-Kategorien sind Drittanbieterberichte, keine offizielle Prüfung. `fetched_at` belegt lokalen Abruf; lastBuildDate/neuste Veröffentlichung ist kein Synchronisierungsbeleg. Ein alter gültiger Feed kann einen Anfangsbestand bilden, bei unbekannter Abdeckung. Produktumfang folgt dem gelieferten Originaltext oder bleibt unbekannt; Titel/Kontext sind Anbieterbehauptungen. Reine ChatGPT-Einträge werden nicht als Codex/Work gemeldet. Ein Kategorienwechsel desselben Beitrags nutzt `first_observed_status_at` als lokal beobachtete Aggregatoränderung, ohne erfundene Bearbeitungszeit. Der Callback nutzt einen vorhandenen lokalen Hostweg; tatsächliche Zustellung ungeprüft. Netzwerk/Library-Download sind hier gesperrt; das direkt gelieferte echte erste ausgeschnittene Element wird getestet. Robots erteilt keine Weiterverbreitungslizenz; siehe Quellenprüfung.

Netzwerk-/HTTP-Fehler, veraltete Anbieterprüfung, ungültige Formate/Daten und gefälschte Quellen bedeuten unbekannt, nie „zurückgesetzt“ oder „nicht zurückgesetzt“; es entsteht kein Ereignis. Ein erfolgreicher Abruf ohne neue Ereignisse beweist keine Abwesenheit eines Resets. `status` ist gespeichert, kein neuer Abruf oder Laufzeitbeleg. Das Register wird vor Ausgabe gespeichert: Abstürze können Zustellung verlieren, und ein Ereignis beweist keine Benachrichtigung. Ruhezustand, Beenden und Netzwerk-/Quellenverzögerungen unterbrechen die Abdeckung. Keine Echtzeitgarantie oder Autostart; kein neues Konto, kostenpflichtige API, Hochladen persönlicher Daten oder neue Systemberechtigung für Benachrichtigungen nötig.

```sh
python3 scripts/quota_guard.py resetwatch --help --locale de
python3 scripts/quota_guard.py resetwatch read --state-dir PUBLIC_STATE --format text --locale de
python3 scripts/quota_guard.py resetwatch start --state-dir PUBLIC_STATE --events completed,banked --interval 3600 --timezone Asia/Shanghai
python3 scripts/quota_guard.py resetwatch stop --state-dir PUBLIC_STATE --format text --locale de
python3 scripts/quota_guard.py resetwatch status --state-dir PUBLIC_STATE --format text --locale de
```

Die öffentliche Überwachung benötigt nur Python/POSIX/Netzwerk und installierte IANA-Zeitzonendaten; offizielle Codex-CLI und Konto sind nicht nötig.

`--fixture FILE` gilt nur für `read`, ohne Netzwerk/Konto und mit isoliertem synthetischem Zustand; ein alter Prüfzeitpunkt wird korrekt als veraltet gemeldet.

[Vertrag / JSON](../RESET-WATCH.md) · [Quellenprüfung](../RESET-SOURCES.md)
