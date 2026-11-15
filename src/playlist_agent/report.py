"""Pflichtbericht je Lauf (P4).

Fuehrt Integritaet (P12), Ergebnis je Playlist (Writer, V1/V3) und nicht sichere
Eintraege (Resolver) in einem Markdown-Bericht zusammen.

Der Bericht enthaelt echte Pfade -> nur privat speichern (P11):
reports/run_reports/ ist nicht im Repo. Bestehende Berichte werden nie ueberschrieben.

Eingaben (DataFrames, entkoppelt von Notebook-Variablen):
  df_playlists : je Playlist  playlist, status, eintraege, geschrieben, n_vorschlag,
                 n_fehlt, n_album_beschaedigt, n_ausgeschlossen, v1_ok, v3_ok
  df_eintraege : je nicht sicherem Eintrag  playlist, eintrag, klasse,
                 optional pfad_ziel, grund, null_byte_ordner,
                 aktion / entschieden_auf (aus decisions.loese_auf; fehlt -> "?" offen, P13)
  df_integritaet : Befunde aus integrity.vergleiche_manifeste (oder None = nicht geprueft)
Einheiten stehen in eckigen Klammern (Entscheidung 13.11.2026).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from playlist_agent.decisions import AKTIONEN, gruppiere_vorschlaege
from playlist_agent.integrity import warnung_noetig, zusammenfassung

KLASSEN_NICHT_SICHER = ["vorschlag", "fehlt", "album_beschaedigt", "ausgeschlossen"]


def _zelle(x) -> str:
    """Text fuer eine Markdown-Tabellenzelle; '|' und Zeilenumbrueche maskieren."""
    if x is None or (not isinstance(x, str) and pd.isna(x)):
        return ""
    return str(x).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def md_tabelle(df: pd.DataFrame) -> str:
    """DataFrame als Markdown-Tabelle (ohne Zusatzpaket wie tabulate)."""
    if df.empty:
        return "_keine_\n"
    kopf = "| " + " | ".join(_zelle(c) for c in df.columns) + " |"
    trenner = "|" + "|".join("---" for _ in df.columns) + "|"
    zeilen = ["| " + " | ".join(_zelle(v) for v in z) + " |" for z in df.itertuples(index=False)]
    return "\n".join([kopf, trenner, *zeilen]) + "\n"


def _je_eintrag(df: pd.DataFrame, spalten: list[str]) -> pd.DataFrame:
    """Verdichtung auf eindeutige Eintraege mit Zaehlern [Eintraege]/[Playlists]."""
    vorhanden = [c for c in spalten if c in df.columns]
    return (df.groupby("eintrag", as_index=False)
            .agg(**{c: (c, "first") for c in vorhanden},
                 **{"n [Eintraege]": ("playlist", "size"),
                    "n [Playlists]": ("playlist", "nunique")})
            .sort_values("eintrag", ignore_index=True))


def _abschnitt_vorschlaege(v: pd.DataFrame) -> str:
    """Abschnitt 4 (je Ordnerpaar, Tracks darunter) und 4b (Verschiebe-Vorschlaege, Aktion b)."""
    t = ["\n## 4 Vorschlaege – Entscheidung je Track, optional je Ordnerpaar (P13)\n",
         "Aktionen: a = Playlist anpassen | b = Zurueckverschieben vorschlagen | ? = offen. "
         "Ohne Entscheidung bleibt der Eintrag offen (P5).\n"]
    if v.empty:
        return "".join(t) + "_keine_\n\n## 4b Verschiebe-Vorschlaege (Ausfuehrung nur durch den Nutzer, P1)\n_keine_\n"
    if "aktion" not in v.columns:
        v = v.assign(aktion="?", entschieden_auf="keine")
    je = (v.groupby(["eintrag", "pfad_ziel"], as_index=False)
          .agg(aktion=("aktion", "first"), entschieden_auf=("entschieden_auf", "first"),
               **{"n [Eintraege]": ("playlist", "size"), "n [Playlists]": ("playlist", "nunique")}))
    g = gruppiere_vorschlaege(je)
    for pid, teil in g.groupby("paar_id", sort=False):
        z = teil["aktion"].value_counts()
        stand = ", ".join(f"{k}: {int(z.get(k, 0))}" for k in AKTIONEN)
        t.append(f"\n### {pid}: {_zelle(teil['alter_ordner'].iat[0])} -> {_zelle(teil['neuer_ordner'].iat[0])}\n")
        t.append(f"{len(teil)} [Pfade], {int(teil['n [Eintraege]'].sum())} [Eintraege]; Stand {stand}\n\n")
        t.append(md_tabelle(teil[["eintrag", "pfad_ziel", "aktion", "entschieden_auf",
                                  "n [Eintraege]", "n [Playlists]"]]
                            .rename(columns={"pfad_ziel": "kandidat"}).sort_values("eintrag")))
    t.append("\n## 4b Verschiebe-Vorschlaege (Ausfuehrung nur durch den Nutzer, P1)\n")
    b = g[g["aktion"] == "b"]
    t.append(md_tabelle(b[["paar_id", "pfad_ziel", "eintrag"]]
                        .rename(columns={"pfad_ziel": "von (heutiger Ort)", "eintrag": "nach (Ort laut Playlist)"})
                        .sort_values(["paar_id", "nach (Ort laut Playlist)"])))
    return "".join(t)


def erstelle_bericht(kopf: dict, df_playlists: pd.DataFrame, df_eintraege: pd.DataFrame,
                     df_integritaet: pd.DataFrame | None = None) -> str:
    """Markdown-Text des Pflichtberichts."""
    t = [f"# Laufbericht {kopf.get('zeit', '')}\n"]
    t.append(md_tabelle(pd.DataFrame({"Feld": list(kopf), "Wert": list(kopf.values())})))

    # 1 Integritaet zuerst: Datenverlust ist wichtiger als jede Playlist
    t.append("\n## 1 Integritaet des Musiktraegers (P12)\n")
    if df_integritaet is None:
        t.append("_nicht geprueft_\n")
    else:
        if warnung_noetig(df_integritaet):
            t.append("**WARNUNG: kritische Befunde seit dem letzten Lauf. "
                     "Vor der naechsten Sicherung pruefen, sonst uebernimmt die Sicherung den Schaden.**\n\n")
        else:
            t.append("Keine kritischen Befunde seit dem letzten Lauf.\n\n")
        t.append(md_tabelle(zusammenfassung(df_integritaet)))
        krit = df_integritaet[df_integritaet["schwere"] != "info"]
        if len(krit):
            t.append("\n" + md_tabelle(krit[["schwere", "typ", "pfad", "detail"]]))

    # 2 Zusammenfassung
    p = df_playlists
    # vollstaendig = alle Audio-Eintraege geschrieben; ausgeschlossene (kein Audio) fehlen nicht (Befund 15.11.2026)
    vollst = p["geschrieben"] == p["eintraege"] - p["n_ausgeschlossen"]
    zus = pd.DataFrame([
        ("Playlists", "[Playlists]", len(p)),
        ("davon vollstaendig (alle Audio-Eintraege geschrieben)", "[Playlists]", int(vollst.sum())),
        ("davon unvollstaendig", "[Playlists]", int((~vollst).sum())),
        ("V1 nicht ok", "[Playlists]", int((~p["v1_ok"]).sum())),
        ("V3 nicht ok", "[Playlists]", int((~p["v3_ok"]).sum())),
        ("Eintraege gesamt", "[Eintraege]", int(p["eintraege"].sum())),
        ("sicher (geschrieben)", "[Eintraege]", int(p["geschrieben"].sum())),
        *[(k, "[Eintraege]", int(p[f"n_{k}"].sum())) for k in KLASSEN_NICHT_SICHER],
    ], columns=["Groesse", "Einheit", "Anzahl"])
    # Vorschlaege nach Nutzerentscheidung (P13); ohne Spalte aktion gilt alles als offen
    v = df_eintraege[df_eintraege["klasse"] == "vorschlag"]
    akt = v["aktion"] if "aktion" in v.columns else pd.Series("?", index=v.index)
    zus = pd.concat([zus, pd.DataFrame(
        [(f"vorschlag – {k} ({name})", "[Eintraege]", int((akt == k).sum())) for k, name in AKTIONEN.items()],
        columns=zus.columns)], ignore_index=True)
    t.append("\n## 2 Zusammenfassung\n")
    t.append(md_tabelle(zus))

    # 3 Schreibaktionen (P3)
    t.append("\n## 3 Schreibaktionen\n")
    st = p["status"].value_counts().rename_axis("status").reset_index(name="Anzahl [Dateien]")
    t.append(md_tabelle(st))
    if (p["status"] == "geaendert").any():
        t.append("\nVorversionen geaenderter Playlists liegen in `_backup/` (P3).\n")

    # 4 Vorschlaege je Ordnerpaar (P13), 4b Verschiebe-Vorschlaege
    e = df_eintraege
    t.append(_abschnitt_vorschlaege(e[e["klasse"] == "vorschlag"]))

    # 5-7 uebrige nicht sichere Eintraege, je eindeutigem Pfad
    abschnitte = [
        ("5 Fehlt – kein Kandidat auf dem Musiktraeger", "fehlt", ["grund"]),
        ("6 Album beschaedigt – Wiederherstellung nur aus Sicherung", "album_beschaedigt", ["null_byte_ordner"]),
        ("7 Ausgeschlossen – kein Audio", "ausgeschlossen", ["grund"]),
    ]
    for titel, klasse, spalten in abschnitte:
        t.append(f"\n## {titel}\n")
        teil = e[e["klasse"] == klasse]
        if klasse == "album_beschaedigt" and "null_byte_ordner" in teil.columns and len(teil):
            je_ordner = (teil.groupby("null_byte_ordner")
                         .agg(**{"pfade [Pfade]": ("eintrag", "nunique"),
                                 "n [Eintraege]": ("eintrag", "size"),
                                 "n [Playlists]": ("playlist", "nunique")})
                         .reset_index().sort_values("n [Eintraege]", ascending=False))
            t.append(md_tabelle(je_ordner))
        else:
            t.append(md_tabelle(_je_eintrag(teil, spalten) if len(teil) else teil))

    # 8 Unvollstaendige Playlists
    t.append("\n## 8 Unvollstaendige Playlists\n")
    u = p.loc[~vollst, ["playlist", "eintraege", "geschrieben",
                        *[f"n_{k}" for k in KLASSEN_NICHT_SICHER]]].sort_values("playlist")
    t.append(md_tabelle(u.rename(columns={"eintraege": "eintraege [Eintraege]",
                                          "geschrieben": "geschrieben [Eintraege]"})))
    return "".join(t)


def speichere_bericht(text: str, ordner, zeit: datetime | None = None) -> Path:
    """Bericht als `lauf_<YYYYmmdd_HHMMSS>.md` speichern; nie ueberschreiben."""
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    stempel = (zeit or datetime.now()).strftime("%Y%m%d_%H%M%S")
    ziel, i = ordner / f"lauf_{stempel}.md", 2
    while ziel.exists():
        ziel, i = ordner / f"lauf_{stempel}_{i}.md", i + 1
    ziel.write_text(text, encoding="utf-8", newline="\n")
    return ziel
