"""Tests fuer playlist_agent.bibliothek (synthetisch, keine echten Namen, P11)."""

import pandas as pd
import pytest

from playlist_agent.bibliothek import (ba_zeiten, be_markiert, be_zeiten, bewertung, dj, genre_woerter,
                                       interpret, lade_kuerzel, merkmale, popm_sterne, zerlege_genre)

KUERZEL = {"XY": "DJ Eins", "ABC": "DJ Zwei"}


@pytest.mark.parametrize("titel, erwartet", [
    ("BE3:08 02 Stueck", ["3:08"]), ("++BE2:58 Stueck", ["2:58"]), ("+BE 4.34 Stueck", ["4:34"]),
    ("XY be7:57 Set 16", ["7:57"]), ("aBE4:05 Name", ["4:05"]), ("Set SVbe7:09 x", ["7:09"]),
    ("BE5:46 und BE14:02 Name", ["5:46", "14:02"]), ("Set gut be 1:42:20", ["1:42:20"]),
    ("BEAT 3:00", []), ("BE Name", []), (None, [])])
def test_be_zeiten(titel, erwartet):
    assert be_zeiten(titel) == erwartet


def test_ba_zeiten():
    assert ba_zeiten("BA0:44 BE5:30 Set") == ["0:44"]
    assert ba_zeiten("BE 6:02 XY ba0:50 be6:37") == ["0:50"]
    assert be_zeiten("BE 6:02 XY ba0:50 be6:37") == ["6:02", "6:37"]


@pytest.mark.parametrize("titel, erwartet", [
    ("BE Name", True), ("Name be", True), ("BE3:00 x", True), ("Be Yourself", False),
    ("THE BEGIN", False), ("I BELIEVE", False), (None, False)])
def test_be_markiert(titel, erwartet):
    assert be_markiert(titel) == erwartet


@pytest.mark.parametrize("genre, woerter", [
    ("PushTechnoBeat", ["push", "techno", "beat"]), ("Techno HAPPY", ["techno", "happy"]),
    ("R&B house", ["r&b", "house"]), ("TechHouse", ["techhouse"]), ("Tech / House", ["techhouse"]),
    ("HappytechHouse", ["happy", "techhouse"]), ("Electronic Beats", ["electronic", "beat"]),
    ("techno house", ["techno", "house"])])
def test_genre_woerter(genre, woerter):
    assert genre_woerter(genre) == woerter


@pytest.mark.parametrize("genre, stimmung, stil", [
    ("SoftTechnoBeat", ["beat", "soft"], ["techno"]), ("HappyTechHouse", ["happy"], ["techhouse"]),
    ("RockTechHouseBeat", ["beat", "rock"], ["techhouse"]), ("Techhouse", [], ["techhouse"]),
    ("RockTechno", ["rock"], ["techno"]), ("Rock", [], ["rock"]),
    ("Classic Rock", [], ["rock"]), ("Folk-Rock", [], ["rock"]),   # Kauf-CD: rock ist Stil
    ("Techno Acid", [], ["acid", "techno"])])
def test_zerlege_genre(genre, stimmung, stil):
    z = zerlege_genre(genre)
    assert (z["stimmung"], z["stil"]) == (stimmung, stil)


def test_genre_notiz_und_keine_info():
    assert zerlege_genre("prüfen")["notiz"] == ["prüfen"]
    assert zerlege_genre("Other")["keine_info"] and zerlege_genre("-255")["keine_info"]
    assert zerlege_genre("Minimal锅")["defekt"]


@pytest.mark.parametrize("comment, serato, sterne, konflikt, herkunft", [
    ("4sterne", "4 Sterne", 4, False, "comment+serato"),
    (None, "3 Sterne", 3, False, "serato"),
    ("5Sterne", None, 5, False, "comment"),
    ("4sterne", "5sterne", None, True, "comment+serato"),
    ("prüfen", None, None, False, None), (None, None, None, False, None)])
def test_bewertung(comment, serato, sterne, konflikt, herkunft):
    b = bewertung(comment, serato)
    assert (b["bewertung"], b["bewertung_konflikt"], b["bewertung_herkunft"]) == (sterne, konflikt, herkunft)


@pytest.mark.parametrize("wert, sterne", [("196", 4), ("255", 5), ("61", None), ("196; 255", None), (None, None)])
def test_popm_sterne(wert, sterne):
    assert popm_sterne(wert) == sterne


@pytest.mark.parametrize("si, titel, ordner, datei, d, herkunft", [
    ("XY Mix", "Titel", "Musik/O", "t.mp3", "DJ Eins", "serato_mix"),
    ("QQ Mix", "Titel", "Musik/O", "t.mp3", "QQ", "serato_mix"),          # Kuerzel ohne Liste bleibt
    (None, "+BE3:00 XY 2009 Set 01", "Musik/O", "t.mp3", "DJ Eins", "titel"),
    (None, "Titel", "Musik/ABC 2008 Set", "t.mp3", "DJ Zwei", "ordner"),
    (None, "Titel", "Musik/O", "ABC 01.wav", "DJ Zwei", "datei"),
    (None, "XYZ Titel", "Musik/O", "xy.mp3", None, "unbekannt")])          # Wortgrenze, Gross/Klein
