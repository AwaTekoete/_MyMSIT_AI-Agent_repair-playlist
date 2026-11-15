"""Tests fuer anchor.py mit simulierten Laufwerken (Ordner unter tmp_path)."""

import pytest

from playlist_agent.anchor import (HostUnbekannt, StickMehrdeutig, StickNichtGefunden,
                                   finde_stick, laptop_fuer_host, verankere)

SIGNATUR = ["Musik", "Playlist", "_ScratchLIVE_/Crates"]
CFG = {"stick": {"signatur": SIGNATUR, "signatur_min_treffer": 3},
       "laptops": [{"name": "l1", "hostname": "HostEins", "laufwerk_beobachtet": "D:"},
                   {"name": "l2", "hostname": "HostZwei", "laufwerk_beobachtet": "E:"}]}


def _laufwerk(tmp_path, name, ordner):
    w = tmp_path / name
    for o in ordner:
        (w / o).mkdir(parents=True)
    w.mkdir(exist_ok=True)
    return w


def test_eindeutiger_stick(tmp_path):
    stick = _laufwerk(tmp_path, "X", SIGNATUR)
    andere = _laufwerk(tmp_path, "Y", ["Musik"])               # nur 1/3 Signatur
    assert finde_stick(SIGNATUR, wurzeln=[andere, stick]) == stick


def test_kein_stick_klare_meldung(tmp_path):
    with pytest.raises(StickNichtGefunden, match="bitte einstecken"):
        finde_stick(SIGNATUR, wurzeln=[_laufwerk(tmp_path, "Y", ["Musik", "Playlist"])])


def test_negativtest_ohne_laufwerke():
    with pytest.raises(StickNichtGefunden):
        finde_stick(SIGNATUR, wurzeln=[])


def test_mehrdeutig(tmp_path):
    a, b = _laufwerk(tmp_path, "A", SIGNATUR), _laufwerk(tmp_path, "B", SIGNATUR)
    with pytest.raises(StickMehrdeutig):
        finde_stick(SIGNATUR, wurzeln=[a, b])


def test_min_treffer_lockerung(tmp_path):
    w = _laufwerk(tmp_path, "X", ["Musik", "Playlist"])
    assert finde_stick(SIGNATUR, min_treffer=2, wurzeln=[w]) == w


def test_signatur_verlangt_ordner_nicht_datei(tmp_path):
    w = _laufwerk(tmp_path, "X", ["Musik", "Playlist", "_ScratchLIVE_"])
    (w / "_ScratchLIVE_/Crates").write_bytes(b"")              # Datei statt Ordner (Muster 0-Byte)
    with pytest.raises(StickNichtGefunden):
        finde_stick(SIGNATUR, wurzeln=[w])


def test_hostname_ohne_gross_klein():
    assert laptop_fuer_host(CFG["laptops"], "hostzwei")["name"] == "l2"


def test_hostname_unbekannt():
    with pytest.raises(HostUnbekannt, match="Phase 7"):
        laptop_fuer_host(CFG["laptops"], "Fremd")


def test_verankere_komplett(tmp_path):
    stick = _laufwerk(tmp_path, "X", SIGNATUR)
    a = verankere(CFG, hostname="HostEins", wurzeln=[stick], seriennummer_pruefen=lambda w: True)
    assert a.wurzel == stick and a.laptop["name"] == "l1" and a.seriennummer_ok is True
    assert a.laufwerk_wie_konfiguriert is False                 # tmp_path hat kein Laufwerk D:


def test_seriennummer_nicht_geprueft(tmp_path):
    stick = _laufwerk(tmp_path, "X", SIGNATUR)
    assert verankere(CFG, hostname="HostEins", wurzeln=[stick]).seriennummer_ok is None
