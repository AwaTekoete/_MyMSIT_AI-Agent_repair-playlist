"""Bestaetigungs-Gate (Paket 5.2), Teil 1: dauerhafte Plaene.

Ablauf (P9): Plan -> Vorschau -> Bestaetigung -> Ausfuehrung -> Bericht.
Ein Plan wird beim Erstellen als JSON privat gespeichert (data/plaene/, nicht im Repo, P11)
und gilt ueber Sitzungen hinweg (Nutzerentscheidung 25.11.2026).
- Plan-Dateien werden nie veraendert: gleiche Plan-ID mit anderem Inhalt -> PlanGeaendert.
- Beim Laden wird der Inhalts-Hash neu berechnet: Abweichung -> PlanBeschaedigt
  (eine von Hand oder fehlerhaft veraenderte Datei wird nie ausgefuehrt).
- Plan-IDs werden gegen ein festes Muster geprueft (keine Pfadangaben von aussen).
Die Ausfuehrung (Teil 2) ist bewusst kein LLM-Werkzeug.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

PLAN_MUSTER = re.compile(r"^P-[0-9a-f]{10}$")


class PlanGeaendert(RuntimeError):
    """Gleiche Plan-ID, anderer Inhalt."""


class PlanBeschaedigt(RuntimeError):
    """Gespeicherter Inhalts-Hash passt nicht zur Pfadliste."""


def inhalt_hash(pfade: list[str]) -> str:
    return hashlib.sha256("\n".join(pfade).encode("utf-8")).hexdigest()


def plan_pfad(ordner, plan_id: str) -> Path:
    if not isinstance(plan_id, str) or not PLAN_MUSTER.match(plan_id):
        raise ValueError(f"ungueltige Plan-ID '{plan_id}'")
    return Path(ordner) / f"{plan_id}.json"


def _text(plan: dict) -> str:
    return json.dumps(plan, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def speichere_plan(plan: dict, ordner) -> Path:
    """Plan als JSON speichern; vorhanden + gleich -> nichts tun, vorhanden + anders -> Fehler."""
    pfad = plan_pfad(ordner, plan["plan_id"])
    if inhalt_hash(plan["pfade"]) != plan["inhalt_hash"]:
        raise PlanBeschaedigt(f"{plan['plan_id']}: Inhalts-Hash passt nicht zur Pfadliste")
    neu = _text(plan)
    if pfad.exists():
        if pfad.read_bytes().decode("utf-8").replace("\r\n", "\n") == neu:
            return pfad
        raise PlanGeaendert(f"{pfad.name} existiert mit anderem Inhalt")
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(neu.encode("utf-8"))
    return pfad


def lade_plan(ordner, plan_id: str) -> dict:
    """Plan laden und Inhalts-Hash pruefen."""
    pfad = plan_pfad(ordner, plan_id)
    if not pfad.exists():
        raise FileNotFoundError(f"Plan {plan_id} nicht gefunden")
    plan = json.loads(pfad.read_bytes().decode("utf-8"))
    if plan.get("plan_id") != plan_id or inhalt_hash(plan.get("pfade", [])) != plan.get("inhalt_hash"):
        raise PlanBeschaedigt(f"{plan_id}: Datei passt nicht zu Plan-ID oder Inhalts-Hash")
    return plan


def liste_plaene(ordner) -> list[dict]:
    """Kurzuebersicht aller gespeicherten Plaene (ohne Pfadlisten)."""
    out = []
    for p in sorted(Path(ordner).glob("P-*.json")):
        if PLAN_MUSTER.match(p.stem):
            plan = json.loads(p.read_bytes().decode("utf-8"))
            out.append({"plan_id": plan["plan_id"], "art": plan.get("art"), "stuecke": plan.get("stuecke"),
                        "kriterien": plan.get("kriterien")})
    return out


# --- Teil 2: Ausfuehrung (KEIN LLM-Werkzeug, P9) -------------------------------------------
# Aufruf nur durch Notebook/UI nach ausdruecklicher Bestaetigung des Nutzers. Das LLM kennt diese
# Funktion nicht (nicht in tools.WERKZEUGE / tools.AUSFUEHRBAR; per Test abgesichert).
ZIELORDNER_MUSTER = re.compile(r"^Playlist_.+_foobar2000$")      # P3: nur hier wird geschrieben


class AusfuehrungAbgelehnt(RuntimeError):
    """Eine Sicherheitspruefung des Gates ist fehlgeschlagen; es wurde nichts geschrieben."""


def fuehre_aus(plan_ordner, plan_id: str, bestaetigter_hash: str, name: str, ziel_ordner,
               laufwerk: str, laptop: str, integritaet=None, trotz_warnung: bool = False,
               ueberschreiben: bool = False) -> dict:
    """Bestaetigten Plan als foobar-Playlist schreiben und protokollieren.

    Pruefungen vor dem Schreiben (jede verletzt -> AusfuehrungAbgelehnt, nichts geschrieben):
    1. Plan laden, Inhalts-Hash neu berechnen (PlanBeschaedigt bei Manipulation).
    2. bestaetigter_hash == Inhalts-Hash: bestaetigt wird genau die gezeigte Vorschau.
    3. Zielordner heisst Playlist_*_foobar2000 (P3).
    4. Integritaet: kritischer Befund -> nur mit trotz_warnung=True (P12, Workflow 0b).
    5. Vorhandene Playlist gleichen Namens mit anderem Inhalt -> nur mit ueberschreiben=True;
       der Writer legt dann ein Backup an (P3). Gleicher Inhalt -> 'unveraendert'.
    Danach: Writer, Protokoll als neue JSON-Datei in <plan_ordner>/ausgefuehrt/ (nie ueberschrieben).
    """
    from datetime import datetime

    from playlist_agent import writer
    from playlist_agent.integrity import warnung_noetig

    plan = lade_plan(plan_ordner, plan_id)
    if bestaetigter_hash != plan["inhalt_hash"]:
        raise AusfuehrungAbgelehnt("Bestaetigung passt nicht zum Plan (Inhalts-Hash verschieden)")
    ziel_ordner = Path(ziel_ordner)
    if not ZIELORDNER_MUSTER.match(ziel_ordner.name):
        raise AusfuehrungAbgelehnt(f"Zielordner '{ziel_ordner.name}' ist kein Playlist_*_foobar2000 (P3)")
    if not plan["pfade"]:
        raise AusfuehrungAbgelehnt("Plan ist leer (0 Stuecke)")
    integritaet_status = "nicht geprueft"
    if integritaet is not None:
        kritisch = warnung_noetig(integritaet)
        integritaet_status = "kritisch" if kritisch else "ok"
        if kritisch and not trotz_warnung:
            raise AusfuehrungAbgelehnt("Integritaet: kritische Befunde seit dem letzten Lauf (P12)")
    datei = ziel_ordner / f"{writer.sicherer_dateiname(name)}.m3u8"
    if datei.exists() and datei.read_bytes() != writer.inhalt_m3u8(plan["pfade"], laufwerk) and not ueberschreiben:
        raise AusfuehrungAbgelehnt(f"'{datei.name}' existiert mit anderem Inhalt; Ueberschreiben nicht bestaetigt")

    erg = writer.schreibe_playlist(ziel_ordner, name, plan["pfade"], laufwerk)
    zeit = datetime.now()
    protokoll = {"plan_id": plan_id, "inhalt_hash": plan["inhalt_hash"], "zeit": zeit.isoformat(timespec="seconds"),
                 "laptop": laptop, "laufwerk": laufwerk, "datei": str(erg.datei), "status": erg.status,
                 "eintraege": erg.eintraege, "backup": str(erg.backup) if erg.backup else None,
                 "integritaet": integritaet_status, "trotz_warnung": trotz_warnung,
                 "ueberschreiben": ueberschreiben}
    pdir = Path(plan_ordner) / "ausgefuehrt"
    pdir.mkdir(parents=True, exist_ok=True)
    basis = f"{plan_id}_{laptop}_{zeit.strftime('%Y%m%d_%H%M%S_%f')}"
    ziel, i = pdir / f"{basis}.json", 2
    while ziel.exists():
        ziel, i = pdir / f"{basis}_{i}.json", i + 1
    ziel.write_bytes(_text(protokoll).encode("utf-8"))
    return {**protokoll, "protokoll": str(ziel)}
