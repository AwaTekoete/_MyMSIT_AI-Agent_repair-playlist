# Methodik-Glossar – Playlist Repair Agent

Laufend gepflegtes Nachschlagewerk. Jedes im Projekt verwendete methodische
Konzept wird bei erstmaliger Verwendung dokumentiert: Definition,
Interpretation, Projektbezug. Reihenfolge = chronologische Einfuehrung.
Ablage im Repo: `docs/methodik_glossar.md`.
Datenschutz (strenge Regel, Entscheidung 07.11.2026): keine Fragmente echter
Pfade, Ordner-, Datei-, Titel- oder Interpretennamen; Beispiele sind generisch.

---

## Phase Konzept / Vorbefunde (06.11.2026)

### Tag-Length-Value-Format (TLV)
**Definition:** Binaeres Datenformat aus wiederholten Bloecken: Kennung (Tag), Laenge des Inhalts, Inhalt. Verschachtelung moeglich (ein Inhalt enthaelt wieder TLV-Bloecke).
**Projektbezug:** Serato-`.crate`: 4-Byte-Tag (z. B. `otrk` = Track, `ptrk` = Pfad), 4-Byte-Laenge Big-Endian, Strings UTF-16-BE. Parser liest Bloecke sequenziell, ohne das Format "raten" zu muessen. EDA 07.11.: alle 167 Crates vollstaendig bis zum letzten Byte gelesen, eine einzige Version (`1.0/Serato ScratchLive Crate`). 09.11.: ebenso alle 203 Subcrates; `database V2` ebenfalls TLV (Datei und alle 5.478 Track-Bloecke gehen exakt auf, Notebook 02 Zelle 08). Dekodierung der Felder nach Tag-Praefix (t/p Text UTF-16-BE, u/s/b Zahl) fuer alle Felder erfolgreich.

### Unicode-Normalformen NFC / NFD
**Definition:** Dasselbe sichtbare Zeichen kann unterschiedlich kodiert sein: NFC = vorkomponiert ("ä" = 1 Codepoint U+00E4), NFD = zerlegt ("a" + kombinierendes Trema U+0308 = 2 Codepoints). Bildschirm identisch, Stringvergleich ungleich.
**Projektbezug:** Vorbefund (2 Crates): 4 NFD-Pfade. EDA (alle Crates, Notebook 02 Zelle 03): 656 von 7.915 Eintraegen bzw. 300 von 2.754 eindeutigen Pfaden in NFD, verteilt auf 72 von 167 Crates; Dateinamen auf dem Stick: 0 NFD; foobar schreibt Pfade in NFC (11/11, Zelle 05). Alle Crates wurden am Mac erstellt (Angabe Projektinhaber), enthalten aber NFC (721 Pfade mit Sonderzeichen) und NFD (300) -> Ursache der Mischung offen. 275 der 300 NFD-Pfade (91,7 %) treffen erst nach NFC-Normalisierung (Stufe 4.2). Nach NFC-Normalisierung schrumpfen die 2.754 eindeutigen Crate-Pfade auf 2.559 (Zelle 07): 195 Pfade lagen in beiden Formen vor. `database V2` (Zelle 09): 746 Pfade doppelt, jeweils genau 1x NFC und 1x NFD, keine Zeichen-identischen Doppel -> Parser fuehrt Eintraege nach NFC zusammen. Lehre: Aus 2 Crates war die Bedeutung von Stufe 4.2 nicht erkennbar (Vorbefund 0,0 % bzw. 0,3 %), ueber alle Crates betrifft sie 10,0 % der eindeutigen Pfade.

### Mojibake
**Definition:** Zeichensalat durch falsch interpretierte Kodierung, typisch UTF-8-Bytes als Windows-1252 gelesen: "Grün" -> "GrÃ¼n".
**Projektbezug:** 20 Dateinamen auf dem Stick mit Mojibake-Verdacht (Index), davon 1 Audiodatei per Reparatur (cp1252 -> UTF-8) rueckfuehrbar; kein Crate-Pfad verweist darauf (Kategorie c = 0, Zelle 06). Aenderung an Musikdateien nur als Vorschlag (P1/P4).

### AppleDouble-Dateien (`._*`)
**Definition:** macOS legt auf Dateisystemen ohne Metadaten-Unterstuetzung (FAT32, exFAT) versteckte Begleitdateien `._<name>` mit Metadaten an. Gleiche Endung wie das Original, Inhalt keine Nutzdaten.
**Projektbezug:** 310 AppleDouble-Dateien im Musikordner, davon 151 mit Audio-Endung (`._*.mp3` 50, `._*.wav` 96, `._*.aif` 5) und 144 `._*.asd`. Ein reiner Endungs-Filter wuerde sie als Musik werten -> Linter-Regel (Praefix + Groesse). Snapshot (07.11.): auch 26 von 55 Dateien im Mac-Playlist-Ordner (47 %) sind AppleDouble, je exakt 4096 Byte.

### Record Linkage / Entity Resolution
**Definition:** Aufgabe, Datensaetze verschiedener Quellen derselben realen Entitaet zuzuordnen, wenn kein gemeinsamer eindeutiger Schluessel existiert. Klassisch: Kandidaten erzeugen (Blocking) -> Paare vergleichen (Merkmale) -> Entscheidung (Regel oder Klassifikator).
**Projektbezug:** Playlist-Eintrag <-> Datei im Index. Stufen 4.3/4.4 der Aufloesungskaskade; ML-Paar-Klassifikator in Phase 4.

### Precision vor Recall (asymmetrische Fehlerkosten)
**Definition:** Precision = Anteil korrekter unter allen als "Treffer" gemeldeten Faellen; Recall = Anteil gefundener unter allen tatsaechlichen Treffern. Bei ungleichen Fehlerkosten wird eine Metrik priorisiert und die Entscheidungsschwelle danach kalibriert.
**Projektbezug:** Falscher Track in einer Playlist ist schlimmer als ein ehrlich gemeldetes "fehlt" (P5). Ziel: Precision = 100 % in der Klasse "sicher"; Recall darf darunter liegen. Belegt durch Vorbefund: naives Fuzzy-Matching schlug fuer einen fehlenden Ordner mit Datum 2006 einen anderen Ordner mit Datum 2007 vor (anderes Ereignis).

