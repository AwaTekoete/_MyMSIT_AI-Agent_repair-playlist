"""Tests fuer playlist_agent.parsers.playlist (synthetische Dateien)."""

from playlist_agent.parsers.playlist import dekodieren, lese_playlist


def test_m3u8_mit_bom_und_kopf(tmp_path):
    f = tmp_path / "a.m3u8"
    f.write_bytes(b"\xef\xbb\xbf#\r\nD:\\Musik\\K\xc3\xa4fer\\01.mp3\r\n")
    p = lese_playlist(f)
    assert p.kodierung == "UTF-8 mit BOM"
    assert p.zeilenende == "CRLF"
    assert p.eintraege == ["D:\\Musik\\K\u00e4fer\\01.mp3"]


def test_m3u_cp1252_umlaut(tmp_path):
    f = tmp_path / "b.m3u"
    f.write_bytes("D:\\Musik\\K\u00e4fer\\01.mp3\r\n".encode("cp1252"))
    p = lese_playlist(f)
    assert p.kodierung == "cp1252"
    assert p.eintraege == ["D:\\Musik\\K\u00e4fer\\01.mp3"]


def test_m3u_kommentare_und_leerzeilen(tmp_path):
    f = tmp_path / "c.m3u"
    f.write_text("#EXTM3U\n#EXTINF:123,Titel\nMusik/A/01.mp3\n\n  \nMusik/A/02.mp3\n",
                 encoding="utf-8", newline="\n")        # Windows wuerde sonst \n -> \r\n umwandeln
    p = lese_playlist(f)
    assert p.kopf_extm3u and p.n_extinf == 1 and p.zeilenende == "LF"
    assert p.eintraege == ["Musik/A/01.mp3", "Musik/A/02.mp3"]


def test_wpl_zeichenreferenzen_zurueck(tmp_path):
    f = tmp_path / "d.wpl"
    f.write_text('<smil><body><seq>'
                 '<media src="..\\A &amp; B\\01.mp3"/>'
                 '<media src="..\\Rock&apos;n Roll\\02.mp3" tid="{x}"/>'
                 '</seq></body></smil>', encoding="utf-8", newline="\n")
    assert lese_playlist(f).eintraege == ["..\\A & B\\01.mp3", "..\\Rock'n Roll\\02.mp3"]


def test_leere_datei(tmp_path):
    f = tmp_path / "e.wpl"
    f.write_bytes(b"")
    p = lese_playlist(f)
    assert p.eintraege == [] and p.zeilenende == "keins"


def test_dekodieren_ascii():
    assert dekodieren(b"abc") == ("abc", "ASCII")