# Methodik-Glossar – Playlist Repair Agent

Laufend gepflegtes Nachschlagewerk. Jedes im Projekt verwendete methodische
Konzept wird bei erstmaliger Verwendung dokumentiert: Definition,
Interpretation, Projektbezug. Reihenfolge = chronologische Einfuehrung.
Ablage im Repo: `docs/methodik_glossar.md`.

---

## Phase Konzept / Vorbefunde (06.11.2026)

### Tag-Length-Value-Format (TLV)
**Definition:** Binaeres Datenformat aus wiederholten Bloecken: Kennung (Tag), Laenge des Inhalts, Inhalt. Verschachtelung moeglich (ein Inhalt enthaelt wieder TLV-Bloecke).
**Projektbezug:** Serato-`.crate`: 4-Byte-Tag (z. B. `otrk` = Track, `ptrk` = Pfad), 4-Byte-Laenge Big-Endian, Strings UTF-16-BE. Parser liest Bloecke sequenziell, ohne das Format "raten" zu muessen.

### Unicode-Normalformen NFC / NFD
**Definition:** Dasselbe sichtbare Zeichen kann unterschiedlich kodiert sein: NFC = vorkomponiert ("ä" = 1 Codepoint), NFD = zerlegt ("a" + kombinierendes Trema = 2 Codepoints). Bildschirm identisch, Stringvergleich ungleich.
**Projektbezug:** macOS speichert historisch NFD, Windows meist NFC. 4 Crate-Pfade in NFD gefunden. Gegenmassnahme: alle Pfade vor dem Vergleich auf NFC normalisieren (Stufe 4.2).

### Mojibake
**Definition:** Zeichensalat durch falsch interpretierte Kodierung, typisch UTF-8-Bytes als Windows-1252 gelesen: "ü" -> "Ã¼".
**Projektbezug:** 20 echte Dateinamen auf dem Stick betroffen (z. B. `FlÃ¼gel`). Nicht nur Playlists, auch Dateinamen selbst. Erkennung/Reparatur z. B. mit `ftfy`; Aenderung an Musikdateien nur als Vorschlag (P1/P4).

### AppleDouble-Dateien (`._*`)
**Definition:** macOS legt auf Dateisystemen ohne Metadaten-Unterstuetzung (FAT32, exFAT) versteckte Begleitdateien `._<name>` mit Metadaten an. Gleiche Endung wie das Original, Inhalt keine Nutzdaten.
**Projektbezug:** 151 Pseudo-Audiodateien `._*.mp3` (max. 4096 Byte) auf dem Stick. Ein reiner Endungs-Filter wuerde sie als Musik werten -> Linter-Regel (Praefix + Groesse).

### Record Linkage / Entity Resolution
**Definition:** Aufgabe, Datensaetze verschiedener Quellen derselben realen Entitaet zuzuordnen, wenn kein gemeinsamer eindeutiger Schluessel existiert. Klassisch: Kandidaten erzeugen (Blocking) -> Paare vergleichen (Merkmale) -> Entscheidung (Regel oder Klassifikator).
**Projektbezug:** Playlist-Eintrag <-> Datei im Index. Stufen 4.3/4.4 der Aufloesungskaskade; ML-Paar-Klassifikator in Phase 4.

### Precision vor Recall (asymmetrische Fehlerkosten)
**Definition:** Precision = Anteil korrekter unter allen als "Treffer" gemeldeten Faellen; Recall = Anteil gefundener unter allen tatsaechlichen Treffern. Bei ungleichen Fehlerkosten wird eine Metrik priorisiert und die Entscheidungsschwelle danach kalibriert.
**Projektbezug:** Falscher Track in einer Playlist ist schlimmer als ein ehrlich gemeldetes "fehlt" (P5). Ziel: Precision = 100 % in der Klasse "sicher"; Recall darf darunter liegen. Belegt durch Vorbefund: naives Fuzzy-Matching lieferte plausible Falschtreffer (`BigFM 2006 ...` -> `BigFM 2007 ...`).

### Harte Vetos (Ausschlussregeln)
**Definition:** Regeln, die einen Kandidaten unabhaengig vom Aehnlichkeitswert verwerfen, wenn ein eindeutiges Unterscheidungsmerkmal widerspricht.
**Projektbezug:** Unterschiedliche Datums-Tokens, Ordnungszahlen (`6th` vs. `8th`) oder Tracknummern -> kein Treffer. Haette beide Falschtreffer der Vorbefunde verhindert.

### Ground Truth / Gold-Set als Messmittel
**Definition:** Von Hand verifizierte Referenzmenge, gegen die automatische Verfahren gemessen werden. Analog Messsystemanalyse: Ein Verfahren wird nicht mit sich selbst kalibriert.
**Projektbezug:** Stichprobe vorhandener Playlist-Eintraege, je Eintrag "richtige Datei" oder "fehlt" bestaetigt; stratifiziert mit Ueberrepraesentation schwieriger Faelle. Ein Agent, der "alle Titel finden" soll, kann sich nicht selbst bewerten.

### Rule of Three (Konfidenz bei null Fehlern)
**Definition:** Werden in n unabhaengigen Faellen 0 Fehler beobachtet, liegt die wahre Fehlerrate mit 95 % Konfidenz unter ca. 3/n.
**Projektbezug:** Bestimmt den Umfang des Gold-Sets fuer das Ziel "Precision 100 %": n = 100 belegt Fehlerrate < 3 %, n = 300 belegt < 1 %. Endgueltiger Umfang nach EDA.