def test_dj(si, titel, ordner, datei, d, herkunft):
    r = dj(si, titel, ordner, datei, KUERZEL)
    assert (r["dj"], r["dj_herkunft"]) == (d, herkunft)


@pytest.mark.parametrize("artist, interp", [("Band A", "Band A"), ("XY Mix", None), ("Diverse", None), (None, None)])
def test_interpret(artist, interp):
    assert interpret(artist)["interpret"] == interp


def test_lade_kuerzel(tmp_path):
    p = tmp_path / "k.csv"
    p.write_text("kuerzel;dj\nXY;DJ Eins\n;leer\n", encoding="utf-8-sig")
    assert lade_kuerzel(p) == {"XY": "DJ Eins"}
    assert lade_kuerzel(tmp_path / "fehlt.csv") == {}


def test_merkmale_rohspalten_unveraendert():
    roh = pd.DataFrame([{"pfad_relativ": "Musik/XY Set/01.mp3", "datei_ordner": "Musik/XY Set",
                         "datei_name": "01.mp3", "tag_title": None, "serato_titel": "BA0:10 BE2:10 01",
                         "tag_genre": None, "serato_genre": "SoftTechno", "tag_popm_wert": "255",
                         "tag_comment": "4sterne", "serato_comment": None, "tag_artist": "XY Mix",
                         "serato_interpret": None}])
    m = merkmale(roh, KUERZEL)
    pd.testing.assert_frame_equal(m[roh.columns], roh)
    r = m.iloc[0]
    assert (r["titel_quelle"], r["be_zeit"], r["ba_zeit"]) == ("serato", "2:10", "0:10")
    assert (r["stimmung"], r["stil"]) == ("soft", "techno")  # SoftTechno ohne Beat
    assert (r["bewertung"], r["popm_sterne"], r["popm_abweichung"]) == (4, 5, True)
    assert (r["dj"], r["dj_herkunft"], r["interpret"]) == ("DJ Eins", "ordner", None)


# --- Jahr (Regel 24.11.2026) ---------------------------------------------------------------
from playlist_agent.bibliothek import jahr  # noqa: E402


@pytest.mark.parametrize("ordner, datei, tag, j, zehn, herkunft", [
    ("Musik/Sendung 2009", "Sendung 2009 02.mp3", None, 2009, None, "ordner"),
    ("Musik/Set 2008 04 05/_Unterordner", "x.mp3", None, 2008, None, "ordner"),          # hoeherer Ordner
    ("Musik/A/Album X (01.02.2011 04-05-06)", "01 Titel.mp3", "1998", 1998, None, "tag"),  # Rip-Zeit
    ("Musik", "Live_Club_12-03-2006_x.mp3", "2004", 2006, None, "datei_datum"),           # Datum > Tag
    ("Musik", "Radio-SAT-04-21-2007_x.mp3", "1998", 2007, None, "datei_datum"),           # MM-TT-JJJJ
    ("Musik/CDx", "radio 20050312.mp3", "2006", 2005, None, "datei_datum"),
    ("Musik/S", "Name 2008 01 Teil.mp3", "1996", 2008, None, "datei_datum"),            # JJJJ MM
    ("Musik/Set 201304 09", "x.mp3", None, 2013, None, "ordner"),                         # JJJJMM
    ("Musik/p", "set_12.03.09_at_x.mp3", None, 2009, None, "datei_datum"),                # TT.MM.JJ
    ("Musik/p", "150309_name_cut.mp3", None, 2009, None, "datei_datum"),                  # TTMMJJ
    ("Musik/p", "Radio_03.04.1989._x.mp3", None, 1989, None, "datei_datum"),
    ("Musik/A", "08 Titel 2000 Name.mp3", "1996", 1996, None, "tag"),                     # Zahl im Titel
    ("Musik/A", "11 Titel 2000.mp3", None, 2000, None, "datei"),                          # ohne Tag: Rueckfall
    ("Musik", "A_20B_20-_20Live_20Tour_202002.mp3", None, 2002, None, "datei"),           # '_20' kodiert
    ("Musik/CDy", "sendung name 199x_1 teil.mp3", None, None, 1990, "jahrzehnt"),
    ("Musik/A", "Titel 1 - Ohne Titel - 05-06-07 - .mp3", None, None, None, "keine"),    # kein Jahr
    ("Musik/A 2001 und 2003", "x.mp3", "1999", 1999, None, "tag"),                        # Ordner mehrdeutig
])
def test_jahr(ordner, datei, tag, j, zehn, herkunft):
    r = jahr(ordner, datei, tag)
    assert (r["jahr"], r["jahrzehnt"], r["jahr_herkunft"]) == (j, zehn, herkunft)
