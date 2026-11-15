"""Tests privacy_check.lese_gold_csv: beide Trenner, BOM, leere Werte (Befund 15.11.2026)."""

import pandas as pd

from playlist_agent.privacy_check import lese_gold_csv


def test_semikolon_mit_bom_und_komma_im_wert(tmp_path):
    f = tmp_path / "a.csv"
    pd.DataFrame({"nr": [1], "original": ["Musik/Alb, x/Song.mp3"], "label": [""]}).to_csv(
        f, sep=";", index=False, encoding="utf-8-sig")
    assert lese_gold_csv(f) == ["1", "Musik/Alb, x/Song.mp3"]


def test_komma_ohne_bom_und_fehlender_wert(tmp_path):
    f = tmp_path / "b.csv"
    pd.DataFrame({"pfad": ["Musik/B/c.mp3"], "x": [None]}).to_csv(f, index=False, encoding="utf-8")
    assert lese_gold_csv(f) == ["Musik/B/c.mp3"]