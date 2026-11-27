"""Bibliothek, Merkmalsschicht (Paket 5.0): abgeleitete Merkmale je Musikstueck.

Eingabe: Rohschicht (NB06 Z.03, eine Zeile je Audiodatei, nichts interpretiert).
Ausgabe: Rohschicht + abgeleitete Spalten mit Herkunft (Entscheidungen 22./24.11.2026):

  be_zeit, be_zeiten      'bestes Ende' aus dem Titel (erste / alle Zeiten), m:ss bzw. h:mm:ss
  ba_zeit, ba_zeiten      'bester Anfang' aus dem Titel
  be_markiert             Marker BE/be im Titel, auch ohne Zeit
  titel_quelle            tag | serato | keine
  stimmung, stil          aus dem Genre-Namen
  genre_notiz             Arbeitsnotizen im Genre (pruefen, schneiden, intro)
  genre_quelle            tag | serato | keine
  bewertung               1-5 Sterne aus Comment (Tag, Serato), nur bei Einigkeit
  bewertung_herkunft      Quellen mit Wert, z. B. 'comment+serato'
  bewertung_konflikt      True = Quellen widersprechen sich -> Nutzer entscheidet
  bewertung_werte         alle Einzelwerte
  popm_sterne             POPM umgerechnet, nur Gegenprobe (nicht vom Nutzer gepflegt)
  popm_abweichung         True = POPM vorhanden und ungleich bewertung
  dj, dj_herkunft         DJ, der das Stueck im Set spielt (serato_mix|titel|ordner|datei_kuerzel)
  interpret, interpret_herkunft   nur Tag-Interpret (tag | unbekannt)
  jahr, jahrzehnt, jahr_herkunft  Entstehungsjahr (ordner|datei_datum|tag|datei|jahrzehnt|keine)

Kuerzel -> DJ ist eine private Eingabe (data/gold, P11); hier nur die Regel.
"""

from __future__ import annotations

import posixpath
import re

import pandas as pd

# --- BE / BA (bestes Ende / bester Anfang) ------------------------------------------
# Zeit direkt oder nach einem Leerzeichen; Praefixe wie '+', 'a', 'x' sind erlaubt
# (Messung 24.11.: 515 Titel mit BE-Zeit, davon 88 nicht am Titelanfang).
_ZEIT = r"\s?(\d{1,2}:\d{2}(?::\d{2})?|\d{1,2}\.\d{2})(?!\d)"
_BE_ZEIT = re.compile(r"be" + _ZEIT, re.IGNORECASE)
_BA_ZEIT = re.compile(r"ba" + _ZEIT, re.IGNORECASE)
# Marker ohne Zeit: nur 'BE' oder 'be' als eigenes Wort ('Be' ist englisch, z. B. 'Be Yourself')
_BE_MARKER = re.compile(r"(?<![A-Za-zÄÖÜäöüß])(BE|be)(?![A-Za-zÄÖÜäöüß])")


def _zeiten(regex, titel) -> list[str]:
    if not isinstance(titel, str):
        return []
    out = []
    for z in regex.findall(titel):
        z = z.replace(".", ":")
        teile = z.split(":")
        teile[0] = str(int(teile[0]))
        out.append(":".join(teile))
    return out


def be_zeiten(titel) -> list[str]:
    """'++BE2:58 x' -> ['2:58']; 'BE5:46 und BE14:02' -> ['5:46', '14:02']."""
    return _zeiten(_BE_ZEIT, titel)


def ba_zeiten(titel) -> list[str]:
    return _zeiten(_BA_ZEIT, titel)


def be_zeit(titel) -> str | None:
    z = be_zeiten(titel)
    return z[0] if z else None


def be_markiert(titel) -> bool:
    return bool(be_zeiten(titel)) or (isinstance(titel, str) and bool(_BE_MARKER.search(titel)))


