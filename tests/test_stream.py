"""Tests Stream-Übernahme (Entscheidung 15.11.2026): Erkennung + unverändertes Schreiben."""

import pytest

from playlist_agent.linter import ist_stream
from playlist_agent.writer import BOM, inhalt_m3u8


@pytest.mark.parametrize("eintrag, erwartet", [
    ("http://www.example.org/radio/high.asx", True),
    ("HTTPS://example.org/x.m3u", True),
    ("mms://example.org/live", True),
    ("  http://example.org/a.mp3", True),
    ("file:///Volumes/Lexar/Musik/a.mp3", False),     # Datei, kein Stream
    ("D:\\Musik\\a.mp3", False),
    ("..\\Album\\http.mp3", False),
])
def test_ist_stream(eintrag, erwartet):
    assert ist_stream(eintrag) is erwartet


def test_writer_schreibt_stream_unveraendert():
    inhalt = inhalt_m3u8(["Musik/A/x.mp3", "http://example.org/r.asx"], "D:")
    assert inhalt == BOM + "#\r\nD:\\Musik\\A\\x.mp3\r\nhttp://example.org/r.asx\r\n".encode("utf-8")