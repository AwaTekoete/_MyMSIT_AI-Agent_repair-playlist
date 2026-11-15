"""Nutzerentscheidungen ueber Vorschlaege (P13).

Identitaet (richtiger Song) ist Sache des Resolvers und der Gold-Labels; hier wird nur
die Reparaturart verwaltet:
  a  Playlist anpassen          -> Writer schreibt den Kandidaten
  b  Zurueckverschieben vorschlagen -> Eintrag bleibt offen, Verschiebe-Vorschlag im Bericht
                                   (Ausfuehrung nur durch den Nutzer, P1/P4)
  ?  offen                      -> Eintrag bleibt offen (P5)

Ebenen: Entscheidung je Track ist immer moeglich; optional eine Sammelentscheidung je
Ordnerpaar (alter Ordner -> neuer Ordner). Vorrang: Track vor Ordnerpaar vor offen.

Speicher = Protokoll (append-only): jede Entscheidung ist eine Zeile mit Zeitstempel;
die juengste Zeile je Schluessel gilt. Fruehere Entscheidungen bleiben nachvollziehbar.
Track-Schluessel = (eintrag, kandidat): aendert sich der Kandidat, gilt die alte
Entscheidung nicht mehr (Entscheidung bezog sich auf einen anderen Song-Ort).
Datei ist privat (echte Pfade, P11), z. B. data/decisions/entscheidungen.csv.
"""

from __future__ import annotations

import posixpath
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

AKTIONEN = {"a": "playlist_anpassen", "b": "zurueckverschieben_vorschlag", "?": "offen"}
EBENEN = ("track", "ordnerpaar")
SPALTEN = ["zeit", "ebene", "eintrag", "kandidat", "alter_ordner", "neuer_ordner", "aktion", "kommentar"]


def _norm(p: str) -> str:
    """NFC und '/' als Trenner, damit Crate-, Index- und Nutzerpfade vergleichbar sind."""
    return unicodedata.normalize("NFC", str(p)).replace("\\", "/")


def ordnerpaar(eintrag: str, kandidat: str) -> tuple[str, str]:
    """(alter Ordner, neuer Ordner) eines Vorschlags."""
    return posixpath.dirname(_norm(eintrag)), posixpath.dirname(_norm(kandidat))


def gruppiere_vorschlaege(df_vorschlag: pd.DataFrame) -> pd.DataFrame:
    """Vorschlaege (Spalten eintrag, pfad_ziel) um Ordnerpaar und Paar-ID O1.. ergaenzen.

    IDs nach Anzahl Tracks absteigend, bei Gleichstand alphabetisch -> reproduzierbar.
    """
    df = df_vorschlag.copy()
    paare = [ordnerpaar(e, k) for e, k in zip(df["eintrag"], df["pfad_ziel"])]
    df["alter_ordner"] = [a for a, _ in paare]
    df["neuer_ordner"] = [n for _, n in paare]
    groesse = df.groupby(["alter_ordner", "neuer_ordner"]).size().rename("n").reset_index()
    groesse = groesse.sort_values(["n", "alter_ordner", "neuer_ordner"],
                                  ascending=[False, True, True], ignore_index=True)
    groesse["paar_id"] = [f"O{i}" for i in range(1, len(groesse) + 1)]
    return df.merge(groesse[["alter_ordner", "neuer_ordner", "paar_id"]],
                    on=["alter_ordner", "neuer_ordner"], how="left")


def leeres_protokoll() -> pd.DataFrame:
    return pd.DataFrame(columns=SPALTEN)


def lade_entscheidungen(pfad) -> pd.DataFrame:
    """Protokoll laden; fehlt die Datei, ist das Protokoll leer (noch keine Entscheidung)."""
    pfad = Path(pfad)
    if not pfad.exists():
        return leeres_protokoll()
    return pd.read_csv(pfad, dtype=str, keep_default_na=False, encoding="utf-8")[SPALTEN]


def speichere_entscheidungen(df: pd.DataFrame, pfad) -> Path:
    """Protokoll speichern (laufend gepflegte Datei; Inhalt waechst nur durch Anhaengen)."""
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    df[SPALTEN].to_csv(pfad, index=False, encoding="utf-8")
    return pfad


def entscheide(df: pd.DataFrame, aktion: str, *, eintrag: str | None = None, kandidat: str | None = None,
               alter_ordner: str | None = None, neuer_ordner: str | None = None,
               kommentar: str = "", zeit: datetime | None = None) -> pd.DataFrame:
    """Neue Entscheidung anhaengen (Track: eintrag+kandidat; Ordnerpaar: alter+neuer Ordner)."""
    if aktion not in AKTIONEN:
        raise ValueError(f"Aktion {aktion!r} unbekannt, erlaubt: {list(AKTIONEN)}")
    if eintrag is not None and kandidat is not None:
        ebene = "track"
        alter_ordner, neuer_ordner = ordnerpaar(eintrag, kandidat)
    elif alter_ordner is not None and neuer_ordner is not None:
        ebene = "ordnerpaar"
    else:
        raise ValueError("Track (eintrag + kandidat) oder Ordnerpaar (alter_ordner + neuer_ordner) angeben")
    zeile = {"zeit": (zeit or datetime.now()).isoformat(timespec="seconds"), "ebene": ebene,
             "eintrag": _norm(eintrag) if ebene == "track" else "",
             "kandidat": _norm(kandidat) if ebene == "track" else "",
             "alter_ordner": _norm(alter_ordner), "neuer_ordner": _norm(neuer_ordner),
             "aktion": aktion, "kommentar": kommentar}
    return pd.concat([df, pd.DataFrame([zeile], columns=SPALTEN)], ignore_index=True)


def loese_auf(df_vorschlag: pd.DataFrame, df_protokoll: pd.DataFrame) -> pd.DataFrame:
    """Je Vorschlag gueltige Aktion und deren Ebene (Track > Ordnerpaar > offen).

    Eingabe: Spalten eintrag, pfad_ziel. Ausgabe: zusaetzlich alter_ordner, neuer_ordner,
    aktion (a/b/?), entschieden_auf (track/ordnerpaar/keine).
    """
    df = df_vorschlag.copy()
    paare = [ordnerpaar(e, k) for e, k in zip(df["eintrag"], df["pfad_ziel"])]
    df["alter_ordner"] = [a for a, _ in paare]
    df["neuer_ordner"] = [n for _, n in paare]

    # juengste Zeile je Schluessel (Protokoll ist zeitlich angehaengt -> letzte gilt)
    tr = df_protokoll[df_protokoll["ebene"] == "track"].drop_duplicates(["eintrag", "kandidat"], keep="last")
    op = df_protokoll[df_protokoll["ebene"] == "ordnerpaar"].drop_duplicates(
        ["alter_ordner", "neuer_ordner"], keep="last")
    je_track = dict(zip(zip(tr["eintrag"], tr["kandidat"]), tr["aktion"]))
    je_paar = dict(zip(zip(op["alter_ordner"], op["neuer_ordner"]), op["aktion"]))

    aktion, ebene = [], []
    for e, k, a, n in zip(df["eintrag"], df["pfad_ziel"], df["alter_ordner"], df["neuer_ordner"]):
        if (_norm(e), _norm(k)) in je_track:
            aktion.append(je_track[(_norm(e), _norm(k))]); ebene.append("track")
        elif (a, n) in je_paar:
            aktion.append(je_paar[(a, n)]); ebene.append("ordnerpaar")
        else:
            aktion.append("?"); ebene.append("keine")
    df["aktion"], df["entschieden_auf"] = aktion, ebene
    return df