# --- Stimmung / Stil aus dem Genre -------------------------------------------------
# beat/beats ist Stimmung (Nutzer 24.11.2026); 'beats' wird zu 'beat' vereinheitlicht
STIMMUNG = {"soft", "push", "happy", "down", "rush", "goodfly", "fly", "rock", "beat"}
ZUSATZ: set[str] = set()
NOTIZ = {"prüfen", "pruefen", "schneiden", "intro"}
KEINE_INFO = {"other", "andere", "unbekanntes genre", "gênero desconhecido", "(255)", "(255", "-255"}
# ganze Genre-Namen von Kauf-CDs: hier ist rock der Stil (Nutzer 22.11.: 'wirklich rock')
ROCK_STIL = {"classic rock", "folk-rock", "folk rock"}
_WORT = re.compile(r"[A-ZÄÖÜ]?[a-zäöüßê]+|[A-ZÄÖÜ]+(?![a-zäöüß])")
_LATEIN = re.compile(r"^[\x20-\x7EÀ-ÿ]*$")


def _trenne_stimmung(wort: str) -> list[str]:
    """'happytech' -> ['happy', 'tech']: Stimmungswort als Praefix eines unbekannten Worts."""
    if wort in STIMMUNG:
        return [wort]
    for st in sorted(STIMMUNG, key=len, reverse=True):
        if wort.startswith(st) and len(wort) - len(st) >= 3:
            return [st, wort[len(st):]]
    return [wort]


def genre_woerter(genre: str) -> list[str]:
    """'PushTechnoBeat' -> ['push', 'techno', 'beat']; 'TechHouse' -> ['techhouse'];
    'R&B house' -> ['r&b', 'house']."""
    s = genre.replace("R&B", " RNB ").replace("r&b", " RNB ")
    roh = []
    for w in _WORT.findall(s):
        w = w.lower()
        roh += ["r&b"] if w == "rnb" else _trenne_stimmung("beat" if w == "beats" else w)
    # TechHouse ist ein Stil (Nutzer 24.11.2026): 'tech' direkt vor 'house' zusammenfassen
    out = []
    for w in roh:
        if w == "house" and out and out[-1] == "tech":
            out[-1] = "techhouse"
        else:
            out.append(w)
    return out


def zerlege_genre(genre) -> dict:
    """Genre-Name -> Stimmung, Stil, Notiz, keine_info, defekt (nicht-lateinische Zeichen)."""
    leer = {"stimmung": [], "stil": [], "notiz": [], "keine_info": False, "defekt": False}
    if not isinstance(genre, str) or not genre.strip():
        return leer
    g = genre.strip()
    if g.casefold() in KEINE_INFO:
        return {**leer, "keine_info": True}
    if g.casefold() in ROCK_STIL:
        return {**leer, "stil": ["rock"]}
    defekt = not _LATEIN.match(g)
    woerter = genre_woerter(g)
    stimmung = [w for w in woerter if w in STIMMUNG]
    notiz = [w for w in woerter if w in NOTIZ]
    stil = [w for w in woerter if w not in STIMMUNG | ZUSATZ | NOTIZ]
    # rock: Stimmung nur zusammen mit einem Stil-Wort, sonst Stil (Entscheidung 22.11.2026)
    if "rock" in stimmung and not stil:
        stimmung = [w for w in stimmung if w != "rock"]
        stil = ["rock"]
    return {"stimmung": sorted(set(stimmung)), "stil": sorted(set(stil)), "notiz": sorted(set(notiz)),
            "keine_info": False, "defekt": defekt}


# --- Bewertung ------------------------------------------------------------------------
# POPM (ID3v2 'Popularimeter'): Rohwert 0-255 je Programm-Kennung; Skala Windows Media
# Player 1/64/128/196/255 = 1-5 Sterne. Vom Nutzer nie bewusst gepflegt (24.11.) ->
# nur Gegenprobe, keine Bewertungsquelle.
POPM_STERNE = {1: 1, 64: 2, 128: 3, 196: 4, 255: 5, 153: 3, 154: 3, 194: 4, 204: 4, 205: 4}
_STERNE = re.compile(r"([1-5])\s*sterne", re.IGNORECASE)


def popm_sterne(wert) -> int | None:
    """Rohwert(e) -> Sterne; mehrere verschiedene oder unbekannte Werte -> None."""
    if not isinstance(wert, str) and (wert is None or pd.isna(wert)):
        return None
    s = {POPM_STERNE[int(t)] for t in str(wert).split(";") if t.strip().isdigit() and int(t) in POPM_STERNE}
    return s.pop() if len(s) == 1 else None


