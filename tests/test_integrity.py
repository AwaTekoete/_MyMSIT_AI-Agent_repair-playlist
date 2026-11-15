"""Tests fuer integrity.py: synthetische Schaeden auf einem Mini-Stick (tmp_path).

Messkriterium P12: jeder Schadenstyp erkannt, 0 Befunde bei unveraendertem Inhalt.
"""

import os
import shutil

import pytest

from playlist_agent.index import scanne
from playlist_agent.integrity import (erstelle_manifest, ordner_aus_pfaden,
                                      vergleiche_manifeste, warnung_noetig, zusammenfassung)


@pytest.fixture
def stick(tmp_path):
    """Mini-Stick: zwei Alben mit je zwei Dateien, eine Datei direkt in Musik/."""
    for rel, inhalt in {"Musik/AlbumA/01.mp3": b"aaaa", "Musik/AlbumA/02.mp3": b"bbbb",
                        "Musik/AlbumB/CD1/01.mp3": b"cccc", "Musik/AlbumB/CD1/02.mp3": b"dddd",
                        "Musik/einzel.mp3": b"eeee"}.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(inhalt)
    return tmp_path


def _lauf(stick, df_alt=None):
    df, n = erstelle_manifest(scanne(stick), stick, df_alt)
    return df, n


def _typen(df_bef):
    return dict(zip(df_bef["pfad"], df_bef["typ"]))


def test_ordner_aus_pfaden():
    assert ordner_aus_pfaden(["Musik/A/B/x.mp3", "Musik/y.mp3"]) == {"Musik", "Musik/A", "Musik/A/B"}


def test_unveraendert_keine_befunde(stick):
    alt, n1 = _lauf(stick)
    neu, n2 = _lauf(stick, alt)
    assert n1 == 5 and n2 == 0                       # zweiter Lauf hasht nichts neu
    assert vergleiche_manifeste(alt, neu).empty


def test_nur_mtime_geaendert_kein_fehlalarm(stick):
    # Sommerzeit-/Zeitzonen-Verschiebung: mtime +3600 s, Inhalt gleich
    alt, _ = _lauf(stick)
    p = stick / "Musik/AlbumA/01.mp3"
    st = p.stat()
    os.utime(p, (st.st_atime, st.st_mtime + 3600))
    neu, n = _lauf(stick, alt)
    assert n == 1                                    # neu gehasht, da mtime anders
    assert vergleiche_manifeste(alt, neu).empty      # Hash gleich -> kein Befund


def test_datei_statt_ordner(stick):
    # Muster 06.02.2020: Album-Ordner durch 0-Byte-Datei gleichen Namens ersetzt
    alt, _ = _lauf(stick)
    shutil.rmtree(stick / "Musik/AlbumA")
    (stick / "Musik/AlbumA").write_bytes(b"")
    bef = vergleiche_manifeste(alt, _lauf(stick, alt)[0])
    assert _typen(bef) == {"Musik/AlbumA": "datei_statt_ordner"}
    assert "2 Dateien" in bef.loc[0, "detail"]
    assert warnung_noetig(bef)


def test_ordner_verschwunden_nur_oberster(stick):
    alt, _ = _lauf(stick)
    shutil.rmtree(stick / "Musik/AlbumB")            # AlbumB und AlbumB/CD1 verschwinden
    bef = vergleiche_manifeste(alt, _lauf(stick, alt)[0])
    assert _typen(bef) == {"Musik/AlbumB": "ordner_verschwunden"}


def test_datei_verschwunden(stick):
    alt, _ = _lauf(stick)
    (stick / "Musik/einzel.mp3").unlink()
    bef = vergleiche_manifeste(alt, _lauf(stick, alt)[0])
    assert _typen(bef) == {"Musik/einzel.mp3": "datei_verschwunden"}


def test_null_byte_neu(stick):
    alt, _ = _lauf(stick)
    (stick / "Musik/AlbumA/02.mp3").write_bytes(b"")
    bef = vergleiche_manifeste(alt, _lauf(stick, alt)[0])
    assert _typen(bef) == {"Musik/AlbumA/02.mp3": "null_byte_neu"}


def test_inhalt_geaendert_gleiche_groesse(stick):
    alt, _ = _lauf(stick)
    p = stick / "Musik/AlbumB/CD1/01.mp3"
    st = p.stat()
    p.write_bytes(b"XXXX")                           # gleiche Groesse, anderer Inhalt
    os.utime(p, (st.st_atime, st.st_mtime + 10))
    bef = vergleiche_manifeste(alt, _lauf(stick, alt)[0])
    assert _typen(bef) == {"Musik/AlbumB/CD1/01.mp3": "inhalt_geaendert"}
    assert bef.loc[0, "schwere"] == "warnung"
    assert not warnung_noetig(bef)


def test_datei_neu_nur_info(stick):
    alt, _ = _lauf(stick)
    (stick / "Musik/AlbumC").mkdir()
    (stick / "Musik/AlbumC/01.mp3").write_bytes(b"ffff")
    bef = vergleiche_manifeste(alt, _lauf(stick, alt)[0])
    assert _typen(bef) == {"Musik/AlbumC/01.mp3": "datei_neu"}
    assert not warnung_noetig(bef)


def test_zusammenfassung_alle_typen(stick):
    alt, _ = _lauf(stick)
    shutil.rmtree(stick / "Musik/AlbumA")
    (stick / "Musik/AlbumA").write_bytes(b"")
    (stick / "Musik/einzel.mp3").unlink()
    z = zusammenfassung(vergleiche_manifeste(alt, _lauf(stick, alt)[0]))
    assert len(z) == 6                               # alle Typen, auch mit 0
    assert z.set_index("typ")["anzahl [Befunde]"].to_dict() == {
        "datei_statt_ordner": 1, "ordner_verschwunden": 0, "datei_verschwunden": 1,
        "null_byte_neu": 0, "inhalt_geaendert": 0, "datei_neu": 0}
