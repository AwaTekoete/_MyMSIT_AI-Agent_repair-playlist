"""Aufloesungs-Kaskade (Workflow 4): kanonischer Pfad -> Klasse + Datei.

Stufen (Entscheidungen 12.11., 20.11., 21.11.2026):
  pfad                  Pfad existiert (exakt/nach NFC)                   -> sicher
  pfadende              genau 1 Kandidat mit >= min_endteile gleichen
                        Endteilen (Ordner + Datei)                        -> sicher (Regel)
  name                  nur Dateiname gleich, eindeutig                   -> Vorschlag (Regel)
  mojibake              wie pfadende/name, Name erst nach Reparatur
  mehrfach_bitgleich    alle Kandidaten gleicher SHA-256; Ort = hoechster
                        Ordner-Jaccard (eindeutig), sonst Vorschlag        -> sicher (Regel)
  mehrfach_audiogleich  alle Kandidaten gleicher Audio-Hash (ohne Tags);
                        Ort wie oben                                      -> sicher (Regel)
  mehrfach              mehrere verschiedene Kandidaten                   -> Vorschlag (Liste)
  0-byte-ordner         ein Elternordner ist 0-Byte-Datei                 -> Album beschaedigt
  0-byte-ordner-praefix wie oben nach Ergaenzung des Praefixes 'Musik/'   -> Album beschaedigt
  0-byte-ordner-lose    Ordnername nur ohne Gross/Klein/Satzzeichen gleich
                        einer 0-Byte-Datei (Hinweis)                      -> Album beschaedigt
  zeichen (R1)          Ordner vorhanden; Name bis auf Rand-Leerzeichen,
                        Gross/Klein oder 1 verlorenes Zeichen gleich      -> sicher (Regel)
  praefix (R2)          Ordner vorhanden; einzige Datei = Name + Anhang   -> Vorschlag
  tracknummer (R3)      Ordner vorhanden oder eindeutig per Ordner-Jaccard;
                        einzige Datei mit gleicher fuehrender Nummer,
                        nicht "Name + Anhang" (Veto V3)                   -> Vorschlag
  ordner_leer           Elternordner ohne Dateien                         -> fehlt
  kein_kandidat         sonst                                             -> fehlt
  Rueckfall             nur bei 'fehlt' und %XX im Pfad: dekodiert erneut aufloesen
Belege: NB04 (Phase 3), NB05 Zellen 11-33 (Gold + Negativkontrollen).
Regeln als Parameter (config.yaml, Abschnitt resolver).
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from urllib.parse import unquote

import pandas as pd

from playlist_agent.canon import nfc
from playlist_agent.index import ist_audio

# %XX-Muster (URL-Kodierung) in Eintraegen ohne file:// (Befund 15.11.2026: 14 Eintraege)
_PCT = re.compile(r"%[0-9A-Fa-f]{2}")
# Fuehrende Tracknummer, gefolgt von Trenner (NB05 Z.28)
_NUM = re.compile(r"^(\d{1,3})(?=[\s_.\-])")
_WORT = re.compile(r"[0-9a-z]+")


@dataclass
class Regeln:
    pfadende_sicher: bool = True
    name_sicher: bool = False
    bitgleich_sicher: bool = True
    min_endteile: int = 2
    audiogleich_sicher: bool = True
    zeichen_sicher: bool = True
    praefix_aktiv: bool = True
    tracknummer_aktiv: bool = True
    nullbyte_lose: bool = True
    jaccard_min: float = 0.5


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


# --- Hilfsfunktionen Phase 4 (NB05) ------------------------------------------------

def stamm_endung(name: str) -> tuple[str, str]:
    """Stamm (ohne Rand-Leerzeichen, casefold) und Endung (casefold)."""
    stamm, endung = posixpath.splitext(nfc(name))
    return stamm.strip().casefold(), endung.casefold()


def zeichen_gleich(gesucht: str, kandidat: str) -> bool:
    """R1: gleiche Endung und Laenge; Unterschied hoechstens 1 Zeichen, das im
    gesuchten Namen ' ', '?' oder U+FFFD ist (verlorenes Zeichen)."""
    g, ge = stamm_endung(gesucht)
    s, se = stamm_endung(kandidat)
    if se != ge or len(s) != len(g):
        return False
    diff = [i for i, (a, b) in enumerate(zip(g, s)) if a != b]
    return not diff or (len(diff) == 1 and g[diff[0]] in " ?�")


def ist_anhang(gesucht: str, kandidat: str) -> bool:
    """R2 / Veto V3: Kandidat = gesuchter Name + Anhang (gleiche Endung)."""
    g, ge = stamm_endung(gesucht)
    s, se = stamm_endung(kandidat)
    return se == ge and len(s) > len(g) and s.startswith(g)


def tracknummer(name: str) -> int | None:
    m = _NUM.match(nfc(name))
    return int(m.group(1)) if m else None


def jaccard(a: str, b: str) -> float:
    """Anteil gemeinsamer Woerter/Zahlen zweier Namen (casefold, NFC)."""
    wa, wb = set(_WORT.findall(nfc(a).casefold())), set(_WORT.findall(nfc(b).casefold()))
    return len(wa & wb) / len(wa | wb) if wa | wb else 0.0


def lose(name: str) -> str:
    """Name ohne Gross/Klein und ohne Satz-/Leerzeichen (Vergleich 0-Byte-Ordner)."""
    return re.sub(r"[^0-9a-z]", "", nfc(name).casefold())


class Resolver:
    def __init__(self, df_index: pd.DataFrame, audio_endungen: list[str],
                 leere_ordner: list[str] | tuple = (), regeln: Regeln | None = None,
                 musik: str = "Musik"):
        self.regeln = regeln or Regeln()
        self._musik = musik
        audio_maske = ist_audio(df_index, audio_endungen)
        audio = df_index[audio_maske]
        pfade = audio["pfad_relativ"].map(nfc)
        self._pfade = set(pfade)
        self._name_zu: dict[str, list[str]] = {}
        self._ordner_dateien: dict[str, list[str]] = {}
        for p in pfade:
            self._name_zu.setdefault(posixpath.basename(p).lower(), []).append(p)
            self._ordner_dateien.setdefault(posixpath.dirname(p), []).append(posixpath.basename(p))
        self._hash = ({nfc(p): h for p, h in zip(df_index["pfad_relativ"], df_index["sha256"])
                       if isinstance(h, str)} if "sha256" in df_index.columns else {})
        self._audio = ({nfc(p): h for p, h in zip(df_index["pfad_relativ"], df_index["audio_sha256"])
                        if isinstance(h, str)} if "audio_sha256" in df_index.columns else {})
        self._null = set(df_index.loc[df_index["bytes"] == 0, "pfad_relativ"].map(nfc))
        null_ordner = df_index.loc[(df_index["bytes"] == 0) & ~audio_maske, "pfad_relativ"].map(nfc)
        self._null_lose = {lose(posixpath.basename(p)): p for p in null_ordner}
        self._leer = {nfc(o) for o in leere_ordner}
        self._ordner_alle = {a for p in df_index["pfad_relativ"].map(nfc) for a in ahnen(p)}
        self._ordner_alle |= self._leer

    def _klasse(self, sicher: bool) -> str:
        return "sicher" if sicher else "vorschlag"

    def aufloesen(self, kanon: str) -> Ergebnis:
        """Kaskade; Rueckfall %-Dekodierung nur, wenn der unveraenderte Pfad 'fehlt'.

        Unveraendert zuerst: 1 echte Datei im Index hat ein %XX-Muster im Namen (NB04 Z.17).
        """
        e = self._aufloesen_roh(kanon)
        if e.klasse == "fehlt" and _PCT.search(kanon):
            d = self._aufloesen_roh(unquote(kanon))
            if d.klasse != "fehlt":
                d.grund = f"{d.grund} (nach %-Dekodierung)"
                return d
        return e

    def _ort(self, p: str, kand: list[str]) -> str | None:
        """Kandidat mit hoechstem Ordner-Jaccard zum Playlist-Ordner; None bei Gleichstand."""
        b = posixpath.basename(posixpath.dirname(p))
        werte = sorted(((jaccard(b, posixpath.basename(posixpath.dirname(c))), c) for c in kand),
                       key=lambda t: (-t[0], t[1]))
        if len(werte) == 1 or werte[0][0] > werte[1][0]:
            return werte[0][1]
        return None

    def _mehrfach_gleich(self, p: str, kand: list[str], stufe: str, sicher: bool,
                         was: str) -> Ergebnis:
        ort = self._ort(p, kand)
        if ort is None:
            return Ergebnis("vorschlag", stufe, None, sorted(kand),
                            f"{len(kand)} {was}e Kandidaten, Ort nicht eindeutig")
        return Ergebnis(self._klasse(sicher), stufe, ort, sorted(kand),
                        f"{len(kand)} {was}e Kandidaten, Ort nach Ordnername")

    def _zielordner_r3(self, ordner: str) -> str | None:
        """Vorhandener Ordner, mit ergaenztem Praefix, oder eindeutig per Ordner-Jaccard."""
        if ordner in self._ordner_dateien:
            return ordner
        mit = f"{self._musik}/{ordner}"
        if not ordner.startswith(self._musik + "/") and mit in self._ordner_dateien:
            return mit
        b = posixpath.basename(ordner)
        if not b:
            return None
        werte = sorted((jaccard(b, posixpath.basename(o)), o) for o in self._ordner_dateien)[::-1]
        if not werte or werte[0][0] < self.regeln.jaccard_min:
            return None
        if len(werte) > 1 and werte[1][0] == werte[0][0]:
            return None
        return werte[0][1]

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
                return self._mehrfach_gleich(p, kand, "mehrfach_bitgleich",
                                             r.bitgleich_sicher, "bitgleich")
            audio = {self._audio.get(c) for c in kand}
            if None not in audio and len(audio) == 1:
                return self._mehrfach_gleich(p, kand, "mehrfach_audiogleich",
                                             r.audiogleich_sicher, "audiogleich")
            return Ergebnis("vorschlag", "mehrfach", None, sorted(kand),
                            f"{len(kand)} verschiedene Kandidaten")

        # --- kein Namenskandidat ----------------------------------------------------
        if any(a in self._null for a in ahnen(p)):
            return Ergebnis("album_beschaedigt", "0-byte-ordner", None, [], "Ordner ist 0-Byte-Datei")

        ordner = posixpath.dirname(p)
        if ordner and ordner not in self._ordner_alle:           # Ordner fehlt (NB05 Z.23)
            if not p.startswith(self._musik + "/"):
                mit = f"{self._musik}/{p}"
                if any(a in self._null for a in ahnen(mit)):
                    return Ergebnis("album_beschaedigt", "0-byte-ordner-praefix", None, [],
                                    f"Ordner ist 0-Byte-Datei (Praefix '{self._musik}/' ergaenzt)")
            if r.nullbyte_lose:
                for t in ordner.split("/"):
                    if t != self._musik and lose(t) in self._null_lose:
                        return Ergebnis("album_beschaedigt", "0-byte-ordner-lose", None,
                                        [self._null_lose[lose(t)]],
                                        "Ordner vermutlich 0-Byte-Datei (Name nur aehnlich)")

        dateien = self._ordner_dateien.get(ordner, [])
        if dateien:                                              # R1, R2 (NB05 Z.11-22)
            r1 = [d for d in dateien if zeichen_gleich(name, d)]
            if len(r1) == 1:
                ziel = f"{ordner}/{r1[0]}"
                return Ergebnis(self._klasse(r.zeichen_sicher), "zeichen", ziel, [ziel],
                                "Name bis auf Leer-/Gross-Klein-/1 verlorenes Zeichen gleich")
            if r.praefix_aktiv:
                r2 = [d for d in dateien if ist_anhang(name, d)]
                if len(r2) == 1:
                    ziel = f"{ordner}/{r2[0]}"
                    return Ergebnis("vorschlag", "praefix", ziel, [ziel],
                                    "Name + Anhang (Version oder Umbenennung)")

        nr = tracknummer(name)
        if r.tracknummer_aktiv and nr is not None:               # R3 + V3 (NB05 Z.28-33)
            zo = self._zielordner_r3(ordner)
            if zo:
                r3 = [d for d in self._ordner_dateien.get(zo, []) if tracknummer(d) == nr]
                if len(r3) == 1 and not ist_anhang(name, r3[0]):
                    ziel = f"{zo}/{r3[0]}"
                    return Ergebnis("vorschlag", "tracknummer", ziel, [ziel],
                                    f"gleiche Tracknummer {nr:02d} im Ordner")

        if any(a in self._leer for a in ahnen(p)):
            return Ergebnis("fehlt", "ordner_leer", None, [], "Ordner ohne Dateien")
        return Ergebnis("fehlt", "kein_kandidat", None, [], "Name nicht im Index")


def regeln_aus_config(cfg: dict) -> Regeln:
    """Regeln aus cfg["resolver"]; fehlende Schluessel = Standardwert der Klasse Regeln.

    Unbekannte Schluessel (z. B. Tippfehler) fuehren zum Abbruch: ein stillschweigend
    ignorierter Schalter wuerde eine Entscheidung unbemerkt ausser Kraft setzen.
    """
    import dataclasses
    werte = cfg.get("resolver") or {}
    unbekannt = set(werte) - {f.name for f in dataclasses.fields(Regeln)}
    if unbekannt:
        raise ValueError(f"Unbekannte Resolver-Regeln in config.yaml: {sorted(unbekannt)}")
    return Regeln(**werte)
