"""Contrôles de cohérence factuelle sur un dossier.

Chaque contrôle renvoie zéro ou un Signal : un code stable, un poids, et une
preuve lisible par un humain. Règle éthique : aucun contrôle ne regarde le nom,
l'origine, la langue ou la nationalité. Les pays de connexion ne comptent que
lorsqu'ils contredisent le lieu déclaré par le candidat.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from . import contact

REF = Path(__file__).resolve().parent / "reference"
FORWARDERS = {contact.address_key(a)
              for a in json.loads((REF / "freight_forwarders.json").read_text(encoding="utf-8"))["addresses"]}
DISPOSABLE = set(json.loads((REF / "disposable_domains.json").read_text(encoding="utf-8"))["domains"])


@dataclass
class Signal:
    code: str
    weight: int          # contribution au score de risque (0-100)
    evidence: str        # phrase factuelle montrée à l'analyste
    mitre: str = ""      # technique ATT&CK associée, pour la fiche de défense

    def to_dict(self) -> dict:
        return asdict(self)


def _month(s: str | None, default: date) -> date:
    return date.fromisoformat(s + "-01") if s else default


def check_timeline_overlap(c: dict) -> Signal | None:
    """Deux postes qui se chevauchent sur plus de 6 mois, ou un poste qui finit avant de commencer."""
    today = date.fromisoformat(c["applied_at"])
    spans = [(e, _month(e["start"], today), _month(e["end"], today)) for e in c["cv"]["experiences"]]
    for e, s, en in spans:
        if en < s:
            return Signal("C1_TIMELINE", 20, f"Poste chez {e['company']} : fin ({e['end']}) avant début ({e['start']}).")
    for i, (e1, s1, en1) in enumerate(spans):
        for e2, s2, en2 in spans[i + 1:]:
            overlap = (min(en1, en2) - max(s1, s2)).days
            if overlap > 180:
                return Signal("C1_TIMELINE", 20,
                              f"Postes chez {e1['company']} et {e2['company']} simultanés pendant {overlap // 30} mois.")
    return None


# « 9 ans d'expérience », « depuis 7 ans », « (9+ years) », « 8 years building… ».
# Exclut l'âge (« 25 ans », « 25 years old », « âgé de 25 ans ») : ce n'est pas une ancienneté.
YEARS = re.compile(r"(\d{1,2})\+?\s*(?:ans|years?)\b(?!\s*old)", re.IGNORECASE)
AGE_BEFORE = re.compile(r"(?:\bde|j'ai|j’ai|i am|i'm|aged?)\s*$", re.IGNORECASE)
EXPERIENCE_AFTER = re.compile(r"\s*(?:d['’]\s?exp|of\s+exp|experience|in\s+|as\s+|dans\s+|en\s+|d['’]\s?ancien)", re.IGNORECASE)


def claimed_years(text: str) -> list[int]:
    """Années d'expérience revendiquées dans un texte libre (résumé de CV)."""
    out = []
    for m in YEARS.finditer(text or ""):
        before, after = text[max(0, m.start() - 12):m.start()], text[m.end():m.end() + 12]
        if AGE_BEFORE.search(before) and not EXPERIENCE_AFTER.match(after):
            continue
        if 0 < int(m.group(1)) <= 45:
            out.append(int(m.group(1)))
    return out


