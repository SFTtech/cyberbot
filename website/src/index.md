Der Cyberbot ist ein modular erweiterbarer Bot für das [Matrixprotokoll](https://matrix.org/), welcher via Plugins Funktionen bereitstellt.


## Wie kann ich den Bot verwenden?

Befehle werden normalerweise aufgerufen, indem man `!<Befehl>` in den Matrixraum schreibt.

Um den Cyberbot zu verwenden, lädt man ihn über seinen Matrix Client in den Room ein.
Der Bot sollte dann dem Raum automatisch beitreten und sich kurz vorstellen.

Wenn der Bot neu in einen Raum hinzugefügt wird, sind nur wenige Plugins aktiv. Um alle Plugins zu sehen, die man in seinen Raum hinzufügen kann, schreibt man den Befehl `!listplugins` in den Raum. Mit `!addplugin` kann man dann eins dieser Plugins in den Raum hinzufügen.

Wir hosten einen Bot unter dem Namen `Cyberbot` und der Matrix-ID `@cyberbot:in.tum.de`.


## Ich habe ein Problem/ein Feature könnte besser sein

Falls es ein Problem mit einem unserer Plugins oder dem Bot allgemein gibt oder ihr Verbesserungsvorschläge habt, dann schreibt uns bitte eine Mail an [cybergruppe@in.tum.de](mailto:cybergruppe@in.tum.de).

## Wo kann ich den Code einsehen?

Der Code ist [hier](https://gitlab.rbg.tum.de/cyber/cyber-matrix-bot) verfügbar. Leider kann man ihn aktuell nur mit einem Zugang zum RBG-Gitlab einsehen.

## Wie hoste ich den Bot selber?

Um den Bot selber zu hosten braucht es:

 * Einen Linuxserver mit `python3`, `sqlite3` und `matrix-nio`
 * Einen Matrixaccount für den Bot
 * (Optional) Einen Gitlabaccount für das Gitlab Plugin

Auf dem Server kann man dann das [Repo](https://gitlab.rbg.tum.de/cyber/cyber-matrix-bot) klonen und nach den Anweisungen im `README.md` den Bot installieren.

## Wie schreibe ich Plugins für den Bot?
https://gitlab.rbg.tum.de/cyber/cyber-matrix-bot/-/blob/master/PLUGINS.md

# Screenshots

*Gitlab Plugin:*

![](res/screenshot_gitlab.png)

---

The Cyberbot™ is brought to you proudly by the [RBG Cybergroup](https://www.in.tum.de/rbg/)!