### Harte Vetos (Ausschlussregeln)
**Definition:** Regeln, die einen Kandidaten unabhaengig vom Aehnlichkeitswert verwerfen, wenn ein eindeutiges Unterscheidungsmerkmal widerspricht.
**Projektbezug:** Unterschiedliche Datums-Tokens, Ordnungszahlen (z. B. `6th` vs. `8th`) oder Tracknummern -> kein Treffer. Haette beide Falschtreffer der Vorbefunde verhindert. Einschraenkung (Zelle 13/14): Dauer-Abweichung ist kein hartes Veto, da 3,2 % der Paare mit nachweislich gleicher Datei > 2 s abweichen.

### Ground Truth / Gold-Set als Messmittel
**Definition:** Von Hand verifizierte Referenzmenge, gegen die automatische Verfahren gemessen werden. Analog Messsystemanalyse: Ein Verfahren wird nicht mit sich selbst kalibriert.
**Projektbezug:** Stichprobe vorhandener Playlist-Eintraege, je Eintrag "richtige Datei" oder "fehlt" bestaetigt; stratifiziert mit Ueberrepraesentation schwieriger Faelle. Ein Agent, der "alle Titel finden" soll, kann sich nicht selbst bewerten. Bisher 13 Gold-Labels (Zelle 05: 10 per foobar bestaetigt, 1 anderer Ort, 2 fehlend) + 10 Nutzerangaben (Zelle 15: 3 richtige Datei, 7 unbekannt). Schichten und Pilot-Vorgehen: Zelle 23 (Entscheidung 12.11.2026). Phase 3: Pruef-Playlist in foobar als Werkzeug (NB04 Z.10/14/19): 142 Vorschlaege + 300 + 81 Pfadende-Paare geprueft, alle richtig.

### Rule of Three (Konfidenz bei null Fehlern)
**Definition:** Werden in n unabhaengigen Faellen 0 Fehler beobachtet, liegt die wahre Fehlerrate mit 95 % Konfidenz unter ca. 3/n.
**Projektbezug:** Bestimmt den Umfang des Gold-Sets fuer das Ziel "Precision 100 %": n = 60 belegt < 5 %, n = 100 < 3 %, n = 300 < 1 %. Beispiele: 0 Fehler in 11 foobar-Vergleichen (Zelle 05) -> nur < 27 %; 0 Lesefehler in 5.236 Dateien (Zelle 12) -> < 0,06 %. Gold-Schichten (Zelle 23): fuer < 3 % in allen Schichten waeren 835 Labels noetig. Exakt (Clopper-Pearson, 0 Fehler): 1 − 0,05^(1/n), z. B. n = 142 -> 2,09 %, n = 300 -> 0,99 %.

### Active Learning / Human in the Loop
**Definition:** Das System legt unsichere Faelle einem Menschen vor; dessen Entscheidungen werden als neue Labels gespeichert und verbessern Modell bzw. Testmenge.
**Projektbezug:** Nutzerbestaetigungen zu "Vorschlaegen" im UI erweitern das Gold-Set. Bewertung trotzdem nur auf festem Testset (sonst keine Vergleichbarkeit der Varianten). Erste Anwendung: Nutzerangaben zu 10 Beispielen (Zelle 15) als private Gold-Labels.

### Drei-Wege-Vergleich (Three-Way Merge)
**Definition:** Zwei geaenderte Fassungen werden gegen ihren gemeinsamen Ausgangsstand (Basis) verglichen. Nur so ist unterscheidbar, wer was geaendert hat; Aenderung auf beiden Seiten = Konflikt.
**Projektbezug:** Sync foobar Asus <-> Medion. Basis = Manifest mit dem Stand beim letzten Sync (P6).

### Verankerung ueber Ordner-Signatur statt Hardware-ID
**Definition:** Identifikation eines Datentraegers ueber seine Inhaltsstruktur (Merkmal ueberlebt Kopieren) statt ueber eine Hardware-Kennung (bricht bei neuem Datentraeger).
**Projektbezug:** Windows lieferte fuer denselben Stick zwei verschiedene Seriennummern (USBSTOR- und WMI-Wert, letzterer platzhalterartig) -> Seriennummer unzuverlaessig, nur Bestaetigung; Signatur primaer. Prototyp (Notebook 01, Zelle 06): Stick-Laufwerk 5/5 Signatur-Ordner, alle anderen Laufwerke 0/5 -> eindeutige Trennung. Negativtest (09.11.): Stick nicht eingesteckt -> 0 Kandidaten, kein Fehlalarm; Abbruch per Assertion. Phase 3: `anchor.py` mit klarer Nutzermeldung ("bitte einstecken", "mehrdeutig"), Hostname -> Laptop. Grenze: eine Sicherung mit gleicher Struktur erfuellt ebenfalls die Signatur.

---

## Phase 0 – Setup (06./07.11.2026)

### src-Layout und Editable Install
**Definition:** Paketcode liegt unter `src/<paket>/` (PyPA-Empfehlung); `pip install -e .` installiert das Paket als Verweis auf den Projektordner. Aenderungen im Code wirken sofort, Imports funktionieren ueberall gleich (`from playlist_agent import ...`), ohne `sys.path`-Manipulation.
**Projektbezug:** `pyproject.toml` (PEP 621), Paket `playlist-agent` 0.1.0; `__init__.py` macht Ordner zu regulaeren Paketen. Neue Abhaengigkeit: nach Eintrag in `dependencies` erneut `pip install -e ".[dev]"`; vorher Datei speichern (Befund 11.11.: ungespeicherte Aenderung -> Paket nicht installiert). Im Notebook ist ein geaendertes Modul erst nach Kernel-Neustart oder `importlib.reload` wirksam.

### `.gitignore`: Ordner-Regeln + Dateityp-Sicherheitsnetz, "letzte Regel gewinnt"
**Definition:** Git wertet `.gitignore` von oben nach unten aus; bei mehreren passenden Regeln gilt die letzte. Negationen (`!`) holen Dateien zurueck, aber nicht aus ausgeschlossenen Elternordnern (daher `!data/**/` vor `!data/**/.gitkeep`).
**Projektbezug:** Test mit echtem Git zeigte 6 Lecks der ersten Fassung (z. B. `.env.local`, `.crate` ausserhalb von `data/`). Fassung 2 kombiniert Ordner-Regeln mit Dateityp-Regeln; Secret-Regeln stehen nach der `tests/fixtures/`-Ausnahme, damit sie Vorrang haben. Verifiziert: 16/16 kritische Testdateien ignoriert.

