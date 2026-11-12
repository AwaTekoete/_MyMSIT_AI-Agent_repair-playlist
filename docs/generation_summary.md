# Generation Summary – Playlist Repair Agent

Dokumentation aller synthetisch erzeugten Daten und Testfaelle. Ablage im Repo:
`docs/generation_summary.md`. Datenschutz (P11): keine echten Pfade, Namen oder Titel;
nur Rechenvorschriften und Zaehlwerte.

---

## Notebook 03 Zelle 06 – Synthetische Testfaelle T1–T8 (12.11.2026)

**Zweck:** Testfaelle mit bekannter richtiger Antwort, ohne Handlabels. Grundlage fuer
Regressionstests (Phase 3) und harte Negativfaelle zur Precision-Pruefung (P5, Phase 3/4).
Ergaenzen die Gold-Labels, ersetzen sie nicht.

**Quelle:** alle 5.236 Audiodateien des Index (Pfad = Datei, Antwort bekannt), NFC.

**Ziehung:** je Typ zufaellige Reihenfolge (SEED 42 + Typ-Nr.), max. 2 Faelle je Ordner,
Ziel 300 je Typ (Rule of Three: 0 Fehler in 300 -> Fehlerrate < 1 %).

| Typ | Verfaelschung (Rechenvorschrift) | Bedingung | Erwartung | Faelle | Ordner |
|---|---|---|---|---|---|
| T1 | Pfad in NFD | Pfad aendert sich durch NFD (Sonderzeichen) | Originaldatei | 240 | 145 |
| T2 | `Musik/` ersetzt durch generisches fremdes Praefix (3 Varianten), `/` -> `\` | – | Originaldatei | 300 | 206 |
| T3 | Ordnername + " old" | Dateiname eindeutig; Zielordner existiert nicht | Originaldatei | 300 | 207 |
| T4 | Ordner ersetzt durch zufaelligen anderen bestehenden Ordner | Dateiname eindeutig; Zielpfad existiert nicht | Originaldatei | 300 | 196 |
| T5 | ganzer Pfad in Kleinschreibung | Pfad aendert sich | Originaldatei | 300 | 211 |
| T6 | Dateiname als UTF-8 kodiert, als cp1252 gelesen (Mojibake) | Sonderzeichen, dekodierbar | Originaldatei | 212 | 125 |
| T7 | letzte Zahl im Dateinamen +1..+9 | geaenderter Name existiert nirgends im Index | **fehlt** | 300 | 205 |
| T8 | Jahreszahl (19xx/20xx) im Dateinamen +1, ueberall im Pfad ersetzt | Jahreszahl im Dateinamen; geaenderter Name existiert nicht | **fehlt** | 300 | 200 |
| **Summe** | | | | **2.252** (Ziel 2.400) | |

**Herkunft der Typen (EDA-Befunde Notebook 02):** T1 300 NFD-Crate-Pfade; T2 2.218 fremde
Windows-Pfade; T3 Fall mit leicht geaendertem Ordnernamen; T4 Kategorie a (166);
T5 Windows/FAT32 unterscheidet Gross/Klein nicht (beobachtet 0); T6 20 Mojibake-Dateinamen;
T7/T8 Vorbefunde mit falschem Fuzzy-Vorschlag (Ordnungszahl, Jahreszahl).

**Abweichungen vom Ziel:** T1 240 und T6 212 < 300, da nur Pfade mit Sonderzeichen geeignet
sind und max. 2 je Ordner gilt -> belegbare Fehlerrate bei 0 Fehlern < 1,25 % bzw. < 1,42 %.

**Bewertung des Nutzens (Reflexion 12.11.2026):** hoch fuer T7/T8 (harte Negativfaelle,
Risiko P5); mittel fuer T2–T4 (realistische Fehler, Regressionstests); gering fuer
T1/T5/T6 (Ergebnis durch Konstruktion der Stufen weitgehend festgelegt).

**Grenzen:** prueft nur bekannte Fehlertypen (z. B. haette kein synthetischer Test die
0-Byte-Ordner gefunden); Verteilung der Fehlertypen entspricht nicht der realen Verteilung;
T4 kann zufaellig einen thematisch passenden Ordner treffen (fuer Namenssuche ohne Belang).

**Ablage:** privat `data/interim/03_06_synthetisch.csv` (Spalten typ, eintrag, original,
erwartung, ordner); public `reports/tables/03_06_synthetisch_zaehlung.csv`.
Oeffentliche pytest-Fixtures mit erfundenen Namen folgen in Phase 3.
