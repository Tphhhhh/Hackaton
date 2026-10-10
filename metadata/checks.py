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


# --- Métadonnées de la session d'entretien (lues par le navigateur et le serveur) ---------
# Volontairement absent : la langue du système. C'est un indicateur indirect d'origine,
# exclu par notre règle éthique (et par l'AI Act), même comme signal faible.

VIRTUAL_DEVICES = ("obs", "manycam", "snap camera", "xsplit", "vb-audio", "voicemod", "virtual cam",
                   "deepfacelive", "avatarify")
VM_RENDERERS = ("swiftshader", "llvmpipe", "vmware", "virtualbox", "microsoft basic render")
EUROPE_MAX_RTT_MS = 150      # vers un serveur à Paris, on attend < 50 ms ; au-delà de 150, c'est loin


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
                      f"Ordinateur réglé sur {s.get('browser_timezone', '?')} (UTC{s['browser_utc_offset']:+d}), "
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
                      f"Temps de réponse médian de {median} ms vers Paris pour un candidat en "
                      f"{c['declared_location']['country']} (attendu < 50 ms) : connexion probablement lointaine "
                      "ou relayée.", "T1090")
    return None


def check_video_settings(c: dict) -> Signal | None:
    s = _session(c)
    if s and s.get("video_settings_changes", 0) >= 3:
        return Signal("I6_VIDEO_SETTINGS", 5,
                      f"Résolution ou cadence de la vidéo modifiée {s['video_settings_changes']} fois pendant l'appel.")
    return None


CHECKS = [check_timeline_overlap, check_claimed_years, check_young_profile, check_camera_refused,
          check_forwarder, check_address_change, check_login_countries, check_working_hours,
          check_payment, check_email, check_virtual_camera, check_browser_timezone, check_vm_gpu,
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
                      "une explication bénigne unique devient peu probable.")
    return None


def run_checks(c: dict) -> list[Signal]:
    signals = [s for check in CHECKS if (s := check(c)) is not None]
    if (bonus := combination_bonus(signals)) is not None:
        signals.append(bonus)
    return signals
