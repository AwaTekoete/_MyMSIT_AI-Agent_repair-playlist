"""create_from_folder (Intent-Katalog): Playlist aus einem Ordner, Reihenfolge per Regel.

Ordnertyp wird bei jedem Aufruf automatisch aus den Dateien bestimmt (kein Pflegeaufwand),
Entscheidung Nutzer 15.11.2026, Messung NB04 Zellen 21/22 (311 Ordner: A 155, S 66, E 90):
  S Set-Mitschnitt  alle Dateinamen = gemeinsamer Anfang + Zahl am Ende (beliebig viele Ziffern,
                    Trenner Leerzeichen/_/-), Zahlen eindeutig -> nach Endzahl.
                    Vorrang vor Tags: Nummer im DATEINAMEN vom Nutzer vergeben.
  A Album           Tracknummern vollstaendig + eindeutig -> nach Tracknummer.
  E Einzeltitel     sonst -> natuerliche Sortierung ('2 x' vor '10 x'), keine echte Sequenz.
Grenzen (gemessen): Dateiname und Track-Reihenfolge stimmen in 162/171 Alben ueberein
(95-%-KI 90,3–97,2 %); Nummern sind von Hand vergeben und nicht garantiert.
Nur Dateien direkt im Ordner (keine Unterordner); Auswahl Audio/Video erfolgt beim Aufrufer.
"""

from __future__ import annotations

import posixpath
import re

ENDZAHL = re.compile(r"^(.*?)[\s_\-]*(\d+)$")


def natur_schluessel(name: str) -> list:
    """Natuerliche Sortierung: Zahlen als Zahl, Text ohne Gross/Klein."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def set_reihenfolge(namen: list[str]) -> list[str] | None:
    """Reihenfolge nach Endzahl, wenn alle Namen gemeinsamen Anfang + eindeutige Endzahl haben."""
    treffer = [ENDZAHL.match(posixpath.splitext(n)[0]) for n in namen]
    if len(namen) < 2 or not all(treffer):
        return None
    anfang = {m.group(1).strip().lower() for m in treffer}
    zahlen = [int(m.group(2)) for m in treffer]
    if len(anfang) != 1 or len(set(zahlen)) != len(zahlen):
        return None
    return [n for _, n in sorted(zip(zahlen, namen))]


def ordne(namen: list[str], tracks: dict[str, int | None] | None = None) -> tuple[list[str], str]:
    """Dateinamen ordnen -> (Reihenfolge, Regel 'endzahl' | 'tracknummer' | 'dateiname')."""
    s = set_reihenfolge(namen)
    if s is not None:
        return s, "endzahl"
    t = [(tracks or {}).get(n) for n in namen]
    if namen and all(isinstance(x, int) for x in t) and len(set(t)) == len(t):
        return [n for _, n in sorted(zip(t, namen))], "tracknummer"
    return sorted(namen, key=natur_schluessel), "dateiname"


def playlist_aus_ordner(pfade: list[str], ordner: str,
                        tracks: dict[str, int | None] | None = None) -> tuple[list[str], str]:
    """Kanonische Pfade (z. B. Audio-Index) -> Pfade direkt in `ordner`, geordnet, + Regel.

    tracks: kanonischer Pfad -> Tracknummer (int) oder None.
    """
    ordner = ordner.strip("/")
    direkt = [p for p in pfade if posixpath.dirname(p) == ordner]
    namen = [posixpath.basename(p) for p in direkt]
    t = {posixpath.basename(p): (tracks or {}).get(p) for p in direkt}
    reihe, regel = ordne(namen, t)
    return [posixpath.join(ordner, n) for n in reihe], regel
