"""Stick-Index: Dateien, leere Ordner, Tags, Hash (nur lesend, P1/P7).

Logik aus Notebook 01 Zelle 08 (Index) und Notebook 02 Zellen 12 (Tags),
20-21 (Hash nur bei gleicher Groesse), 25 (0-Byte-Dateien). Neu: leere Ordner,
die im Datei-Index unsichtbar sind (Hinweis "Album vermutlich geloescht").
Pfade relativ zur Stick-Wurzel, Trenner '/', NFC.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import pandas as pd
from tinytag import TinyTag

from playlist_agent.canon import nfc

SPALTEN = ["pfad_relativ", "endung", "appledouble", "bytes", "mtime"]
TAG_FELDER = ["title", "artist", "album", "track", "year", "duration"]


def scanne(wurzel: Path, unterordner: str = "Musik") -> pd.DataFrame:
    """Alle Dateien unter wurzel/unterordner (rekursiv), sortiert nach Pfad."""
    wurzel = Path(wurzel)
    zeilen = []
    for f in (wurzel / unterordner).rglob("*"):
        if f.is_file():
            st = f.stat()
            zeilen.append({
                "pfad_relativ": nfc(f.relative_to(wurzel).as_posix()),
                "endung": f.suffix.lower() or "(ohne)",
                "appledouble": f.name.startswith("._"),
                "bytes": st.st_size,
                "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            })
    return pd.DataFrame(zeilen, columns=SPALTEN).sort_values("pfad_relativ").reset_index(drop=True)


def leere_ordner(wurzel: Path, unterordner: str = "Musik") -> list[str]:
    """Ordner ohne eine einzige Datei (auch nicht in Unterordnern)."""
    wurzel = Path(wurzel)
    return sorted(nfc(d.relative_to(wurzel).as_posix())
                  for d in (wurzel / unterordner).rglob("*")
                  if d.is_dir() and not any(p.is_file() for p in d.rglob("*")))


def ist_audio(df: pd.DataFrame, endungen: list[str]) -> pd.Series:
    """Echte Audiodatei: Endung in der Positivliste und kein AppleDouble."""
    return df["endung"].isin(endungen) & ~df["appledouble"]


def lese_tags(datei: Path) -> dict:
    """Tags und Dauer einer Datei; Fehler werden erfasst, nicht verschluckt."""
    try:
        tag = TinyTag.get(datei, image=False)
        return {**{f: getattr(tag, f, None) for f in TAG_FELDER}, "tag_fehler": None}
    except Exception as e:                    # einzelne Datei darf den Lauf nicht stoppen
        return {**{f: None for f in TAG_FELDER}, "tag_fehler": repr(e)}


def ergaenze_tags(df: pd.DataFrame, wurzel: Path, endungen: list[str]) -> pd.DataFrame:
    """Haengt Tag-Spalten an (nur fuer echte Audiodateien, sonst leer)."""
    audio = ist_audio(df, endungen)
    tags = [lese_tags(Path(wurzel) / p) if a else {} for p, a in zip(df["pfad_relativ"], audio)]
    return pd.concat([df, pd.DataFrame(tags, index=df.index)], axis=1)


def sha256_datei(pfad: Path) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def ergaenze_hash(df: pd.DataFrame, wurzel: Path, endungen: list[str],
                  nur_gleiche_groesse: bool = True) -> pd.DataFrame:
    """SHA-256 fuer Audiodateien; standardmaessig nur bei mehrfach vorkommender Groesse
    (notwendige Bedingung fuer bitgleichen Inhalt, NB 02 Zelle 20)."""
    df = df.copy()
    auswahl = ist_audio(df, endungen)
    if nur_gleiche_groesse:
        auswahl &= df["bytes"].map(df.loc[auswahl, "bytes"].value_counts()).fillna(0) >= 2
    df["sha256"] = None
    df.loc[auswahl, "sha256"] = [sha256_datei(Path(wurzel) / p) for p in df.loc[auswahl, "pfad_relativ"]]
    return df