def _comment_sterne(text) -> list[int]:
    return [int(x) for x in _STERNE.findall(text)] if isinstance(text, str) else []


def bewertung(tag_comment, serato_comment) -> dict:
    """Sterne aus Tag- und Serato-Comment; uebernommen nur bei Einigkeit, sonst Konflikt."""
    quellen = {"comment": _comment_sterne(tag_comment), "serato": _comment_sterne(serato_comment)}
    mit = {q: sorted(set(v)) for q, v in quellen.items() if v}
    werte = sorted({w for v in mit.values() for w in v})
    text = "; ".join(f"{q}={','.join(map(str, v))}" for q, v in mit.items()) or None
    herkunft = "+".join(mit) or None
    if not werte:
        return {"bewertung": None, "bewertung_herkunft": None, "bewertung_konflikt": False,
                "bewertung_werte": None}
    konflikt = len(werte) > 1
    return {"bewertung": None if konflikt else werte[0], "bewertung_herkunft": herkunft,
            "bewertung_konflikt": konflikt, "bewertung_werte": text}


# --- Jahr (Entstehungsjahr: Erscheinungsjahr der CD bzw. Jahr des Sets) ---------------------
# Quellen: Ordnername, Dateiname, tag_year; datei_mtime/serato_hinzugefuegt nicht (Nutzer 24.11.).
# Regel (Nutzerlabels NB06 Z.14, 17 Faelle Datei <> Tag): Jahreszahl in DATUMSFORM im Dateinamen
# stimmt (14/14), allein stehende Jahreszahl im Titel nicht (3/3, z. B. Titel mit '2000') ->
# Reihenfolge: Ordner (genau 1 Jahr) > Datei-Datum > Tag > Datei (allein stehende Zahl).
_J = r"(19[5-9]\d|20[0-2]\d)"
_RIP_ORDNER = re.compile(r"\(\d{1,2}\.\d{1,2}\.(?:19|20)\d{2} \d{2}-\d{2}-\d{2}\)")   # Rip-Zeitpunkt
_DATUM = [
    re.compile(r"(?<!\d)" + _J + r"(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(?!\d)"),          # JJJJMMTT
    re.compile(r"(?<!\d)" + _J + r"(?:0[1-9]|1[0-2])(?!\d)"),                                  # JJJJMM
    re.compile(r"(?<!\d)" + _J + r"[ _.-](?:0[1-9]|1[0-2])(?!\d)"),                            # JJJJ MM (TT)
    re.compile(r"(?<!\d)\d{1,2}[.-]\d{1,2}[.-]" + _J + r"(?!\d)"),                             # TT.MM.JJJJ, MM-TT-JJJJ
]
_DATUM_KURZ = [
    re.compile(r"(?<!\d)(?:0[1-9]|[12]\d|3[01])\.(?:0[1-9]|1[0-2])\.(\d{2})(?!\d)"),          # TT.MM.JJ
    re.compile(r"(?:^|[_ -])(?:0[1-9]|[12]\d|3[01])(?:0[1-9]|1[0-2])(\d{2})(?=[_ -])"),          # TTMMJJ als Wort
]
_ALLEIN = re.compile(r"(?<!\d)" + _J + r"(?!\d)")
_JAHRZEHNT = re.compile(r"(?<!\d)(19[5-9]|20[0-2])x", re.IGNORECASE)


def _bereinige(text: str) -> str:
    # URL-kodierte Leerzeichen ('_20' mehrfach, z. B. 'Name_20Name_20-_20Live') zurueckwandeln
    if text.count("_20") >= 3:
        text = text.replace("_20", " ")
    return _RIP_ORDNER.sub(" ", text)


def jahre_im_text(text) -> dict:
    """{'datum': {...}, 'allein': {...}, 'jahrzehnt': {...}} gefundene Jahre je Form."""
    if not isinstance(text, str):
        return {"datum": set(), "allein": set(), "jahrzehnt": set()}
    t = _bereinige(text)
    datum = {int(m) for r in _DATUM for m in r.findall(t)}
    datum |= {2000 + int(m) if int(m) <= 26 else 1900 + int(m) for r in _DATUM_KURZ for m in r.findall(t)}
    return {"datum": datum, "allein": {int(m) for m in _ALLEIN.findall(t)} - datum,
            "jahrzehnt": {int(m) * 10 for m in _JAHRZEHNT.findall(t)}}