### Git-Clean-Filter (nbstripout) und seine Grenze
**Definition:** Ein Filter, den Git beim Uebertragen ins Repository auf Dateien anwendet. Arbeitskopie bleibt unveraendert, nur der gespeicherte Stand wird bereinigt.
**Projektbezug:** Notebook-Ausgaben werden beim Commit entfernt. Nachweis: lokal 2 Treffer "Projektwurzel:", im Commit 1 (nur Quellcode). Filter-Definition liegt in `.git/config` (pro Rechner!) -> auf dem Medion erneut `nbstripout --install`. **Grenze (Befund 07.11.):** Code- und Markdown-Zellen werden vollstaendig committet; echte Pfade im Code waren dadurch oeffentlich -> Regel: echte Werte nur in privaten Eingabedateien (`data/`), Pruefung vor jedem Commit. Hinweis (09.11.): Git sieht nur den gespeicherten Notebook-Stand; ungespeicherte Zellen in VS Code fehlen im Commit (Befund Commit e3781ab). `git status` zeigt ein Notebook mit nur geaenderten Ausgaben als ` M`, `git diff` dagegen leer (Filter angewendet).

### Inhaltsadressierte Speicherung (Git-Objekte)
**Definition:** Git speichert Inhalte unter ihrem Hash; identische Inhalte existieren nur einmal (Blobs fuer Dateien, Trees fuer Ordner).
**Projektbezug:** Erster Push: 32 Dateien, aber 21 Objekte (alle leeren `.gitkeep`/`__init__.py` = 1 Blob, 17 identische Ordner = 1 Tree). Zweiter Push: 23 Objekte (+ Blob `config.yaml`, + Tree `config/`). Zahlen exakt nachgerechnet.

### Historie bereinigen: Force-Push vs. Neuanlage
**Definition:** Umgeschriebene Commits ersetzen per Force-Push den alten Stand; der alte Commit kann aber ueber seine ID noch abrufbar bleiben, bis der Server aufraeumt. Nur Loeschen und Neuanlegen des Repos garantiert die Entfernung.
**Projektbezug:** Name aus LICENSE/pyproject entfernt; lokal `git commit --amend`, Repo neu angelegt. Nachweis: alte Commit-URL liefert 404. Zweiter Fall (07.11.): Pfadfragmente in Zellen 03-06 -> Entscheidung "nur kuenftig korrigieren", Historie bleibt. Lokaler, nie gepushter Commit (Hook-Test 15.11.): `git reset --soft HEAD~1` genuegt; Eintrag bleibt nur im lokalen Reflog.

### Trennung oeffentliche Konfiguration / lokale Secrets
**Definition:** Versionierte Konfiguration enthaelt nur unkritische, allgemeine Werte; maschinenspezifische und geheime Werte liegen in einer nicht versionierten Datei (`.env`), dokumentiert ueber eine Vorlage (`.env.example`).
**Projektbezug:** `config.yaml` (public) vs. `.env` (Seriennummer, API-Key, PRIVATE_TERMS). Regel: echte Werte nie im Notebook-Code, da Code committet wird. Nachweis: `git check-ignore -v .env` -> Regel Zeile 44; Seriennummer per `git grep --cached` nicht im Commit. Resolver-Regeln (Entscheidungen) stehen bewusst in `config.yaml`, Tippfehler fuehren zum Abbruch.

### Snapshot mit kryptografischer Pruefsumme (SHA-256)
**Definition:** Eine Pruefsumme ist ein Fingerabdruck des Dateiinhalts: Schon ein geaendertes Bit ergibt eine voellig andere SHA-256-Summe. Gleiche Summe von Original und Kopie belegt eine bitgenaue Kopie. Ein Manifest (Liste aus Pfad, Groesse, Pruefsumme, Aenderungsdatum) dokumentiert den Stand zum Zeitpunkt des Snapshots.
**Projektbezug:** 380 Dateien (167 Crates, 213 Playlists, 2,8 MB) vom Stick nach `data/raw` kopiert, 380/380 bitgenau identisch. `shutil.copy2` erhaelt das Aenderungsdatum (relevant fuer Sync-Analyse). Manifest privat in `data/raw/snapshot_manifest.csv`; im Repo nur Zaehlstatistik `01_07_snapshot_pruefung.csv`. Schutz: Abbruch, falls `data/raw` schon Dateien enthaelt (P7). Ergaenzungen 09.11. mit eigenem Manifest, wiederholbar (vorhandene Kopie nur vergleichen, nie ueberschreiben): `database V2` (Zelle 10, 1 Datei), restlicher Serato-Ordner (Zelle 12, 215 Dateien, 1.124.467 Byte, alle bitgenau; Byte-Summe vorab aus Zelle 11 berechnet und bestaetigt). Dubletten-Suche (Notebook 02 Zelle 21): SHA-256 als Beleg fuer bitgleichen Inhalt. Vollhash des Sticks (NB04 Z.08): 7.386 Dateien, 6.633 eindeutige Hashes; Audio-Dubletten exakt die 45 Paare der EDA.

### Unabhaengige Messwege zur Plausibilisierung
**Definition:** Dieselbe Groesse wird mit zwei voneinander unabhaengigen Werkzeugen gemessen; Uebereinstimmung erhoeht das Vertrauen, Abweichung zeigt einen Fehler in mindestens einem Messweg.
**Projektbezug:** PowerShell-Index v2 (06.11.) und Python (07.11., Zellen 06/08) stimmen vollstaendig ueberein: 7.386 Dateien, 128,4 GB, 310 AppleDouble, 5.236 echte Audiodateien (4.924 mp3 + 266 wav + 46 aif), 110 `.m3u`, 36 `.wpl`. Gegenbeispiel (Zelle 14): Serato-Dauer und Datei-Dauer widersprechen sich bei 72 Paaren; mit nur zwei Messwegen ist nicht entscheidbar, welcher falsch ist -> dritter Messweg (foobar) in Phase 4.

---

## Phase 1 – EDA (07.–12.11.2026)

