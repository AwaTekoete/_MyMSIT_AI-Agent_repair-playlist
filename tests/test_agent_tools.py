"""Tests fuer playlist_agent.agent.tools (synthetisch, P11)."""

import json

import pandas as pd
import pytest

from playlist_agent.agent import tools as t


@pytest.fixture
def db():
    ce = pd.DataFrame({"crate": ["Set A", "Set A", "Set B", "Set B"], "position": ["1", "2", "1", "2"],
                       "pfad": ["M/a.mp3", "M/b.mp3", "M/a.mp3", "M/c.mp3"]})
    res = pd.DataFrame([
        {"pfad": "M/a.mp3", "quelle": "crates", "klasse_neu": "sicher", "stufe_neu": "pfad", "pfad_ziel_neu": "M/a.mp3", "datei": None},
        {"pfad": "M/b.mp3", "quelle": "crates", "klasse_neu": "vorschlag", "stufe_neu": "name", "pfad_ziel_neu": "M/x/b.mp3", "datei": None},
        {"pfad": "M/c.mp3", "quelle": "crates", "klasse_neu": "sicher", "stufe_neu": "pfad", "pfad_ziel_neu": "M/c.mp3", "datei": None},
        {"pfad": "M/d.mp3", "quelle": "mac", "klasse_neu": "fehlt", "stufe_neu": "kein_kandidat", "pfad_ziel_neu": None, "datei": "Liste 1.m3u"},
        {"pfad": "M/a.mp3", "quelle": "mac", "klasse_neu": "sicher", "stufe_neu": "pfad", "pfad_ziel_neu": "M/a.mp3", "datei": "Liste 1.m3u"},
    ])
    # wie die echte Datei: alte NB04-Spalten liegen daneben (Befund NB06 Z.09)
    res = res.assign(klasse="alt", stufe="alt", pfad_ziel="alt")
    return t.Datenbasis(t.eintraege_tabelle(ce, res))


def test_eintraege_tabelle(db):
    e = db.eintraege
    assert len(e) == 6 and set(e["quelle"]) == {"crates", "mac"}
    assert e.loc[e["playlist"] == "Liste 1.m3u", "position"].tolist() == [1, 2]


def test_merge_bricht_bei_doppeltem_pfad_ab():
    ce = pd.DataFrame({"crate": ["A"], "position": ["1"], "pfad": ["M/a.mp3"]})
    res = pd.DataFrame([{"pfad": "M/a.mp3", "quelle": "crates", "klasse_neu": "sicher",
                         "stufe_neu": "pfad", "pfad_ziel_neu": "M/a.mp3", "datei": None}] * 2)
    with pytest.raises(pd.errors.MergeError):
        t.eintraege_tabelle(ce, res)


def test_merge_bricht_bei_fehlendem_ergebnis_ab():
    ce = pd.DataFrame({"crate": ["A"], "position": ["1"], "pfad": ["M/fehlt.mp3"]})
    res = pd.DataFrame(columns=["pfad", "quelle", "klasse_neu", "stufe_neu", "pfad_ziel_neu", "datei"])
    with pytest.raises(ValueError):
        t.eintraege_tabelle(ce, res)


def test_status(db):
    s = {q["quelle"]: q for q in t.status(db)["je_quelle"]}
    assert (s["crates"]["playlists"], s["crates"]["vollstaendig"], s["crates"]["vorschlag"]) == (2, 1, 1)
    assert (s["mac"]["playlists"], s["mac"]["vollstaendig"], s["mac"]["fehlt"]) == (1, 0, 1)
    json.dumps(t.status(db))   # JSON-faehig


def test_finde_playlist(db):
    r = t.finde_playlist(db, "set b")
    assert r["eindeutig"] and r["treffer"][0]["playlist"] == "Set B"
    r = t.finde_playlist(db, "set")                   # zwei passende -> nicht eindeutig
    assert not r["eindeutig"] and {x["playlist"] for x in r["treffer"][:2]} == {"Set A", "Set B"}
    assert t.finde_playlist(db, "Sett B")["treffer"][0]["playlist"] == "Set B"   # Tippfehler