def jahr(datei_ordner, datei_name, tag_year) -> dict:
    """Entstehungsjahr mit Herkunft; Ordner vom tiefsten zum obersten, 'Musik' ausgenommen."""
    leer = {"jahr": None, "jahrzehnt": None, "jahr_herkunft": "keine"}
    ordner = [o for o in (datei_ordner.split("/") if isinstance(datei_ordner, str) else []) if o and o != "Musik"]
    for o in reversed(ordner):
        j = jahre_im_text(o)
        alle = j["datum"] | j["allein"]
        if len(alle) == 1:
            return {**leer, "jahr": alle.pop(), "jahr_herkunft": "ordner"}
        if alle:
            break                                   # mehrere Jahre im naechsten Ordner -> weiter mit Datei
    d = jahre_im_text(datei_name)
    if len(d["datum"]) == 1:
        return {**leer, "jahr": next(iter(d["datum"])), "jahr_herkunft": "datei_datum"}
    t = {int(m) for m in _ALLEIN.findall(str(tag_year))} if isinstance(tag_year, str) else set()
    if len(t) == 1:
        return {**leer, "jahr": t.pop(), "jahr_herkunft": "tag"}
    if len(d["allein"]) == 1 and not d["datum"]:
        return {**leer, "jahr": next(iter(d["allein"])), "jahr_herkunft": "datei"}
    zehn = d["jahrzehnt"] | {z for o in ordner for z in jahre_im_text(o)["jahrzehnt"]}
    if len(zehn) == 1:
        return {**leer, "jahrzehnt": zehn.pop(), "jahr_herkunft": "jahrzehnt"}
    return leer


# --- DJ und Interpret -----------------------------------------------------------------
GENERISCH = {"diverse", "various", "various artists", "unbekannter interpret", "unknown artist",
             "artista desconhecido", "va", "imported"}
_SERATO_MIX = re.compile(r"^\s*([A-Za-zÄÖÜ]{1,6})\s+Mix\b")
_GRENZE = r"(?<![A-Za-zÄÖÜäöüß]){k}(?![A-Za-zÄÖÜäöüß])"


def _kuerzel_im_text(text, kuerzel: dict[str, str]) -> str | None:
    """Laengstes Kuerzel, das als eigenes Wort im Text steht (Gross/Klein exakt)."""
    if not isinstance(text, str):
        return None
    for k in sorted(kuerzel, key=len, reverse=True):
        if re.search(_GRENZE.format(k=re.escape(k)), text):
            return kuerzel[k]
    return None


def dj(serato_interpret, titel, ordner, dateiname, kuerzel: dict[str, str]) -> dict:
    """DJ des Sets: Serato '<K> Mix' -> Titel -> Ordner -> Dateiname (Kuerzel aus privater Liste)."""
    m = _SERATO_MIX.match(serato_interpret) if isinstance(serato_interpret, str) else None
    if m:
        return {"dj": kuerzel.get(m.group(1), m.group(1)), "dj_herkunft": "serato_mix"}
    for herkunft, text in (("titel", titel),
                           ("ordner", posixpath.basename(ordner) if isinstance(ordner, str) else None),
                           ("datei", dateiname)):
        d = _kuerzel_im_text(text, kuerzel)
        if d:
            return {"dj": d, "dj_herkunft": herkunft}
    return {"dj": None, "dj_herkunft": "unbekannt"}


def interpret(tag_artist) -> dict:
    """Interpret nur aus dem Tag; '<K> Mix' und Sammelbezeichnungen zaehlen nicht."""
    if isinstance(tag_artist, str):
        a = tag_artist.strip()
        if a and a.casefold() not in GENERISCH and not _SERATO_MIX.match(a):
            return {"interpret": a, "interpret_herkunft": "tag"}
    return {"interpret": None, "interpret_herkunft": "unbekannt"}


