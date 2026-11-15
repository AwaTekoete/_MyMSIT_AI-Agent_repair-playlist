"""Writer (Workflow 5): foobar-Playlist schreiben.

Format (Entscheidung 12.11.2026): immer .m3u8 = UTF-8 mit BOM, Kopfzeile '#',
Zeilenende CRLF, absolute Pfade mit Laufwerk des Ziel-Laptops (wie foobar selbst
schreibt, NB 02 Zelle 05). Messung NB 04 Zelle 05: 100 Dateien im Musikordner
sind in cp1252 nicht darstellbar -> UTF-8 noetig fuer verlustfreie Pfade.
P3: Ueberschreiben nur mit Backup der Vorversion (Unterordner _backup);
gleicher Inhalt -> nichts schreiben; nie loeschen.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from playlist_agent.linter import ist_stream

BOM = b"\xef\xbb\xbf"
_VERBOTEN = re.compile(r'[\\/:*?"<>|]')


def sicherer_dateiname(name: str) -> str:
    """Playlist-Name -> gueltiger Windows-Dateiname (Subcrate-Hierarchie '%%' -> ' - ')."""
    s = _VERBOTEN.sub("_", name.replace("%%", " - ")).strip(" .")
    return s or "_"


def eindeutige_dateinamen(namen: list[str]) -> dict[str, str]:
    """Playlist-Namen -> eindeutige Dateinamen (Windows: Gross/Klein egal).
    Kollision nach Bereinigung (z. B. 'X' und 'X.') -> ' (2)', ' (3)' ...;
    Reihenfolge sortiert -> jeder Lauf ergibt dieselben Namen."""
    vergeben, ergebnis = set(), {}
    for name in sorted(namen):
        basis = sicherer_dateiname(name)
        kandidat, n = basis, 1
        while kandidat.lower() in vergeben:
            n += 1
            kandidat = f"{basis} ({n})"
        vergeben.add(kandidat.lower())
        ergebnis[name] = kandidat
    return ergebnis


def inhalt_m3u8(pfade: list[str], laufwerk: str) -> bytes:
    """Kanonische Pfade ('Musik/A/x.mp3') -> Dateiinhalt fuer foobar; Streams unveraendert."""
    zeilen = ["#"] + [p if ist_stream(p) else f"{laufwerk}\\" + p.replace("/", "\\") for p in pfade]
    return BOM + ("\r\n".join(zeilen) + "\r\n").encode("utf-8")


@dataclass
class SchreibErgebnis:
    datei: Path
    status: str                 # neu | geaendert | unveraendert
    eintraege: int
    backup: Path | None = None


def schreibe_playlist(ordner: Path, name: str, pfade: list[str], laufwerk: str,
                      dateiname: str | None = None) -> SchreibErgebnis:
    """Schreibt <ordner>/<name>.m3u8; bei Aenderung vorher Backup nach <ordner>/_backup/."""
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / f"{dateiname or sicherer_dateiname(name)}.m3u8"
    neu = inhalt_m3u8(pfade, laufwerk)
    if datei.exists():
        if datei.read_bytes() == neu:
            return SchreibErgebnis(datei, "unveraendert", len(pfade))
        backup_dir = ordner / "_backup"
        backup_dir.mkdir(exist_ok=True)
        stempel = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup = backup_dir / f"{datei.stem}_{stempel}{datei.suffix}"
        shutil.copy2(datei, backup)
        datei.write_bytes(neu)
        return SchreibErgebnis(datei, "geaendert", len(pfade), backup)
    datei.write_bytes(neu)
    return SchreibErgebnis(datei, "neu", len(pfade))