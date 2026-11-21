"""Inhaltsbelege zu Vorschlaegen aus der Quelle (Serato database V2).

Im Ernstfall fehlt die Originaldatei; Dauer und Groesse sind dann nur noch in der
Quelle gespeichert. Kalibrierung NB05 Z.21: tsiz in MiB (2^20, 1 Nachkommastelle),
tlen 'mm:ss.hh'; gleiche Datei: Dauer 92,4 % <= 0,1 s, Groesse 76,2 % <= 0,05 MiB.
Entscheidung 20.11.2026: nur Hinweis im Bericht, kein Veto und kein "sicher"
(Titel werden nachtraeglich geschnitten; Groesse/Dauer trennen Version und
Umbenennung nicht sicher, NB05 Z.22).
"""

from __future__ import annotations

import math

import pandas as pd

from playlist_agent.canon import nfc

TOL_DAUER_S = 0.1
TOL_GROESSE_MIB = 0.05


def tsiz_mib(s) -> float:
    """'8.0MB' -> 8.0 (MiB); sonst NaN."""
    if isinstance(s, str) and s.strip().upper().endswith("MB"):
        try:
            return float(s.strip()[:-2])
        except ValueError:
            return math.nan
    return math.nan


def tlen_s(s) -> float:
    """'07:56.16' -> 476.16 s; sonst NaN."""
    if not isinstance(s, str) or ":" not in s:
        return math.nan
    m, sek = s.strip().split(":", 1)
    try:
        return int(m) * 60 + float(sek)
    except ValueError:
        return math.nan


def serato_meta(df_db: pd.DataFrame, schluessel: str = "schluessel") -> dict[str, tuple[float, float]]:
    """Kanonischer Pfad -> (Dauer [s], Groesse [MiB]) aus database V2 (NB02 Z.08)."""
    return {nfc(str(k)).replace("\\", "/"): (tlen_s(l), tsiz_mib(z))
            for k, l, z in zip(df_db[schluessel], df_db["tlen"], df_db["tsiz"])}


def _zahl(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def hinweis(sek_quelle, mib_quelle, sek_kandidat, bytes_kandidat) -> str:
    """Kurztext fuer den Bericht: Abweichung Dauer/Groesse Quelle -> Kandidat."""
    teile = []
    if _zahl(sek_quelle) and _zahl(sek_kandidat):
        d = sek_kandidat - sek_quelle
        teile.append(f"Dauer {d:+.2f} s ({'passt' if abs(d) <= TOL_DAUER_S else 'abweichend'})")
    if _zahl(mib_quelle) and _zahl(bytes_kandidat):
        k = bytes_kandidat / 2**20
        ok = abs(k - mib_quelle) <= TOL_GROESSE_MIB + 1e-9
        teile.append(f"Groesse {mib_quelle:.1f} -> {k:.1f} MiB ({'passt' if ok else 'abweichend'})")
    return "Serato: " + ", ".join(teile) if teile else "keine Serato-Daten"