### pandas 3: Datentyp `str` fuer Textspalten
**Definition:** Ab pandas 3 werden Textspalten standardmaessig mit einem eigenen String-Datentyp (`str`) gespeichert statt mit dem allgemeinen Typ `object` (pandas 2).
**Projektbezug:** Index- und Crate-Pfade haben Typ `str`. Pruefung, ob pandas Unicode-Normalformen stillschweigend angleicht: Zaehlung der NFD-Pfade mit reinem Python und mit pandas-Vergleich ergibt beide 656 -> Normalform bleibt erhalten, NFC/NFD in pandas sicher unterscheidbar.

### Rechtsschiefe Verteilung: Median statt Mittelwert, logarithmische Achse
**Definition:** Bei rechtsschiefen Verteilungen (viele kleine, wenige sehr grosse Werte) zieht der Mittelwert nach oben; der Median beschreibt den typischen Wert robuster. In Histogrammen draengt eine lineare Achse die Masse in den ersten Balken; logarithmische Klassen geben jeder Groessenordnung gleich viel Platz.
**Projektbezug:** Tracks je Crate: Median 13, Mittelwert 47,4, Maximum 1.330; lineare Achse legte 140 von 167 Crates in den ersten Balken -> Grafik `02_02_tracks_je_crate.png` mit log-Achse. Log-Achse auch fuer Dauer-Abweichungen (Zelle 13); Beschriftung mit `FuncFormatter` als Dezimalzahl, da die Schrift keine Hochzeichen enthaelt.

### Mehrfachzugehoerigkeit: eindeutige Pfade statt Eintraege zaehlen
**Definition:** Kommt dasselbe Objekt in mehreren Gruppen vor, verzerrt die Zaehlung je Eintrag die Statistik (ein Fehler wird mehrfach gezaehlt). Fuer Aussagen ueber Objekte wird je eindeutigem Objekt gezaehlt, fuer Aussagen ueber Gruppen je Gruppe.
**Projektbezug:** 7.915 Crate-Eintraege, aber 2.754 eindeutige Pfade (jeder Pfad im Schnitt in 2,9 Crates). Song-Ebene (eindeutige Pfade) = technische Kernmetrik; Playlist-Ebene (je Crate: vollstaendig wiederherstellbar?) = Nutzersicht (Zelle 10). Einschraenkung: Song ist nicht gleich Pfad (Dubletten, Zelle 21). Phase 3: Einheit steht im Spaltennamen in eckigen Klammern ([Playlists], [Eintraege], [Pfade], [Dateien]), Entscheidung 13.11.2026.

### UTF-16 im Texteditor: scheinbare Leerzeichen
**Definition:** UTF-16 speichert jedes Zeichen in 2 Byte; bei lateinischen Buchstaben ist ein Byte `00`. Ein Editor, der die Datei als 1-Byte-Text liest, zeigt `00` als Luecke ("A b c"). Kombinierende Zeichen (z. B. Trema U+0308) werden dabei oft unsichtbar ("a" statt "ä"). Feldkennungen wie `talb` erscheinen als scheinbar chinesische Zeichen.
**Projektbezug:** Stichprobe (07.11.): Editor zeigte in einer Crate einen Umlaut als "a", Codepoint-Analyse belegt `a` + U+0308 (NFD). Gleicher Effekt in Serato `database V2`. Lehre: Kodierungsfragen nur mit Codepoint-Analyse beantworten, nie per Augenschein.

### Trefferstufen-Kaskade (Stufen 1-4) und Akzent-Entfernung als Diagnose
**Definition:** Je Pfad wird gegen alle Index-Pfade nacheinander geprueft; die erste zutreffende Stufe zaehlt: 1 Zeichen-identisch; 2 identisch nach NFC-Normalisierung beider Seiten; 2b zusaetzlich ohne Gross-/Kleinschreibung (Windows/FAT32); 3 identisch nach Akzent-Entfernung; 4 kein Treffer. "Treffer" bedeutet Gleichheit der Zeichenkette, nicht Inhaltsgleichheit (V2).
**Projektbezug:** Crates (Zelle 03, 2.754 Pfade): Stufe 1 2.075 (75,3 %), Stufe 2 275 (10,0 %), Stufe 3 0, Stufe 4 404 (14,7 %). Uebrige Quellen (Zelle 17, 10.289 Eintraege): Stufe 1 6.304, Stufe 2 43, Stufe 2b 0, Stufe 3 0, Stufe 4 3.942. Gross-/Kleinschreibung und Akzente spielen in den Daten keine Rolle.

### Unabhaengige Referenz durch Fremdsystem (foobar-Test)
**Definition:** Ergebnisse des eigenen Codes werden gegen ein System geprueft, das den Code nicht kennt; Uebereinstimmung belegt die Logik ohne Zirkelschluss.
**Projektbezug:** 13 geschichtete Stichproben-Songs (SEED 42): foobar schrieb fuer 11 Songs die Pfade selbst. 11/11 identisch mit dem Referenzpfad des Codes -> Stufen 1, 2 und "anderer Ort" unabhaengig bestaetigt. Zielformat foobar durch Daten belegt (Zelle 17): Asus 197/197 absolut `D:\`, Medion 322/325 absolut `E:\` -> eigener Test relativer Pfade unnoetig (Entscheidung 12.11.2026).

### Zeichenkodierung von Playlist-Dateien: ANSI (.m3u) vs. UTF-8 mit BOM (.m3u8)
**Definition:** ANSI/cp1252 speichert jedes Zeichen in 1 Byte (ca. 250 darstellbare Zeichen); UTF-8 nutzt 1-4 Byte und kann alle Unicode-Zeichen darstellen. Ein BOM (Byte Order Mark, `EF BB BF`) am Dateianfang kennzeichnet UTF-8.
**Projektbezug:** foobar (Asus, Zelle 05): `.m3u` = cp1252, kein BOM, keine Kopfzeile, CRLF; `.m3u8` = UTF-8 mit BOM, Kopfzeile `#`, CRLF. Uebrige Quellen (Zelle 16): ASCII, UTF-8 ohne BOM, "cp1252" gemischt, kein BOM in keiner Datei. Grenze: "cp1252" heisst nur "nicht als UTF-8 lesbar"; ob MacRoman o. Ae. vorliegt, ist offen (bisher keine Hinweise: Stufe 3 = 0).

