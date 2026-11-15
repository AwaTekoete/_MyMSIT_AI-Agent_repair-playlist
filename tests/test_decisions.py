"""Tests fuer decisions.py (P13): Vorrang, Protokoll, Gruppierung."""

from datetime import datetime

import pandas as pd
import pytest

from playlist_agent.decisions import (entscheide, gruppiere_vorschlaege, lade_entscheidungen,
                                      leeres_protokoll, loese_auf, ordnerpaar,
                                      speichere_entscheidungen)


@pytest.fixture
def df_v():
    """Drei Vorschlaege: zwei aus Ordnerpaar A->A_neu, einer aus B->C."""
    return pd.DataFrame({
        "eintrag":   ["Musik/A/1.mp3", "Musik/A/2.mp3", "Musik/B/3.mp3"],
        "pfad_ziel": ["Musik/A_neu/1.mp3", "Musik/A_neu/2.mp3", "Musik/C/3.mp3"],
    })


def _aktionen(df):
    return dict(zip(df["eintrag"], zip(df["aktion"], df["entschieden_auf"])))


def test_ordnerpaar_normiert_trenner():
    assert ordnerpaar("Musik\\A\\1.mp3", "Musik/B/1.mp3") == ("Musik/A", "Musik/B")


def test_gruppierung_ids(df_v):
    g = gruppiere_vorschlaege(df_v)
    assert dict(zip(g["eintrag"], g["paar_id"])) == {
        "Musik/A/1.mp3": "O1", "Musik/A/2.mp3": "O1", "Musik/B/3.mp3": "O2"}


def test_ohne_entscheidung_offen(df_v):
    r = loese_auf(df_v, leeres_protokoll())
    assert set(r["aktion"]) == {"?"} and set(r["entschieden_auf"]) == {"keine"}


def test_ordnerpaar_gilt_fuer_alle_tracks(df_v):
    p = entscheide(leeres_protokoll(), "a", alter_ordner="Musik/A", neuer_ordner="Musik/A_neu")
    r = _aktionen(loese_auf(df_v, p))
    assert r["Musik/A/1.mp3"] == ("a", "ordnerpaar") and r["Musik/A/2.mp3"] == ("a", "ordnerpaar")
    assert r["Musik/B/3.mp3"] == ("?", "keine")


def test_track_hat_vorrang_vor_ordnerpaar(df_v):
    p = entscheide(leeres_protokoll(), "a", alter_ordner="Musik/A", neuer_ordner="Musik/A_neu")
    p = entscheide(p, "b", eintrag="Musik/A/2.mp3", kandidat="Musik/A_neu/2.mp3")
    r = _aktionen(loese_auf(df_v, p))
    assert r["Musik/A/1.mp3"] == ("a", "ordnerpaar")
    assert r["Musik/A/2.mp3"] == ("b", "track")


def test_juengste_entscheidung_gilt(df_v):
    p = entscheide(leeres_protokoll(), "a", eintrag="Musik/B/3.mp3", kandidat="Musik/C/3.mp3")
    p = entscheide(p, "?", eintrag="Musik/B/3.mp3", kandidat="Musik/C/3.mp3")
    assert len(p) == 2                                   # Protokoll behaelt beide
    assert _aktionen(loese_auf(df_v, p))["Musik/B/3.mp3"] == ("?", "track")


def test_anderer_kandidat_entwertet_track_entscheidung(df_v):
    p = entscheide(leeres_protokoll(), "a", eintrag="Musik/B/3.mp3", kandidat="Musik/X/3.mp3")
    assert _aktionen(loese_auf(df_v, p))["Musik/B/3.mp3"] == ("?", "keine")


def test_ungueltige_aktion_und_fehlender_schluessel():
    with pytest.raises(ValueError):
        entscheide(leeres_protokoll(), "z", eintrag="a", kandidat="b")
    with pytest.raises(ValueError):
        entscheide(leeres_protokoll(), "a", eintrag="nur_eintrag")


def test_speichern_laden_roundtrip(tmp_path, df_v):
    pfad = tmp_path / "decisions" / "entscheidungen.csv"
    assert lade_entscheidungen(pfad).empty               # Datei fehlt -> leer
    p = entscheide(leeres_protokoll(), "b", alter_ordner="Musik/B", neuer_ordner="Musik/C",
                   kommentar="Test", zeit=datetime(2026, 1, 1, 12, 0, 0))
    speichere_entscheidungen(p, pfad)
    q = lade_entscheidungen(pfad)
    assert q.loc[0, "zeit"] == "2026-01-01T12:00:00" and q.loc[0, "kommentar"] == "Test"
    assert _aktionen(loese_auf(df_v, q))["Musik/B/3.mp3"] == ("b", "ordnerpaar")
