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
**Projektbezug:** Serato-`.crate`: 4-Byte-Tag (z. B. `otrk` = Track, `ptrk` = Pfad), 4-Byte-Laenge Big-Endian, Strings UTF-16-BE. Parser liest Bloecke sequenziell, ohne das Format "raten" zu muessen. EDA 07.11.: alle 167 Crates vollstaendig bis zum letzten Byte gelesen, eine einzige Version (`1.0/Serato ScratchLive Crate`).

### Unicode-Normalformen NFC / NFD
**Definition:** Dasselbe sichtbare Zeichen kann unterschiedlich kodiert sein: NFC = vorkomponiert ("ä" = 1 Codepoint U+00E4), NFD = zerlegt ("a" + kombinierendes Trema U+0308 = 2 Codepoints). Bildschirm identisch, Stringvergleich ungleich.
**Projektbezug:** Vorbefund (2 Crates): 4 NFD-Pfade. EDA (alle Crates, Notebook 02 Zelle 03): 656 von 7.915 Eintraegen bzw. 300 von 2.754 eindeutigen Pfaden in NFD, verteilt auf 72 von 167 Crates; Dateinamen auf dem Stick: 0 NFD; foobar schreibt Pfade in NFC (11/11, Zelle 05). Alle Crates wurden am Mac erstellt (Angabe Projektinhaber), enthalten aber NFC (721 Pfade mit Sonderzeichen) und NFD (300) -> Ursache der Mischung offen. 275 der 300 NFD-Pfade (91,7 %) treffen erst nach NFC-Normalisierung (Stufe 4.2); fuer 25 NFD-Pfade auch danach kein Treffer (alle in Kategorie e, Zelle 06). Evidenz (Zelle 04): Crate `a`+U+0308 bzw. `u`+U+0308 vs. Stick U+00E4 bzw. U+00FC. Lehre: Aus 2 Crates war die Bedeutung von Stufe 4.2 nicht erkennbar (Vorbefund 0,0 % bzw. 0,3 %), ueber alle Crates betrifft sie 10,0 % der eindeutigen Pfade.

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
**Projektbezug:** Unterschiedliche Datums-Tokens, Ordnungszahlen (z. B. `6th` vs. `8th`) oder Tracknummern -> kein Treffer. Haette beide Falschtreffer der Vorbefunde verhindert.

### Ground Truth / Gold-Set als Messmittel
**Definition:** Von Hand verifizierte Referenzmenge, gegen die automatische Verfahren gemessen werden. Analog Messsystemanalyse: Ein Verfahren wird nicht mit sich selbst kalibriert.
**Projektbezug:** Stichprobe vorhandener Playlist-Eintraege, je Eintrag "richtige Datei" oder "fehlt" bestaetigt; stratifiziert mit Ueberrepraesentation schwieriger Faelle. Ein Agent, der "alle Titel finden" soll, kann sich nicht selbst bewerten. Erste 13 Gold-Labels (Zelle 05): 10 per foobar bestaetigt, 1 an anderem Ort per Handsuche gefunden, 2 fehlend.

### Rule of Three (Konfidenz bei null Fehlern)
**Definition:** Werden in n unabhaengigen Faellen 0 Fehler beobachtet, liegt die wahre Fehlerrate mit 95 % Konfidenz unter ca. 3/n.
**Projektbezug:** Bestimmt den Umfang des Gold-Sets fuer das Ziel "Precision 100 %": n = 100 belegt Fehlerrate < 3 %, n = 300 belegt < 1 %. Endgueltiger Umfang nach EDA. Beispiel Zelle 05: 0 Fehler in 11 foobar-Vergleichen belegen nur Fehlerrate < 27 % -> bestaetigt den Mechanismus, nicht die Garantie.

