"""Tests create_from_folder-Reihenfolge (Entscheidung 15.11.2026, Typen S/A/E)."""

from playlist_agent.ordner import natur_schluessel, ordne, playlist_aus_ordner, set_reihenfolge


def test_natuerliche_sortierung():
    assert sorted(["10 b.mp3", "2 a.mp3", "1 c.mp3"], key=natur_schluessel) == ["1 c.mp3", "2 a.mp3", "10 b.mp3"]


def test_set_endzahl_ein_bis_dreistellig():
    namen = ["Set 2007 10.mp3", "Set 2007 2.mp3", "Set 2007_129.mp3"]
    assert set_reihenfolge(namen) == ["Set 2007 2.mp3", "Set 2007 10.mp3", "Set 2007_129.mp3"]


def test_set_verschiedener_anfang_ist_kein_set():
    assert set_reihenfolge(["A 01.mp3", "B 02.mp3"]) is None


def test_set_doppelte_endzahl_ist_kein_set():
    assert set_reihenfolge(["A 01.mp3", "A 1.mp3"]) is None


def test_typ_s_vorrang_vor_tags():
    # Endzahl im Dateinamen gewinnt gegen widersprechende Tags (Nutzerentscheidung)
    namen = ["Mix 01.mp3", "Mix 02.mp3"]
    reihe, regel = ordne(namen, {"Mix 01.mp3": 2, "Mix 02.mp3": 1})
    assert (reihe, regel) == (["Mix 01.mp3", "Mix 02.mp3"], "endzahl")


def test_typ_a_nach_tracknummer():
    namen = ["Zebra.mp3", "Apfel.mp3"]
    assert ordne(namen, {"Zebra.mp3": 1, "Apfel.mp3": 2}) == (["Zebra.mp3", "Apfel.mp3"], "tracknummer")


def test_typ_e_bei_fehlender_oder_doppelter_tracknummer():
    namen = ["b.mp3", "a.mp3"]
    assert ordne(namen, {"b.mp3": 1, "a.mp3": None})[1] == "dateiname"
    assert ordne(namen, {"b.mp3": 1, "a.mp3": 1}) == (["a.mp3", "b.mp3"], "dateiname")


def test_playlist_aus_ordner_nur_direkte_dateien():
    pfade = ["Musik/X/Set 02.mp3", "Musik/X/Set 01.mp3", "Musik/X/Unter/z.mp3", "Musik/Y/a.mp3"]
    assert playlist_aus_ordner(pfade, "Musik/X/") == (["Musik/X/Set 01.mp3", "Musik/X/Set 02.mp3"], "endzahl")


def test_playlist_aus_leerem_ordner():
    assert playlist_aus_ordner(["Musik/Y/a.mp3"], "Musik/X") == ([], "dateiname")