### pandas: `None` wird zu `NaN`, `NaN` gilt als wahr
**Definition:** Fehlende Werte in DataFrame-Spalten werden als `NaN` (Typ `float`) gespeichert, auch wenn `None` eingetragen wurde. In Python ist `NaN` "wahr" (`bool(float('nan')) == True`); `if wert:` erkennt fehlende Werte daher nicht. Korrekt: `pd.notna(wert)` / `pd.isna(wert)`.
**Projektbezug:** Fehler in Zelle 04 (Stichprobe): Stufe-4-Zeilen ohne Index-Partner wurden faelschlich als vorhanden behandelt -> `AttributeError`. Behoben durch `pd.notna`. Gleiche Ursache NB04 Z.23: ganzzahlige Tracknummern mit Luecken werden zu `float` -> vor Uebergabe explizit `int(...)`.

### Kategorisierung ueber Rechenvorschrift statt Ursachenbehauptung
**Definition:** Kategorien werden ueber das definiert, was der Code berechnet (z. B. "Name genau 1x im Index"), nicht ueber vermutete Ursachen ("verschoben", "geloescht"). Ursachen werden ausdruecklich als Hypothesen gekennzeichnet. Namensgleichheit belegt keine Inhaltsgleichheit.
**Projektbezug:** Zelle 06, 404 Fehltreffer: a Name 1x im Index, anderer Ordner 166; b mehrfach 0; c Mojibake 0; d Name nicht im Index, Ordner vorhanden 8; e Name nicht im Index, Ordner nicht vorhanden 230. Validierung gegen Handsuche 3/3. **Korrektur (Zelle 25):** "Ordner nicht vorhanden" war ungenau – 229 der 238 d/e-Pfade zeigen in Ordner, die heute 0-Byte-Dateien sind. Bestaetigt den Wert der Regel: Die Ursachen-Hypothese "geloescht" haette in die Irre gefuehrt.

### pandas 3: `astype(str)` behaelt `NaN`
**Definition:** In pandas 2 wandelte `astype(str)` fehlende Werte in den Text `"nan"` um. In pandas 3 bleibt ein fehlender Wert auch nach `astype(str)` fehlend (`NaN`, Typ `float`). Robust: Typ je Wert pruefen (`isinstance(wert, str)`) oder fehlende Werte vorher explizit entfernen (`dropna`).
**Projektbezug:** Fehler im Privacy-Check (08.11.) beim Einlesen der Gold-CSV-Dateien (leere Zellen). Behoben durch `isinstance(wert, str)`; seit 15.11. Einlesen mit `dtype=str, keep_default_na=False`.

### pandas 3: `groupby().apply()` ohne Gruppierungsspalte
**Definition:** Ab pandas 3 erhaelt die an `apply` uebergebene Funktion die Gruppierungsspalte nicht mehr (pandas 2: mit Warnung noch enthalten). Folgecode, der die Spalte erwartet, bricht mit `KeyError`.
**Projektbezug:** Zelle 11, geschichtete Stichprobe je Endung. Loesung: `df.groupby("endung").sample(n=40, random_state=SEED)` – behaelt alle Spalten; n = 40 zulaessig, da kleinste Gruppe (aif) 46 Dateien.

### Privacy-Check vor dem Commit (Abgleich gegen private Begriffsliste)
**Definition:** Automatische Pruefung der zum Commit vorgemerkten Dateien (Staging-Bereich, `git show :<pfad>`) gegen eine Liste privater Begriffe. Die Liste wird zur Laufzeit aus privaten Quellen erzeugt und selbst nie committet. Treffer -> Exit-Code 1, Commit wird nicht ausgefuehrt. Ausnahmen: erlaubte Begriffe (bewusst entschieden, vor der Pruefung aus dem Text entfernt) und generische Begriffe (allgemeine Woerter, aus der Begriffsliste entfernt). Mindestlaenge begrenzt Fehlalarme.
**Projektbezug:** `python -m playlist_agent.privacy_check`; Quellen: Index-Pfade, Crate-Namen, private Eingabedateien in `data/gold`, `PRIVATE_TERMS` aus `.env`; erlaubt: `ALLOWED_TERMS` (Hostname, P10); generisch: `{"playlist", "software"}`; Mindestlaenge 8. Binaerdateien (PNG) werden uebersprungen. Seit 08.11. vor jedem Commit, 0 Treffer in allen Abnahmelaeufen. Grenzen: erkennt nur Begriffe aus der Liste; 2 Fehlalarme in 2 Laeufen mit neuen Dateien. Seit 15.11. automatisch als Git-Hook (siehe "Exit-Code als Schnittstelle"); Stand 6.583 abgeleitete Begriffe + PRIVATE_TERMS.

### Mengenvergleich von Playlists: Relation und Jaccard-Index
**Definition:** Zwei Playlists werden als Mengen von Pfaden A und B verglichen (Reihenfolge und Mehrfacheintraege ignoriert, Pfade NFC-normalisiert). Relation: identisch, Teilmenge, Obermenge, Ueberlappung, disjunkt. Jaccard-Index J = |A ∩ B| / |A ∪ B|, 0 (nichts gemeinsam) bis 1 (identisch).
**Projektbezug:** Zelle 07: Serato `Crates` (167, 2009-2016) vs. `Subcrates` (203, 2021). Je alter Crate: identisch 97, Teilmenge 8, Obermenge 3, Ueberlappung 3, kein Namenspartner 56; 91 Subcrates ohne Partner. Pfade: nur Subcrates 765 (88,5 % auf dem Stick). Grundlage fuer Entscheidung d (09.11.2026). Gleiches Verfahren spaeter fuer `_mac`-Varianten, `.m3u`/`.wpl`-Dubletten und Sync-Konflikte (P6).

### Namenskollision im Notebook-Kernel
**Definition:** Alle Zellen eines Notebooks teilen einen Namensraum. Definiert eine spaetere Zelle denselben Namen neu (Funktion, Schleifenvariable), rechnet eine fruehere Zelle bei erneutem Einzelaufruf mit der neuen Bedeutung – oft ohne Fehlermeldung.
**Projektbezug:** Notebook 02 (11.11.): `ordner` (Funktion Zelle 06, Schleifenvariable Zelle 07) und `schluessel` (Zelle 06 vs. Zelle 08). Ergebnisse bei "Run All" korrekt, bei Einzelaufruf von Zelle 06 still falsch. Behoben durch eindeutige Namen (`quelle_ordner`, `pfad_schluessel`). Strukturelle Loesung: Funktionen nach `src/` (Phase 3, umgesetzt in 13 Modulen).

