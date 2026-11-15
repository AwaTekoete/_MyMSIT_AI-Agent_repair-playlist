"""Aufloesungs-Kaskade (Workflow 4): kanonischer Pfad -> Klasse + Datei.

Stufen (Entscheidung 12.11.2026, Variante a):
  pfad               Pfad existiert (exakt/nach NFC)                  -> sicher
  pfadende           genau 1 Kandidat mit >= min_endteile gleichen
                     Endteilen (Ordner + Datei)                       -> sicher (Regel)
  name               nur Dateiname gleich, eindeutig                  -> Vorschlag (Regel)
  mojibake           wie pfadende/name, Name erst nach Reparatur
  mehrfach_bitgleich mehrere Kandidaten, alle gleicher SHA-256        -> sicher (Regel)
  mehrfach           mehrere verschiedene Kandidaten                  -> Vorschlag (Liste)
  0-byte-ordner      kein Kandidat, ein Elternordner ist 0-Byte-Datei -> Album beschaedigt
  ordner_leer        kein Kandidat, Elternordner ohne Dateien         -> fehlt
  kein_kandidat      sonst                                            -> fehlt
  Rückfall           nur bei 'fehlt' und %XX im Pfad: dekodiert erneut auflösen
Regeln als Parameter: Gold-Messung (Phase 3) kann Stufen herabstufen.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from urllib.parse import unquote

import pandas as pd

from playlist_agent.canon import nfc
from playlist_agent.index import ist_audio

# %XX-Muster (URL-Kodierung) in Einträgen ohne file:// (Befund 15.11.2026: 14 Einträge)
_PCT = re.compile(r"%[0-9A-Fa-f]{2}")


@dataclass
class Regeln:
    pfadende_sicher: bool = True
    name_sicher: bool = False
    bitgleich_sicher: bool = True
    min_endteile: int = 2


@dataclass
class Ergebnis:
    klasse: str                 # sicher | vorschlag | fehlt | album_beschaedigt
    stufe: str
    pfad: str | None
    kandidaten: list[str] = field(default_factory=list)
    grund: str = ""


def teile(p: str) -> list[str]:
    return [t for t in nfc(p).lower().split("/") if t]


def gleiche_endteile(a: str, b: str) -> int:
    """Anzahl uebereinstimmender Pfadteile von hinten (NFC, Kleinschreibung)."""
    x, y = teile(a), teile(b)
    n = 0
    while n < min(len(x), len(y)) and x[-1 - n] == y[-1 - n]:
        n += 1
    return n


def mojibake_reparieren(name: str) -> str:
    """'KÃ¤fer' -> 'Käfer' (UTF-8 als cp1252 gelesen); sonst unveraendert."""
    try:
        return name.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def ahnen(p: str) -> list[str]:
    """'Musik/A/B/x.mp3' -> ['Musik', 'Musik/A', 'Musik/A/B']."""
    t = p.split("/")
    return ["/".join(t[:i]) for i in range(1, len(t))]


class Resolver:
    def __init__(self, df_index: pd.DataFrame, audio_endungen: list[str],
                 leere_ordner: list[str] | tuple = (), regeln: Regeln | None = None):
        self.regeln = regeln or Regeln()
        audio = df_index[ist_audio(df_index, audio_endungen)]
        pfade = audio["pfad_relativ"].map(nfc)
        self._pfade = set(pfade)
        self._name_zu: dict[str, list[str]] = {}
        for p in pfade:
            self._name_zu.setdefault(posixpath.basename(p).lower(), []).append(p)
        self._hash = ({nfc(p): h for p, h in zip(df_index["pfad_relativ"], df_index["sha256"])
                       if isinstance(h, str)} if "sha256" in df_index.columns else {})
        self._null = set(df_index.loc[df_index["bytes"] == 0, "pfad_relativ"].map(nfc))
        self._leer = {nfc(o) for o in leere_ordner}

    def _klasse(self, sicher: bool) -> str:
        return "sicher" if sicher else "vorschlag"

    def aufloesen(self, kanon: str) -> Ergebnis:
        """Kaskade; Rückfall %-Dekodierung nur, wenn der unveränderte Pfad 'fehlt'.

        Unverändert zuerst: 1 echte Datei im Index hat ein %XX-Muster im Namen (NB04 Z.17).
        """
        e = self._aufloesen_roh(kanon)
        if e.klasse == "fehlt" and _PCT.search(kanon):
            d = self._aufloesen_roh(unquote(kanon))
            if d.klasse != "fehlt":
                d.grund = f"{d.grund} (nach %-Dekodierung)"
                return d
        return e

    def _aufloesen_roh(self, kanon: str) -> Ergebnis:
        r, p = self.regeln, nfc(kanon)
        if p in self._pfade:
            return Ergebnis("sicher", "pfad", p, [p], "Pfad existiert")

        name, stufe_name, p_vgl = posixpath.basename(p), "name", p
        kand = self._name_zu.get(name.lower(), [])
        if not kand:
            rep = nfc(mojibake_reparieren(name))
            if rep != name and (kand := self._name_zu.get(rep.lower(), [])):
                p_vgl, stufe_name = posixpath.join(posixpath.dirname(p), rep), "mojibake"

        if kand:
            endteile = {c: gleiche_endteile(p_vgl, c) for c in kand}
            best = max(endteile.values())
            beste = [c for c, n in endteile.items() if n == best]
            if len(kand) == 1 or (best >= r.min_endteile and len(beste) == 1):
                c = beste[0]
                if best >= r.min_endteile:
                    stufe = "pfadende" if stufe_name == "name" else stufe_name
                    return Ergebnis(self._klasse(r.pfadende_sicher), stufe, c, sorted(kand),
                                    f"{best} Endteile gleich")
                return Ergebnis(self._klasse(r.name_sicher), stufe_name, c, sorted(kand),
                                "nur Dateiname gleich")
            hashes = {self._hash.get(c) for c in kand}
            if None not in hashes and len(hashes) == 1:
                return Ergebnis(self._klasse(r.bitgleich_sicher), "mehrfach_bitgleich",
                                sorted(kand)[0], sorted(kand), f"{len(kand)} bitgleiche Kandidaten")
            return Ergebnis("vorschlag", "mehrfach", None, sorted(kand),
                            f"{len(kand)} verschiedene Kandidaten")

        anc = ahnen(p)
        if any(a in self._null for a in anc):
            return Ergebnis("album_beschaedigt", "0-byte-ordner", None, [], "Ordner ist 0-Byte-Datei")
        if any(a in self._leer for a in anc):
            return Ergebnis("fehlt", "ordner_leer", None, [], "Ordner ohne Dateien")
        return Ergebnis("fehlt", "kein_kandidat", None, [], "Name nicht im Index")
  

def regeln_aus_config(cfg: dict) -> Regeln:
    """Regeln aus cfg["resolver"]; fehlende Schlüssel = Standardwert der Klasse Regeln.

    Unbekannte Schlüssel (z. B. Tippfehler) führen zum Abbruch: ein stillschweigend
    ignorierter Schalter würde eine Entscheidung unbemerkt außer Kraft setzen.
    """
    import dataclasses
    werte = cfg.get("resolver") or {}
    unbekannt = set(werte) - {f.name for f in dataclasses.fields(Regeln)}
    if unbekannt:
        raise ValueError(f"Unbekannte Resolver-Regeln in config.yaml: {sorted(unbekannt)}")
    return Regeln(**werte)