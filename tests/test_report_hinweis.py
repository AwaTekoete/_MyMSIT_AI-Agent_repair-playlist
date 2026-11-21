"""Ergaenzung test_report.py: optionale Spalten stufe/hinweis in Abschnitt 4 (4.9b)."""

import pandas as pd

from playlist_agent.report import erstelle_bericht

KOPF = {"zeit": "2026-01-01 12:00"}
P = pd.DataFrame([{"playlist": "P2", "status": "neu", "eintraege": 1, "geschrieben": 0,
                   "n_vorschlag": 1, "n_fehlt": 0, "n_album_beschaedigt": 0,
                   "n_ausgeschlossen": 0, "v1_ok": True, "v3_ok": True}])
E = pd.DataFrame([{"playlist": "P2", "eintrag": "Musik/A/x.mp3", "klasse": "vorschlag",
                   "pfad_ziel": "Musik/A/x neu.mp3", "stufe": "praefix",
                   "hinweis": "Serato: Dauer -0.60 s (abweichend)"}])


def test_hinweis_und_stufe_in_abschnitt_4():
    a4 = erstelle_bericht(KOPF, P, E).split("## 4 ")[1].split("## 4b")[0]
    assert "| stufe |" in a4 and "hinweis |" in a4
    assert "praefix" in a4 and "Dauer -0.60 s (abweichend)" in a4


def test_ohne_hinweis_spalte_unveraendert():
    a4 = erstelle_bericht(KOPF, P, E.drop(columns=["stufe", "hinweis"])).split("## 4 ")[1].split("## 4b")[0]
    assert "hinweis" not in a4 and "stufe" not in a4