def check_claimed_years(c: dict) -> Signal | None:
    """Ancienneté annoncée dans le résumé ou le champ dédié vs somme des expériences listées."""
    if not c["cv"]["experiences"]:  # aucune expérience saisie : information manquante, pas incohérence
        return None
    claimed = set(claimed_years(c["cv"]["summary"]))
    if c["cv"].get("years_experience"):
        claimed.add(int(c["cv"]["years_experience"]))
    today = date.fromisoformat(c["applied_at"])
    months = sum(max(0, (_month(e["end"], today) - _month(e["start"], today)).days // 30) for e in c["cv"]["experiences"])
    listed = months / 12
    gaps = sorted(y for y in claimed if abs(y - listed) >= 2)
    if gaps:
        return Signal("C2_SENIORITY", 10,
                      f"Annonce {' ou '.join(map(str, gaps))} ans d'expérience, mais les postes listés "
                      f"totalisent {listed:.0f} an{'s' if round(listed) > 1 else ''}.")
    return None


def check_young_profile(c: dict) -> Signal | None:
    """Profil professionnel créé peu avant la candidature alors que le CV revendique des années d'expérience."""
    applied = date.fromisoformat(c["applied_at"])
    years = c["cv"].get("years_experience", 0)
    for p in c["profiles"]:
        if not p.get("created_at"):  # date inconnue (profil non enrichi) : pas de signal
            continue
        age_days = (applied - date.fromisoformat(p["created_at"])).days
        if p["platform"] == "linkedin" and age_days < 180 and years >= 3:
            return Signal("C3_YOUNG_PROFILE", 15,
                          f"Profil {p['platform'].replace('linkedin', 'LinkedIn').replace('github', 'GitHub')} créé {age_days} jours avant la candidature "
                          f"({p.get('connections', '?')} relations) pour {years} ans d'expérience revendiqués.",
                          "T1585.001")
    return None


def check_camera_refused(c: dict) -> Signal | None:
    if c["interview"].get("camera_refused"):
        return Signal("C4_CAMERA", 15, "Caméra refusée pendant l'entretien.", "T1656")
    return None


def check_forwarder(c: dict) -> Signal | None:
    for s in c["shipping_addresses"]:
        addr = contact.address_key(s["address"])
        if any(f == addr or f in addr for f in FORWARDERS):
            return Signal("C5_FORWARDER", 25, f"Matériel envoyé chez un transitaire connu : {s['address']}.")
    for s in c["shipping_addresses"]:
        words = contact.logistics_words(s["address"])
        if words:
            return Signal("C5_FORWARDER", 20,
                          f"Matériel à livrer à une adresse d'entrepôt ou de réexpédition "
                          f"(« {', '.join(words)} ») : {s['address']}.")
    return None


def check_shipping_country(c: dict) -> Signal | None:
    """Ordinateur à livrer dans un autre pays que la résidence déclarée (schéma des « fermes d'ordinateurs »)."""
    home = c["declared_location"].get("country", "")
    for s in c["shipping_addresses"]:
        country = contact.address_country(s["address"])
        if country and home and country != home and not ({country, home} <= {"UK", "GB"}):
            return Signal("C18_SHIPPING_COUNTRY", 20,
                          f"Matériel à livrer en {country} alors que le candidat déclare résider en {home} : "
                          f"{s['address']}.")
    return None


def check_address_change(c: dict) -> Signal | None:
    """Adresse de livraison modifiée dans les 30 jours suivant l'embauche."""
    if not c.get("hired_at") or len(c["shipping_addresses"]) < 2:
        return None
    hired = date.fromisoformat(c["hired_at"])
    for s in c["shipping_addresses"][1:]:
        delta = (date.fromisoformat(s["from"]) - hired).days
        if 0 <= delta <= 30:
            when = "dès l'embauche" if delta == 0 else f"{delta} jour(s) après l'embauche"
            return Signal("C6_ADDRESS_CHANGE", 10,
                          f"Matériel à livrer ailleurs qu'à l'adresse de résidence, {when}.")
    return None


def check_login_countries(c: dict) -> Signal | None:
    """Connexions depuis des pays autres que celui déclaré."""
    home = c["declared_location"]["country"]
    events = c["activity"]
    if not events:
        return None
    others = {e["ip_country"] for e in events if e["ip_country"] != home}
    share = sum(e["ip_country"] != home for e in events) / len(events)
    # Un voyage ponctuel produit quelques connexions isolées : on exige une part significative.
    if share > 0.4 or (len(others) >= 2 and share > 0.15):
        return Signal("C7_LOGIN_COUNTRIES", 20,
                      f"{share:.0%} des connexions hors du pays déclaré ({home}), depuis {len(others)} autre(s) pays.",
                      "T1078")
    return None


def check_working_hours(c: dict) -> Signal | None:
    """Activité concentrée la nuit dans le fuseau horaire déclaré."""
    offset = c["declared_location"].get("utc_offset", 0)
    events = c["activity"]
    if not events:
        return None
    night = 0
    for e in events:
        h = (datetime.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ").hour + offset) % 24
        night += h < 6
    share = night / len(events)
    if share > 0.4:
        return Signal("C8_NIGHT_HOURS", 15,
                      f"{share:.0%} de l'activité entre minuit et 6 h, heure locale déclarée.")
    return None


def check_payment(c: dict) -> Signal | None:
    if c["payment"]["method"] == "crypto":
        return Signal("C9_CRYPTO", 20, "Paiement du salaire demandé en cryptomonnaie.")
    return None


def check_payee(c: dict) -> Signal | None:
    """Compte de paie au nom d'une autre personne (salaire reversé à un intermédiaire).

    Ne compare que l'identité déclarée par le candidat à celle du titulaire du compte :
    rien n'est déduit du nom lui-même (ni origine, ni langue).
    """
    holder = c["payment"].get("holder", "").strip()
    if not holder or c["payment"]["method"] == "crypto":
        return None
    if not contact.name_tokens(holder) & contact.name_tokens(c["full_name"]):
        return Signal("C11_PAYEE", 20, f"Le compte de paie est au nom de « {holder} », pas du candidat.")
    return None


def check_email(c: dict) -> Signal | None:
    domain = c["email"].rsplit("@", 1)[-1].lower().strip()
    if any(domain == d or domain.endswith("." + d) for d in DISPOSABLE):
        return Signal("C10_DISPOSABLE_EMAIL", 10, f"Adresse email sur un domaine jetable ({domain}).")
    return None


# --- Coordonnées : forme du téléphone, de l'email et du profil ------------------------
# Signaux faibles, pensés pour s'additionner : une coordonnée bizarre isolée s'explique
# presque toujours (numéro gardé après un déménagement, pseudo d'étudiant…).

def check_phone_format(c: dict) -> Signal | None:
    """Numéro mal formé pour son indicatif, motif fabriqué ou plage réservée à la fiction."""
    p = contact.parse_phone(c["phone"], c["declared_location"].get("country", ""))
    if p is None:
        return None
    problems = contact.phone_problems(p)
    if problems:
        return Signal("C12_PHONE_INVALID", 10,
                      f"Numéro de téléphone {c['phone'].strip()} invalide : {' ; '.join(problems)}.", "T1585")
    return None


def check_phone_virtual(c: dict) -> Signal | None:
    """Numéro virtuel (VoIP nomade, numéro personnel de renvoi), joignable de n'importe où."""
    p = contact.parse_phone(c["phone"], c["declared_location"].get("country", ""))
    if p and contact.phone_is_virtual(p):
        return Signal("C13_PHONE_VOIP", 10,
                      f"Le numéro {c['phone'].strip()} appartient à une tranche de numéros virtuels (VoIP), "
                      "utilisables depuis n'importe quel pays.", "T1585")
    return None


def check_phone_country(c: dict) -> Signal | None:
    """Indicatif du téléphone différent de celui du pays de RÉSIDENCE déclaré.

    Comparé au lieu de vie que le candidat déclare, jamais à une origine supposée. Un
    expatrié garde souvent son ancien numéro : poids minimal, utile seulement en
    combinaison. Aucun pays n'est plus suspect qu'un autre.
    """
    home = c["declared_location"].get("country", "")
    p = contact.parse_phone(c["phone"], home)
    plan = contact.PLANS.get(home)
    if not p or not plan or not p["international"] or not p["digits"]:
        return None
    if not p["digits"].startswith(plan["cc"]):
        shown = p["cc"] or p["digits"][:3]
        return Signal("C14_PHONE_COUNTRY", 5,
                      f"Téléphone en +{shown} pour une résidence déclarée en {home} (+{plan['cc']}).")
    return None


def check_email_pattern(c: dict) -> Signal | None:
    """Partie avant @ qui semble générée : suite de chiffres, lettres imprononçables."""
    reasons = contact.random_looking(contact.email_local(c["email"]), c["full_name"])
    if reasons:
        return Signal("C15_EMAIL_RANDOM", 10,
                      f"Adresse email d'apparence générée ({c['email'].strip()}) : {' ; '.join(reasons)}.")
    return None


def check_email_name(c: dict) -> Signal | None:
    """Adresse email qui ne reprend ni le prénom ni le nom déclaré."""
    local = contact.email_local(c["email"])
    domain = c["email"].rsplit("@", 1)[-1].split(".")[0] if "@" in c["email"] else ""
    own_domain = len(domain) >= 4 and contact.mentions_name(domain, c["full_name"])   # contact@janedoe.dev
    if local and not own_domain and not contact.mentions_name(local, c["full_name"]):
        word = contact.persona_word(local)
        extra = f", mais un mot générique (« {word} »)" if word else ""
        return Signal("C16_EMAIL_NAME", 10 if word else 5,
                      f"L'adresse {c['email'].strip()} ne contient ni le prénom ni le nom du candidat{extra}.")
    return None


def check_profile_name(c: dict) -> Signal | None:
    """URL LinkedIn sans rapport avec le nom (les pseudos GitHub, eux, sont libres et courants)."""
    for p in c["profiles"]:
        handle = contact.profile_handle(p.get("url", ""))
        if p.get("platform") == "linkedin" and handle and not contact.mentions_name(handle, c["full_name"]):
            word = contact.persona_word(handle)
            extra = f", mais un mot générique (« {word} »)" if word else ""
            return Signal("C17_PROFILE_NAME", 10 if word else 5,
                          f"Le profil LinkedIn « {handle} » ne reprend pas le nom du candidat{extra}.", "T1585.001")
    return None


# --- Métadonnées de la session d'entretien (lues par le navigateur et le serveur) ---------
# Volontairement absent : la langue du système. C'est un indicateur indirect d'origine,
# exclu par notre règle éthique (et par l'AI Act), même comme signal faible.

VIRTUAL_DEVICES = ("obs", "manycam", "snap camera", "xsplit", "vb-audio", "voicemod", "virtual cam",
                   "deepfacelive", "avatarify")
VM_RENDERERS = ("swiftshader", "llvmpipe", "vmware", "virtualbox", "microsoft basic render")
EUROPE_MAX_RTT_MS = 150      # Exploratory threshold; latency does not establish distance.


def _session(c: dict) -> dict | None:
    return c.get("interview_session")


def check_virtual_camera(c: dict) -> Signal | None:
    s = _session(c)
    if not s:
        return None
    names = s["devices"].get("video", []) + s["devices"].get("audio", [])
    virtual = [n for n in names if any(v in n.lower() for v in VIRTUAL_DEVICES)]
    if virtual:
        return Signal("I1_VIRTUAL_DEVICE", 10, f"Périphérique virtuel pendant l'entretien : {', '.join(virtual)}.", "T1656")
    if s.get("device_changed_during_call"):
        return Signal("I1_VIRTUAL_DEVICE", 5, "La caméra a changé en cours d'appel.", "T1656")
    return None


def check_browser_timezone(c: dict) -> Signal | None:
    s = _session(c)
    if not s or "browser_utc_offset" not in s:
        return None
    gap = abs(s["browser_utc_offset"] - c["declared_location"].get("utc_offset", 0))
    if gap >= 2:
        return Signal("I2_TIMEZONE", 10,
                      f"Ordinateur réglé sur {s.get('browser_timezone', '?')} (UTC{s['browser_utc_offset']:+g}), "
                      f"à {gap} h du fuseau déclaré.")
    return None


def check_vm_gpu(c: dict) -> Signal | None:
    s = _session(c)
    if s and any(v in s.get("gpu_renderer", "").lower() for v in VM_RENDERERS):
        return Signal("I3_VIRTUAL_MACHINE", 15,
                      f"Rendu graphique logiciel ou machine virtuelle ({s['gpu_renderer']}).", "T1564.006")
    return None


def check_interview_ip(c: dict) -> Signal | None:
    s = _session(c)
    if not s or "ip" not in s:
        return None
    reasons, weight = [], 0
    if s["ip"]["country"] != c["declared_location"]["country"]:
        reasons.append(f"IP située en {s['ip']['country']} et non en {c['declared_location']['country']}")
        weight += 10
    if s["ip"].get("type") == "datacenter":
        reasons.append("IP d'hébergeur (datacenter) et non d'opérateur grand public")
        weight += 10
    if s.get("ip_changed_during_call"):
        reasons.append("IP changée pendant l'appel")
        weight += 10
    if reasons:
        return Signal("I4_INTERVIEW_IP", min(weight, 25), "Pendant l'entretien : " + " ; ".join(reasons) + ".", "T1090")
    return None


def check_latency(c: dict) -> Signal | None:
    s = _session(c)
    rtt = sorted(s.get("rtt_ms", [])) if s else []
    if not rtt:
        return None
    median = rtt[len(rtt) // 2]
    if median > EUROPE_MAX_RTT_MS:
        return Signal("I5_LATENCY", 15,
                      f"Temps de réponse médian de {median} ms vers le service réseau de référence. "
                      "Une connexion lente, un VPN ou un relais peuvent l’expliquer ; la distance n’est pas établie.", "T1090")
    return None


def check_video_settings(c: dict) -> Signal | None:
    s = _session(c)
    if s and s.get("video_settings_changes", 0) >= 3:
        return Signal("I6_VIDEO_SETTINGS", 5,
                      f"Résolution ou cadence de la vidéo modifiée {s['video_settings_changes']} fois pendant l'appel.")
    return None


CHECKS = [check_timeline_overlap, check_claimed_years, check_young_profile, check_camera_refused,
          check_forwarder, check_shipping_country, check_address_change, check_login_countries, check_working_hours,
          check_payment, check_payee, check_email, check_phone_format, check_phone_virtual, check_phone_country,
          check_email_pattern, check_email_name, check_profile_name, check_virtual_camera, check_browser_timezone, check_vm_gpu,
          check_interview_ip, check_latency, check_video_settings]


# Combinaisons : un signal isolé s'explique souvent (flou d'arrière-plan, VPN d'entreprise,
# 4G faible). Plusieurs signaux d'entretien qui pointent dans le même sens pèsent plus lourd.
INTERVIEW_CODES = {"I1_VIRTUAL_DEVICE", "I3_VIRTUAL_MACHINE", "I4_INTERVIEW_IP", "I5_LATENCY", "I2_TIMEZONE"}


def combination_bonus(signals: list[Signal]) -> Signal | None:
    hits = sorted({s.code for s in signals} & INTERVIEW_CODES)
    if len(hits) >= 2:
        weight = 15 if len(hits) == 2 else 25
        return Signal("X1_COMBINATION", weight,
                      f"{len(hits)} signaux d'entretien concordants ({', '.join(h.split('_', 1)[0] for h in hits)}) : "
                      "à vérifier ensemble ; une configuration professionnelle peut aussi les expliquer.")
    return None


# Coordonnées : on compte les CHAMPS touchés (email, téléphone, profil), pas les codes, pour ne
# pas compter deux fois une même adresse email bizarre.
CONTACT_FIELDS = {"C10_DISPOSABLE_EMAIL": "email", "C15_EMAIL_RANDOM": "email", "C16_EMAIL_NAME": "email",
                  "C12_PHONE_INVALID": "téléphone", "C13_PHONE_VOIP": "téléphone", "C14_PHONE_COUNTRY": "téléphone",
                  "C17_PROFILE_NAME": "profil"}


def contact_bonus(signals: list[Signal]) -> Signal | None:
    fields = sorted({CONTACT_FIELDS[s.code] for s in signals if s.code in CONTACT_FIELDS})
    if len(fields) >= 2:
        return Signal("X2_CONTACT_COMBINATION", 10 if len(fields) == 2 else 15,
                      f"Anomalies sur plusieurs coordonnées à la fois ({', '.join(fields)}) : chacune s'explique, "
                      "leur accumulation beaucoup moins.", "T1585")
    return None


def run_checks(c: dict) -> list[Signal]:
    signals = [s for check in CHECKS if (s := check(c)) is not None]
    for combo in (combination_bonus, contact_bonus):
        if (bonus := combo(signals)) is not None:
            signals.append(bonus)
    return signals
