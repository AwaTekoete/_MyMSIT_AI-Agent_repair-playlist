"""Tests Phase 4 (NB05): neue Resolver-Stufen und Audio-Hash (synthetisch).

Faelle nachgebaut aus den Befunden NB05 Z.11-33 (ohne echte Namen, P11).
"""

import hashlib

import pandas as pd
import pytest

from playlist_agent.index import audio_sha256_datei, ergaenze_audio_hash, scanne
from playlist_agent.resolver import Regeln, Resolver

AUDIO = [".mp3", ".wav", ".aif"]


def index(zeilen):
    """zeilen: (pfad, bytes, sha256, audio_sha256)"""
    df = pd.DataFrame(zeilen, columns=["pfad_relativ", "bytes", "sha256", "audio_sha256"])
    df["endung"] = df["pfad_relativ"].map(
        lambda p: "." + p.rsplit(".", 1)[-1].lower() if "." in p.split("/")[-1] else "(ohne)")
    df["appledouble"] = False
    return df


IDX = index([
    # R1 verlorenes Zeichen / Rand-Leerzeichen
    ("Musik/K/Zaehlerä_3d.wav", 10, None, None),
    ("Musik/K/Name!!!.mp3", 10, None, None),
    # R2 Name + Anhang; Nachbar mit aehnlichem Namen
    ("Musik/P/klang 022 stimme.mp3", 10, None, None),
    ("Musik/P/klang 002.mp3", 10, None, None),
    # R2 mehrdeutig
    ("Musik/P2/teil 1 x.mp3", 10, None, None),
    ("Musik/P2/teil 1 y.mp3", 10, None, None),
    # R3 neues Namensschema NN_Titel_Album
    ("Musik/S/01_Blume_Album.mp3", 10, None, None),
    ("Musik/S/02_Zahl_Album.mp3", 10, None, None),
    # R3 Ordner per Jaccard (eindeutig) und Gleichstand
    ("Musik/Raum Nacht Vol 1 Scheibe 9/03_Titel.mp3", 10, None, None),
    ("Musik/Raum Nacht Vol 1 Scheibe 8/04_Titel.mp3", 10, None, None),
    ("Musik/Raum Nacht Vol 3 Scheibe 8/04_Anders.mp3", 10, None, None),
    # R3 Sammelordner (Nummer = Set-Teil)
    ("Musik/Sammel/01-set_a.mp3", 10, None, None),
    ("Musik/Sammel/01-set_b.mp3", 10, None, None),
    # V3: einzige Datei mit gleicher Nummer ist "Name + Anhang"
    ("Musik/CN/01 Nacht Spricht.mp3", 10, None, None),
    # 0-Byte-"Ordner"
    ("Musik/Verloren", 0, None, None),
    ("Musik/Raum Vol 5 Scheibe 2", 0, None, None),
    # mehrfach: audiogleich (Tags verschieden), Ort per Ordnername
    ("Musik/Set 2007 04 24/t.mp3", 10, "s1", "a1"),
    ("Musik/Kopie/t.mp3", 10, "s2", "a1"),
    ("Musik/Neu/t.mp3", 10, "s3", "a1"),
    # mehrfach: audiogleich, Ort Gleichstand
    ("Musik/U/u.mp3", 10, "s4", "a2"),
    ("Musik/V/u.mp3", 10, "s5", "a2"),
    # mehrfach: Versionen verschieden (eine Kopie gekuerzt)
    ("Musik/W1/v.mp3", 10, "s6", "a3"),
    ("Musik/W2/v.mp3", 9, "s7", "a4"),
    # mehrfach: bitgleich, Ort per Ordnername bzw. Gleichstand
    ("Musik/Abend Set/b.mp3", 10, "h1", None),
    ("Musik/Sicherung/b.mp3", 10, "h1", None),
])
R = Resolver(IDX, AUDIO)


@pytest.mark.parametrize("eintrag, klasse, stufe, ziel", [
    # R1
    ("Musik/K/Zaehler _3d.wav", "sicher", "zeichen", "Musik/K/Zaehlerä_3d.wav"),
    ("Musik/K/ Name!!!.mp3", "sicher", "zeichen", "Musik/K/Name!!!.mp3"),
    ("Musik/K/Zaehlerx_3d.wav", "fehlt", "kein_kandidat", None),          # anderes Zeichen
    # R2
    ("Musik/P/klang 022.mp3", "vorschlag", "praefix", "Musik/P/klang 022 stimme.mp3"),
    ("Musik/P2/teil 1.mp3", "fehlt", "kein_kandidat", None),              # 2 Anhaenge
    # R3
    ("Musik/S/01 blume.mp3", "vorschlag", "tracknummer", "Musik/S/01_Blume_Album.mp3"),
    ("Alt/Raum Nacht Scheibe 9/03 titel.mp3", "vorschlag", "tracknummer",
     "Musik/Raum Nacht Vol 1 Scheibe 9/03_Titel.mp3"),
    ("Alt/Raum Nacht Scheibe 8/04 titel.mp3", "fehlt", "kein_kandidat", None),   # Gleichstand
    ("Musik/Sammel/01-set_c.mp3", "fehlt", "kein_kandidat", None),        # Sammelordner
    ("Musik/S/07 fehlt.mp3", "fehlt", "kein_kandidat", None),             # Nummer fehlt
    # R2 vor R3 (Version "Name + Anhang" wird Vorschlag praefix, nicht tracknummer)
    ("Musik/CN/01 Nacht.mp3", "vorschlag", "praefix", "Musik/CN/01 Nacht Spricht.mp3"),
    # 0-Byte-Ordner mit Praefix-Ergaenzung / lose
    ("Verloren/Unter/x.mp3", "album_beschaedigt", "0-byte-ordner-praefix", None),
    ("Alt/Raum, Vol. 5 Scheibe 2/x.mp3", "album_beschaedigt", "0-byte-ordner-lose", None),
    # mehrfach
    ("Musik/Set_2007_04_24/t.mp3", "sicher", "mehrfach_audiogleich", "Musik/Set 2007 04 24/t.mp3"),
    ("Musik/X/u.mp3", "vorschlag", "mehrfach_audiogleich", None),          # Ort Gleichstand
    ("Musik/W/v.mp3", "vorschlag", "mehrfach", None),                      # Versionen verschieden
    ("Musik/Abend/b.mp3", "sicher", "mehrfach_bitgleich", "Musik/Abend Set/b.mp3"),
])
def test_kaskade_phase4(eintrag, klasse, stufe, ziel):
    e = R.aufloesen(eintrag)
    assert (e.klasse, e.stufe, e.pfad) == (klasse, stufe, ziel)