### Active Learning / Human in the Loop
**Definition:** Das System legt unsichere Faelle einem Menschen vor; dessen Entscheidungen werden als neue Labels gespeichert und verbessern Modell bzw. Testmenge.
**Projektbezug:** Nutzerbestaetigungen zu "Vorschlaegen" im UI erweitern das Gold-Set. Bewertung trotzdem nur auf festem Testset (sonst keine Vergleichbarkeit der Varianten).

### Drei-Wege-Vergleich (Three-Way Merge)
**Definition:** Zwei geaenderte Fassungen werden gegen ihren gemeinsamen Ausgangsstand (Basis) verglichen. Nur so ist unterscheidbar, wer was geaendert hat; Aenderung auf beiden Seiten = Konflikt.
**Projektbezug:** Sync foobar Asus <-> Medion. Basis = Manifest mit dem Stand beim letzten Sync (P6).

### Verankerung ueber Ordner-Signatur statt Hardware-ID
**Definition:** Identifikation eines Datentraegers ueber seine Inhaltsstruktur (Merkmal ueberlebt Kopieren) statt ueber eine Hardware-Kennung (bricht bei neuem Datentraeger).
**Projektbezug:** Windows lieferte fuer denselben Stick zwei verschiedene Seriennummern (USBSTOR- und WMI-Wert, letzterer platzhalterartig) -> Seriennummer unzuverlaessig, nur Bestaetigung; Signatur primaer. Prototyp (Notebook 01, Zelle 06): Stick-Laufwerk 5/5 Signatur-Ordner, alle anderen Laufwerke 0/5 -> eindeutige Trennung.

---

## Phase 0 – Setup (06./07.11.2026)

### src-Layout und Editable Install
**Definition:** Paketcode liegt unter `src/<paket>/` (PyPA-Empfehlung); `pip install -e .` installiert das Paket als Verweis auf den Projektordner. Aenderungen im Code wirken sofort, Imports funktionieren ueberall gleich (`from playlist_agent import ...`), ohne `sys.path`-Manipulation.
**Projektbezug:** `pyproject.toml` (PEP 621), Paket `playlist-agent` 0.1.0; `__init__.py` macht Ordner zu regulaeren Paketen.

### `.gitignore`: Ordner-Regeln + Dateityp-Sicherheitsnetz, "letzte Regel gewinnt"
**Definition:** Git wertet `.gitignore` von oben nach unten aus; bei mehreren passenden Regeln gilt die letzte. Negationen (`!`) holen Dateien zurueck, aber nicht aus ausgeschlossenen Elternordnern (daher `!data/**/` vor `!data/**/.gitkeep`).
**Projektbezug:** Test mit echtem Git zeigte 6 Lecks der ersten Fassung (z. B. `.env.local`, `.crate` ausserhalb von `data/`). Fassung 2 kombiniert Ordner-Regeln mit Dateityp-Regeln; Secret-Regeln stehen nach der `tests/fixtures/`-Ausnahme, damit sie Vorrang haben. Verifiziert: 16/16 kritische Testdateien ignoriert.

### Git-Clean-Filter (nbstripout) und seine Grenze
**Definition:** Ein Filter, den Git beim Uebertragen ins Repository auf Dateien anwendet. Arbeitskopie bleibt unveraendert, nur der gespeicherte Stand wird bereinigt.
**Projektbezug:** Notebook-Ausgaben werden beim Commit entfernt. Nachweis: lokal 2 Treffer "Projektwurzel:", im Commit 1 (nur Quellcode). Filter-Definition liegt in `.git/config` (pro Rechner!) -> auf dem Medion erneut `nbstripout --install`. **Grenze (Befund 07.11.):** Code- und Markdown-Zellen werden vollstaendig committet; echte Pfade im Code waren dadurch oeffentlich -> Regel: echte Werte nur in privaten Eingabedateien (`data/`), Pruefung vor jedem Commit.

