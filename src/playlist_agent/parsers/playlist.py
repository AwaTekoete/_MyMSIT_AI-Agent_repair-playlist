"""Playlist-Dateien lesen: M3U/M3U8 und WPL (Windows Media Player).

Befunde EDA (Notebook 02, Zelle 16): Kodierung gemischt (ASCII, UTF-8 ohne BOM,
nicht-UTF-8 -> als cp1252 gelesen), kein BOM im Bestand (foobar .m3u8 schreibt
aber BOM, Zelle 05), Zeilenende CRLF oder LF.
M3U: jede nicht leere Zeile ohne '#' ist ein Eintrag.
WPL: XML, Eintrag = Attribut src="..." in <media>; XML-Zeichenreferenzen
(&amp; &apos; &quot; &lt; &gt; &#...;) werden zurueckverwandelt.
Nur lesend (P2).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

_WPL_SRC = re.compile(r'<media[^>]*\bsrc="([^"]*)"', re.I)


def dekodieren(b: bytes) -> tuple[str, str]:
    """Bytes -> (Text, Kodierung). BOM zuerst, dann UTF-8 streng, sonst cp1252."""
    if b.startswith(b"\xef\xbb\xbf"):
        return b[3:].decode("utf-8", errors="replace"), "UTF-8 mit BOM"
    if b.startswith((b"\xff\xfe", b"\xfe\xff")):
        return b.decode("utf-16"), "UTF-16 mit BOM"
    try:
        return b.decode("utf-8"), ("ASCII" if b.isascii() else "UTF-8 ohne BOM")
    except UnicodeDecodeError:
        return b.decode("cp1252", errors="replace"), "cp1252"


@dataclass
class PlaylistInhalt:
    eintraege: list[str] = field(default_factory=list)
    kodierung: str = ""
    zeilenende: str = ""
    kopf_extm3u: bool = False
    n_extinf: int = 0


def lese_playlist(pfad: Path) -> PlaylistInhalt:
    """Liest .m3u/.m3u8/.wpl; Eintraege in Originalreihenfolge, unveraendert (roh)."""
    b = Path(pfad).read_bytes()
    text, kodierung = dekodieren(b)
    zeilen = text.splitlines()
    inhalt = PlaylistInhalt(
        kodierung=kodierung,
        zeilenende="CRLF" if b"\r\n" in b else "LF" if b"\n" in b else "CR" if b"\r" in b else "keins",
        kopf_extm3u=text.lstrip("\ufeff").startswith("#EXTM3U"),
        n_extinf=sum(z.startswith("#EXTINF") for z in zeilen),
    )
    if Path(pfad).suffix.lower() == ".wpl":
        inhalt.eintraege = [html.unescape(s) for s in _WPL_SRC.findall(text)]
    else:
        inhalt.eintraege = [z.strip() for z in zeilen if z.strip() and not z.lstrip().startswith("#")]
    return inhalt