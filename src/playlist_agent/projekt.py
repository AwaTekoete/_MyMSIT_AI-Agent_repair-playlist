"""Gemeinsamer Projekt-Kontext fuer alle Notebooks (Arbeitspaket 4.8).

Ersetzt die kopierte Setup-Zelle 01 je Notebook:
- Projektwurzel ueber pyproject.toml finden (unabhaengig vom Ordnernamen und
  davon, ob das Notebook aus notebooks/ oder der Wurzel gestartet wird)
- config.yaml laden, Standardpfade (data/, reports/) bereitstellen
- tabelle_speichern(): Namensschema <NB>_<Zelle>_<slug>; ueberschreibt nie
  stillschweigend (Befund 15.11.2026: NB02-Tabellen bei erneutem Lauf geaendert)
- stick(): Musiktraeger ueber anchor.verankere (Signatur aus config.yaml),
  keine eigene Laufwerkssuche in Notebooks

Rein lesend bis auf tabelle_speichern (schreibt nur nach reports/ bzw. data/).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import yaml

from playlist_agent import anchor
from playlist_agent.viz_config import ARTEFAKT_MUSTER

SEED = 42


class ArtefaktGeaendert(FileExistsError):
    """Datei existiert mit anderem Inhalt; Ueberschreiben nur ausdruecklich."""


def projekt_wurzel(start: Path | None = None) -> Path:
    """Erster Ordner ab start (Standard: aktuelles Verzeichnis) aufwaerts mit pyproject.toml."""
    p = Path.cwd() if start is None else Path(start)
    for kandidat in (p, *p.parents):
        if (kandidat / "pyproject.toml").is_file():
            return kandidat
    raise FileNotFoundError(f"Keine Projektwurzel (pyproject.toml) oberhalb von {p}")


@dataclass(frozen=True)
class Kontext:
    wurzel: Path
    cfg: dict
    raw: Path
    interim: Path
    gold: Path
    fig: Path
    tab: Path
    err: Path
    seed: int = SEED


def kontext(start: Path | None = None) -> Kontext:
    """Projekt-Kontext: Wurzel, Konfiguration und Standardpfade."""
    w = projekt_wurzel(start)
    cfg = yaml.safe_load((w / "config" / "config.yaml").read_text(encoding="utf-8"))
    return Kontext(wurzel=w, cfg=cfg,
                   raw=w / "data" / "raw", interim=w / "data" / "interim",
                   gold=w / "data" / "gold", fig=w / "reports" / "figures",
                   tab=w / "reports" / "tables", err=w / "reports" / "errors")


def tabelle_speichern(df: pd.DataFrame, name: str, ordner: Path,
                      ueberschreiben: bool = False) -> Path:
    """CSV nach <ordner>/<name>.csv; Name nach Schema <NB>_<Zelle>_<slug>.

    Datei fehlt -> schreiben. Datei existiert mit gleichem Inhalt -> nichts tun
    ("Run All" bleibt lauffaehig). Datei existiert mit anderem Inhalt ->
    ArtefaktGeaendert, ausser ueberschreiben=True. Meldet Pfad und Zeilenzahl.
    """
    if not ARTEFAKT_MUSTER.match(name):
        raise ValueError(f"Name '{name}' entspricht nicht <NB>_<Zelle>_<slug>.")
    pfad = Path(ordner) / f"{name}.csv"
    # Zeilenende fest LF; Vergleich unabhaengig von CRLF/LF (Windows-Uebersetzung,
    # aeltere Artefakte wurden mit CRLF geschrieben)
    neu = df.to_csv(index=False, lineterminator="\n")
    anzeige = "/".join(pfad.parts[-3:])          # z. B. reports/errors/06_02_....csv
    if pfad.exists() and not ueberschreiben:
        # beide Seiten gleich normalisieren: Feldwerte koennen selbst CRLF enthalten
        # (z. B. mehrzeilige Comments, Befund 22.11.2026)
        alt = pfad.read_bytes().decode("utf-8").replace("\r\n", "\n")
        if alt == neu.replace("\r\n", "\n"):
            print(f"vorhanden (unveraendert): {anzeige} ({len(df)} Zeilen)")
            return pfad
        raise ArtefaktGeaendert(
            f"{pfad.name} existiert mit anderem Inhalt; Ergebnis hat sich geaendert. "
            "Pruefen, dann bewusst mit ueberschreiben=True speichern.")
    pfad.write_bytes(neu.encode("utf-8"))
    print(f"gespeichert: {anzeige} ({len(df)} Zeilen)")
    return pfad


def stick(cfg: dict) -> Path:
    """Wurzel des Musiktraegers ueber die Ordner-Signatur (anchor.verankere)."""
    return anchor.verankere(cfg).wurzel