def test_finde_playlist_exakt_vor_enthalten():
    ce = pd.DataFrame({"crate": ["Set", "Set A"], "position": ["1", "1"], "pfad": ["M/a.mp3", "M/a.mp3"]})
    res = pd.DataFrame([{"pfad": "M/a.mp3", "quelle": "crates", "klasse_neu": "sicher", "stufe_neu": "pfad",
                         "pfad_ziel_neu": "M/a.mp3", "datei": None}])
    db2 = t.Datenbasis(t.eintraege_tabelle(ce, res))
    r = t.finde_playlist(db2, "set")      # 'Set' exakt, 'Set A' enthaelt das Wort
    assert r["eindeutig"] and r["treffer"][0]["playlist"] == "Set" and r["treffer"][0]["exakt"]


def test_zeige_vorschlaege(db):
    r = t.zeige_vorschlaege(db)
    assert (r["pfade"], r["eintraege"], r["je_stufe"]) == (1, 1, {"name": 1})
    assert r["liste"][0]["kandidat"] == "M/x/b.mp3"
    assert t.zeige_vorschlaege(db, playlist="Set B")["eintraege"] == 0
    json.dumps(r)


def test_rufe_auf(db):
    assert "fehler" in t.rufe_auf(db, "loesche_alles", {})
    assert "fehler" in t.rufe_auf(db, "status", {"x": 1})
    assert t.rufe_auf(db, "finde_playlist", {"text": "Set A"})["eindeutig"]


def test_schema_passt_zu_funktionen():
    assert {w["name"] for w in t.WERKZEUGE} == set(t.AUSFUEHRBAR)


def test_finde_playlist_quelle():
    ce = pd.DataFrame({"crate": ["Liste"], "position": ["1"], "pfad": ["M/a.mp3"]})
    res = pd.DataFrame([
        {"pfad": "M/a.mp3", "quelle": "crates", "klasse_neu": "sicher", "stufe_neu": "pfad", "pfad_ziel_neu": "M/a.mp3", "datei": None},
        {"pfad": "M/a.mp3", "quelle": "foobar_asus", "klasse_neu": "sicher", "stufe_neu": "pfad", "pfad_ziel_neu": "M/a.mp3", "datei": "Liste"},
        {"pfad": "M/a.mp3", "quelle": "mac_playlists", "klasse_neu": "sicher", "stufe_neu": "pfad", "pfad_ziel_neu": "M/a.mp3", "datei": " Liste"},
    ])
    db3 = t.Datenbasis(t.eintraege_tabelle(ce, res))
    r = t.finde_playlist(db3, "Liste")                 # gleicher Name in 3 Quellen -> Rueckfrage
    assert not r["eindeutig"] and len(r["treffer"]) == 3
    r = t.finde_playlist(db3, "Liste", quelle="foobar_asus")
    assert r["eindeutig"] and r["treffer"][0]["quelle"] == "foobar_asus"
    assert "fehler" in t.finde_playlist(db3, "Liste", quelle="laptop_x")



@pytest.fixture
def dbb(db):
    b = pd.DataFrame([
        # pfad, stimmung, stil, bewertung, dj, dj_herkunft, jahr, jahrzehnt, dauer, audio_hash
        ("M/s1.mp3", "soft", "techno", "5", "DJ Eins", "serato_mix", "2009", None, "300", "h1"),
        ("M/s2.mp3", "happy", "techno", "4", "DJ Eins", "ordner", "2008", None, "400", "h2"),
        ("M/kopie/s1.mp3", "soft", "techno", "5", "DJ Eins", "serato_mix", "2009", None, "300", "h1"),
        ("M/s3.mp3", "down", "minimal", "5", None, "unbekannt", None, "1990", "200", "h3"),
        ("M/s4.mp3", None, "house", None, None, "unbekannt", "2001", None, "600", "h4"),
    ], columns=["pfad_relativ", "stimmung", "stil", "bewertung", "dj", "dj_herkunft", "jahr", "jahrzehnt",
                "audio_duration", "audio_sha256"]).assign(sha256=lambda d: d["audio_sha256"], tag_title="T")
    b["datei_ordner"] = b["pfad_relativ"].str.rsplit("/", n=1).str[0]
    b["datei_name"] = b["pfad_relativ"].str.rsplit("/", n=1).str[1]
    b["interpret"] = [None, "Band X", None, "Band X", "Band X"]
    b["tag_composer"] = ["Komp Eins", None, "Komp Eins", None, None]
    b["be_markiert"] = ["True", "False", "True", "False", "False"]       # aus CSV als Text
    b["tag_title"] = ["Erstes Stueck", "Suchwort Zwei", "Erstes Stueck", "Drei", "Vier"]
    db.bibliothek = b
    return db


