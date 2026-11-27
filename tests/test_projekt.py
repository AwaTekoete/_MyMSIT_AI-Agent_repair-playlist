"""Tests fuer playlist_agent.projekt (synthetisch, ohne Stick)."""

from pathlib import Path

import pandas as pd
import pytest

from playlist_agent import projekt


def _projekt(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text("a: 1\n", encoding="utf-8")
    (tmp_path / "notebooks").mkdir()
    return tmp_path


def test_wurzel_aus_unterordner(tmp_path):
    w = _projekt(tmp_path)
    assert projekt.projekt_wurzel(w / "notebooks") == w


def test_wurzel_fehlt(tmp_path):
    with pytest.raises(FileNotFoundError):
        projekt.projekt_wurzel(tmp_path)


def test_kontext_pfade(tmp_path):
    k = projekt.kontext(_projekt(tmp_path) / "notebooks")
    assert k.cfg == {"a": 1}
    assert k.tab == tmp_path / "reports" / "tables"
    assert k.gold == tmp_path / "data" / "gold"


def test_tabelle_schema(tmp_path):
    with pytest.raises(ValueError):
        projekt.tabelle_speichern(pd.DataFrame({"x": [1]}), "falscher_name", tmp_path)


def test_tabelle_neu_und_gleich(tmp_path):
    df = pd.DataFrame({"x": [1, 2]})
    p1 = projekt.tabelle_speichern(df, "05_01_test", tmp_path)
    inhalt = p1.read_bytes()
    p2 = projekt.tabelle_speichern(df, "05_01_test", tmp_path)   # gleicher Inhalt: kein Fehler
    assert p1 == p2 and p2.read_bytes() == inhalt


def test_tabelle_geaendert_bricht_ab(tmp_path):
    projekt.tabelle_speichern(pd.DataFrame({"x": [1]}), "05_01_test", tmp_path)
    with pytest.raises(projekt.ArtefaktGeaendert):
        projekt.tabelle_speichern(pd.DataFrame({"x": [2]}), "05_01_test", tmp_path)


def test_tabelle_ueberschreiben_ausdruecklich(tmp_path):
    projekt.tabelle_speichern(pd.DataFrame({"x": [1]}), "05_01_test", tmp_path)
    p = projekt.tabelle_speichern(pd.DataFrame({"x": [2]}), "05_01_test", tmp_path,
                                  ueberschreiben=True)
    assert pd.read_csv(p)["x"].tolist() == [2]


def test_stick_ueber_signatur(tmp_path, monkeypatch):
    musik = tmp_path / "stick"
    for o in ("Musik", "_ScratchLIVE_"):
        (musik / o).mkdir(parents=True)
    cfg = {"stick": {"signatur": ["Musik", "_ScratchLIVE_"]},
           "laptops": [{"hostname": "testhost"}]}
    monkeypatch.setattr(projekt.anchor.socket, "gethostname", lambda: "testhost")
    monkeypatch.setattr(projekt.anchor, "laufwerks_wurzeln", lambda: [musik])
    assert projekt.stick(cfg) == musik


def test_tabelle_meldet_pfad(tmp_path, capsys):
    o = tmp_path / "reports" / "tables"
    o.mkdir(parents=True)
    projekt.tabelle_speichern(pd.DataFrame({"x": [1, 2]}), "05_01_test", o)
    assert "gespeichert: reports/tables/05_01_test.csv (2 Zeilen)" in capsys.readouterr().out
    projekt.tabelle_speichern(pd.DataFrame({"x": [1, 2]}), "05_01_test", o)
    assert "vorhanden (unveraendert): reports/tables/05_01_test.csv" in capsys.readouterr().out


def test_tabelle_crlf_im_feldwert(tmp_path):
    # Befund 22.11.2026: Feldwerte mit CRLF (mehrzeilige Comments) galten faelschlich als geaendert
    df = pd.DataFrame({"x": ["a\r\nb", "c"]})
    projekt.tabelle_speichern(df, "06_04_test", tmp_path)
    projekt.tabelle_speichern(df, "06_04_test", tmp_path)          # darf nicht abbrechen