### Inhaltsadressierte Speicherung (Git-Objekte)
**Definition:** Git speichert Inhalte unter ihrem Hash; identische Inhalte existieren nur einmal (Blobs fuer Dateien, Trees fuer Ordner).
**Projektbezug:** Erster Push: 32 Dateien, aber 21 Objekte (alle leeren `.gitkeep`/`__init__.py` = 1 Blob, 17 identische Ordner = 1 Tree). Zweiter Push: 23 Objekte (+ Blob `config.yaml`, + Tree `config/`). Zahlen exakt nachgerechnet.

### Historie bereinigen: Force-Push vs. Neuanlage
**Definition:** Umgeschriebene Commits ersetzen per Force-Push den alten Stand; der alte Commit kann aber ueber seine ID noch abrufbar bleiben, bis der Server aufraeumt. Nur Loeschen und Neuanlegen des Repos garantiert die Entfernung.
**Projektbezug:** Name aus LICENSE/pyproject entfernt; lokal `git commit --amend`, Repo neu angelegt. Nachweis: alte Commit-URL liefert 404. Zweiter Fall (07.11.): Pfadfragmente in Zellen 03-06 -> Entscheidung "nur kuenftig korrigieren", Historie bleibt.

### Trennung oeffentliche Konfiguration / lokale Secrets
**Definition:** Versionierte Konfiguration enthaelt nur unkritische, allgemeine Werte; maschinenspezifische und geheime Werte liegen in einer nicht versionierten Datei (`.env`), dokumentiert ueber eine Vorlage (`.env.example`).
**Projektbezug:** `config.yaml` (public) vs. `.env` (Seriennummer, API-Key). Regel: echte Werte nie im Notebook-Code, da Code committet wird. Nachweis: `git check-ignore -v .env` -> Regel Zeile 44; Seriennummer per `git grep --cached` nicht im Commit.

### Snapshot mit kryptografischer Pruefsumme (SHA-256)
**Definition:** Eine Pruefsumme ist ein Fingerabdruck des Dateiinhalts: Schon ein geaendertes Bit ergibt eine voellig andere SHA-256-Summe. Gleiche Summe von Original und Kopie belegt eine bitgenaue Kopie. Ein Manifest (Liste aus Pfad, Groesse, Pruefsumme, Aenderungsdatum) dokumentiert den Stand zum Zeitpunkt des Snapshots.
**Projektbezug:** 380 Dateien (167 Crates, 213 Playlists, 2,8 MB) vom Stick nach `data/raw` kopiert, 380/380 bitgenau identisch. `shutil.copy2` erhaelt das Aenderungsdatum (relevant fuer Sync-Analyse). Manifest privat in `data/raw/snapshot_manifest.csv`; im Repo nur Zaehlstatistik `01_07_snapshot_pruefung.csv`. Schutz: Abbruch, falls `data/raw` schon Dateien enthaelt (P7).

### Unabhaengige Messwege zur Plausibilisierung
**Definition:** Dieselbe Groesse wird mit zwei voneinander unabhaengigen Werkzeugen gemessen; Uebereinstimmung erhoeht das Vertrauen, Abweichung zeigt einen Fehler in mindestens einem Messweg.
**Projektbezug:** PowerShell-Index v2 (06.11.) und Python (07.11., Zellen 06/08) stimmen vollstaendig ueberein: 7.386 Dateien, 128,4 GB, 310 AppleDouble, 5.236 echte Audiodateien (4.924 mp3 + 266 wav + 46 aif), 110 `.m3u`, 36 `.wpl`. Folgerungen: Stick seit 06.11. unveraendert; `.aiff`/`.flac`/`.m4a` kommen nicht vor -> Positivliste der Audio-Endungen in `config.yaml` belegt vollstaendig.

---

## Phase 1 – EDA (07.11.2026)

### pandas 3: Datentyp `str` fuer Textspalten
**Definition:** Ab pandas 3 werden Textspalten standardmaessig mit einem eigenen String-Datentyp (`str`) gespeichert statt mit dem allgemeinen Typ `object` (pandas 2).
**Projektbezug:** Index- und Crate-Pfade haben Typ `str`. Pruefung, ob pandas Unicode-Normalformen stillschweigend angleicht: Zaehlung der NFD-Pfade mit reinem Python und mit pandas-Vergleich ergibt beide 656 -> Normalform bleibt erhalten, NFC/NFD in pandas sicher unterscheidbar.

