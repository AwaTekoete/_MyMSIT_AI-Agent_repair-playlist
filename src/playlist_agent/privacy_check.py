"""Prüfung vor dem Commit: keine echten Pfade, Titel oder Namen im public Repo.

Prüft die zum Commit vorgemerkten Textdateien – mit dem Inhalt, der tatsächlich
committet wird (nach nbstripout) – gegen private Begriffe:
  - Ordner- und Dateinamen aus dem privaten Index (data/raw/index/musik_index.csv)
  - Crate-Namen (data/raw/crates/*.crate)
  - Inhalte privater Eingabe- und Gold-Dateien (data/gold/*.txt, *.csv)
  - zusätzliche Begriffe aus .env: PRIVATE_TERMS (kommagetrennt)
Bewusst erlaubte Begriffe aus .env: ALLOWED_TERMS (z. B. entschiedene Ausnahmen).
Automatisch abgeleitete Begriffe erst ab MIN_LAENGE Zeichen (sonst zu viele
Fehlalarme durch allgemeine Wörter wie "Musik").

Aufruf: python -m playlist_agent.privacy_check   -> Exit-Code 1 bei Fund.
"""

from __future__ import annotations

import subprocess
import sys
import unicodedata
from pathlib import Path

import pandas as pd
from dotenv import dotenv_values

MIN_LAENGE = 8
TEXT_ENDUNGEN = {".ipynb", ".py", ".md", ".csv", ".yaml", ".yml", ".toml", ".txt", ".json"}

# Allgemeine Wörter, die zufällig auch als Datei-/Ordnername auf dem Stick
# vorkommen, aber Teil des Projektvokabulars sind (Fehlalarme, belegt 09.11.2026).
# "neuer ordner": Windows-Standardname eines Ordners auf dem Stick und Projektvokabular (P13),
# kein privates Merkmal (Fehlalarm 15.11.2026).
GENERISCHE_BEGRIFFE = {"playlist", "software", "neuer ordner"}

def _norm(s: str) -> str:
    """NFC + Kleinschreibung: gleiche Schreibweise unabhängig von Kodierung."""
    return unicodedata.normalize("NFC", s).lower()


def _git(*args: str) -> bytes:
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def _pfad_teile(pfad: str) -> set[str]:
    """'Musik/A/b.mp3' -> {'A', 'b'} (Ordnernamen und Dateiname ohne Endung)."""
    teile = pfad.replace("\\", "/").split("/")[1:]
    return {t.rsplit(".", 1)[0] if "." in t else t for t in teile if t}


def lese_gold_csv(pfad: Path) -> list[str]:
    """Alle nichtleeren Textwerte einer Gold-CSV; Trenner ';' oder ',' (BOM-fest).

    Gold-Dateien ab NB04 Z.10 nutzen ';' (Excel-tauglich), ältere ',' (Befund 15.11.2026:
    Komma-Annahme brach den Check ab). Trenner aus der Kopfzeile: häufigeres Zeichen gewinnt.
    """
    erste = Path(pfad).read_text(encoding="utf-8-sig").split("\n", 1)[0]
    sep = ";" if erste.count(";") > erste.count(",") else ","
    df = pd.read_csv(pfad, sep=sep, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    return [w for w in df.to_numpy().ravel() if isinstance(w, str) and w]


def private_begriffe(root: Path) -> tuple[set[str], list[str]]:
    abgeleitet: set[str] = set()
    idx = root / "data/raw/index/musik_index.csv"
    if idx.exists():
        for p in pd.read_csv(idx)["pfad_relativ"]:
            abgeleitet |= _pfad_teile(p)
    abgeleitet |= {f.stem for f in (root / "data/raw/crates").glob("*.crate")}
    for f in (root / "data/gold").glob("*.txt"):
        abgeleitet |= {z.strip() for z in f.read_text(encoding="utf-8").splitlines()}
    for f in (root / "data/gold").glob("*.csv"):
        for wert in lese_gold_csv(f):
            if "/" in wert or "\\" in wert:             # auch Windows-Pfade aus Gold-Originalen
                abgeleitet |= _pfad_teile(wert)

    env = dotenv_values(root / ".env")
    explizit = {t.strip() for t in (env.get("PRIVATE_TERMS") or "").split(",") if t.strip()}
    erlaubt = [_norm(t.strip()) for t in (env.get("ALLOWED_TERMS") or "").split(",") if t.strip()]

    begriffe = {_norm(b) for b in abgeleitet if len(b.strip()) >= MIN_LAENGE}
    begriffe -= GENERISCHE_BEGRIFFE
    begriffe |= {_norm(b) for b in explizit}          # explizite Begriffe ohne Mindestlänge
    return begriffe, erlaubt


def pruefe() -> int:
    root = Path(_git("rev-parse", "--show-toplevel").decode().strip())
    begriffe, erlaubt = private_begriffe(root)
    # splitlines statt split: Dateinamen mit Leerzeichen bleiben ganz (sonst ungeprüft)
    dateien = _git("diff", "--cached", "--name-only", "--diff-filter=ACM").decode("utf-8").splitlines()
    dateien = [d for d in dateien if Path(d).suffix.lower() in TEXT_ENDUNGEN]

    funde = []
    for d in dateien:
        text = _norm(_git("show", f":{d}").decode("utf-8", errors="replace"))
        for e in erlaubt:                              # bewusst erlaubte Stellen ausblenden
            text = text.replace(e, "")
        funde += [(d, b) for b in sorted(begriffe) if b in text]

    print(f"Geprüft: {len(dateien)} vorgemerkte Textdatei(en) gegen {len(begriffe)} private Begriffe")
    for d, b in funde:
        print(f"  FUND  {d}: '{b}'")
    print("Ergebnis:", "FEHLER – nicht committen" if funde else "OK – keine privaten Begriffe")
    return 1 if funde else 0


if __name__ == "__main__":
    sys.exit(pruefe())