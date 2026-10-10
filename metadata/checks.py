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

REF = Path(__file__).resolve().parent / "reference"
FORWARDERS = {a.lower() for a in json.loads((REF / "freight_forwarders.json").read_text(encoding="utf-8"))["addresses"]}
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


def check_claimed_years(c: dict) -> Signal | None:
    """Ancienneté annoncée dans le résumé ou le champ dédié vs somme des expériences listées."""
    claimed = [int(x) for x in re.findall(r"(\d+)\s+years", c["cv"]["summary"])]
    claimed.append(int(c["cv"].get("years_experience", 0)))
    today = date.fromisoformat(c["applied_at"])
    months = sum(max(0, (_month(e["end"], today) - _month(e["start"], today)).days // 30) for e in c["cv"]["experiences"])
    listed = months / 12
    gaps = [y for y in claimed if abs(y - listed) >= 2]
    if gaps:
        return Signal("C2_SENIORITY", 10,
                      f"Ancienneté annoncée {sorted(set(claimed))} an(s) mais {listed:.1f} an(s) d'expériences listées.")
    return None


def check_young_profile(c: dict) -> Signal | None:
    """Profil professionnel créé peu avant la candidature alors que le CV revendique des années d'expérience."""
    applied = date.fromisoformat(c["applied_at"])
    years = c["cv"].get("years_experience", 0)
    for p in c["profiles"]:
        age_days = (applied - date.fromisoformat(p["created_at"])).days
        if p["platform"] == "linkedin" and age_days < 180 and years >= 3:
            return Signal("C3_YOUNG_PROFILE", 15,
                          f"Profil {p['platform']} créé {age_days} jours avant la candidature "
                          f"({p['connections']} relations) pour {years} ans d'expérience revendiqués.", "T1585.001")
    return None


def check_camera_refused(c: dict) -> Signal | None:
    if c["interview"].get("camera_refused"):
        return Signal("C4_CAMERA", 15, "Caméra refusée pendant l'entretien.", "T1656")
    return None


def check_forwarder(c: dict) -> Signal | None:
    for s in c["shipping_addresses"]:
        if s["address"].lower() in FORWARDERS:
            return Signal("C5_FORWARDER", 25, f"Matériel envoyé chez un transitaire connu : {s['address']}.")
    return None


def check_address_change(c: dict) -> Signal | None:
    """Adresse de livraison modifiée dans les 30 jours suivant l'embauche."""
    if not c.get("hired_at") or len(c["shipping_addresses"]) < 2:
        return None
    hired = date.fromisoformat(c["hired_at"])
    for s in c["shipping_addresses"][1:]:
        delta = (date.fromisoformat(s["from"]) - hired).days
        if 0 <= delta <= 30:
            return Signal("C6_ADDRESS_CHANGE", 10,
                          f"Adresse de livraison changée {delta} jour(s) après l'embauche.")
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


def check_email(c: dict) -> Signal | None:
    domain = c["email"].rsplit("@", 1)[-1].lower()
    if domain in DISPOSABLE:
        return Signal("C10_DISPOSABLE_EMAIL", 10, f"Adresse email sur un domaine jetable ({domain}).")
    return None


CHECKS = [check_timeline_overlap, check_claimed_years, check_young_profile, check_camera_refused,
          check_forwarder, check_address_change, check_login_countries, check_working_hours,
          check_payment, check_email]


def run_checks(c: dict) -> list[Signal]:
    return [s for check in CHECKS if (s := check(c)) is not None]
