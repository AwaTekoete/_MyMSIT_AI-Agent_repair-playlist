"""Tests fuer playlist_agent.parsers.serato (synthetische TLV-Dateien)."""

from playlist_agent.parsers.serato import feldwert, lese_crate, lese_database_v2


def blk(tag: str, inhalt: bytes) -> bytes:
    return tag.encode("latin-1") + len(inhalt).to_bytes(4, "big") + inhalt


def txt(s: str) -> bytes:
    return s.encode("utf-16-be")


VRSN = blk("vrsn", txt("1.0/Serato ScratchLive Crate"))


def test_crate_zwei_tracks(tmp_path):
    f = tmp_path / "a.crate"
    f.write_bytes(VRSN + blk("otrk", blk("ptrk", txt("Musik/A/01.mp3")))
                  + blk("otrk", blk("ptrk", txt("Musik/A/02.mp3"))))
    c = lese_crate(f)
    assert c.version == "1.0/Serato ScratchLive Crate"
    assert c.pfade == ["Musik/A/01.mp3", "Musik/A/02.mp3"]
    assert c.vollstaendig


def test_crate_abgeschnitten_ist_unvollstaendig(tmp_path):
    f = tmp_path / "b.crate"
    f.write_bytes((VRSN + blk("otrk", blk("ptrk", txt("Musik/A/01.mp3"))))[:-3])
    assert not lese_crate(f).vollstaendig


def test_crate_track_ohne_pfad_wird_ignoriert(tmp_path):
    f = tmp_path / "c.crate"
    f.write_bytes(VRSN + blk("otrk", blk("tvcn", txt("x"))))
    assert lese_crate(f).pfade == []


def test_database_felder(tmp_path):
    f = tmp_path / "database V2"
    track = (blk("pfil", txt("Musik/A/01.mp3")) + blk("tsng", txt("Titel"))
             + blk("uadd", (1234).to_bytes(4, "big")) + blk("bbgl", b"\x01"))
    f.write_bytes(blk("vrsn", txt("2.0/Serato Scratch LIVE Database")) + blk("otrk", track))
    tracks, ok = lese_database_v2(f)
    assert ok
    assert tracks == [{"pfil": "Musik/A/01.mp3", "tsng": "Titel", "uadd": 1234, "bbgl": 1}]


def test_feldwert_unbekannt_nur_laenge():
    assert feldwert("xabc", b"\x00\x01\x02") == "<3 Byte>"