### Bootstrap-Konfidenzintervall und Abhaengigkeit der Einheiten
**Definition:** Aus der Stichprobe wird vielfach mit Zuruecklegen neu gezogen; die Verteilung der Kennzahl ueber alle Wiederholungen liefert das Intervall (95 %: 2,5- bis 97,5-Perzentil). Voraussetzung: unabhaengige Einheiten. Sind Einheiten abhaengig (teilen sie Daten), wird das Intervall zu schmal.
**Projektbezug:** Zelle 10: mittlerer Anteil sicher je Crate 93,2 % (KI 90,1-96,0 %, 10.000 Wiederholungen). Grenze: Crates teilen Pfade (im Mittel 2,9 Crates je Pfad) -> Intervall vermutlich zu schmal.

### Probelauf mit Hochrechnung vor teuren Operationen
**Definition:** Vor einer langen oder riskanten Operation wird eine geschichtete Stichprobe ausgefuehrt; gemessen werden Laufzeit je Einheit, Fehlerrate und Nutzen. Hochrechnung je Schicht: mittlere Zeit x Anzahl. Entscheidung ueber den Vollauf auf Basis der Messung.
**Projektbezug:** Zelle 11: 120 Dateien, 0 Fehler, Hochrechnung 4,4 min; Vollauf Zelle 12: gemessen 4,3 min, 0 Fehler in 5.236 Dateien. Vorbehalt Cache bestaetigte sich nicht. NB04 Z.08: Vollhash aus Messung NB02 Z.21 auf 14 min hochgerechnet, gemessen 14,0 min.

### Vorauswahl ueber eine notwendige Bedingung
**Definition:** Ist eine billige Eigenschaft notwendig fuer das gesuchte Merkmal, wird zuerst nach ihr gefiltert und nur der Rest teuer geprueft. Kein Treffer geht verloren, weil Faelle ohne die Eigenschaft das Merkmal nicht haben koennen.
**Projektbezug:** Dubletten (Zellen 20-21): bitgleicher Inhalt setzt gleiche Dateigroesse voraus -> nur 190 von 5.236 Dateien (2,9 GB statt 128,4 GB) gehasht, 19 s. Ergebnis: 45 bitgleiche Paare; bei 15 von 48 Mehrfach-Kandidaten alle bitgleich. Bestaetigt durch Vollhash (NB04 Z.08): exakt dieselben 45 Audio-Paare.

### Lizenzpruefung von Abhaengigkeiten
**Definition:** Jede Abhaengigkeit bringt ihre Lizenz mit. Copyleft-Lizenzen (GPL) verlangen bei Weitergabe des Gesamtwerks dieselbe Lizenz; permissive Lizenzen (MIT, BSD) nicht. Pruefung vor Aufnahme: Lizenzfeld bzw. Classifier in den Paket-Metadaten.
**Projektbezug:** mutagen 1.48.1 = GPL-2.0-or-later, Projekt = MIT -> ersetzt durch tinytag (MIT, reines Python, ohne Abhaengigkeiten, nur lesend; Entscheidung 11.11.2026). Zusatznutzen: Bibliothek kann Musikdateien nicht veraendern -> stuetzt P1 technisch. `pip show` zeigt bei tinytag ein leeres `License`-Feld; Lizenz steht im Classifier.

### Kalibrierung eines Inhaltsbelegs an bekannt gleichen Paaren (empirische Verteilungsfunktion)
**Definition:** Bevor ein Merkmal (z. B. Dauer) als Beleg dient, wird an Paaren gemessen, die nachweislich zusammengehoeren, wie stark es dort streut. Die empirische Verteilungsfunktion zeigt fuer jede Abweichung x den Anteil der Paare mit Abweichung <= x. Erst daraus ist eine Toleranz begruendbar.
**Projektbezug:** Zelle 13: Referenz (Pfad = Datei, n = 2.264) 92,1 % <= 0,1 s, 96,6 % <= 1 s; Namenskandidaten (n = 87) 98,9 % <= 1 s. Zelle 14: 72 Ausreisser > 2 s, alle mp3, kein einheitlicher Faktor -> Dauer ist starker, aber nicht fehlerfreier Beleg; kein hartes Veto bis Phase 4.

