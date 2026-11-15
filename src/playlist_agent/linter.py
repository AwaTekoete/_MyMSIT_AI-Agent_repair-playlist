"""Linter (Workflow 3b): Eintraege pruefen, bevor der Resolver sucht.

Regel 1 – kein Audio (Befund NB 02 Zelle 26, 12.11.2026): 21 Eintraege mit
Endung ausserhalb der Audio-Positivliste (.asd, .mxc2, .wmv, .asx, .m3u).
Solche Eintraege werden NICHT gesucht und NICHT stillschweigend entfernt,
sondern als "ausgeschlossen" mit Untertyp gemeldet (P4).
AppleDouble ('._*') gilt als Begleitdatei, auch mit Audio-Endung.
Weitere Regeln folgen (gemischte Trenner, Mojibake, EXTINF-Widerspruch ...).
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass

BEGLEITDATEI = {".asd"}                                        # Ableton-Analysedatei
VIDEO = {".wmv", ".m4v", ".mp4", ".avi", ".mov", ".mkv"}
PLAYLIST_VERWEIS = {".m3u", ".m3u8", ".asx", ".wpl", ".pls", ".crate"}
# Internet-Streams (Entscheidung 15.11.2026: unverändert übernehmen; foobar spielt sie ab)
STREAM = re.compile(r"^(?:https?|mms|rtsp)://", re.IGNORECASE)


@dataclass
class LintBefund:
    klasse: str          # immer "ausgeschlossen" bei Regel 1
    untertyp: str        # begleitdatei | video | playlist_verweis | sonstige
    grund: str


def ist_stream(eintrag: str) -> bool:
    """Roheintrag ist eine Stream-Adresse -> vor Kanonisierung erkennen, unverändert schreiben."""
    return bool(STREAM.match(eintrag.strip()))


def pruefe_eintrag(pfad: str, audio_endungen: list[str]) -> LintBefund | None:
    """None = Eintrag geht weiter an den Resolver; sonst Befund (ausgeschlossen)."""
    name = posixpath.basename(pfad)
    endung = posixpath.splitext(name)[1].lower()
    if name.startswith("._"):
        return LintBefund("ausgeschlossen", "begleitdatei", "AppleDouble-Datei")
    if endung in audio_endungen:
        return None
    if endung in BEGLEITDATEI:
        untertyp = "begleitdatei"
    elif endung in VIDEO:
        untertyp = "video"
    elif endung in PLAYLIST_VERWEIS:
        untertyp = "playlist_verweis"
    else:
        untertyp = "sonstige"
    return LintBefund("ausgeschlossen", untertyp, f"Endung {endung or '(ohne)'} ist kein Audio")