def test_plan_filter_und_oder(dbb):
    r = t.plane_playlist_nach_kriterien(dbb, stimmung=["soft", "happy"], stil=["techno"])
    assert r["stuecke"] == 2 and r["filterwirkung"] == {"stimmung": 3, "stil": 3}
    assert "1 Dubletten ausgelassen (gleicher Inhalt)" in r["hinweise"]
    assert [s["pfad"] for s in r["vorschau"]] == ["M/s1.mp3", "M/s2.mp3"]      # kuerzester Pfad der Dublette
    json.dumps(r)


def test_plan_dj_hinweis_und_bewertung(dbb):
    r = t.plane_playlist_nach_kriterien(dbb, dj="dj eins", bewertung_min=5)
    assert r["stuecke"] == 1
    r = t.plane_playlist_nach_kriterien(dbb, dj="eins")
    assert any("ohne Gold-Beleg" in h for h in r["hinweise"])


def test_plan_jahr_und_jahrzehnt(dbb):
    assert t.plane_playlist_nach_kriterien(dbb, jahr_von=1990, jahr_bis=1999)["stuecke"] == 1   # Jahrzehnt ganz drin
    assert t.plane_playlist_nach_kriterien(dbb, jahr_von=1995, jahr_bis=1999)["stuecke"] == 0   # nur teilweise
    r = t.plane_playlist_nach_kriterien(dbb, jahr_von=2025, jahr_bis=2026)
    assert r["stuecke"] == 0 and "Jahre im Bestand: 2001 bis 2009" in r["hinweise"]


def test_plan_gesamtdauer_ohne_nachfuellen(dbb):
    r = t.plane_playlist_nach_kriterien(dbb, sortierung="dauer", gesamtdauer_max=900)
    # Dauer aufsteigend: 200, 300, 400 (=900), 600 passt nicht mehr
    assert r["stuecke"] == 3 and r["gesamtdauer_min"] == 15.0
    r = t.plane_playlist_nach_kriterien(dbb, sortierung="pfad", gesamtdauer_max=500)
    assert [s["pfad"] for s in r["vorschau"]] == ["M/s1.mp3"]   # s2 (400) passt nicht, s3 wird nicht nachgefuellt


def test_plan_reproduzierbar_und_gespeichert(dbb):
    a = t.plane_playlist_nach_kriterien(dbb, sortierung="zufall", seed=7)
    b = t.plane_playlist_nach_kriterien(dbb, sortierung="zufall", seed=7)
    assert a["plan_id"] == b["plan_id"] and a["inhalt_hash"] == b["inhalt_hash"]
    assert a["plan_id"] in dbb.plaene and len(dbb.plaene[a["plan_id"]]["pfade"]) == a["stuecke"]
    assert "fehler" in t.plane_playlist_nach_kriterien(dbb, sortierung="beliebt")


def test_plan_ohne_bibliothek(db):
    # konkrete Meldung pruefen: 'fehler' allein kaeme auch bei unbekanntem Werkzeug (Befund 25.11.)
    r = t.rufe_auf(db, "plane_playlist_nach_kriterien", {})
    assert "Masterliste nicht geladen" in r["fehler"]


def test_plan_wird_dauerhaft_gespeichert(dbb, tmp_path):
    from playlist_agent.agent import gate
    dbb.plan_ordner = tmp_path
    r = t.plane_playlist_nach_kriterien(dbb, stil=["techno"])
    p = gate.lade_plan(tmp_path, r["plan_id"])
    assert p["inhalt_hash"] == r["inhalt_hash"] and len(p["pfade"]) == r["stuecke"]
    t.plane_playlist_nach_kriterien(dbb, stil=["techno"])          # gleicher Plan erneut: kein Fehler
    assert len(gate.liste_plaene(tmp_path)) == 1



