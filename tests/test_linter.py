"""Tests fuer playlist_agent.linter (Regel kein Audio)."""

import pytest

from playlist_agent.linter import pruefe_eintrag

AUDIO = [".mp3", ".wav", ".aif"]


@pytest.mark.parametrize("pfad, untertyp", [
    ("Musik/A/01.MP3", None),                       # Audio (Gross-/Kleinschreibung egal)
    ("Musik/A/01.mp3.asd", "begleitdatei"),
    ("Musik/A/._01.mp3", "begleitdatei"),           # AppleDouble trotz Audio-Endung
    ("Musik/A/clip.wmv", "video"),
    ("Musik/A/liste.m3u", "playlist_verweis"),
    ("Musik/A/x.mxc2", "sonstige"),
    ("Musik/A/ohne_endung", "sonstige"),
])
def test_kein_audio(pfad, untertyp):
    b = pruefe_eintrag(pfad, AUDIO)
    assert (b.untertyp if b else None) == untertyp