def test_v3_ohne_r2_kein_tracknummer_treffer():
    # Mit abgeschaltetem R2 darf R3 die Version nicht zuordnen (Veto V3)
    e = Resolver(IDX, AUDIO, regeln=Regeln(praefix_aktiv=False)).aufloesen("Musik/CN/01 Nacht.mp3")
    assert (e.klasse, e.stufe) == ("fehlt", "kein_kandidat")


def test_lose_abschaltbar():
    e = Resolver(IDX, AUDIO, regeln=Regeln(nullbyte_lose=False)).aufloesen(
        "Alt/Raum, Vol. 5 Scheibe 2/x.mp3")
    assert e.klasse == "fehlt"


def test_zeichen_als_vorschlag_konfigurierbar():
    e = Resolver(IDX, AUDIO, regeln=Regeln(zeichen_sicher=False)).aufloesen("Musik/K/ Name!!!.mp3")
    assert (e.klasse, e.stufe) == ("vorschlag", "zeichen")


def test_ohne_audio_spalte_bleibt_mehrfach():
    e = Resolver(IDX.drop(columns="audio_sha256"), AUDIO).aufloesen("Musik/Set_2007_04_24/t.mp3")
    assert (e.klasse, e.stufe) == ("vorschlag", "mehrfach")


# --- Audio-Hash (index.py) ---------------------------------------------------------

AUDIODATEN = b"\xff\xfbAUDIO-DATEN" * 20


def _id3v2(groesse: int = 20, footer: bool = False) -> bytes:
    flags = 0x10 if footer else 0x00
    kopf = b"ID3\x03\x00" + bytes([flags]) + bytes([0, 0, 0, groesse])
    return kopf + b"\x00" * groesse + (b"3DI" + b"\x00" * 7 if footer else b"")


def _id3v1() -> bytes:
    return b"TAG" + b"\x00" * 125


def _apev2(mit_kopf: bool = True) -> bytes:
    items = b"x" * 8
    groesse = (len(items) + 32).to_bytes(4, "little")
    flags = (0x80000000 if mit_kopf else 0).to_bytes(4, "little")
    block = b"APETAGEX" + b"\xd0\x07\x00\x00" + groesse + b"\x01\x00\x00\x00"
    kopf_fuss = block + flags + b"\x00" * 8               # Kopf und Fuss gleich aufgebaut
    return (kopf_fuss if mit_kopf else b"") + items + kopf_fuss


@pytest.mark.parametrize("vorne, hinten", [
    (b"", b""),
    (_id3v2(), b""),
    (_id3v2(footer=True), b""),
    (b"", _id3v1()),
    (_id3v2(), _id3v1()),
    (b"", _apev2()),
    (b"", _apev2(mit_kopf=False)),
    (_id3v2(30), _apev2() + _id3v1()),
])
def test_audio_hash_ignoriert_tags(tmp_path, vorne, hinten):
    f = tmp_path / "t.mp3"
    f.write_bytes(vorne + AUDIODATEN + hinten)
    assert audio_sha256_datei(f) == hashlib.sha256(AUDIODATEN).hexdigest()


def test_audio_hash_erkennt_andere_musik(tmp_path):
    a, b = tmp_path / "a.mp3", tmp_path / "b.mp3"
    a.write_bytes(_id3v2() + AUDIODATEN)
    b.write_bytes(_id3v2() + AUDIODATEN[:-5])                  # gekuerzt
    assert audio_sha256_datei(a) != audio_sha256_datei(b)


def test_ergaenze_audio_hash_nur_namensdubletten(tmp_path):
    m = tmp_path / "Musik"
    for o in ("A", "B"):
        (m / o).mkdir(parents=True)
    (m / "A" / "t.mp3").write_bytes(_id3v2() + AUDIODATEN)
    (m / "B" / "T.mp3").write_bytes(_id3v2(40) + AUDIODATEN)    # anderer Tag, gleiche Musik
    (m / "A" / "einzeln.mp3").write_bytes(AUDIODATEN)
    df = ergaenze_audio_hash(scanne(tmp_path), tmp_path).set_index("pfad_relativ")
    assert df.at["Musik/A/t.mp3", "audio_sha256"] == df.at["Musik/B/T.mp3", "audio_sha256"]
    assert df.at["Musik/A/einzeln.mp3", "audio_sha256"] is None
    alle = ergaenze_audio_hash(scanne(tmp_path), tmp_path, nur_namensdubletten=False)
    assert alle["audio_sha256"].notna().all()
