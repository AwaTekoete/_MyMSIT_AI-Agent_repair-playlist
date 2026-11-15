"""Serato-Dateien lesen: .crate (Crates/Subcrates) und 'database V2'.

Format (EDA Notebook 02, Zellen 02 und 08): TLV-Bloecke aus 4-Byte-Tag,
4-Byte-Laenge (Big-Endian), Inhalt; Texte UTF-16-BE. Track = 'otrk'.
Crate: Pfad je Track in 'ptrk'. database V2: Felder je Track, Dekodierung
nach erstem Buchstaben des Tags (t/p Text, u 4-Byte-Zahl, s 2-Byte-Zahl,
b 1-Byte-Flag). Integritaet: Datei und jeder Track muessen exakt aufgehen.
Nur lesend (P2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def tlv_bloecke(b: bytes) -> tuple[list[tuple[str, bytes]], bool]:
    """Zerlegt Bytes in (Tag, Inhalt)-Bloecke; zweiter Wert: geht exakt auf?"""
    i, bloecke = 0, []
    while i + 8 <= len(b):
        tag, n = b[i:i + 4], int.from_bytes(b[i + 4:i + 8], "big")
        if i + 8 + n > len(b):          # Block laenger als Restdatei -> abgeschnitten
            return bloecke, False       # unvollstaendigen Block nicht uebernehmen
        bloecke.append((tag.decode("latin-1"), b[i + 8:i + 8 + n]))
        i += 8 + n
    return bloecke, i == len(b)


@dataclass
class CrateInhalt:
    version: str | None
    pfade: list[str] = field(default_factory=list)
    vollstaendig: bool = True


def lese_crate(pfad: Path) -> CrateInhalt:
    """Liest eine .crate-Datei: Version, Pfade (Reihenfolge erhalten), Integritaet."""
    bloecke, ok = tlv_bloecke(Path(pfad).read_bytes())
    inhalt = CrateInhalt(version=None, vollstaendig=ok)
    for tag, wert in bloecke:
        if tag == "vrsn":
            inhalt.version = wert.decode("utf-16-be")
        elif tag == "otrk":
            felder, ok_track = tlv_bloecke(wert)
            inhalt.vollstaendig &= ok_track
            inhalt.pfade += [w.decode("utf-16-be") for t, w in felder if t == "ptrk"]
    return inhalt


def feldwert(tag: str, wert: bytes):
    """Dekodierung nach Tag-Praefix; unbekannt -> nur Laenge (keine Annahme)."""
    try:
        if tag[0] in "tp":
            return wert.decode("utf-16-be")
        if tag[0] == "u" and len(wert) == 4:
            return int.from_bytes(wert, "big")
        if tag[0] == "s" and len(wert) == 2:
            return int.from_bytes(wert, "big")
        if tag[0] == "b" and len(wert) == 1:
            return wert[0]
    except UnicodeDecodeError:
        pass
    return f"<{len(wert)} Byte>"


def lese_database_v2(pfad: Path) -> tuple[list[dict], bool]:
    """Liest 'database V2': je Track ein Dict {Tag: Wert}; zweiter Wert: alles exakt?"""
    bloecke, ok = tlv_bloecke(Path(pfad).read_bytes())
    tracks = []
    for tag, wert in bloecke:
        if tag == "otrk":
            felder, ok_track = tlv_bloecke(wert)
            ok &= ok_track
            tracks.append({t: feldwert(t, w) for t, w in felder})
    return tracks, ok