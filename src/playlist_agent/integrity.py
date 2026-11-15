"""Integritaetspruefung des Musiktraegers (P12).

Vergleicht den Index eines Laufs mit dem Manifest des letzten Laufs und meldet
Datenverlust, bevor eine Sicherung den Schaden uebernimmt.

Manifest = Index-Spalten + SHA-256 je Datei. Der Hash wird nur fuer Dateien
neu berechnet, deren Groesse oder mtime sich geaendert hat; sonst wird er aus dem
alten Manifest uebernommen. Erster Lauf: alle Dateien (ca. 14 min fuer 128 GB).

Entscheidungsgrundlage ist der Hash, nicht die mtime: FAT32 speichert lokale Zeit
mit 2 s Aufloesung, Zeitzonen- und Sommerzeitwechsel verschieben mtime ohne
Inhaltsaenderung. Eine reine mtime-Aenderung bei gleichem Hash ist daher kein Befund
(Ziel: 0 Fehlalarme bei unveraendertem Inhalt).

Rein lesend (P1/P7). Grenze: leere Ordner tauchen im Datei-Index nicht auf;
ihr Verschwinden wird nicht erkannt (Verlust ohne Dateien = kein Datenverlust).
"""

from __future__ import annotations

import posixpath
from pathlib import Path
from typing import Callable

import pandas as pd

from playlist_agent.index import sha256_datei

# Befundtypen und Schwere; Reihenfolge = Sortierung im Bericht
BEFUNDE = {
    "datei_statt_ordner": "kritisch",   # Ordner durch Datei gleichen Namens ersetzt (Muster 06.02.2020)
    "ordner_verschwunden": "kritisch",  # oberster verschwundener Ordner
    "datei_verschwunden": "kritisch",
    "null_byte_neu": "kritisch",        # Datei hatte Inhalt, hat jetzt 0 Byte (oder neu mit 0 Byte)
    "inhalt_geaendert": "warnung",      # gleicher Pfad, anderer Hash
    "datei_neu": "info",
}
BEFUND_SPALTEN = ["pfad", "typ", "schwere", "detail"]


def _mtime_schluessel(s: pd.Series) -> pd.Series:
    """Einheitliche Textform der mtime (ISO mit 'T' oder Leerzeichen -> Leerzeichen)."""
    return s.astype(str).str.replace("T", " ", regex=False)


def ordner_aus_pfaden(pfade) -> set[str]:
    """Alle Vorfahr-Ordner der Dateipfade ('Musik/A/x.mp3' -> {'Musik', 'Musik/A'})."""
    ordner = set()
    for p in pfade:
        kopf = posixpath.dirname(p)
        while kopf and kopf not in ordner:
            ordner.add(kopf)
            kopf = posixpath.dirname(kopf)
    return ordner


def erstelle_manifest(df_index: pd.DataFrame, wurzel, df_alt: pd.DataFrame | None = None,
                      hash_fn: Callable = sha256_datei) -> tuple[pd.DataFrame, int]:
    """Manifest aus aktuellem Index; liefert (Manifest, Anzahl neu gehashter Dateien).

    Hash-Uebernahme nur bei identischem Pfad, gleicher Groesse und gleicher mtime.
    """
    df = df_index.copy()
    df["sha256"] = pd.NA
    if df_alt is not None and len(df_alt):
        alt = df_alt.assign(_m=_mtime_schluessel(df_alt["mtime"])).set_index("pfad_relativ")
        m_neu = _mtime_schluessel(df["mtime"])
        for i, (p, b, m) in enumerate(zip(df["pfad_relativ"], df["bytes"], m_neu)):
            if p in alt.index and alt.at[p, "bytes"] == b and alt.at[p, "_m"] == m \
                    and pd.notna(alt.at[p, "sha256"]):
                df.iat[i, df.columns.get_loc("sha256")] = alt.at[p, "sha256"]
    offen = df["sha256"].isna()
    wurzel = Path(wurzel)
    df.loc[offen, "sha256"] = [hash_fn(wurzel / p) for p in df.loc[offen, "pfad_relativ"]]
    return df, int(offen.sum())


def vergleiche_manifeste(df_alt: pd.DataFrame, df_neu: pd.DataFrame) -> pd.DataFrame:
    """Befunde zwischen zwei Manifesten; eine Zeile je Befund."""
    alt = df_alt.set_index("pfad_relativ")
    neu = df_neu.set_index("pfad_relativ")
    p_alt, p_neu = set(alt.index), set(neu.index)
    o_alt, o_neu = ordner_aus_pfaden(p_alt), ordner_aus_pfaden(p_neu)
    zeilen = []

    def befund(pfad, typ, detail=""):
        zeilen.append({"pfad": pfad, "typ": typ, "schwere": BEFUNDE[typ], "detail": detail})

    # Ordner: nur der oberste verschwundene Ordner wird gemeldet (keine Folgemeldungen)
    weg_ordner = o_alt - o_neu
    statt_ordner = weg_ordner & p_neu
    for o in sorted(weg_ordner):
        if posixpath.dirname(o) in weg_ordner:
            continue
        n = sum(1 for p in p_alt if p.startswith(o + "/"))
        if o in statt_ordner:
            befund(o, "datei_statt_ordner", f"{n} Dateien vorher; jetzt Datei mit {int(neu.at[o, 'bytes'])} Byte")
        else:
            befund(o, "ordner_verschwunden", f"{n} Dateien vorher")

    # Dateien
    def in_weg_ordner(p):
        kopf = posixpath.dirname(p)
        while kopf:
            if kopf in weg_ordner:
                return True
            kopf = posixpath.dirname(kopf)
        return False

    for p in sorted(p_alt - p_neu):
        if not in_weg_ordner(p):        # bereits ueber den Ordner gemeldet
            befund(p, "datei_verschwunden", f"{int(alt.at[p, 'bytes'])} Byte vorher")
    for p in sorted(p_neu - p_alt):
        if p in statt_ordner:
            continue                    # bereits als datei_statt_ordner gemeldet
        if neu.at[p, "bytes"] == 0:
            befund(p, "null_byte_neu", "neue Datei mit 0 Byte")
        else:
            befund(p, "datei_neu")
    for p in sorted(p_alt & p_neu):
        b_alt, b_neu = int(alt.at[p, "bytes"]), int(neu.at[p, "bytes"])
        if b_neu == 0 and b_alt > 0:
            befund(p, "null_byte_neu", f"{b_alt} Byte vorher")
        elif alt.at[p, "sha256"] != neu.at[p, "sha256"]:
            befund(p, "inhalt_geaendert", f"{b_alt} -> {b_neu} Byte")

    df = pd.DataFrame(zeilen, columns=BEFUND_SPALTEN)
    reihenfolge = {t: i for i, t in enumerate(BEFUNDE)}
    return df.sort_values(["typ", "pfad"], key=lambda s: s.map(reihenfolge) if s.name == "typ" else s,
                          ignore_index=True)


def zusammenfassung(df_befunde: pd.DataFrame) -> pd.DataFrame:
    """Anzahl Befunde je Typ in fester Reihenfolge (auch 0), Einheit [Befunde]."""
    n = df_befunde["typ"].value_counts()
    return pd.DataFrame({"typ": list(BEFUNDE), "schwere": list(BEFUNDE.values()),
                         "anzahl [Befunde]": [int(n.get(t, 0)) for t in BEFUNDE]})


def warnung_noetig(df_befunde: pd.DataFrame) -> bool:
    """True, wenn ein kritischer Befund vorliegt -> Warnung vor Sicherung und vor Schreiben."""
    return bool((df_befunde["schwere"] == "kritisch").any())
