"""Lecture des coordonnées : téléphone, email, identifiant de profil.

Fonctions pures, sans dépendance, utilisées par les contrôles (checks.py) et par la
détection de réseaux (similarity.py). Rien ici ne regarde l'origine d'un nom : on
vérifie seulement si une coordonnée est bien formée et si elle se rattache à
l'identité que le candidat a lui-même déclarée.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

REF = Path(__file__).resolve().parent / "reference"
PLANS = json.loads((REF / "phone_plans.json").read_text(encoding="utf-8"))["countries"]
# Indicatif -> pays possibles (+1 couvre US et CA, +44 couvre UK et GB, +7 RU et KZ).
BY_CC: dict[str, list[str]] = {}
for _iso, _plan in PLANS.items():
    BY_CC.setdefault(_plan["cc"], []).append(_iso)


# --- Téléphone ------------------------------------------------------------------------

def parse_phone(raw: str, home: str = "") -> dict | None:
    """Découpe un numéro en indicatif + numéro national.

    Accepte « +33 6 12 34 56 78 », « 0033 6… », « +33 (0)6… » et le format national
    « 06 12… » (rattaché alors au pays de résidence déclaré). Renvoie None si vide.
    """
    s = (raw or "").strip()
    if not s:
        return None
    s = s.replace("(0)", "")
    if s.startswith("00"):
        s = "+" + s[2:]
    digits = re.sub(r"\D", "", s)
    if not digits:
        return {"raw": raw, "cc": "", "nsn": "", "digits": "", "countries": [], "international": False}
    if s.startswith("+"):
        cc = next((digits[:n] for n in (3, 2, 1) if digits[:n] in BY_CC), "")
        nsn = digits[len(cc):] if cc else digits
        international = True
    else:
        plan = PLANS.get(home)
        cc, international = (plan["cc"] if plan else ""), False
        nsn = digits
    countries = BY_CC.get(cc, [])
    keep_zero = any(PLANS[c].get("keep_zero") for c in countries)
    if nsn.startswith("0") and not keep_zero:
        nsn = nsn[1:]          # « +33 06… » : 0 national laissé par habitude, pas une anomalie
    return {"raw": raw, "cc": cc, "nsn": nsn, "digits": digits, "countries": countries, "international": international}


def normalize_phone(raw: str) -> str:
    """Forme canonique pour comparer deux dossiers (indicatif + numéro national)."""
    p = parse_phone(raw)
    return f"{p['cc']}{p['nsn']}" if p and p["nsn"] else ""


def phone_problems(p: dict) -> list[str]:
    """Défauts de forme d'un numéro déjà découpé : longueur, motif fictif, plage de fiction."""
    if not p["nsn"]:
        return ["aucun chiffre"]
    out = []
    nsn = p["nsn"]
    if p["international"] and p["digits"].startswith("0"):
        out.append("indicatif pays impossible")   # un indicatif ne commence jamais par 0
    plans = [PLANS[c] for c in p["countries"]]
    if plans and len(nsn) not in {n for pl in plans for n in pl["nsn"]}:
        expected = sorted({n for pl in plans for n in pl["nsn"]})
        want = f"{expected[0]}" if len(expected) == 1 else f"{expected[0]} à {expected[-1]}"
        out.append(f"{len(nsn)} chiffres après l'indicatif +{p['cc']}, au lieu de {want}")
    if len(set(nsn)) <= 2 and len(nsn) >= 6:
        out.append("chiffres répétés")
    if any(run in nsn for run in ("1234567", "2345678", "3456789", "9876543", "8765432")):
        out.append("suite de chiffres consécutifs")
    for pl in plans:
        if any(nsn.startswith(f) for f in pl.get("fiction", [])) or (
                pl.get("fiction_regex") and re.match(pl["fiction_regex"], nsn)):
            out.append("plage réservée aux films et séries (numéro qui n'existe pas)")
            break
    return out