### Active Learning / Human in the Loop
**Definition:** Das System legt unsichere Faelle einem Menschen vor; dessen Entscheidungen werden als neue Labels gespeichert und verbessern Modell bzw. Testmenge.
**Projektbezug:** Nutzerbestaetigungen zu "Vorschlaegen" im UI erweitern das Gold-Set. Bewertung trotzdem nur auf festem Testset (sonst keine Vergleichbarkeit der Varianten).

### Drei-Wege-Vergleich (Three-Way Merge)
**Definition:** Zwei geaenderte Fassungen werden gegen ihren gemeinsamen Ausgangsstand (Basis) verglichen. Nur so ist unterscheidbar, wer was geaendert hat; Aenderung auf beiden Seiten = Konflikt.
**Projektbezug:** Sync foobar Asus <-> Medion. Basis = Manifest mit dem Stand beim letzten Sync (P6).

### Verankerung ueber Ordner-Signatur statt Hardware-ID
**Definition:** Identifikation eines Datentraegers ueber seine Inhaltsstruktur (Merkmal ueberlebt Kopieren) statt ueber eine Hardware-Kennung (bricht bei neuem Datentraeger).
**Projektbezug:** Windows lieferte fuer denselben Stick zwei verschiedene Seriennummern (USBSTOR `0113...`, WMI `AA00...` platzhalterartig) -> Seriennummer unzuverlaessig, nur Bestaetigung; Signatur primaer.

---

## Phase 0 – Setup (06./07.11.2026)

### src-Layout und Editable Install
**Definition:** Paketcode liegt unter `src/<paket>/` (PyPA-Empfehlung); `pip install -e .` installiert das Paket als Verweis auf den Projektordner. Aenderungen im Code wirken sofort, Imports funktionieren ueberall gleich (`from playlist_agent import ...`), ohne `sys.path`-Manipulation.
**Projektbezug:** `pyproject.toml` (PEP 621), Paket `playlist-agent` 0.1.0; `__init__.py` macht Ordner zu regulaeren Paketen.

### `.gitignore`: Ordner-Regeln + Dateityp-Sicherheitsnetz, "letzte Regel gewinnt"
**Definition:** Git wertet `.gitignore` von oben nach unten aus; bei mehreren passenden Regeln gilt die letzte. Negationen (`!`) holen Dateien zurueck, aber nicht aus ausgeschlossenen Elternordnern (daher `!data/**/` vor `!data/**/.gitkeep`).
**Projektbezug:** Test mit echtem Git zeigte 6 Lecks der ersten Fassung (z. B. `.env.local`, `.crate` ausserhalb von `data/`). Fassung 2 kombiniert Ordner-Regeln mit Dateityp-Regeln; Secret-Regeln stehen nach der `tests/fixtures/`-Ausnahme, damit sie Vorrang haben. Verifiziert: 16/16 kritische Testdateien ignoriert.

### Git-Clean-Filter (nbstripout)
**Definition:** Ein Filter, den Git beim Uebertragen ins Repository auf Dateien anwendet. Arbeitskopie bleibt unveraendert, nur der gespeicherte Stand wird bereinigt.
**Projektbezug:** Notebook-Ausgaben (Pfade wie `c:\Users\...`, Tracklisten) werden beim Commit entfernt. Nachweis: lokal 2 Treffer "Projektwurzel:", im Commit 1 (nur Quellcode). Filter-Definition liegt in `.git/config` (pro Rechner!) -> auf dem Medion erneut `nbstripout --install`.

### Inhaltsadressierte Speicherung (Git-Objekte)
**Definition:** Git speichert Inhalte unter ihrem Hash; identische Inhalte existieren nur einmal (Blobs fuer Dateien, Trees fuer Ordner).
**Projektbezug:** Erster Push: 32 Dateien, aber 21 Objekte (alle leeren `.gitkeep`/`__init__.py` = 1 Blob, 17 identische Ordner = 1 Tree). Zweiter Push: 23 Objekte (+ Blob `config.yaml`, + Tree `config/`). Zahlen exakt nachgerechnet.

### Historie bereinigen: Force-Push vs. Neuanlage
**Definition:** Umgeschriebene Commits ersetzen per Force-Push den alten Stand; der alte Commit kann aber ueber seine ID noch abrufbar bleiben, bis der Server aufraeumt. Nur Loeschen und Neuanlegen des Repos garantiert die Entfernung.
**Projektbezug:** Name aus LICENSE/pyproject entfernt; lokal `git commit --amend`, Repo neu angelegt. Nachweis: alte Commit-URL liefert 404.

### Trennung oeffentliche Konfiguration / lokale Secrets
**Definition:** Versionierte Konfiguration enthaelt nur unkritische, allgemeine Werte; maschinenspezifische und geheime Werte liegen in einer nicht versionierten Datei (`.env`), dokumentiert ueber eine Vorlage (`.env.example`).
**Projektbezug:** `config.yaml` (public) vs. `.env` (Seriennummer, API-Key). Regel: echte Werte nie im Notebook-Code, da Code committet wird. Nachweis: `git check-ignore -v .env` -> Regel Zeile 44; Seriennummer per `git grep --cached` nicht im Commit.

---

*Wird bei jedem neuen methodischen Konzept ergaenzt.*
