"""Kanonische Pfade: jede Quelle -> 'Musik/.../x.mp3' (NFC, Trenner '/').

Regeln aus der EDA (Notebook 02, Zellen 03 und 17):
  URL file://       Prozent-Dekodierung, '/Volumes/<Datentraeger>/' entfernen
  /Volumes/...      wie URL ohne Schema
  Windows absolut   'X:\\' entfernen, '\\' -> '/'
  relativ           gegen den Ordner der Playlist-Datei aufloesen ('..' erlaubt)
  Unix absolut      fuehrenden '/' entfernen (kommt in den Daten nicht vor)
Ergebnis immer NFC (Stick-Dateinamen sind NFC; Crates teils NFD) und ohne '.'/'..'-Segmente.
"""

from __future__ import annotations

import posixpath
import re
import unicodedata
from urllib.parse import unquote, urlparse

_WINDOWS = re.compile(r"^[A-Za-z]:[\\/]")


def nfc(s: str) -> str:
    """Unicode-Normalform NFC (vorkomponiert)."""
    return unicodedata.normalize("NFC", s)


def pfadform(eintrag: str) -> str:
    """Pfadform eines Roheintrags: 'url', 'windows', 'volumes', 'unix' oder 'relativ'."""
    if eintrag.lower().startswith("file://"):
        return "url"
    if _WINDOWS.match(eintrag):
        return "windows"
    if eintrag.startswith("/Volumes/"):
        return "volumes"
    if eintrag.startswith("/"):
        return "unix"
    return "relativ"


def _ohne_volumes(p: str) -> tuple[str, str]:
    """'/Volumes/<Name>/rest' -> ('rest', 'Volumes/<Name>')."""
    teile = p.split("/")                      # ['', 'Volumes', '<Name>', ...]
    if len(teile) > 3 and teile[1] == "Volumes":
        return "/".join(teile[3:]), f"Volumes/{teile[2]}"
    return p.lstrip("/"), "ohne Volumes"


def kanonisch(eintrag: str, playlist_ordner: str | None = None) -> tuple[str, str]:
    """Roheintrag -> (kanonischer Pfad relativ zur Stick-Wurzel, Herkunftsmerkmal).

    playlist_ordner: Ordner der Playlist-Datei relativ zur Stick-Wurzel
    (z. B. 'Musik/Album'); nur fuer relative Eintraege noetig.
    """
    e = eintrag.strip()
    form = pfadform(e)
    if form == "url":
        pfad, herkunft = _ohne_volumes(unquote(urlparse(e).path))
    elif form == "volumes":
        pfad, herkunft = _ohne_volumes(e)
    elif form == "windows":
        pfad, herkunft = e[3:].replace("\\", "/"), f"Laufwerk {e[0].upper()}:"
    elif form == "unix":
        pfad, herkunft = e.lstrip("/"), "Unix absolut"
    else:
        if playlist_ordner is None:
            raise ValueError("Relativer Eintrag ohne Ordner der Playlist-Datei")
        pfad = posixpath.normpath(posixpath.join(playlist_ordner, e.replace("\\", "/")))
        herkunft = "relativ"
    # '..' und '.' für alle Formen auflösen (Befund 15.11.2026: 2.191 Windows-Einträge mit '\..\')
    pfad = posixpath.normpath(pfad) if pfad else pfad
    return nfc(pfad), herkunft