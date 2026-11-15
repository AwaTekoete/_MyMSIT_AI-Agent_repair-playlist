"""Tests fuer report.py mit synthetischen Laufergebnissen."""

from datetime import datetime

import pandas as pd
import pytest

from playlist_agent.report import erstelle_bericht, md_tabelle, speichere_bericht

KOPF = {"zeit": "2026-01-01 12:00", "laptop": "testlaptop", "laufwerk": "X:"}


@pytest.fixture
def df_playlists():
    return pd.DataFrame([
        # vollstaendig
        {"playlist": "P1", "status": "neu", "eintraege": 3, "geschrieben": 3, "n_vorschlag": 0,
         "n_fehlt": 0, "n_album_beschaedigt": 0, "n_ausgeschlossen": 0, "v1_ok": True, "v3_ok": True},
        # unvollstaendig: 1 Vorschlag, 2 beschaedigt
        {"playlist": "P2", "status": "geaendert", "eintraege": 5, "geschrieben": 2, "n_vorschlag": 1,
         "n_fehlt": 0, "n_album_beschaedigt": 2, "n_ausgeschlossen": 0, "v1_ok": True, "v3_ok": True},
    ])


@pytest.fixture
def df_eintraege():
    return pd.DataFrame([
        {"playlist": "P2", "eintrag": "Musik/A/x.mp3", "klasse": "vorschlag",
         "pfad_ziel": "Musik/B/x.mp3", "grund": "name"},
        {"playlist": "P2", "eintrag": "Musik/Z/1.mp3", "klasse": "album_beschaedigt",
         "null_byte_ordner": "Musik/Z"},
        {"playlist": "P2", "eintrag": "Musik/Z/2.mp3", "klasse": "album_beschaedigt",
         "null_byte_ordner": "Musik/Z"},
    ])


def _integritaet(kritisch: bool):
    zeilen = [{"pfad": "Musik/Z", "typ": "datei_statt_ordner", "schwere": "kritisch",
               "detail": "2 Dateien vorher"}] if kritisch else []
    return pd.DataFrame(zeilen, columns=["pfad", "typ", "schwere", "detail"])


def test_md_tabelle_maskiert_pipe():
    t = md_tabelle(pd.DataFrame({"a": ["x|y"]}))
    assert "x\\|y" in t and t.count("\n") == 3


def test_md_tabelle_leer():
    assert md_tabelle(pd.DataFrame()) == "_keine_\n"


def test_alle_abschnitte_vorhanden(df_playlists, df_eintraege):
    b = erstelle_bericht(KOPF, df_playlists, df_eintraege, _integritaet(False))
    for n in range(1, 9):
        assert f"\n## {n} " in b


def test_zaehler(df_playlists, df_eintraege):
    b = erstelle_bericht(KOPF, df_playlists, df_eintraege)
    assert "| davon vollstaendig (alle Audio-Eintraege geschrieben) | [Playlists] | 1 |" in b
    assert "| sicher (geschrieben) | [Eintraege] | 5 |" in b
    assert "| album_beschaedigt | [Eintraege] | 2 |" in b
    # Abschnitt 6 verdichtet je 0-Byte-Ordner: 2 Pfade, 2 Eintraege, 1 Playlist
    assert "| Musik/Z | 2 | 2 | 1 |" in b


def test_integritaet_warnung_nur_bei_kritisch(df_playlists, df_eintraege):
    mit = erstelle_bericht(KOPF, df_playlists, df_eintraege, _integritaet(True))
    ohne = erstelle_bericht(KOPF, df_playlists, df_eintraege, _integritaet(False))
    assert "WARNUNG" in mit and "datei_statt_ordner" in mit
    assert "WARNUNG" not in ohne and "Keine kritischen Befunde" in ohne


def test_integritaet_nicht_geprueft(df_playlists, df_eintraege):
    assert "_nicht geprueft_" in erstelle_bericht(KOPF, df_playlists, df_eintraege, None)


def test_backup_hinweis_bei_geaendert(df_playlists, df_eintraege):
    assert "_backup/" in erstelle_bericht(KOPF, df_playlists, df_eintraege)


def test_speichern_ueberschreibt_nie(tmp_path):
    z = datetime(2026, 1, 1, 12, 0, 0)
    a = speichere_bericht("eins", tmp_path, z)
    b = speichere_bericht("zwei", tmp_path, z)
    assert a != b and a.read_text(encoding="utf-8") == "eins"
    assert b.name == "lauf_20260101_120000_2.md"


def _mit_entscheidung(df_eintraege, aktion):
    e = df_eintraege.copy()
    ist_v = e["klasse"] == "vorschlag"
    e.loc[ist_v, "aktion"], e.loc[ist_v, "entschieden_auf"] = aktion, "track"
    return e


def test_vorschlaege_je_ordnerpaar_ohne_entscheidung(df_playlists, df_eintraege):
    b = erstelle_bericht(KOPF, df_playlists, df_eintraege)
    assert "### O1: Musik/A -> Musik/B" in b
    assert "| vorschlag – ? (offen) | [Eintraege] | 1 |" in b
    assert b.split("## 4b")[1].split("\n## 5")[0].strip().endswith("_keine_")


def test_verschiebe_vorschlag_bei_b(df_playlists, df_eintraege):
    b = erstelle_bericht(KOPF, df_playlists, _mit_entscheidung(df_eintraege, "b"))
    abschnitt_4b = b.split("## 4b")[1].split("\n## 5")[0]
    assert "| O1 | Musik/B/x.mp3 | Musik/A/x.mp3 |" in abschnitt_4b      # von heute -> nach Playlist-Ort
    assert "| vorschlag – b (zurueckverschieben_vorschlag) | [Eintraege] | 1 |" in b


def test_entscheidung_a_kein_verschiebe_vorschlag(df_playlists, df_eintraege):
    b = erstelle_bericht(KOPF, df_playlists, _mit_entscheidung(df_eintraege, "a"))
    assert b.split("## 4b")[1].split("\n## 5")[0].strip().endswith("_keine_")
    assert "| vorschlag – a (playlist_anpassen) | [Eintraege] | 1 |" in b


def test_vollstaendig_zaehlt_ausgeschlossene_nicht_als_fehlend(df_playlists, df_eintraege):
    p = df_playlists.copy()
    p.loc[0, ["eintraege", "n_ausgeschlossen"]] = [4, 1]          # 3 geschrieben + 1 kein Audio
    b = erstelle_bericht(KOPF, p, df_eintraege)
    assert "| davon vollstaendig (alle Audio-Eintraege geschrieben) | [Playlists] | 1 |" in b