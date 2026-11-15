"""Tests für playlist_agent.canon (synthetische Beispiele, public-tauglich)."""

import unicodedata

import pytest

from playlist_agent.canon import kanonisch, nfc, pfadform

NFC_AE = "Musik/K\u00e4fer/Lied.mp3"          # 'ä' vorkomponiert
NFD_AE = "Musik/Ka\u0308fer/Lied.mp3"         # 'a' + Trema


def test_nfc_vereinheitlicht():
    assert nfc(NFD_AE) == NFC_AE


@pytest.mark.parametrize("eintrag, form", [
    ("file:///Volumes/Stick/Musik/a.mp3", "url"),
    ("D:\\Musik\\a.mp3", "windows"),
    ("d:/Musik/a.mp3", "windows"),
    ("/Volumes/Stick/Musik/a.mp3", "volumes"),
    ("/home/a.mp3", "unix"),
    ("..\\Musik\\a.mp3", "relativ"),
])
def test_pfadform(eintrag, form):
    assert pfadform(eintrag) == form


@pytest.mark.parametrize("eintrag, ordner, erwartet, herkunft", [
    ("D:\\Musik\\Album\\01.mp3", None, "Musik/Album/01.mp3", "Laufwerk D:"),
    ("q:\\Musik\\Album\\01.mp3", None, "Musik/Album/01.mp3", "Laufwerk Q:"),
    ("file:///Volumes/Stick/Musik/A%20B/c.mp3", None, "Musik/A B/c.mp3", "Volumes/Stick"),
    ("file:///Volumes/Stick/Musik/Ka%CC%88fer/Lied.mp3", None, NFC_AE, "Volumes/Stick"),
    ("/Volumes/Stick/Musik/x.mp3", None, "Musik/x.mp3", "Volumes/Stick"),
    ("..\\Album\\01.mp3", "Musik/Listen", "Musik/Album/01.mp3", "relativ"),
    ("01.mp3", "Musik/Album", "Musik/Album/01.mp3", "relativ"),
    (NFD_AE, "", NFC_AE, "relativ"),
])
def test_kanonisch(eintrag, ordner, erwartet, herkunft):
    pfad, h = kanonisch(eintrag, ordner)
    assert pfad == erwartet
    assert h == herkunft
    assert unicodedata.is_normalized("NFC", pfad)


def test_relativ_ohne_ordner_wirft_fehler():
    with pytest.raises(ValueError):
        kanonisch("01.mp3")