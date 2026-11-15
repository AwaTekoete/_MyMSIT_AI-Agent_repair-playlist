"""Tests fuer playlist_agent.writer (synthetische Daten, tmp_path)."""

from playlist_agent.writer import inhalt_m3u8, schreibe_playlist, sicherer_dateiname

PFADE = ["Musik/A/01.mp3", "Musik/K\u00e4fer/02 \u0e17.mp3"]   # Umlaut + Thai-Zeichen


def test_inhalt_exakt():
    b = inhalt_m3u8(["Musik/A/01.mp3"], "D:")
    assert b == b"\xef\xbb\xbf#\r\nD:\\Musik\\A\\01.mp3\r\n"


def test_inhalt_unicode_verlustfrei():
    text = inhalt_m3u8(PFADE, "E:")[3:].decode("utf-8")
    assert "E:\\Musik\\K\u00e4fer\\02 \u0e17.mp3" in text


def test_sicherer_dateiname():
    assert sicherer_dateiname('Eltern%%Kind: "Live" 2008/09?') == "Eltern - Kind_ _Live_ 2008_09_"


def test_neu_dann_unveraendert(tmp_path):
    assert schreibe_playlist(tmp_path, "Liste", PFADE, "D:").status == "neu"
    e = schreibe_playlist(tmp_path, "Liste", PFADE, "D:")
    assert e.status == "unveraendert" and not (tmp_path / "_backup").exists()


def test_geaendert_mit_backup(tmp_path):
    schreibe_playlist(tmp_path, "Liste", PFADE[:1], "D:")
    e = schreibe_playlist(tmp_path, "Liste", PFADE, "D:")
    assert e.status == "geaendert" and e.backup.exists()
    assert e.backup.read_bytes() == inhalt_m3u8(PFADE[:1], "D:")      # Vorversion gesichert
    assert e.datei.read_bytes() == inhalt_m3u8(PFADE, "D:")


def test_nichts_wird_geloescht(tmp_path):
    alt = tmp_path / "Liste.m3u"
    alt.write_bytes(b"alt")
    schreibe_playlist(tmp_path, "Liste", PFADE, "D:")
    assert alt.exists() and alt.read_bytes() == b"alt"                # .m3u bleibt unberuehrt (P3)


from playlist_agent.writer import eindeutige_dateinamen


def test_eindeutige_dateinamen_punkt_und_gross_klein():
    m = eindeutige_dateinamen(["Live 2011", "Live 2011.", "live 2011", "Andere"])
    assert len(set(v.lower() for v in m.values())) == 4
    assert m["Live 2011"] == "Live 2011" and m["Live 2011."] == "Live 2011 (2)"