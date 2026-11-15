"""Verankerung (Workflow-Schritt 0): Stick finden, Ziel-Laptop bestimmen.

Primaeres Merkmal ist die Ordner-Signatur aus config.yaml (alle Laufwerke A-Z),
nicht der Laufwerksbuchstabe: Windows vergibt Buchstaben je nach eingesteckten
Geraeten neu. Ein abweichender Buchstabe ist daher nur ein Hinweis, kein Fehler.
Hostname -> Laptop-Eintrag aus config.yaml; Windows-Hostnamen sind ohne
Gross-/Kleinschreibung eindeutig -> Vergleich mit casefold().

Seriennummer: optional ueber eine uebergebene Pruef-Funktion (Bestaetigung,
nicht Erkennung); ohne Funktion bleibt der Status "nicht geprueft" (None).
Rein lesend.
"""

from __future__ import annotations

import socket
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


class StickNichtGefunden(RuntimeError):
    """Kein Laufwerk erfuellt die Signatur."""


class StickMehrdeutig(RuntimeError):
    """Mehr als ein Laufwerk erfuellt die Signatur."""


class HostUnbekannt(LookupError):
    """Hostname steht nicht in config.yaml (Selbstregistrierung: Phase 7)."""


@dataclass
class Anker:
    wurzel: Path
    laufwerk: str                     # z. B. "D:" (leer ausserhalb von Windows-Laufwerken)
    hostname: str
    laptop: dict                      # Eintrag aus cfg["laptops"]
    laufwerk_wie_konfiguriert: bool   # Hinweis, kein Abbruch
    seriennummer_ok: bool | None      # None = nicht geprueft


def laufwerks_wurzeln() -> list[Path]:
    """Vorhandene Laufwerkswurzeln A:/ bis Z:/ (Windows)."""
    return [Path(f"{lw}:/") for lw in string.ascii_uppercase if Path(f"{lw}:/").exists()]


def signatur_treffer(wurzel: Path, signatur: Iterable[str]) -> int:
    """Anzahl der Signatur-Ordner, die unter der Wurzel als Ordner existieren."""
    return sum((Path(wurzel) / s).is_dir() for s in signatur)


def finde_stick(signatur: list[str], min_treffer: int | None = None,
                wurzeln: Iterable[Path] | None = None) -> Path:
    """Einzige Wurzel mit mindestens min_treffer Signatur-Ordnern (Standard: alle).

    wurzeln: fuer Tests; Standard = alle vorhandenen Laufwerke.
    """
    min_treffer = len(signatur) if min_treffer is None else min_treffer
    kandidaten = laufwerks_wurzeln() if wurzeln is None else [Path(w) for w in wurzeln]
    treffer = [w for w in kandidaten if signatur_treffer(w, signatur) >= min_treffer]
    if not treffer:
        raise StickNichtGefunden(
            f"Stick nicht gefunden – bitte einstecken (geprueft: {len(kandidaten)} Laufwerke, "
            f"Signatur {min_treffer}/{len(signatur)} Ordner)")
    if len(treffer) > 1:
        raise StickMehrdeutig(f"Signatur auf mehreren Laufwerken: {[str(t) for t in treffer]} – "
                              "nur einen Musiktraeger einstecken")
    return treffer[0]


def laptop_fuer_host(laptops: list[dict], hostname: str | None = None) -> dict:
    """Laptop-Eintrag zum Hostnamen (Standard: Hostname dieses Rechners)."""
    hostname = socket.gethostname() if hostname is None else hostname
    passend = [l for l in laptops if str(l.get("hostname", "")).casefold() == hostname.casefold()]
    if not passend:
        raise HostUnbekannt(f"Hostname {hostname!r} unbekannt – in config.yaml eintragen "
                            "(Selbstregistrierung: Phase 7)")
    return passend[0]


def verankere(cfg: dict, hostname: str | None = None, wurzeln: Iterable[Path] | None = None,
              seriennummer_pruefen: Callable[[Path], bool] | None = None) -> Anker:
    """Workflow-Schritt 0 komplett: Stick + Laptop + Hinweise."""
    st = cfg["stick"]
    wurzel = finde_stick(st["signatur"], st.get("signatur_min_treffer"), wurzeln)
    hostname = socket.gethostname() if hostname is None else hostname
    laptop = laptop_fuer_host(cfg["laptops"], hostname)
    laufwerk = wurzel.drive if wurzel.drive else ""
    return Anker(
        wurzel=wurzel, laufwerk=laufwerk, hostname=hostname, laptop=laptop,
        laufwerk_wie_konfiguriert=laufwerk.upper() == str(laptop.get("laufwerk_beobachtet", "")).upper(),
        seriennummer_ok=None if seriennummer_pruefen is None else bool(seriennummer_pruefen(wurzel)),
    )
