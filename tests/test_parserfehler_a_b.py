"""Regressionstests Parser-Fehler A ('..') und B (%XX ohne file://), Befund NB04 Zelle 17."""

import pandas as pd

from playlist_agent.canon import kanonisch
from playlist_agent.resolver import Resolver

AUDIO = [".mp3", ".wav", ".aif"]


def index(zeilen):
    df = pd.DataFrame(zeilen, columns=["pfad_relativ", "bytes", "sha256"])
    df["endung"] = df["pfad_relativ"].map(lambda p: "." + p.rsplit(".", 1)[-1] if "." in p.split("/")[-1] else "(ohne)")
    df["appledouble"] = False
    return df


# --- A: '..' in allen Pfadformen ------------------------------------------------------
def test_windows_punktpunkt_aufgeloest():
    assert kanonisch("D:\\Musik\\A\\B\\..\\..\\C\\x.mp3") == ("Musik/C/x.mp3", "Laufwerk D:")


def test_url_punktpunkt_aufgeloest():
    assert kanonisch("file:///Volumes/Lexar/Musik/A/../B/x.mp3")[0] == "Musik/B/x.mp3"


def test_windows_ohne_punktpunkt_unveraendert():
    assert kanonisch("E:\\Musik/A B/x.mp3")[0] == "Musik/A B/x.mp3"


# --- B: %-Rückfall nur bei 'fehlt' ------------------------------------------------------
IDX_PCT = index([("Musik/P/a b.mp3", 10, None), ("Musik/Q/x%20y.mp3", 20, None),
                 ("Musik/Kaputt", 0, None)])
R_PCT = Resolver(IDX_PCT, AUDIO)


def test_prozent_rueckfall_findet_datei():
    e = R_PCT.aufloesen("Musik/P/a%20b.mp3")
    assert (e.klasse, e.stufe, e.pfad) == ("sicher", "pfad", "Musik/P/a b.mp3")
    assert "Dekodierung" in e.grund


def test_prozent_echter_dateiname_bleibt_geschuetzt():
    e = R_PCT.aufloesen("Musik/Q/x%20y.mp3")
    assert (e.klasse, e.pfad) == ("sicher", "Musik/Q/x%20y.mp3") and "Dekodierung" not in e.grund


def test_prozent_ohne_treffer_bleibt_fehlt():
    assert R_PCT.aufloesen("Musik/Z/n%20n.mp3").klasse == "fehlt"


def test_kein_rueckfall_wenn_nicht_fehlt():
    assert R_PCT.aufloesen("Musik/Kaputt/t%201.mp3").klasse == "album_beschaedigt"