def phone_is_virtual(p: dict) -> bool:
    return any(p["nsn"].startswith(v) for c in p["countries"] for v in PLANS[c].get("virtual", []))


# --- Noms et email -------------------------------------------------------------------

GERMAN = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "ø": "oe", "æ": "ae", "å": "aa"})


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def name_tokens(name: str) -> set[str]:
    """Jetons d'un nom, avec deux translittérations (Müller -> muller et mueller)."""
    low = (name or "").lower()
    out = set()
    for form in (_ascii(low), _ascii(low.translate(GERMAN))):
        out |= {t for t in re.split(r"[^a-z]+", form) if len(t) > 1}
    return out


def email_local(email: str) -> str:
    """Partie avant @, sans étiquette « +xyz », en ASCII minuscule."""
    local = (email or "").rsplit("@", 1)[0]
    return _ascii(local.split("+", 1)[0])


def normalize_email(email: str) -> str:
    """Forme canonique : Gmail ignore les points et les étiquettes « +xyz »."""
    if "@" not in (email or ""):
        return (email or "").strip().lower()
    local, domain = email.strip().lower().rsplit("@", 1)
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local, domain = local.replace(".", ""), "gmail.com"
    return f"{local}@{domain}"


def mentions_name(handle: str, name: str) -> bool:
    """Le pseudo (email, URL de profil) reprend-il le prénom ou le nom déclaré ?

    Tolère les diminutifs (« alex » pour Alexander), les noms collés (« vandijk ») et
    les initiales suivies du nom (« jdupont »).
    """
    h = re.sub(r"[^a-z]", "", _ascii(handle))
    tokens = name_tokens(name)
    if not h or not tokens:
        return True             # rien à comparer : on ne signale pas
    for t in tokens:
        if len(t) >= 3 and t in h:
            return True
        if len(t) >= 5 and t[:4] in h:
            return True
    # Initiale + nom, même très court : « hli » pour Hiroshi Li, « jdupont » pour Jean Dupont.
    if any(a[0] + b in h or b + a[0] in h for a in tokens for b in tokens if a != b):
        return True
    initials = "".join(sorted(t[0] for t in tokens))
    return len(h) <= 3 and "".join(sorted(h)) == initials


YEAR = re.compile(r"(?:19[5-9]\d|20[0-2]\d)")
# Mots génériques qu'on retrouve dans les pseudos de personas (« superdev2190 », « blockchain.guru »).
PERSONA_WORDS = ("dev", "coder", "code", "engineer", "fullstack", "backend", "frontend", "blockchain",
                 "crypto", "web3", "tech", "senior", "expert", "master", "guru", "ninja", "star", "king",
                 "hire", "remote", "freelance", "official", "work", "job", "soft")