### Kanonisierung fremder Pfadformen und Pfadende-Abgleich
**Definition:** Eintraege verschiedener Quellen werden vor dem Abgleich in eine gemeinsame Form gebracht: URL dekodieren und Datentraegerpraefix entfernen, Laufwerk entfernen und Trenner vereinheitlichen, relative Pfade gegen den Ordner der Playlist aufloesen. Scheitert der Abgleich, wird verglichen, wie viele Pfadteile von hinten uebereinstimmen.
**Projektbezug:** Zellen 16-19: 3 Pfadformen (URL 495, Windows absolut 2.747, relativ 7.047). Fremde Windows-Pfade (Laufwerke C:, D:, I:, Q:) 0/2.218 exakte Treffer, aber 1.750 mit eindeutigem Kandidaten bei gleichem Ordner + Datei -> moegliche deterministische Regel "eindeutiges Pfadende >= 2 Teile" (Precision am Gold-Set). Methodischer Fehler dokumentiert: Kennzahl "Praefix-Paare je Datei" durch unterschiedlich viele gleiche Endteile verfaelscht -> keine Aussage. **Korrektur Phase 3 (NB04 Z.17):** Die meisten dieser Windows-Pfade enthielten `\..\`, das fuer absolute Pfade nicht aufgeloest wurde (2.191 Eintraege). Seit Fix `normpath` fuer alle Formen; "pfadende" betrifft danach nur noch 138 Paare.

### Deterministische Namenssuche vs. lernende Verfahren (Abgrenzung)
**Definition:** Eine Suche nach eindeutigem Dateinamen oder Pfadende ist ebenso deterministisch wie der exakte Pfadvergleich (vgl. Suche im Explorer). Der Raum fuer Fuzzy-, ML- und Agent-Verfahren beginnt erst dort, wo der Name mehrdeutig ist oder fehlt.
**Projektbezug:** Korrektur 12.11.2026 (Hinweis Projektinhaber, Faelle C1-C7): Namenssuche loest 166 Crate-Pfade und 3.000 Eintraege uebriger Quellen. Echter Raum fuer lernende Verfahren: 9 Crate-Pfade, 385 Eintraege ohne Namenskandidaten, 33 mit verschiedenen Mehrfach-Kandidaten. Stand Phase 3 (nach Fix A/B): 8 Crate-Pfade + 71 Eintraege "fehlt", 2 Mehrfach-Kandidaten; Gold-Faelle fuer Phase 4: umbenannte Dateien, verlorene Zeichen.

### Gruppierter Split gegen Leakage und Obergrenze je Gruppe in Stichproben
**Definition:** Liegen aehnliche Faelle derselben Gruppe (hier Ordner) in Training und Test, kann ein Modell Gruppenmuster auswendig lernen und wirkt besser als es ist (Leakage). Gruppierter Split: jede Gruppe nur in einem Teil. Analog bei Stichproben: Obergrenze je Gruppe, damit eine grosse Gruppe die Messung nicht dominiert.
**Projektbezug:** Zelle 23: in schweren Schichten stellt ein Ordner 41-49 % der Pfade, die 5 groessten 72-90 % (K1 exakt: 5,6 % bzw. 15 %). Entscheidung 12.11.2026: Split gruppiert nach Ordner; Gold-Set mit Pilot (20 Labels, Zeit je Label messen) und Obergrenze je Ordner. Angewendet NB04 Z.14: Obergrenze 5 je Zielordner (825 -> 423 Paare), dann Stichprobe 300.

### Datenverlust erkennen: 0-Byte-Datei an Stelle eines Ordners
**Definition:** Ein Verzeichnis, an dessen Stelle eine leere Datei gleichen Namens steht, ist fuer jeden Pfad darunter unerreichbar. Nachweis ueber Dateityp (PowerShell `Mode` ohne `d`) und Groesse 0; im Datei-Index sind solche Faelle nur als 0-Byte-Datei sichtbar, echte leere Ordner gar nicht.
**Projektbezug:** Zelle 25 (Entdeckung durch Pruefung des Projektinhabers, Fall C10): 23 Dateien mit 0 Byte, davon 10 an Stelle von Album-Ordnern; betroffen 229 von 238 Crate-Pfaden ohne Namenskandidaten (96,2 %) und 509 von 894 Eintraegen uebriger Quellen. Hypothese: Dateisystemschaden. Kein Zuordnungsproblem, sondern Datenverlust -> Bericht "Album beschaedigt/verloren"; Wiederherstellung nur aus Sicherungen (regelmaessige Backups vorhanden, Angabe Projektinhaber) -> Bonus "Suche auf Backup-Datentraegern" gewinnt an Wert. **Praezisierung Phase 3 (NB04 Z.07, Gold B1):** alle 23 ohne Endung, 22 am 06.02.2020 entstanden (06:43–08:38, alphabetisch aufsteigend), 1 am 29.12.2020; 11 betreffen Crates (230 Pfade / 509 Eintraege), uebrige Quellen nach Fix A 678 Eintraege.

---

## Phase 2 – Gold-Set, Split, synthetische Faelle (12.–13.11.2026)

### Pilot mit Zeitmessung je Label und Konfundierung
**Definition:** Vor einer grossen Label-Aktion wird an wenigen Faellen die Zeit je Label gemessen, um den Gesamtaufwand hochzurechnen. Wird die Reihenfolge nicht zufaellig gemischt, vermischt sich der Einfluss der Schicht mit dem Lerneffekt (Konfundierung).
**Projektbezug:** Notebook 03 Zelle 03/04: 20/20 richtig, Median 21 s (KI 18–33 s); Reihenfolge war nach Schicht sortiert -> Zeit je Schicht nicht trennbar. Entscheidung: kein grosses Labeling vorab, Gold spaeter gezielt aus der "sicher"-Ausgabe.

### Leave-One-Group-Out (LOGO)
**Definition:** Kreuzvalidierung, bei der je Durchgang genau eine Gruppe (Ordner) Testmenge ist und alle anderen Training. Fuer Schichten mit wenigen, grossen Gruppen genauer als ein fester Hash-Split.
**Projektbezug:** Hash-Split nach Ordner (SHA-1 mod 5) ergab fuer K3/K4/Q4 stark abweichende Testanteile (2,9–44,6 %) -> LOGO fuer diese Schichten in Phase 4.

### Synthetische Testfaelle mit harten Negativen
**Definition:** Kuenstlich erzeugte Faelle mit bekannter Wahrheit, darunter Faelle, bei denen die richtige Antwort "kein Treffer" ist, obwohl ein aehnlicher Kandidat existiert. Pruefen gezielt, ob eine Regel "sicher" behauptet, wo sie es nicht darf.
**Projektbezug:** T1–T8, 2.252 Faelle (`docs/generation_summary.md`); T7/T8 je 300 harte Negative: 600/600 korrekt "kein Treffer", 0 falsch sicher in allen Laeufen von NB04.

---

## Phase 3 – Deterministischer Kern (13.–15.11.2026)

### Regressionstest gegen fruehere Analyse
**Definition:** Neuer Produktivcode wird auf denselben Daten gegen die Ergebnisse einer frueheren Analyse verglichen; Abweichungen sind entweder ein Fehler im neuen Code oder ein bisher unentdeckter Fehler der Analyse.
**Projektbezug:** NB04 Zellen 01–03: `canon` 10.289/10.289 gleich; Playlist-Parser deckte 107 WPL-Eintraege mit XML-Zeichenreferenzen auf (EDA-Fehler, 105 davon jetzt im Index). Nach Fix ".." (Zelle 17): 2.191 bewusste Abweichungen, alle in "Windows absolut" -> Abweichung als Beleg der Korrektur.

### XML-Zeichenreferenzen in WPL-Dateien
**Definition:** In XML werden Sonderzeichen als Referenz geschrieben (`&amp;` fuer &, `&#228;` fuer ä). Wer XML-Inhalte mit regulaeren Ausdruecken statt XML-Parser liest, muss sie selbst aufloesen (`html.unescape`).
**Projektbezug:** EDA las WPL ohne Aufloesung -> 107 Eintraege falsch "nicht im Index". Korrigiert im Parser.