def test_ausschluss_komponist_be_ordner(dbb):
    assert t.plane_playlist_nach_kriterien(dbb, stil_nicht=["techno"])["stuecke"] == 2          # s3, s4
    assert t.plane_playlist_nach_kriterien(dbb, stimmung_nicht=["soft", "happy"])["stuecke"] == 2
    assert t.plane_playlist_nach_kriterien(dbb, komponist="komp eins")["stuecke"] == 1          # Dublette weg
    assert t.plane_playlist_nach_kriterien(dbb, be_markiert=True)["stuecke"] == 1
    assert t.plane_playlist_nach_kriterien(dbb, be_markiert=False)["stuecke"] == 3
    assert t.plane_playlist_nach_kriterien(dbb, ordner=["kopie"])["stuecke"] == 1
    assert t.plane_playlist_nach_kriterien(dbb, ordner=["m*"])["stuecke"] == 4                  # alle (Dublette weg)


def test_vielfalt_und_mindestdauer(dbb):
    r = t.plane_playlist_nach_kriterien(dbb, max_je_person=1)
    # Band X dreimal (s2, s3, s4) -> 1 bleibt; s1 hat DJ Eins -> bleibt
    assert r["stuecke"] == 2 and any("Vielfalt: 2" in h for h in r["hinweise"])
    r = t.plane_playlist_nach_kriterien(dbb, stil=["minimal"], gesamtdauer_min=3600)
    assert any("Mindestdauer nicht erreicht" in h for h in r["hinweise"])


def test_finde_titel(dbb):
    dbb.eintraege = pd.DataFrame({"quelle": ["crates"], "playlist": ["Set A"], "position": [1],
                                  "pfad": ["alt/s2.mp3"], "klasse": ["vorschlag"], "stufe": ["name"],
                                  "pfad_ziel": ["M/s2.mp3"]})
    r = t.finde_titel(dbb, "suchwort")
    assert r["stuecke"] == 1 and r["liste"][0]["playlists"] == ["crates: Set A"]
    assert t.finde_titel(dbb, "gibt es nicht")["stuecke"] == 0



# --- 5.1c Teil 2 ---------------------------------------------------------------------------
@pytest.fixture
def dbo(db):
    b = pd.DataFrame({"pfad_relativ": ["M/Album/02 B.mp3", "M/Album/01 A.mp3", "M/Set/Set 10.mp3",
                                       "M/Set/Set 2.mp3", "M/Album 2/x.mp3"],
                      "tag_track": ["2/10", "1", None, None, None],
                      "audio_duration": ["100", "200", "300", "400", "50"]})
    b["datei_ordner"] = b["pfad_relativ"].str.rsplit("/", n=1).str[0]
    db.bibliothek = b
    db.index = pd.DataFrame({"pfad_relativ": ["M/kaputt", "M/leer.mp3", "M/._x", "M/a.mp3"],
                             "bytes": ["0", "0", "0", "5"], "appledouble": ["False", "False", "True", "False"]})
    return db


def test_finde_ordner(dbo):
    r = t.finde_ordner(dbo, "album")
    assert r["eindeutig"] and r["treffer"][0]["ordner"] == "M/Album"          # exakt vor 'Album 2'
    assert not t.finde_ordner(dbo, "alb")["eindeutig"]                         # zwei enthalten 'alb'


def test_create_from_folder(dbo):
    r = t.plane_create_from_folder(dbo, "M/Album")
    assert r["reihenfolge"] == "tracknummer" and r["vorschau"] == ["01 A.mp3", "02 B.mp3"]
    assert r["gesamtdauer_min"] == 5.0 and r["plan_id"] in dbo.plaene
    assert t.plane_create_from_folder(dbo, "M/Set")["vorschau"] == ["Set 2.mp3", "Set 10.mp3"]   # Endzahl
    assert "vorschlaege" in t.plane_create_from_folder(dbo, "M/Albun")


def test_playlist_status_und_update(dbo):
    r = t.zeige_playlist_status(dbo, "Set A")
    assert (r["eintraege"], r["vollstaendig"], r["offen"][0]["klasse"]) == (2, False, "vorschlag")
    p = t.plane_update(dbo, "Set A")
    assert p["stuecke"] == 1 and p["ausgelassen"] == {"vorschlag": 1}
    assert dbo.plaene[p["plan_id"]]["pfade"] == ["M/a.mp3"]
    assert "fehler" in t.zeige_playlist_status(dbo, "gibt es nicht")


