"""Tests fuer playlist_agent.belege (synthetisch)."""

import math

import pandas as pd
import pytest

from playlist_agent.belege import hinweis, serato_meta, tlen_s, tsiz_mib


@pytest.mark.parametrize("s, erwartet", [("8.0MB", 8.0), ("648.9MB", 648.9), ("", None),
                                         (None, None), ("x MB", None)])
def test_tsiz(s, erwartet):
    w = tsiz_mib(s)
    assert (math.isnan(w) if erwartet is None else w == erwartet)


@pytest.mark.parametrize("s, erwartet", [("07:56.16", 476.16), ("100:00.00", 6000.0),
                                         ("", None), (None, None)])
def test_tlen(s, erwartet):
    w = tlen_s(s)
    assert (math.isnan(w) if erwartet is None else abs(w - erwartet) < 1e-9)


def test_serato_meta_schluessel_normalisiert():
    df = pd.DataFrame({"schluessel": ["Musik\\A\\Käfer.mp3"], "tlen": ["01:00.00"],
                       "tsiz": ["1.0MB"]})
    assert serato_meta(df) == {"Musik/A/Käfer.mp3": (60.0, 1.0)}


def test_hinweis_passt():
    assert hinweis(60.0, 1.0, 60.05, 2**20) == \
        "Serato: Dauer +0.05 s (passt), Groesse 1.0 -> 1.0 MiB (passt)"


def test_hinweis_geschnitten():
    h = hinweis(60.0, 1.0, 59.4, 0.9 * 2**20)
    assert "Dauer -0.60 s (abweichend)" in h and "(abweichend)" in h.split("Groesse")[1]


def test_hinweis_ohne_daten():
    assert hinweis(math.nan, math.nan, 60.0, 100) == "keine Serato-Daten"
    assert hinweis(60.0, math.nan, 60.0, None) == "Serato: Dauer +0.00 s (passt)"
