"""Tests fuer playlist_agent.resolver (synthetischer Index, ohne Dateien)."""

import pandas as pd
import pytest

from playlist_agent.resolver import Regeln, Resolver

AUDIO = [".mp3", ".wav", ".aif"]
KAEFER = "K\u00e4fer.mp3"


def index(zeilen):
    df = pd.DataFrame(zeilen, columns=["pfad_relativ", "bytes", "sha256"])
    df["endung"] = df["pfad_relativ"].map(lambda p: "." + p.rsplit(".", 1)[-1] if "." in p.split("/")[-1] else "(ohne)")
    df["appledouble"] = False
    return df


IDX = index([
    ("Musik/A/01 Lied.mp3", 100, None),
    ("Musik/B/x.mp3", 50, "h1"), ("Musik/C/x.mp3", 50, "h1"),          # bitgleich
    ("Musik/D/y.mp3", 60, "h2"), ("Musik/E/y.mp3", 61, None),          # verschieden
    ("Musik/F/z.mp3", 70, None), ("Musik/G/z.mp3", 71, None),          # mehrfach, ein Pfadende
    ("Musik/H/" + KAEFER, 80, None),
    ("Musik/Kaputt", 0, None),                                         # 0-Byte "Ordner"
])
R = Resolver(IDX, AUDIO, leere_ordner=["Musik/Leer"])


@pytest.mark.parametrize("eintrag, klasse, stufe", [
    ("Musik/A/01 Lied.mp3", "sicher", "pfad"),
    ("Musik/A/01 Lied.mp3".replace("a", "a"), "sicher", "pfad"),
    ("Music/A/01 Lied.mp3", "sicher", "pfadende"),                     # fremdes Praefix
    ("Musik/Z/01 Lied.mp3", "vorschlag", "name"),                      # nur Name
    ("Musik/X/x.mp3", "sicher", "mehrfach_bitgleich"),
    ("Musik/X/y.mp3", "vorschlag", "mehrfach"),
    ("Musik/G/z.mp3".replace("Musik", "Alt"), "sicher", "pfadende"),   # einer von zwei passt
    ("Musik/H/" + KAEFER.encode("utf-8").decode("cp1252"), "sicher", "mojibake"),
    ("Musik/Kaputt/03.mp3", "album_beschaedigt", "0-byte-ordner"),
    ("Musik/Leer/03.mp3", "fehlt", "ordner_leer"),
    ("Musik/A/02 Lied.mp3", "fehlt", "kein_kandidat"),                 # harter Negativfall (T7)
])
def test_kaskade(eintrag, klasse, stufe):
    e = R.aufloesen(eintrag)
    assert (e.klasse, e.stufe) == (klasse, stufe)


def test_nfd_eingabe_trifft_pfad():
    e = R.aufloesen("Musik/H/Ka\u0308fer.mp3")
    assert (e.klasse, e.stufe, e.pfad) == ("sicher", "pfad", "Musik/H/" + KAEFER)


def test_regel_name_sicher():
    e = Resolver(IDX, AUDIO, regeln=Regeln(name_sicher=True)).aufloesen("Musik/Z/01 Lied.mp3")
    assert e.klasse == "sicher"


def test_bitgleich_waehlt_deterministisch():
    assert R.aufloesen("Musik/X/x.mp3").pfad == "Musik/B/x.mp3"




# --- Regeln aus config.yaml ---------------------------------------------------------
from pathlib import Path

import pytest
import yaml

from playlist_agent.resolver import Regeln, regeln_aus_config


def test_regeln_ohne_abschnitt_standard():
    assert regeln_aus_config({}) == Regeln()


def test_regeln_einzelwert_ueberschreibt():
    r = regeln_aus_config({"resolver": {"name_sicher": True}})
    assert r.name_sicher is True and r.pfadende_sicher is True


def test_regeln_tippfehler_bricht_ab():
    with pytest.raises(ValueError, match="name_sicherr"):
        regeln_aus_config({"resolver": {"name_sicherr": True}})


def test_projekt_config_entspricht_entscheidungen():
    # Schutz gegen unbeabsichtigte Änderung: config.yaml = Entscheidungen 12./14.11.2026
    cfg = yaml.safe_load((Path(__file__).parents[1] / "config/config.yaml").read_text(encoding="utf-8"))
    assert regeln_aus_config(cfg) == Regeln(pfadende_sicher=True, min_endteile=2,
                                            name_sicher=False, bitgleich_sicher=True)