def test_gleicher_name_mehrere_quellen(dbo):
    dbo.eintraege = pd.concat([dbo.eintraege, dbo.eintraege.assign(quelle="foobar_asus")], ignore_index=True)
    assert "quellen" in t.zeige_playlist_status(dbo, "Set A")
    assert t.zeige_playlist_status(dbo, "Set A", quelle="crates")["quelle"] == "crates"


def test_beschaedigte_ordner(dbo):
    dbo.eintraege = pd.concat([dbo.eintraege, pd.DataFrame(
        {"quelle": ["crates"], "playlist": ["Set C"], "position": [1], "pfad": ["M/kaputt/a.mp3"],
         "klasse": ["album_beschaedigt"], "stufe": ["0-byte-ordner"], "pfad_ziel": [None]})], ignore_index=True)
    r = t.zeige_beschaedigte_ordner(dbo)
    assert r["ordner"] == 1 and r["liste"][0] == {"pfad": "M/kaputt", "eintraege": 1, "playlists": 1}


def test_status_mit_anker(db):
    assert "hinweis" in t.status(db)["stick"]
    db.anker = {"laufwerk": "D:", "laptop": {"name": "asus"}, "laufwerk_wie_konfiguriert": True}
    assert t.status(db)["stick"] == {"laufwerk": "D:", "laptop": "asus", "laufwerk_wie_konfiguriert": True}



# --- check_integrity (synthetischer Stick in tmp_path) --------------------------------------
def _stick(tmp_path):
    w = tmp_path / "stick"
    (w / "Musik" / "Album").mkdir(parents=True)
    (w / "Musik" / "Album" / "a.mp3").write_bytes(b"aaaa")
    (w / "Musik" / "Album" / "b.mp3").write_bytes(b"bbbb")
    (w / "Musik" / "c.mp3").write_bytes(b"cccc")
    return w


def test_integritaet_ohne_befund_wird_basis(db, tmp_path):
    from playlist_agent import index as ix
    from playlist_agent.integrity import erstelle_manifest
    w = _stick(tmp_path)
    start = tmp_path / "start.csv"
    erstelle_manifest(ix.scanne(w), w)[0].to_csv(start, index=False)
    db.anker, db.manifest_ordner, db.startmanifest = {"wurzel": str(w)}, tmp_path / "m", start
    r = t.check_integrity(db)
    assert (r["kritisch"], r["neu_gehasht"], r["verglichen_mit"]) == (False, 0, "start.csv")
    assert r["neues_manifest"].startswith("manifest_")


def test_integritaet_schaden_nur_kandidat(db, tmp_path):
    from playlist_agent import index as ix
    from playlist_agent.integrity import erstelle_manifest
    w = _stick(tmp_path)
    start = tmp_path / "start.csv"
    erstelle_manifest(ix.scanne(w), w)[0].to_csv(start, index=False)
    # Schadensmuster 06.02.2020: Ordner durch 0-Byte-Datei gleichen Namens ersetzt
    for f in (w / "Musik" / "Album").iterdir():
        f.unlink()
    (w / "Musik" / "Album").rmdir()
    (w / "Musik" / "Album").write_bytes(b"")
    db.anker, db.manifest_ordner, db.startmanifest = {"wurzel": str(w)}, tmp_path / "m", start
    r = t.check_integrity(db)
    assert r["kritisch"] and r["zusammenfassung"]["datei_statt_ordner"] == 1
    assert r["neues_manifest"].startswith("kandidat_")
    assert not list((tmp_path / "m").glob("manifest_*.csv"))           # Basis unveraendert
    assert t.uebernehme_kandidat(tmp_path / "m", r["neues_manifest"]).startswith("manifest_")
    with pytest.raises(ValueError):
        t.uebernehme_kandidat(tmp_path / "m", "../x.csv")


def test_integritaet_ohne_stick(db):
    assert "nicht verankert" in t.check_integrity(db)["fehler"]


def test_uebernahme_kein_llm_werkzeug():
    assert "uebernehme_kandidat" not in t.AUSFUEHRBAR


def test_interne_argumente_gesperrt(db):
    assert "nicht erlaubte" in t.rufe_auf(db, "check_integrity", {"_scanne": "x"})["fehler"]
