"""Tests fuer playlist_agent.index (synthetischer Mini-Stick in tmp_path)."""

import unicodedata
import wave

from playlist_agent.index import ergaenze_hash, leere_ordner, lese_tags, scanne

AUDIO = [".mp3", ".wav", ".aif"]


def stick(tmp_path):
    m = tmp_path / "Musik"
    (m / "A").mkdir(parents=True)
    (m / "A" / "01.mp3").write_bytes(b"abc")
    (m / "A" / "02.mp3").write_bytes(b"abc")            # gleiche Groesse + gleicher Inhalt
    (m / "A" / "03.mp3").write_bytes(b"abcdef")         # andere Groesse
    (m / "A" / "._01.mp3").write_bytes(b"x" * 10)       # AppleDouble
    (m / "B").mkdir()                                   # leerer Ordner
    (m / "C").write_bytes(b"")                          # 0-Byte-Datei an Stelle eines Ordners
    return tmp_path


def test_scanne_zaehlt_und_markiert(tmp_path):
    df = scanne(stick(tmp_path))
    assert len(df) == 5
    assert df.loc[df["pfad_relativ"] == "Musik/A/._01.mp3", "appledouble"].item()
    c = df[df["pfad_relativ"] == "Musik/C"].iloc[0]
    assert c["bytes"] == 0 and c["endung"] == "(ohne)"


def test_leere_ordner(tmp_path):
    assert leere_ordner(stick(tmp_path)) == ["Musik/B"]


def test_scanne_nfc(tmp_path):
    (tmp_path / "Musik").mkdir()
    (tmp_path / "Musik" / "Ka\u0308fer.mp3").write_bytes(b"x")
    p = scanne(tmp_path)["pfad_relativ"].item()
    assert unicodedata.is_normalized("NFC", p)


def test_lese_tags_wav_dauer(tmp_path):
    f = tmp_path / "s.wav"
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000)
        w.writeframes(b"\x00\x00" * 8000)                # 1 Sekunde
    t = lese_tags(f)
    assert t["tag_fehler"] is None and abs(t["duration"] - 1.0) < 0.01


def test_lese_tags_fehler_wird_erfasst(tmp_path):
    f = tmp_path / "kaputt.mp3"
    f.write_bytes(b"keine Audiodaten")
    t = lese_tags(f)
    assert t["duration"] is None or t["tag_fehler"] is not None


def test_hash_nur_gleiche_groesse(tmp_path):
    w = stick(tmp_path)
    df = ergaenze_hash(scanne(w), w, AUDIO).set_index("pfad_relativ")
    assert df.at["Musik/A/01.mp3", "sha256"] == df.at["Musik/A/02.mp3", "sha256"]
    assert df.at["Musik/A/03.mp3", "sha256"] is None
    assert df.at["Musik/A/._01.mp3", "sha256"] is None