# --- Merkmalsschicht --------------------------------------------------------------------
def lade_kuerzel(pfad) -> dict[str, str]:
    """Private Liste 'kuerzel;dj' (UTF-8, Semikolon) -> dict; fehlt sie, leer."""
    try:
        df = pd.read_csv(pfad, sep=";", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except FileNotFoundError:
        return {}
    return {k.strip(): v.strip() for k, v in zip(df["kuerzel"], df["dj"]) if k.strip() and v.strip()}


def _spalte(df, name):
    return df[name] if name in df.columns else pd.Series([None] * len(df), index=df.index)


def _wahl(a, b):
    """(Wert, Quelle): erster nicht-leerer Text aus Tag, sonst Serato."""
    if isinstance(a, str) and a.strip():
        return a, "tag"
    if isinstance(b, str) and b.strip():
        return b, "serato"
    return None, "keine"


def merkmale(df_roh: pd.DataFrame, kuerzel: dict[str, str]) -> pd.DataFrame:
    """Rohschicht -> Rohschicht + abgeleitete Spalten (Rohspalten bleiben unveraendert)."""
    df = df_roh.copy()
    t = [_wahl(a, b) for a, b in zip(_spalte(df, "tag_title"), _spalte(df, "serato_titel"))]
    titel = [x[0] for x in t]
    df["titel_quelle"] = [x[1] for x in t]
    be = [be_zeiten(x) for x in titel]
    ba = [ba_zeiten(x) for x in titel]
    df["be_zeit"] = [z[0] if z else None for z in be]
    df["be_zeiten"] = ["; ".join(z) or None for z in be]
    df["ba_zeit"] = [z[0] if z else None for z in ba]
    df["ba_zeiten"] = ["; ".join(z) or None for z in ba]
    df["be_markiert"] = [be_markiert(x) for x in titel]

    g = [_wahl(a, b) for a, b in zip(_spalte(df, "tag_genre"), _spalte(df, "serato_genre"))]
    df["genre_quelle"] = [x[1] for x in g]
    z = [zerlege_genre(x[0]) for x in g]
    df["stimmung"] = ["; ".join(x["stimmung"]) or None for x in z]
    df["stil"] = ["; ".join(x["stil"]) or None for x in z]
    df["genre_notiz"] = ["; ".join(x["notiz"]) or None for x in z]
    df["genre_keine_info"] = [x["keine_info"] for x in z]
    df["genre_defekt"] = [x["defekt"] for x in z]

    b = [bewertung(c, s) for c, s in zip(_spalte(df, "tag_comment"), _spalte(df, "serato_comment"))]
    for sp in ("bewertung", "bewertung_herkunft", "bewertung_konflikt", "bewertung_werte"):
        df[sp] = [x[sp] for x in b]
    df["bewertung"] = df["bewertung"].astype("Int64")
    df["popm_sterne"] = pd.array([popm_sterne(p) for p in _spalte(df, "tag_popm_wert")], dtype="Int64")
    df["popm_abweichung"] = [pd.notna(p) and pd.notna(w) and p != w
                             for p, w in zip(df["popm_sterne"], df["bewertung"])]

    d = [dj(si, ti, o, n, kuerzel) for si, ti, o, n in
         zip(_spalte(df, "serato_interpret"), titel, _spalte(df, "datei_ordner"), _spalte(df, "datei_name"))]
    df["dj"] = [x["dj"] for x in d]
    df["dj_herkunft"] = [x["dj_herkunft"] for x in d]
    jj = [jahr(o, n, y) for o, n, y in zip(_spalte(df, "datei_ordner"), _spalte(df, "datei_name"),
                                           _spalte(df, "tag_year"))]
    df["jahr"] = pd.array([x["jahr"] for x in jj], dtype="Int64")
    df["jahrzehnt"] = pd.array([x["jahrzehnt"] for x in jj], dtype="Int64")
    df["jahr_herkunft"] = [x["jahr_herkunft"] for x in jj]
    i = [interpret(a) for a in _spalte(df, "tag_artist")]
    df["interpret"] = [x["interpret"] for x in i]
    df["interpret_herkunft"] = [x["interpret_herkunft"] for x in i]
    return df