def random_looking(handle: str, name: str) -> list[str]:
    """Raisons pour lesquelles un pseudo semble généré (chiffres en série, lettres sans voyelles…).

    On retire d'abord le prénom, le nom et une année plausible : ce qui reste doit
    ressembler à quelque chose qu'un humain choisit.
    """
    rest = _ascii(handle)
    for t in sorted(name_tokens(name), key=len, reverse=True):
        rest = rest.replace(t, " ")
    reasons = []
    no_year = YEAR.sub(" ", rest, count=1)
    digits = sum(ch.isdigit() for ch in no_year)
    if digits >= 5:
        reasons.append(f"{digits} chiffres sans signification apparente")
    transitions = len(re.findall(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", rest))
    if transitions >= 4:
        reasons.append("lettres et chiffres entremêlés")
    for chunk in re.findall(r"[a-z]{4,}", rest):
        if any(w in chunk for w in PERSONA_WORDS):
            continue
        if not re.search(r"[aeiouy]", chunk) or re.search(r"[^aeiouy]{5,}", chunk):
            reasons.append(f"suite de lettres imprononçable (« {chunk} »)")
            break
    return reasons


def persona_word(handle: str) -> str:
    h = _ascii(handle)
    return next((w for w in PERSONA_WORDS if w in h), "")


def profile_handle(url: str) -> str:
    """Identifiant d'un profil à partir de son URL (« …/in/camille-laurent-4a1/ » -> « camille-laurent-4a1 »)."""
    path = re.sub(r"^[a-z]+://", "", (url or "").strip().lower()).split("?", 1)[0].rstrip("/")
    parts = path.split("/")
    return parts[-1] if len(parts) > 1 else ""


def normalize_url(url: str) -> str:
    u = re.sub(r"^[a-z]+://", "", (url or "").strip().lower()).split("?", 1)[0].split("#", 1)[0].rstrip("/")
    return u[4:] if u.startswith("www.") else u


def normalize_address(addr: str) -> str:
    """Adresse comparable : sans accents, ponctuation ni espaces multiples (« Straße » = « strasse »)."""
    a = _ascii((addr or "").lower().replace("ß", "ss"))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", a)).strip()


COUNTRY_WORDS = {
    "FR": ("fr", "france"), "DE": ("de", "germany", "deutschland", "allemagne"), "NL": ("nl", "netherlands",
    "the netherlands", "nederland", "pays bas"), "BE": ("be", "belgium", "belgique", "belgie"), "ES": ("es", "spain",
    "espana", "espagne"), "PT": ("pt", "portugal"), "IT": ("it", "italy", "italia", "italie"), "CH": ("ch",
    "switzerland", "suisse", "schweiz"), "UK": ("uk", "gb", "united kingdom", "england", "royaume uni"), "IE": ("ie",
    "ireland", "irlande"), "PL": ("pl", "poland", "polska", "pologne"), "SE": ("se", "sweden", "sverige", "suede"),
    "US": ("us", "usa", "united states", "etats unis"), "AT": ("at", "austria", "osterreich", "autriche"),
    "LU": ("lu", "luxembourg"), "DK": ("dk", "denmark", "danemark"), "CA": ("ca", "canada"),
}
UK_POSTCODE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b")
US_STATE_ZIP = re.compile(r"\b[A-Z]{2} \d{5}(?:-\d{4})?\b")


def address_country(addr: str) -> str:
    """Pays d'une adresse postale, lu dans son dernier segment (« …, 20457 Hamburg, DE »). Vide si inconnu."""
    parts = [p for p in re.split(r"[,/\n]", addr or "") if p.strip()]
    if not parts:
        return ""
    last = normalize_address(parts[-1])
    for iso, words in COUNTRY_WORDS.items():
        if last in words:
            return iso
    if US_STATE_ZIP.search(addr or ""):
        return "US"
    if UK_POSTCODE.search(addr or ""):
        return "UK"
    return ""


# Vocabulaire d'une adresse d'entrepôt ou de réexpédition, pas d'un domicile (FR, EN, DE, NL, ES, IT).
LOGISTICS = re.compile(r"\b(?:logisti\w*|freight|cargo|warehouse|entrepot|lager|lagerhalle|dock|fret|forwarding|"
                       r"reshipp\w*|fulfil+ment|parcel|pakketpunt|magazijn|almacen|magazzino|hangar|pmb|"
                       r"mail ?box|zone industrielle|industrial estate|gewerbegebiet)\b")


def logistics_words(addr: str) -> list[str]:
    return sorted(set(LOGISTICS.findall(normalize_address(addr))))


def address_key(addr: str) -> str:
    """Adresse normalisée sans le segment pays final (« …Hamburg, DE » = « …Hamburg / Germany »)."""
    parts = [p for p in re.split(r"[,/\n]", addr or "") if p.strip()]
    if len(parts) > 1 and any(normalize_address(parts[-1]) in w for w in COUNTRY_WORDS.values()):
        parts = parts[:-1]
    return normalize_address(" ".join(parts))