### Rechtsschiefe Verteilung: Median statt Mittelwert, logarithmische Achse
**Definition:** Bei rechtsschiefen Verteilungen (viele kleine, wenige sehr grosse Werte) zieht der Mittelwert nach oben; der Median beschreibt den typischen Wert robuster. In Histogrammen draengt eine lineare Achse die Masse in den ersten Balken; logarithmische Klassen geben jeder Groessenordnung gleich viel Platz.
**Projektbezug:** Tracks je Crate: Median 13, Mittelwert 47,4, Maximum 1.330; lineare Achse legte 140 von 167 Crates in den ersten Balken -> Grafik `02_02_tracks_je_crate.png` mit log-Achse.

### Mehrfachzugehoerigkeit: eindeutige Pfade statt Eintraege zaehlen
**Definition:** Kommt dasselbe Objekt in mehreren Gruppen vor, verzerrt die Zaehlung je Eintrag die Statistik (ein Fehler wird mehrfach gezaehlt). Fuer Aussagen ueber Objekte wird je eindeutigem Objekt gezaehlt, fuer Aussagen ueber Gruppen je Gruppe.
**Projektbezug:** 7.915 Crate-Eintraege, aber 2.754 eindeutige Pfade (jeder Pfad im Schnitt in 2,9 Crates). Song-Ebene (eindeutige Pfade) = technische Kernmetrik; Playlist-Ebene (je Crate: vollstaendig wiederherstellbar?) = Nutzersicht. Einschraenkung: Song ist nicht gleich Pfad (Dubletten) -> Inhalts-Hash in Zelle 09.

### UTF-16 im Texteditor: scheinbare Leerzeichen
**Definition:** UTF-16 speichert jedes Zeichen in 2 Byte; bei lateinischen Buchstaben ist ein Byte `00`. Ein Editor, der die Datei als 1-Byte-Text liest, zeigt `00` als Luecke ("A b c"). Kombinierende Zeichen (z. B. Trema U+0308) werden dabei oft unsichtbar ("a" statt "ä"). Feldkennungen wie `talb` erscheinen als scheinbar chinesische Zeichen.
**Projektbezug:** Stichprobe (07.11.): Editor zeigte in einer Crate einen Umlaut als "a", Codepoint-Analyse belegt `a` + U+0308 (NFD). Gleicher Effekt in Serato `database V2`. Lehre: Kodierungsfragen nur mit Codepoint-Analyse beantworten, nie per Augenschein.

### Trefferstufen-Kaskade (Stufen 1-4) und Akzent-Entfernung als Diagnose
**Definition:** Je Crate-Pfad wird gegen alle Index-Pfade nacheinander geprueft; die erste zutreffende Stufe zaehlt: 1 Zeichen-identisch; 2 identisch nach NFC-Normalisierung beider Seiten; 3 identisch nach Akzent-Entfernung (NFKD, kombinierende Zeichen entfernt, Kleinschreibung, "ä" -> "a"); 4 kein Treffer. "Treffer" bedeutet Gleichheit der Zeichenkette, nicht Inhaltsgleichheit (V2).
**Projektbezug:** Notebook 02 Zelle 03, alle 2.754 eindeutigen Pfade vollstaendig geprueft: Stufe 1 2.075 (75,3 %), Stufe 2 275 (10,0 %), Stufe 3 0, Stufe 4 404 (14,7 %). Belegte Aussage: Unter den Pfaden, die bis auf Akzente identisch sind, gibt es keinen verlorenen Umlaut. Nicht belegt: verlorene Umlaute in zusaetzlich verschobenen Pfaden (landen in Stufe 4). Fehlquote je Klasse: ASCII 18,8 %, NFC 7,5 %, NFD 8,3 % -> Hauptursache der Fehltreffer nicht Kodierung. Evidenz je Stufe in Zelle 04, unabhaengige Bestaetigung durch foobar in Zelle 05.

