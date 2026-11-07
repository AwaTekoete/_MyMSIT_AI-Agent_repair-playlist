"""Store44-Visualisierungsstil fuer alle Grafiken im Projekt.

Quelle der Farben: Praesentationsstil_Store44.md.
Grundsatz: Farbe traegt Bedeutung (Gold = wichtigste Zahl,
Blau = Vergleichswert, Gruen = Loesung/Champion), sonst nicht.
Alle Grafiken werden ueber figur_speichern() abgelegt; die Funktion
erzwingt das Namensschema <NB>_<Zelle>_<slug> aus den Projektanweisungen.
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

# --- Farbpalette laut Praesentationsstil_Store44.md --------------------------
FARBEN = {
    "hintergrund": "#1C1C1C",   # alle Flaechen
    "karte": "#2A2A2A",         # Achsenhintergrund, Boxen
    "gruen": "#4A5C3A",         # Champion / Loesung
    "gold": "#F5A623",          # wichtigste Kennzahl
    "blau": "#6CB4E4",          # Vergleichswert
    "text": "#FFFFFF",
    "text_gedimmt": "#AAAAAA",
}

# Namensschema fuer Artefakte: zwei Ziffern Notebook, zwei Ziffern Zelle, slug
ARTEFAKT_MUSTER = re.compile(r"^\d{2}_\d{2}_[a-z0-9_]+$")


def stil_aktivieren() -> None:
    """Setzt den Store44-Stil global fuer alle folgenden matplotlib-Grafiken."""
    mpl.rcParams.update({
        # Flaechen: durchgehend dunkel (Store44: kein heller Hintergrund)
        "figure.facecolor": FARBEN["hintergrund"],
        "axes.facecolor": FARBEN["karte"],
        "savefig.facecolor": FARBEN["hintergrund"],
        # Text und Achsen: ausreichender Kontrast auf dunklem Grund
        "text.color": FARBEN["text"],
        "axes.labelcolor": FARBEN["text"],
        "axes.edgecolor": FARBEN["text_gedimmt"],
        "xtick.color": FARBEN["text_gedimmt"],
        "ytick.color": FARBEN["text_gedimmt"],
        "axes.titlecolor": FARBEN["text"],
        # Reihenfolge der Standardfarben: Bedeutungsfarben zuerst
        "axes.prop_cycle": mpl.cycler(
            color=[FARBEN["gold"], FARBEN["blau"], FARBEN["gruen"]]
        ),
        # Raster dezent, Schrift mind. 12 pt (Store44-Regel)
        "axes.grid": True,
        "grid.color": FARBEN["text_gedimmt"],
        "grid.alpha": 0.2,
        "font.size": 12,
        "font.family": ["Calibri", "Arial", "DejaVu Sans"],
    })


def figur_speichern(fig: plt.Figure, name: str, ordner: str | Path,
                    dpi: int = 150) -> Path:
    """Speichert eine Grafik als PNG nach dem Namensschema <NB>_<Zelle>_<slug>.

    Bricht mit ValueError ab, wenn der Name nicht dem Schema entspricht -
    so entstehen keine falsch benannten Artefakte (Lehre aus Vorprojekt).
    """
    if not ARTEFAKT_MUSTER.match(name):
        raise ValueError(
            f"Name '{name}' entspricht nicht dem Schema <NB>_<Zelle>_<slug>, "
            "z. B. '02_07_abgleichsraten_crates'."
        )
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    pfad = ordner / f"{name}.png"
    fig.savefig(pfad, dpi=dpi, bbox_inches="tight")
    return pfad