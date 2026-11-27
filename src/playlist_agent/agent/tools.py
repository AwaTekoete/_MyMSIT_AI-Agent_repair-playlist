"""Agent-Werkzeuge (Paket 5.1a): lesende Werkzeuge auf gespeicherten Artefakten.

Grundsaetze:
- Werkzeuge lesen nur (P2, P7); schreibende Aktionen laufen spaeter ueber Plan -> Vorschau ->
  Bestaetigung (P9, Paket 5.2). Das LLM ruft Werkzeuge auf, es schreibt nie selbst.
- Rueckgabe immer JSON-faehig (dict/list/str/int/float/bool/None), damit lokales LLM und API
  dieselbe Schnittstelle sehen.
- Datenbasis = Artefakte statt Stick: Crate-Eintraege (NB02 Z.02) + Resolver-Ergebnis (NB05 Z.35).
  Schluessel Crate-Eintrag -> Resolver: exakter Pfad (NB06 Z.08: 7.915/7.915 Treffer, 0 Widersprueche).
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from playlist_agent.agent import gate

KLASSEN = ["sicher", "vorschlag", "fehlt", "album_beschaedigt", "ausgeschlossen", "stream"]
# eine Playlist ist vollstaendig, wenn kein Eintrag offen ist (ausgeschlossen = kein Audio, Stream
# wird unveraendert uebernommen; Definition wie Bericht, Befund 15.11.2026)
OFFEN = ["vorschlag", "fehlt", "album_beschaedigt"]


# --- Datenbasis ------------------------------------------------------------------------
def eintraege_tabelle(df_crate_eintraege: pd.DataFrame, df_resolver: pd.DataFrame) -> pd.DataFrame:
    """Eine Zeile je Playlist-Eintrag: quelle, playlist, position, pfad, klasse, stufe, pfad_ziel."""
    spalten = {"klasse_neu": "klasse", "stufe_neu": "stufe", "pfad_ziel_neu": "pfad_ziel"}
    rc = df_resolver[df_resolver["quelle"] == "crates"][["pfad", *spalten]].rename(columns=spalten)
    # m:1 erzwingt eindeutige Resolver-Pfade; Verstoss -> MergeError statt stiller Vervielfachung
    c = (df_crate_eintraege.merge(rc, on="pfad", how="left", validate="m:1", indicator=True)
         .rename(columns={"crate": "playlist"}).assign(quelle="crates"))
    if (c["_merge"] != "both").any():
        raise ValueError(f"{int((c['_merge'] != 'both').sum())} Crate-Eintraege ohne Resolver-Ergebnis")
    c["position"] = pd.to_numeric(c["position"], errors="coerce")
    # erst Spalten waehlen, dann umbenennen: die Resolver-Datei enthaelt auch die alten Spalten
    # klasse/stufe/pfad_ziel (NB04) -> sonst doppelte Spaltennamen (Befund NB06 Z.09)
    ro = (df_resolver[df_resolver["quelle"] != "crates"][["quelle", "datei", "pfad", *spalten]]
          .rename(columns={**spalten, "datei": "playlist"}))
    ro = ro.assign(position=ro.groupby(["quelle", "playlist"]).cumcount() + 1)
    teile = [t[["quelle", "playlist", "position", "pfad", "klasse", "stufe", "pfad_ziel"]] for t in (c, ro)]
    return pd.concat(teile, ignore_index=True)


@dataclass
class Datenbasis:
    eintraege: pd.DataFrame
    bibliothek: pd.DataFrame | None = None          # Masterliste (NB06 Z.06), fuer planende Werkzeuge
    plaene: dict = field(default_factory=dict)      # Plan-ID -> Plan (Vorschau; Ausfuehrung nur ueber Gate, P9)
    plan_ordner: Path | None = None                 # gesetzt -> Plaene dauerhaft als JSON (Entscheidung 25.11.)
    index: pd.DataFrame | None = None               # alle Dateien des Sticks (NB05 Z.34), fuer 0-Byte-Ordner
    anker: dict | None = None                       # Verankerung (anchor.verankere), vom Aufrufer gesetzt
    manifest_ordner: Path | None = None             # Manifeste je Lauf (P12), privat, nie ueberschrieben
    startmanifest: Path | None = None               # Basis, solange noch kein Lauf-Manifest existiert

    @classmethod
    def aus_artefakten(cls, interim: Path, processed: Path | None = None,
                       plan_ordner: Path | None = None, manifest_ordner: Path | None = None) -> "Datenbasis":
        lies = lambda p: pd.read_csv(p, dtype=str, low_memory=False)
        e = eintraege_tabelle(lies(Path(interim) / "02_02_crate_eintraege.csv"),
                              lies(Path(interim) / "05_35_resolver_alt_neu.csv"))
        b = lies(Path(processed) / "06_06_bibliothek.csv") if processed else None
        ix_pfad = Path(interim) / "05_34_index_audiohash.csv"
        ix = lies(ix_pfad) if ix_pfad.exists() else None
        start = Path(interim) / "04_08_manifest_stick.csv"
        return cls(e, b, plan_ordner=Path(plan_ordner) if plan_ordner else None, index=ix,
                   manifest_ordner=Path(manifest_ordner) if manifest_ordner else None,
                   startmanifest=start if start.exists() else None)


# --- Hilfen ----------------------------------------------------------------------------
def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).casefold().strip()


def _je_playlist(e: pd.DataFrame) -> pd.DataFrame:
    z = (e.pivot_table(index=["quelle", "playlist"], columns="klasse", values="pfad",
                       aggfunc="size", fill_value=0)
         .reindex(columns=KLASSEN, fill_value=0))
    z["eintraege"] = z.sum(axis=1)
    z["vollstaendig"] = z[OFFEN].sum(axis=1) == 0
    return z.reset_index()


# --- Werkzeuge -------------------------------------------------------------------------
def status(db: Datenbasis) -> dict:
    """Uebersicht je Quelle: Playlists, davon vollstaendig, Eintraege je Klasse."""
    p = _je_playlist(db.eintraege)
    g = p.groupby("quelle").agg(playlists=("playlist", "size"), vollstaendig=("vollstaendig", "sum"),
                                eintraege=("eintraege", "sum"), **{k: (k, "sum") for k in KLASSEN})
    a = db.anker
    stick = ({"laufwerk": a.get("laufwerk"), "laptop": a.get("laptop", {}).get("name"),
              "laufwerk_wie_konfiguriert": a.get("laufwerk_wie_konfiguriert")} if a else
             {"hinweis": "Stick nicht verankert (nicht eingesteckt oder nicht geprueft)"})
    return {"stick": stick,
            "je_quelle": [{"quelle": q, **{k: int(v) for k, v in r.items()}} for q, r in g.iterrows()]}


def finde_playlist(db: Datenbasis, text: str, max_treffer: int = 5, quelle: str | None = None) -> dict:
    """Playlists, deren Name zum Text passt (unscharf). Mehrere Treffer -> Agent fragt nach.

    Rangfolge: 1. exakter Name (NFC, Gross/Klein egal) 2. alle Woerter enthalten
    3. Aehnlichkeit (difflib). Ohne Stufe 1 haette ein Name, der in einem laengeren Namen
    enthalten ist, gegen diesen alphabetisch verloren (Befund NB06 Z.09: 313 von 345).
    quelle: optionaler Filter ("... auf dem Asus"); gleicher Name in mehreren Quellen ist
    moeglich und inhaltlich unabhaengig (Befund NB06 Z.10).
    """
    p = _je_playlist(db.eintraege)
    if quelle is not None:
        if quelle not in set(p["quelle"]):
            return {"fehler": f"unbekannte Quelle '{quelle}'", "verfuegbar": sorted(set(p["quelle"]))}
        p = p[p["quelle"] == quelle].copy()
    q = _norm(text)
    woerter = q.split()
    n = p["playlist"].map(_norm)
    p["exakt"] = n == q
    p["alle_woerter"] = n.map(lambda x: all(w in x for w in woerter))
    p["aehnlich"] = n.map(lambda x: round(difflib.SequenceMatcher(None, q, x).ratio(), 3))
    p["score"] = p["exakt"] * 2.0 + p["alle_woerter"] * 1.0 + p["aehnlich"] * 0.5
    t = p.sort_values(["score", "playlist"], ascending=[False, True]).head(max_treffer)
    # eindeutig: genau eine Playlist (Quelle + Name) exakt, sonst genau eine mit allen Woertern;
    # gleicher Name in mehreren Quellen ist NICHT eindeutig -> Rueckfrage nach der Quelle
    exakt = p.loc[p["exakt"], ["quelle", "playlist"]]
    alle = p.loc[p["alle_woerter"], ["quelle", "playlist"]]
    eindeutig = len(exakt) == 1 or (len(exakt) == 0 and len(alle) == 1)
    return {"eindeutig": bool(eindeutig),
            "treffer": [{"playlist": r.playlist, "quelle": r.quelle, "score": round(float(r.score), 3),
                         "exakt": bool(r.exakt), "eintraege": int(r.eintraege),
                         "vollstaendig": bool(r.vollstaendig)} for r in t.itertuples()]}


def zeige_vorschlaege(db: Datenbasis, playlist: str | None = None, max_eintraege: int = 50) -> dict:
    """Offene Vorschlaege (Klasse 'vorschlag'), optional fuer eine Playlist; je Pfad verdichtet."""
    e = db.eintraege[db.eintraege["klasse"] == "vorschlag"]
    if playlist is not None:
        e = e[e["playlist"] == playlist]
    je = (e.groupby(["pfad", "pfad_ziel", "stufe"], dropna=False)
          .agg(eintraege=("playlist", "size"), playlists=("playlist", "nunique"))
          .reset_index().sort_values(["eintraege", "pfad"], ascending=[False, True]))
    return {"pfade": int(len(je)), "eintraege": int(len(e)),
            "je_stufe": {str(k): int(v) for k, v in e["stufe"].value_counts().items()},
            "liste": [{"pfad": r.pfad, "kandidat": None if pd.isna(r.pfad_ziel) else r.pfad_ziel,
                       "stufe": r.stufe, "eintraege": int(r.eintraege), "playlists": int(r.playlists)}
                      for r in je.head(max_eintraege).itertuples()],
            "gekuerzt": bool(len(je) > max_eintraege)}


def finde_titel(db: Datenbasis, text: str, max_treffer: int = 20) -> dict:
    """Musikstuecke, deren Titel (Tag, sonst Serato) oder Dateiname alle Woerter enthaelt,
    und die Playlists, in denen sie stehen (Ziel des Resolvers = dieses Stueck). Luecke e (Z.18)."""
    if db.bibliothek is None:
        return {"fehler": "Masterliste nicht geladen (Datenbasis.aus_artefakten(..., processed=...))"}
    b = db.bibliothek
    woerter = _norm(text).split()
    titel = b["tag_title"].where(b["tag_title"].notna(), b.get("serato_titel"))
    such = (titel.fillna("") + " " + b["datei_name"].fillna("")).map(_norm)
    t = b[such.map(lambda x: all(w in x for w in woerter))]
    e = db.eintraege[db.eintraege["pfad_ziel"].isin(set(t["pfad_relativ"]))]
    je = e.groupby("pfad_ziel").apply(
        lambda g: sorted({f"{q}: {p}" for q, p in zip(g["quelle"], g["playlist"])}), include_groups=False)
    liste = [{"pfad": r.pfad_relativ, "titel": titel[i] if isinstance(titel[i], str) else None,
              "playlists": je.get(r.pfad_relativ, [])} for i, r in t.head(max_treffer).iterrows()]
    return {"stuecke": int(len(t)), "liste": liste, "gekuerzt": bool(len(t) > max_treffer)}


# --- planende Werkzeuge ----------------------------------------------------------------
def _plan_id(kriterien: dict, inhalt_hash: str) -> str:
    """Deterministisch aus Kriterien + Inhalt: gleicher Auftrag -> gleiche Plan-ID (reproduzierbar)."""
    return "P-" + hashlib.sha256(json.dumps(kriterien, sort_keys=True, ensure_ascii=False).encode("utf-8")
                                 + inhalt_hash.encode()).hexdigest()[:10]


def _merke_plan(db: Datenbasis, plan: dict) -> None:
    db.plaene[plan["plan_id"]] = plan
    if db.plan_ordner is not None:
        gate.speichere_plan(plan, db.plan_ordner)


def _neuer_plan(db: Datenbasis, art: str, kriterien: dict, pfade: list[str], **extra) -> dict:
    h = gate.inhalt_hash(pfade)
    plan = {"plan_id": _plan_id({"art": art, **kriterien}, h), "art": art, "kriterien": kriterien,
            "stuecke": len(pfade), "inhalt_hash": h, "pfade": pfade, **extra}
    _merke_plan(db, plan)
    return plan

SORTIERUNGEN = ["pfad", "bewertung", "jahr", "dauer", "zufall"]


def _werte(x) -> set[str]:
    """'soft; beat' -> {'soft', 'beat'}."""
    return {w.strip() for w in x.split(";") if w.strip()} if isinstance(x, str) else set()


def _liste(x) -> list[str]:
    if x is None:
        return []
    return [str(v).strip().casefold() for v in (x if isinstance(x, list) else [x]) if str(v).strip()]


def plane_playlist_nach_kriterien(db: Datenbasis, stimmung=None, stil=None, bewertung_min: int | None = None,
                                  dj=None, interpret=None, jahr_von: int | None = None,
                                  jahr_bis: int | None = None, dauer_min: float | None = None,
                                  dauer_max: float | None = None, gesamtdauer_max: float | None = None,
                                  sortierung: str = "pfad", seed: int = 42, max_anzeige: int = 50,
                                  stimmung_nicht=None, stil_nicht=None, komponist=None,
                                  be_markiert: bool | None = None, ordner=None,
                                  max_je_person: int | None = None,
                                  gesamtdauer_min: float | None = None) -> dict:
    """Plan (Vorschau) einer Playlist aus der Masterliste; schreibt nichts (P9).

    Regeln (Nutzerentscheidungen 25.11.2026): mehrere Werte je Kriterium = ODER, Kriterien = UND;
    Gesamtdauer: der Reihe nach aufnehmen bis das naechste Stueck nicht mehr passt (kein Nachfuellen);
    DJ-Treffer jeder Herkunft zaehlen, Herkunft wird je Stueck angezeigt; Dubletten (gleicher
    Audio-Hash, sonst gleicher Datei-Hash) nur einmal, kuerzester Pfad.
    Dauer in Sekunden (gemessen, audio_duration). Bewertungskonflikt = ohne Bewertung.
    Ergaenzungen 5.1c (Testset NB06 Z.18, Luecken a-f, i): Ausschluss (stimmung_nicht, stil_nicht),
    komponist (tag_composer/serato_komponist), be_markiert, ordner (Teilwort oder Muster mit *),
    max_je_person (Vielfalt: hoechstens n Stuecke je Interpret, sonst DJ), gesamtdauer_min (Hinweis).
    """
    if db.bibliothek is None:
        return {"fehler": "Masterliste nicht geladen (Datenbasis.aus_artefakten(..., processed=...))"}
    if sortierung not in SORTIERUNGEN:
        return {"fehler": f"unbekannte Sortierung '{sortierung}'", "verfuegbar": SORTIERUNGEN}
    b = db.bibliothek
    num = lambda s: pd.to_numeric(b[s], errors="coerce") if s in b.columns else pd.Series(float("nan"), index=b.index)
    dauer, bew, jahr, zehn = num("audio_duration"), num("bewertung"), num("jahr"), num("jahrzehnt")

    filter_ = {}
    if stimmung:
        w = set(_liste(stimmung)); filter_["stimmung"] = b["stimmung"].map(lambda x: bool(_werte(x) & w))
    if stil:
        w = set(_liste(stil)); filter_["stil"] = b["stil"].map(lambda x: bool(_werte(x) & w))
    if stimmung_nicht:
        w = set(_liste(stimmung_nicht)); filter_["stimmung_nicht"] = ~b["stimmung"].map(lambda x: bool(_werte(x) & w))
    if stil_nicht:
        w = set(_liste(stil_nicht)); filter_["stil_nicht"] = ~b["stil"].map(lambda x: bool(_werte(x) & w))
    if bewertung_min is not None:
        filter_["bewertung_min"] = bew >= bewertung_min
    for name, spalte, werte in (("dj", "dj", dj), ("interpret", "interpret", interpret)):
        w = _liste(werte)
        if w:
            filter_[name] = b[spalte].map(lambda x: isinstance(x, str) and any(v in x.casefold() for v in w))
    w = _liste(komponist)
    if w:
        k = pd.Series(False, index=b.index)
        for spalte in ("tag_composer", "serato_komponist"):
            if spalte in b.columns:
                k |= b[spalte].map(lambda x: isinstance(x, str) and any(v in x.casefold() for v in w))
        filter_["komponist"] = k
    if be_markiert is not None:
        ist = b["be_markiert"].astype(str).str.casefold() == "true"
        filter_["be_markiert"] = ist if be_markiert else ~ist
    muster = _liste(ordner)
    if muster:
        import fnmatch
        o = b["datei_ordner"].fillna("").str.casefold()
        filter_["ordner"] = o.map(lambda x: any(fnmatch.fnmatch(x, f"*{m}*") if "*" in m else m in x
                                                for m in muster))
    if jahr_von is not None or jahr_bis is not None:
        von, bis = jahr_von if jahr_von is not None else 0, jahr_bis if jahr_bis is not None else 9999
        # nur Jahrzehnt bekannt: zaehlt nur, wenn das ganze Jahrzehnt im Zeitraum liegt (vorsichtig, P5)
        filter_["jahr"] = jahr.between(von, bis) | (jahr.isna() & (zehn >= von) & (zehn + 9 <= bis))
    if dauer_min is not None:
        filter_["dauer_min"] = dauer >= dauer_min
    if dauer_max is not None:
        filter_["dauer_max"] = dauer <= dauer_max

    maske = pd.Series(True, index=b.index)
    for f in filter_.values():
        maske &= f.fillna(False).astype(bool)
    t = b[maske].assign(_dauer=dauer[maske], _bew=bew[maske], _jahr=jahr[maske])

    # Dubletten: eine Fassung je Inhalt, kuerzester Pfad
    schluessel = t["audio_sha256"].where(t["audio_sha256"].notna(), t["sha256"]) if "audio_sha256" in t else t["sha256"]
    t = (t.assign(_k=schluessel.fillna(t["pfad_relativ"]), _l=t["pfad_relativ"].str.len())
         .sort_values(["_k", "_l", "pfad_relativ"]))
    n_dubletten = int(t["_k"].duplicated().sum())
    t = t.drop_duplicates("_k")

    if sortierung == "bewertung":
        t = t.sort_values(["_bew", "_jahr", "pfad_relativ"], ascending=[False, False, True], na_position="last")
    elif sortierung == "jahr":
        t = t.sort_values(["_jahr", "pfad_relativ"], ascending=[False, True], na_position="last")
    elif sortierung == "dauer":
        t = t.sort_values(["_dauer", "pfad_relativ"], na_position="last")
    elif sortierung == "zufall":
        t = t.sample(frac=1.0, random_state=seed)
    else:
        t = t.sort_values("pfad_relativ")

    n_vielfalt = 0
    if max_je_person is not None:
        # Vielfalt: Person = Interpret, sonst DJ; ohne beides keine Begrenzung (Hinweis)
        person = t["interpret"].where(t["interpret"].notna(), t["dj"]).str.casefold()
        rang = person.groupby(person).cumcount()
        behalten = person.isna() | (rang < max_je_person)
        n_vielfalt = int((~behalten).sum())
        n_ohne_person = int(person.isna().sum())
        t = t[behalten]

    n_vor_dauer = len(t)
    if gesamtdauer_max is not None:
        summe = t["_dauer"].fillna(0).cumsum()
        t = t[summe <= gesamtdauer_max]

    pfade = t["pfad_relativ"].tolist()
    kriterien = {k: v for k, v in dict(stimmung=stimmung, stil=stil, bewertung_min=bewertung_min, dj=dj,
                 interpret=interpret, jahr_von=jahr_von, jahr_bis=jahr_bis, dauer_min=dauer_min,
                 dauer_max=dauer_max, gesamtdauer_max=gesamtdauer_max, sortierung=sortierung,
                 seed=seed if sortierung == "zufall" else None, stimmung_nicht=stimmung_nicht,
                 stil_nicht=stil_nicht, komponist=komponist, be_markiert=be_markiert, ordner=ordner,
                 max_je_person=max_je_person, gesamtdauer_min=gesamtdauer_min).items() if v is not None}
    inhalt_hash = gate.inhalt_hash(pfade)
    plan_id = _plan_id(kriterien, inhalt_hash)

    hinweise = []
    if not pfade:
        hinweise.append("0 Treffer")
        if "jahr" in filter_ and jahr.notna().any():
            hinweise.append(f"Jahre im Bestand: {int(jahr.min())} bis {int(jahr.max())}")
    if n_dubletten:
        hinweise.append(f"{n_dubletten} Dubletten ausgelassen (gleicher Inhalt)")
    if gesamtdauer_max is not None and n_vor_dauer > len(pfade):
        hinweise.append(f"Gesamtdauer begrenzt: {len(pfade)} von {n_vor_dauer} Stuecken aufgenommen")
    if max_je_person is not None:
        if n_vielfalt:
            hinweise.append(f"Vielfalt: {n_vielfalt} Stuecke ausgelassen (max {max_je_person} je Person)")
        if n_ohne_person:
            hinweise.append(f"{n_ohne_person} Stuecke ohne Interpret/DJ: Vielfalt dort nicht pruefbar")
    summe_min = t["_dauer"].fillna(0).sum() / 60
    if gesamtdauer_min is not None and pfade and summe_min * 60 < gesamtdauer_min:
        hinweise.append(f"Mindestdauer nicht erreicht: {summe_min:.1f} von {gesamtdauer_min / 60:.0f} min")
    if "dj" in filter_ and len(t) and (t["dj_herkunft"] != "serato_mix").any():
        hinweise.append(f"{int((t['dj_herkunft'] != 'serato_mix').sum())} DJ-Treffer nur ueber Kuerzel "
                        f"in Ordner/Titel/Datei (ohne Gold-Beleg)")

    def titel(r):
        for s in ("tag_title", "serato_titel"):
            if s in r and isinstance(r[s], str) and r[s].strip():
                return r[s]
        return r["datei_name"] if "datei_name" in r else None

    stuecke = [{"pfad": r["pfad_relativ"], "titel": titel(r),
                "dj": r.get("dj") if isinstance(r.get("dj"), str) else None,
                "dj_herkunft": r.get("dj_herkunft"),
                "bewertung": None if pd.isna(r["_bew"]) else int(r["_bew"]),
                "jahr": None if pd.isna(r["_jahr"]) else int(r["_jahr"]),
                "dauer_s": None if pd.isna(r["_dauer"]) else round(float(r["_dauer"]), 1)}
               for _, r in t.iterrows()]
    plan = {"plan_id": plan_id, "art": "playlist_nach_kriterien", "kriterien": kriterien,
            "stuecke": len(stuecke), "gesamtdauer_min": round(t["_dauer"].fillna(0).sum() / 60, 1),
            "inhalt_hash": inhalt_hash, "pfade": pfade,
            "filterwirkung": {k: int(v.fillna(False).astype(bool).sum()) for k, v in filter_.items()},
            "hinweise": hinweise}
    _merke_plan(db, plan)
    # an das LLM nur die Vorschau (gekuerzt), der volle Plan bleibt in db.plaene
    return {**{k: v for k, v in plan.items() if k != "pfade"},
            "vorschau": stuecke[:max_anzeige], "gekuerzt": len(stuecke) > max_anzeige}


# --- Ordner, Status je Playlist, beschaedigte Ordner, Aktualisieren (5.1c Teil 2) --------
def _ordner_liste(db: Datenbasis) -> pd.DataFrame:
    b = db.bibliothek
    return (b.groupby("datei_ordner").size().rename("dateien").reset_index()
            .rename(columns={"datei_ordner": "ordner"}))


def finde_ordner(db: Datenbasis, text: str, max_treffer: int = 5) -> dict:
    """Musikordner (mit Audiodateien direkt darin) nach Name; Rangfolge wie finde_playlist,
    verglichen mit dem letzten Ordnernamen und dem ganzen Pfad."""
    if db.bibliothek is None:
        return {"fehler": "Masterliste nicht geladen (Datenbasis.aus_artefakten(..., processed=...))"}
    o = _ordner_liste(db)
    q = _norm(text).strip("/")
    woerter = q.split()
    letzter = o["ordner"].map(lambda x: _norm(x.rsplit("/", 1)[-1]))
    ganz = o["ordner"].map(_norm)
    o["exakt"] = (letzter == q) | (ganz == q)
    o["alle_woerter"] = ganz.map(lambda x: all(w in x for w in woerter))
    o["aehnlich"] = letzter.map(lambda x: round(difflib.SequenceMatcher(None, q, x).ratio(), 3))
    o["score"] = o["exakt"] * 2.0 + o["alle_woerter"] * 1.0 + o["aehnlich"] * 0.5
    t = o.sort_values(["score", "ordner"], ascending=[False, True]).head(max_treffer)
    eindeutig = int(o["exakt"].sum()) == 1 or (not o["exakt"].any() and int(o["alle_woerter"].sum()) == 1)
    return {"eindeutig": bool(eindeutig),
            "treffer": [{"ordner": r.ordner, "dateien": int(r.dateien), "score": round(float(r.score), 3),
                         "exakt": bool(r.exakt)} for r in t.itertuples()]}


def _tracknummer(x) -> int | None:
    """'3', '03', '3/12' -> 3; sonst None."""
    if not isinstance(x, str):
        return None
    m = re.match(r"^\s*(\d+)", x)
    return int(m.group(1)) if m else None


def plane_create_from_folder(db: Datenbasis, ordner: str, max_anzeige: int = 50) -> dict:
    """Plan einer Playlist aus einem Ordner; Reihenfolge per Regel (ordner.playlist_aus_ordner):
    Endzahl im Dateinamen > Tracknummer > natuerliche Sortierung. Schreibt nichts (P9)."""
    from playlist_agent.ordner import playlist_aus_ordner
    if db.bibliothek is None:
        return {"fehler": "Masterliste nicht geladen (Datenbasis.aus_artefakten(..., processed=...))"}
    b = db.bibliothek
    ordner = ordner.strip("/")
    if ordner not in set(b["datei_ordner"]):
        return {"fehler": f"Ordner '{ordner}' nicht gefunden oder ohne Audiodateien",
                "vorschlaege": finde_ordner(db, ordner)["treffer"]}
    teil = b[b["datei_ordner"] == ordner]
    tracks = {p: _tracknummer(t) for p, t in zip(teil["pfad_relativ"], teil.get("tag_track", [None] * len(teil)))}
    pfade, regel = playlist_aus_ordner(teil["pfad_relativ"].tolist(), ordner, tracks)
    dauer = pd.to_numeric(teil.set_index("pfad_relativ")["audio_duration"], errors="coerce")
    plan = _neuer_plan(db, "playlist_aus_ordner", {"ordner": ordner}, pfade, reihenfolge=regel,
                       gesamtdauer_min=round(float(dauer.reindex(pfade).fillna(0).sum()) / 60, 1),
                       hinweise=[] if regel != "dateiname" else
                       ["Reihenfolge nach Dateiname (keine eindeutigen Tracknummern/Endzahlen)"])
    return {**{k: v for k, v in plan.items() if k != "pfade"},
            "vorschau": [p.rsplit("/", 1)[-1] for p in pfade[:max_anzeige]],
            "gekuerzt": len(pfade) > max_anzeige}


def _eine_playlist(db: Datenbasis, playlist: str, quelle: str | None) -> tuple[pd.DataFrame | None, dict | None]:
    e = db.eintraege[db.eintraege["playlist"] == playlist]
    if quelle is not None:
        e = e[e["quelle"] == quelle]
    quellen = sorted(set(e["quelle"]))
    if not len(e):
        return None, {"fehler": f"Playlist '{playlist}' nicht gefunden (Name exakt wie finde_playlist)"}
    if len(quellen) > 1:
        return None, {"fehler": "Name in mehreren Quellen -> Quelle angeben", "quellen": quellen}
    return e.sort_values("position"), None


def zeige_playlist_status(db: Datenbasis, playlist: str, quelle: str | None = None,
                          max_eintraege: int = 50) -> dict:
    """Eintraege einer Playlist je Klasse und Liste der nicht sicheren Eintraege."""
    e, fehler = _eine_playlist(db, playlist, quelle)
    if fehler:
        return fehler
    offen = e[e["klasse"].isin(OFFEN)]
    return {"playlist": playlist, "quelle": e["quelle"].iat[0], "eintraege": int(len(e)),
            "je_klasse": {str(k): int(v) for k, v in e["klasse"].value_counts().items()},
            "vollstaendig": bool(offen.empty),
            "offen": [{"position": int(r.position), "pfad": r.pfad, "klasse": r.klasse, "stufe": r.stufe,
                       "kandidat": None if pd.isna(r.pfad_ziel) else r.pfad_ziel}
                      for r in offen.head(max_eintraege).itertuples()],
            "gekuerzt": bool(len(offen) > max_eintraege)}


def zeige_beschaedigte_ordner(db: Datenbasis) -> dict:
    """0-Byte-Dateien ohne Audio-Endung an Stelle eines Ordners (Datenverlust) und betroffene
    Playlist-Eintraege (Pfad beginnt mit dem 0-Byte-Pfad). Wiederherstellung nur aus Sicherung."""
    if db.index is None:
        return {"fehler": "Index nicht geladen (05_34_index_audiohash.csv fehlt)"}
    ix = db.index
    null = ix[(pd.to_numeric(ix["bytes"], errors="coerce") == 0)
              & (ix["appledouble"].astype(str).str.casefold() != "true")]
    null = null[~null["pfad_relativ"].str.lower().str.endswith((".mp3", ".wav", ".aif"))]
    e = db.eintraege
    liste = []
    for p in sorted(null["pfad_relativ"]):
        betroffen = e[e["pfad"].str.startswith(p + "/", na=False)]
        liste.append({"pfad": p, "eintraege": int(len(betroffen)),
                      "playlists": int(betroffen[["quelle", "playlist"]].drop_duplicates().shape[0])})
    return {"ordner": len(liste), "album_beschaedigt_eintraege": int((e["klasse"] == "album_beschaedigt").sum()),
            "liste": liste}


def plane_update(db: Datenbasis, playlist: str, quelle: str | None = None, max_anzeige: int = 50) -> dict:
    """Plan: alte Playlist in foobar-Form uebertragen bzw. aktualisieren. Geschrieben werden nur
    sichere Eintraege (P5) und Streams; Vorschlaege, Fehlendes, Beschaedigtes werden gemeldet."""
    e, fehler = _eine_playlist(db, playlist, quelle)
    if fehler:
        return fehler
    pfade = [z if k == "sicher" else p for k, z, p in zip(e["klasse"], e["pfad_ziel"], e["pfad"])
             if k in ("sicher", "stream")]
    ausgelassen = {str(k): int(v) for k, v in e.loc[~e["klasse"].isin(["sicher", "stream"]), "klasse"]
                   .value_counts().items()}
    plan = _neuer_plan(db, "playlist_aktualisieren", {"playlist": playlist, "quelle": e["quelle"].iat[0]},
                       pfade, ausgelassen=ausgelassen,
                       hinweise=[f"{sum(ausgelassen.values())} Eintraege nicht sicher, nicht geschrieben "
                                 f"(siehe zeige_playlist_status)"] if ausgelassen else [])
    return {**{k: v for k, v in plan.items() if k != "pfade"},
            "vorschau": [p.rsplit("/", 1)[-1] for p in pfade[:max_anzeige]],
            "gekuerzt": len(pfade) > max_anzeige}


# --- Integritaet (P12) -----------------------------------------------------------------
# Basis = neuestes Manifest 'manifest_<Zeit>.csv' in manifest_ordner, sonst Startmanifest (NB04 Z.08).
# Ohne kritischen Befund wird das neue Manifest Basis; mit kritischem Befund nur als Kandidat
# gespeichert -> Basis erneuert erst nach Bestaetigung (Entscheidung a, Paket 5.0), damit ein
# Schaden nicht unbemerkt zur neuen 'Wahrheit' wird. Rein lesend auf dem Stick (P1/P7).
def _basis_manifest(db: Datenbasis) -> tuple[pd.DataFrame | None, str]:
    if db.manifest_ordner is not None:
        laeufe = sorted(Path(db.manifest_ordner).glob("manifest_*.csv"))
        if laeufe:
            return pd.read_csv(laeufe[-1], dtype={"pfad_relativ": str, "sha256": str}), laeufe[-1].name
    if db.startmanifest is not None:
        return pd.read_csv(db.startmanifest, dtype={"pfad_relativ": str, "sha256": str}), db.startmanifest.name
    return None, ""


def check_integrity(db: Datenbasis, max_befunde: int = 50, _scanne=None, _hash=None) -> dict:
    """Stick einlesen, mit dem Manifest des letzten Laufs vergleichen, Befunde melden.
    _scanne/_hash nur fuer Tests (Standard: index.scanne, index.sha256_datei)."""
    from datetime import datetime

    from playlist_agent import index as ix
    from playlist_agent.integrity import erstelle_manifest, vergleiche_manifeste, warnung_noetig, zusammenfassung
    if not db.anker or not db.anker.get("wurzel"):
        return {"fehler": "Stick nicht verankert – bitte einstecken"}
    if db.manifest_ordner is None:
        return {"fehler": "kein Ablageordner fuer Manifeste (Datenbasis.manifest_ordner)"}
    alt, basis = _basis_manifest(db)
    if alt is None:
        return {"fehler": "kein Vergleichsmanifest vorhanden"}
    wurzel = Path(db.anker["wurzel"])
    df_ix = (_scanne or ix.scanne)(wurzel)
    neu, n_hash = erstelle_manifest(df_ix, wurzel, alt, hash_fn=_hash or ix.sha256_datei)
    befunde = vergleiche_manifeste(alt, neu)
    kritisch = warnung_noetig(befunde)
    stempel = datetime.now().strftime("%Y%m%d_%H%M%S")
    ordner = Path(db.manifest_ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / (f"kandidat_{stempel}.csv" if kritisch else f"manifest_{stempel}.csv")
    neu.to_csv(ziel, index=False, lineterminator="\n")
    db.index = neu if db.index is None else db.index
    zeige = befunde[befunde["schwere"] != "info"]
    z = zusammenfassung(befunde)
    return {"verglichen_mit": basis, "dateien": int(len(neu)), "neu_gehasht": n_hash,
            "kritisch": bool(kritisch),
            "zusammenfassung": dict(zip(z["typ"], z["anzahl [Befunde]"].astype(int).tolist())),
            "befunde": zeige.head(max_befunde).to_dict("records"), "gekuerzt": bool(len(zeige) > max_befunde),
            "neues_manifest": ziel.name,
            "hinweis": ("WARNUNG: kritische Befunde. Vor der naechsten Sicherung pruefen. Neues Manifest nur "
                        "als Kandidat gespeichert; Basis bleibt bis zur Bestaetigung." if kritisch else
                        "Keine kritischen Befunde; neues Manifest ist Basis fuer den naechsten Lauf.")}


def uebernehme_kandidat(manifest_ordner, kandidat: str) -> str:
    """KEIN LLM-Werkzeug: Kandidat nach Bestaetigung des Nutzers zur Basis machen (Kopie, nie verschieben)."""
    import re as _re
    import shutil
    if not _re.match(r"^kandidat_\d{8}_\d{6}\.csv$", kandidat):
        raise ValueError(f"ungueltiger Kandidat '{kandidat}'")
    q = Path(manifest_ordner) / kandidat
    z = q.with_name(kandidat.replace("kandidat_", "manifest_"))
    if z.exists():
        raise FileExistsError(z.name)
    shutil.copy2(q, z)
    return z.name


# --- Beschreibung fuer das LLM (JSON-Schema, Format wie Tool-Use der gaengigen APIs) -------
WERKZEUGE = [
    {"name": "status",
     "description": "Uebersicht: Playlists je Quelle, davon vollstaendig, Eintraege je Klasse.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "finde_playlist",
     "description": "Sucht Playlists nach Name (unscharf). Bei mehreren Treffern beim Nutzer nachfragen.",
     "input_schema": {"type": "object",
                      "properties": {"text": {"type": "string", "description": "Name oder Teil davon"},
                                     "max_treffer": {"type": "integer", "minimum": 1, "maximum": 20},
                                     "quelle": {"type": "string",
                                                "enum": ["crates", "foobar_asus", "foobar_medion",
                                                         "mac_playlists", "musik_playlists"],
                                                "description": "nur in dieser Quelle suchen"}},
                      "required": ["text"]}},
    {"name": "zeige_vorschlaege",
     "description": "Offene Vorschlaege (Song gefunden, aber an anderem Ort); optional fuer eine Playlist.",
     "input_schema": {"type": "object",
                      "properties": {"playlist": {"type": "string", "description": "exakter Name aus finde_playlist"},
                                     "max_eintraege": {"type": "integer", "minimum": 1, "maximum": 200}},
                      "required": []}},
    {"name": "plane_playlist_nach_kriterien",
     "description": ("Plant (Vorschau, schreibt nichts) eine Playlist aus der Musikbibliothek nach Kriterien. "
                     "Mehrere Werte je Kriterium = ODER, Kriterien = UND. Ergebnis hat eine plan_id; "
                     "geschrieben wird erst nach Bestaetigung durch den Nutzer."),
     "input_schema": {"type": "object", "properties": {
         "stimmung": {"type": "array", "items": {"type": "string",
                      "enum": ["soft", "push", "happy", "down", "rush", "goodfly", "fly", "rock", "beat"]}},
         "stil": {"type": "array", "items": {"type": "string"}, "description": "z. B. techno, minimal, techhouse"},
         "bewertung_min": {"type": "integer", "minimum": 1, "maximum": 5},
         "dj": {"type": "array", "items": {"type": "string"}, "description": "DJ, der das Stueck im Set spielt"},
         "interpret": {"type": "array", "items": {"type": "string"}},
         "jahr_von": {"type": "integer"}, "jahr_bis": {"type": "integer"},
         "dauer_min": {"type": "number", "description": "Sekunden"},
         "dauer_max": {"type": "number", "description": "Sekunden"},
         "gesamtdauer_max": {"type": "number", "description": "Sekunden"},
         "sortierung": {"type": "string", "enum": SORTIERUNGEN},
         "seed": {"type": "integer"}, "max_anzeige": {"type": "integer", "minimum": 1, "maximum": 200},
         "stimmung_nicht": {"type": "array", "items": {"type": "string"}, "description": "ausschliessen"},
         "stil_nicht": {"type": "array", "items": {"type": "string"}, "description": "ausschliessen"},
         "komponist": {"type": "array", "items": {"type": "string"}},
         "be_markiert": {"type": "boolean", "description": "nur Stuecke mit BE-Markierung (bestes Ende)"},
         "ordner": {"type": "array", "items": {"type": "string"}, "description": "Teil des Ordnernamens, * erlaubt"},
         "max_je_person": {"type": "integer", "minimum": 1, "description": "Vielfalt: hoechstens n je Interpret/DJ"},
         "gesamtdauer_min": {"type": "number", "description": "Sekunden; wird nur gemeldet, nicht erzwungen"}},
         "required": []}},
    {"name": "finde_titel",
     "description": "Sucht Musikstuecke nach Titel und zeigt, in welchen Playlists sie stehen.",
     "input_schema": {"type": "object",
                      "properties": {"text": {"type": "string"},
                                     "max_treffer": {"type": "integer", "minimum": 1, "maximum": 100}},
                      "required": ["text"]}},
    {"name": "finde_ordner",
     "description": "Sucht Musikordner nach Name (unscharf). Bei mehreren Treffern nachfragen.",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"},
                      "max_treffer": {"type": "integer", "minimum": 1, "maximum": 20}}, "required": ["text"]}},
    {"name": "plane_create_from_folder",
     "description": "Plant (Vorschau) eine Playlist aus einem Ordner in Album-/Set-Reihenfolge. Ordner exakt aus finde_ordner.",
     "input_schema": {"type": "object", "properties": {"ordner": {"type": "string"},
                      "max_anzeige": {"type": "integer", "minimum": 1, "maximum": 200}}, "required": ["ordner"]}},
    {"name": "zeige_playlist_status",
     "description": "Zeigt, welche Eintraege einer Playlist fehlen, beschaedigt oder nur Vorschlaege sind.",
     "input_schema": {"type": "object", "properties": {"playlist": {"type": "string"},
                      "quelle": {"type": "string", "enum": ["crates", "foobar_asus", "foobar_medion",
                                                            "mac_playlists", "musik_playlists"]},
                      "max_eintraege": {"type": "integer", "minimum": 1, "maximum": 200}}, "required": ["playlist"]}},
    {"name": "zeige_beschaedigte_ordner",
     "description": "Listet Ordner, die als 0-Byte-Datei verloren sind, mit betroffenen Playlist-Eintraegen.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "check_integrity",
     "description": ("Prueft den Stick auf Datenverlust seit dem letzten Lauf (verschwundene Dateien/Ordner, "
                     "0-Byte-Dateien, geaenderter Inhalt). Rein lesend; dauert bei vielen Aenderungen laenger."),
     "input_schema": {"type": "object", "properties": {"max_befunde": {"type": "integer", "minimum": 1,
                      "maximum": 500}}, "required": []}},
    {"name": "plane_update",
     "description": "Plant (Vorschau) das Uebertragen/Aktualisieren einer alten Playlist; nur sichere Eintraege.",
     "input_schema": {"type": "object", "properties": {"playlist": {"type": "string"},
                      "quelle": {"type": "string", "enum": ["crates", "foobar_asus", "foobar_medion",
                                                            "mac_playlists", "musik_playlists"]},
                      "max_anzeige": {"type": "integer", "minimum": 1, "maximum": 200}}, "required": ["playlist"]}},
]
AUSFUEHRBAR = {"status": status, "finde_playlist": finde_playlist, "zeige_vorschlaege": zeige_vorschlaege,
               "plane_playlist_nach_kriterien": plane_playlist_nach_kriterien, "finde_titel": finde_titel,
               "finde_ordner": finde_ordner, "plane_create_from_folder": plane_create_from_folder,
               "zeige_playlist_status": zeige_playlist_status,
               "zeige_beschaedigte_ordner": zeige_beschaedigte_ordner, "plane_update": plane_update,
               "check_integrity": check_integrity}


def rufe_auf(db: Datenbasis, name: str, argumente: dict) -> dict:
    """Einziger Einstieg fuer den Agent-Loop: unbekannte Werkzeuge -> Fehlermeldung statt Ausnahme."""
    if name not in AUSFUEHRBAR:
        return {"fehler": f"unbekanntes Werkzeug '{name}'", "verfuegbar": sorted(AUSFUEHRBAR)}
    argumente = dict(argumente or {})
    intern = [k for k in argumente if k.startswith("_")]
    if intern:
        # interne Parameter (z. B. Test-Haken) sind fuer das LLM gesperrt (Schutz vor Injektion)
        return {"fehler": f"nicht erlaubte Argumente: {intern}"}
    try:
        return AUSFUEHRBAR[name](db, **argumente)
    except TypeError as e:
        return {"fehler": f"falsche Argumente: {e}"}