### Zeilenenden CRLF / LF und Textmodus unter Windows
**Definition:** Windows trennt Zeilen mit CR+LF (`\r\n`), Linux/macOS mit LF (`\n`). Python uebersetzt im Textmodus unter Windows `\n` beim Schreiben in `\r\n`, wenn nicht `newline="\n"` angegeben ist. Shell-Skripte (`sh`) verlangen LF.
**Projektbezug:** Testfehler `test_playlist` (Windows schrieb CRLF) -> `write_text(..., newline="\n")`. Writer schreibt bewusst CRLF (wie foobar). Git-Hook `.githooks/pre-commit` muss LF haben (`.gitattributes`: `.githooks/* text eol=lf`), sonst bricht `sh` ab.

### Abdeckung einer Zeichenkodierung messen (cp1252 vs. UTF-8)
**Definition:** Vor der Formatwahl wird gezaehlt, wie viele echte Werte in der engeren Kodierung darstellbar sind; nicht darstellbare Zeichen gingen verloren.
**Projektbezug:** NB04 Zelle 05: Zielpfade 2.558/2.558 in cp1252 darstellbar, aber 100 Dateien im Musikordner nicht (Thai, Sonderzeichen) -> Entscheidung immer `.m3u8` (UTF-8 mit BOM), zukunftssicher.

### Integritaetspruefung per Manifest-Vergleich (Hash-Uebernahme)
**Definition:** Ein Manifest speichert je Datei Pfad, Groesse, Aenderungszeit und Inhalts-Hash. Folgelaeufe hashen nur Dateien mit geaenderter Groesse oder Zeit neu und uebernehmen sonst den Hash; entschieden wird ueber den Hash, nicht ueber die Zeit (Zeitzonen-/Sommerzeitwechsel aendern die Zeit ohne Inhaltsaenderung).
**Projektbezug:** P12, `integrity.py`: erster Lauf 7.386 Dateien in 14,0 min (Vorhersage 14 min), Folgelauf 0 neu gehasht in 4,6 s, 0 Befunde (0 Fehlalarme). Muster "Datei an Stelle eines Ordners" als eigener Befundtyp (Ereignis 06.02.2020: 22 Ordner, Zeitstempel alphabetisch aufsteigend).

### Identitaet vs. Reparaturart (Trennung im Labeling)
**Definition:** Ein Label "richtiger Song" belegt nur, dass der Kandidat dieselbe Aufnahme ist. Ob die Playlist angepasst oder die Datei zurueckverschoben werden soll, ist eine getrennte Nutzerentscheidung.
**Projektbezug:** P13, `decisions.py`: Aktion a/b/? je Track, optional je Ordnerpaar; Vorrang Track > Ordnerpaar > offen; Protokoll nur anhaengend. 142 Vorschlaege -> 7 Ordnerpaare (-95 % Entscheidungen). Gold 142/142 Identitaet richtig, obere Grenze 2,09 % -> Regel bleibt "Vorschlag".

### Vollerhebung statt Stichprobe; Gueltigkeit von Gold-Belegen
**Definition:** Ist die Grundgesamtheit klein genug, wird jeder Fall geprueft; fuer den heutigen Bestand entfaellt die Stichprobenunsicherheit, fuer kuenftige Daten gilt weiter die Grenze nach Clopper-Pearson. Gold-Belege gelten nur fuer den Stand der Verarbeitung, auf dem sie erhoben wurden.
**Projektbezug:** Regel "pfadende -> sicher": Stichprobe 300/300 (< 0,99 %). Nach Fix ".." schrumpfte die Regel von 825 auf 138 Paare (sie hatte den Fehler verdeckt); nur 57 Gold-Paare gehoerten noch dazu (< 5,12 %). Vollpruefung der restlichen 81: 138/138 richtig, kuenftig < 2,15 %.

### Rueckfallstufe statt pauschaler Umwandlung
**Definition:** Eine riskante Umwandlung (z. B. URL-Dekodierung) wird nur angewendet, wenn der unveraenderte Wert keinen Treffer liefert; so bleiben seltene echte Werte geschuetzt, die wie kodiert aussehen.
**Projektbezug:** 14 Eintraege mit `%20` ohne `file://`; 1 echte Datei mit %XX-Muster im Namen -> Resolver dekodiert nur bei "fehlt" (14 -> sicher), die echte Datei bleibt unveraendert auffindbar.

### Regel aus Nutzerwissen + Messung (Reihenfolge in Ordnern)
**Definition:** Fachwissen des Nutzers wird in pruefbare Merkmale uebersetzt und an den Daten gemessen, statt es als Annahme zu uebernehmen.
**Projektbezug:** Ordnertypen S (Set: gemeinsamer Name + Endzahl), A (Album: Tracknummern vollstaendig + eindeutig), E (Einzeltitel). Messung 311 Ordner: A 155, S 66, E 90; natuerliche Sortierung = Track-Reihenfolge in 162/171 Alben (KI 90,3–97,2 %). Typ wird je Aufruf automatisch bestimmt (kein Pflegeaufwand); Bericht nennt die angewandte Regel.

### Exit-Code als Schnittstelle (Git-Hook, CI)
**Definition:** Automatisierte Werkzeuge (Git-Hooks, CI) erkennen Erfolg oder Fehler nur am Exit-Code (0 = ok), nicht am Text der Ausgabe. Ein Hook mit Exit-Code != 0 bricht den Commit ab.
**Projektbezug:** `.githooks/pre-commit` ruft den Privacy-Check (versioniert, `git config core.hooksPath .githooks` je Rechner). Funktionstest: Commit mit privatem Begriff abgebrochen. Zuvor gefunden: Check brach an ';'-Gold-Dateien ab, Dateinamen mit Leerzeichen waeren ungeprueft geblieben (`split` -> `splitlines`). Zusaetzliche Begriffe (z. B. eigener Name) ueber `PRIVATE_TERMS` in `.env` (= gesperrt, nicht erlaubt). CI (GitHub Actions, Windows) fuehrt pytest bei jedem Push aus; Privacy-Check bleibt lokal (braucht private Daten).

---

*Wird bei jedem neuen methodischen Konzept ergaenzt.*