### Unabhaengige Referenz durch Fremdsystem (foobar-Test)
**Definition:** Ergebnisse des eigenen Codes werden gegen ein System geprueft, das den Code nicht kennt; Uebereinstimmung belegt die Logik ohne Zirkelschluss.
**Projektbezug:** 13 geschichtete Stichproben-Songs (SEED 42): foobar schrieb fuer 11 Songs die Pfade selbst. 11/11 identisch mit dem Referenzpfad des Codes; NFD-Faelle (3) nach NFC gleich, Fall an anderem Ort (1) weder exakt noch nach NFC gleich -> Stufen 1, 2 und "anderer Ort" unabhaengig bestaetigt. 2 Songs auch per Handsuche nicht auffindbar.

### Zeichenkodierung von Playlist-Dateien: ANSI (.m3u) vs. UTF-8 mit BOM (.m3u8)
**Definition:** ANSI/cp1252 speichert jedes Zeichen in 1 Byte (ca. 250 darstellbare Zeichen); UTF-8 nutzt 1-4 Byte und kann alle Unicode-Zeichen darstellen. Ein BOM (Byte Order Mark, `EF BB BF`) am Dateianfang kennzeichnet UTF-8.
**Projektbezug:** foobar (Asus, Zelle 05): `.m3u` = cp1252, kein BOM, keine Kopfzeile, CRLF, `ä` = `e4`; `.m3u8` = UTF-8 mit BOM, Kopfzeile `#`, CRLF, `ä` = `c3 a4`. Folge fuer den Writer: Format bestimmt zwingend die Kodierung; UTF-8 in `.m3u` erzeugt Zeichensalat und tote Eintraege. Wahl des Ausgabeformats = Design-Entscheidung (Phase 3).

### pandas: `None` wird zu `NaN`, `NaN` gilt als wahr
**Definition:** Fehlende Werte in DataFrame-Spalten werden als `NaN` (Typ `float`) gespeichert, auch wenn `None` eingetragen wurde. In Python ist `NaN` "wahr" (`bool(float('nan')) == True`); `if wert:` erkennt fehlende Werte daher nicht. Korrekt: `pd.notna(wert)` / `pd.isna(wert)`.
**Projektbezug:** Fehler in Zelle 04 (Stichprobe): Stufe-4-Zeilen ohne Index-Partner wurden faelschlich als vorhanden behandelt -> `AttributeError`. Behoben durch `pd.notna`.

### Kategorisierung ueber Rechenvorschrift statt Ursachenbehauptung
**Definition:** Kategorien werden ueber das definiert, was der Code berechnet (z. B. "Name genau 1x im Index"), nicht ueber vermutete Ursachen ("verschoben", "geloescht"). Ursachen werden ausdruecklich als Hypothesen gekennzeichnet. Namensgleichheit belegt keine Inhaltsgleichheit.
**Projektbezug:** Zelle 06, 404 Fehltreffer, Schluessel Kleinschreibung(NFC(Dateiname)) gegen 5.236 Audiodateien: a Name 1x im Index, anderer Ordner 166 (41,1 %); b mehrfach 0; c erst nach Mojibake-Reparatur 0; d Name nicht im Index, Ordner vorhanden 8 (2,0 %); e Name nicht im Index, Ordner nicht vorhanden 230 (56,9 %). Zusatzmerkmal "gleichnamiger Ordner anderswo": 25, alle in a (15,1 % von a), in d/e 0. Validierung gegen Handsuche 3/3. Ueber Namensgleichheit Kandidat fuer 2.516 von 2.754 Pfaden (91,4 %); fuer 238 (8,6 %) kein Kandidat -> Metadatenquelle noetig (Serato `database V2`, Zelle 07).

---

*Wird bei jedem neuen methodischen Konzept ergaenzt.*
