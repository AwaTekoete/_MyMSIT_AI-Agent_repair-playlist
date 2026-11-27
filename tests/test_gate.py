"""Tests fuer playlist_agent.agent.gate, Teil 1 (synthetisch)."""

import json

import pytest

from playlist_agent.agent import gate


def plan(pfade=("M/a.mp3", "M/b.mp3"), pid="P-0123456789"):
    return {"plan_id": pid, "art": "test", "pfade": list(pfade), "inhalt_hash": gate.inhalt_hash(list(pfade)),
            "stuecke": len(pfade), "kriterien": {}}


def test_speichern_laden(tmp_path):
    gate.speichere_plan(plan(), tmp_path)
    assert gate.lade_plan(tmp_path, "P-0123456789")["pfade"] == ["M/a.mp3", "M/b.mp3"]
    gate.speichere_plan(plan(), tmp_path)                         # idempotent


def test_gleiche_id_anderer_inhalt(tmp_path):
    gate.speichere_plan(plan(), tmp_path)
    with pytest.raises(gate.PlanGeaendert):
        gate.speichere_plan(plan(pfade=("M/c.mp3",)), tmp_path)


def test_manipulierte_datei_wird_erkannt(tmp_path):
    p = gate.speichere_plan(plan(), tmp_path)
    d = json.loads(p.read_text(encoding="utf-8"))
    d["pfade"].append("M/fremd.mp3")
    p.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(gate.PlanBeschaedigt):
        gate.lade_plan(tmp_path, "P-0123456789")


def test_falscher_hash_wird_nicht_gespeichert(tmp_path):
    with pytest.raises(gate.PlanBeschaedigt):
        gate.speichere_plan({**plan(), "inhalt_hash": "0" * 64}, tmp_path)


@pytest.mark.parametrize("pid", ["../x", "P-123", "P-0123456789/../y", None])
def test_ungueltige_plan_id(tmp_path, pid):
    with pytest.raises(ValueError):
        gate.lade_plan(tmp_path, pid)


def test_fehlender_plan(tmp_path):
    with pytest.raises(FileNotFoundError):
        gate.lade_plan(tmp_path, "P-aaaaaaaaaa")


# --- Teil 2: Ausfuehrung -------------------------------------------------------------------
import pandas as pd  # noqa: E402


@pytest.fixture
def umgebung(tmp_path):
    plaene = tmp_path / "plaene"
    gate.speichere_plan(plan(), plaene)
    ziel = tmp_path / "Stick" / "Playlist_Test_foobar2000"
    return plaene, ziel, gate.inhalt_hash(["M/a.mp3", "M/b.mp3"])


def test_ausfuehren_schreibt_und_protokolliert(umgebung):
    plaene, ziel, h = umgebung
    r = gate.fuehre_aus(plaene, "P-0123456789", h, "Meine Liste", ziel, "D:", "asus")
    assert r["status"] == "neu" and r["eintraege"] == 2 and r["integritaet"] == "nicht geprueft"
    inhalt = (ziel / "Meine Liste.m3u8").read_bytes().decode("utf-8-sig")
    assert "D:\\M\\a.mp3" in inhalt
    assert len(list((plaene / "ausgefuehrt").glob("*.json"))) == 1
    r2 = gate.fuehre_aus(plaene, "P-0123456789", h, "Meine Liste", ziel, "D:", "asus")   # idempotent
    assert r2["status"] == "unveraendert" and len(list((plaene / "ausgefuehrt").glob("*.json"))) == 2


def test_falsche_bestaetigung(umgebung):
    plaene, ziel, _ = umgebung
    with pytest.raises(gate.AusfuehrungAbgelehnt):
        gate.fuehre_aus(plaene, "P-0123456789", "0" * 64, "L", ziel, "D:", "asus")
    assert not ziel.exists()


def test_nur_in_zielordner(umgebung, tmp_path):
    plaene, _, h = umgebung
    with pytest.raises(gate.AusfuehrungAbgelehnt):
        gate.fuehre_aus(plaene, "P-0123456789", h, "L", tmp_path / "Musik", "D:", "asus")
    assert not (tmp_path / "Musik").exists()


def test_integritaet_kritisch(umgebung):
    plaene, ziel, h = umgebung
    befund = pd.DataFrame({"schwere": ["kritisch"], "typ": ["datei_verschwunden"], "pfad": ["x"], "detail": [""]})
    with pytest.raises(gate.AusfuehrungAbgelehnt):
        gate.fuehre_aus(plaene, "P-0123456789", h, "L", ziel, "D:", "asus", integritaet=befund)
    r = gate.fuehre_aus(plaene, "P-0123456789", h, "L", ziel, "D:", "asus", integritaet=befund, trotz_warnung=True)
    assert r["integritaet"] == "kritisch" and r["trotz_warnung"]


def test_ueberschreiben_nur_mit_bestaetigung(umgebung):
    plaene, ziel, h = umgebung
    ziel.mkdir(parents=True)
    (ziel / "L.m3u8").write_bytes(b"alt")
    with pytest.raises(gate.AusfuehrungAbgelehnt):
        gate.fuehre_aus(plaene, "P-0123456789", h, "L", ziel, "D:", "asus")
    assert (ziel / "L.m3u8").read_bytes() == b"alt"
    r = gate.fuehre_aus(plaene, "P-0123456789", h, "L", ziel, "D:", "asus", ueberschreiben=True)
    assert r["status"] == "geaendert" and r["backup"] and (ziel / "_backup").exists()


def test_leerer_plan_wird_abgelehnt(tmp_path):
    gate.speichere_plan(plan(pfade=(), pid="P-bbbbbbbbbb"), tmp_path)
    with pytest.raises(gate.AusfuehrungAbgelehnt):
        gate.fuehre_aus(tmp_path, "P-bbbbbbbbbb", gate.inhalt_hash([]), "L",
                        tmp_path / "Playlist_X_foobar2000", "D:", "asus")


def test_gate_ist_kein_llm_werkzeug():
    from playlist_agent.agent import tools
    namen = {w["name"] for w in tools.WERKZEUGE} | set(tools.AUSFUEHRBAR)
    assert not any("fuehre" in n or "ausf" in n or "schreib" in n for n in namen)
