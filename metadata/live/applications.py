"""Candidatures déposées via le site de démo (offre d'emploi, puis onboarding).

Comme dans un vrai recrutement, les données arrivent en deux temps :
1. **Candidature** : CV, coordonnées, parcours, prétentions salariales, disponibilité.
2. **Onboarding**, une fois le candidat recruté : adresse de résidence, adresse de livraison
   de l'ordinateur et compte bancaire pour la paie. C'est là que le FBI observe les signaux les plus
   forts (ordinateur envoyé chez un transitaire, salaire versé sur le compte d'un tiers).

Chaque dépôt est converti au format de `schema.py`, puis analysé AVEC le jeu de dossiers
existant : un candidat qui recycle le téléphone, le compte de paiement ou le CV d'un dossier
déjà reçu est immédiatement relié à son réseau.
"""
from __future__ import annotations

import json
import random
import threading
from datetime import date, timedelta
from pathlib import Path

from ..run import analyse
from ..schema import load_candidates
from ..video import load_video_scores

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "synthetic"
STORE = Path("out/applications.json")
COUNTRY_OFFSET = {"FR": 2, "DE": 2, "CH": 2, "BE": 2, "NL": 2, "ES": 2, "IT": 2, "PT": 1, "UK": 1, "IE": 1}
COUNTRY_TZ = {"FR": "Europe/Paris", "DE": "Europe/Berlin", "CH": "Europe/Zurich", "BE": "Europe/Brussels",
              "NL": "Europe/Amsterdam", "ES": "Europe/Madrid", "IT": "Europe/Rome", "PT": "Europe/Lisbon",
              "UK": "Europe/London", "IE": "Europe/Dublin"}

LOCK = threading.Lock()
APPLICATIONS: dict[str, dict] = {}   # id -> dossier au format schema.py
RESULTS: dict[str, dict] = {}        # id -> résultat d'analyse


def _load_store() -> None:
    if STORE.exists():
        for c in json.loads(STORE.read_text(encoding="utf-8")):
            APPLICATIONS[c["id"]] = c


def _save_store() -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(list(APPLICATIONS.values()), indent=2, ensure_ascii=False), encoding="utf-8")


def _month(s: str | None) -> str | None:
    """Accepte « 2021-03 » ou « 2021-03-15 » et renvoie « 2021-03 »."""
    return s[:7] if s else None


def _session_meta(meta: dict, country: str) -> dict | None:
    """Métadonnées techniques lues par le navigateur (annoncées au candidat sur le formulaire)."""
    if not meta:
        return None
    ip = {k: v for k, v in (meta.get("ip") or {}).items() if k in ("country", "type", "org", "address")}
    session = {
        "devices": {"video": [], "audio": []},
        "browser_timezone": meta.get("browser_timezone"),
        "browser_utc_offset": meta.get("browser_utc_offset", COUNTRY_OFFSET.get(country, 2)),
        "gpu_renderer": meta.get("gpu_renderer", ""),
        "rtt_ms": meta.get("rtt_ms", []),
    }
    if ip.get("country"):  # sans géolocalisation, pas de signal IP inventé
        session["ip"] = ip
    return session


def _profile_lookup(url: str) -> dict | None:
    """Enrichissement du profil professionnel (date de création, nombre de relations).

    Le candidat ne déclare jamais ces valeurs : en production, elles viennent d'un fournisseur
    de données de profil. Ici, on les simule pour les deux CV de démo ; un autre profil n'est
    pas enrichi et le contrôle C3 ne s'applique pas.
    """
    norm = url.lower().rstrip("/").replace("https://", "").replace("http://", "").replace("www.", "")
    for kind in ("honest", "fraud"):
        ex = demo_example(kind)
        if ex["linkedin_url"].replace("https://", "") == norm:
            return ex
    return None


def to_candidate(form: dict, app_id: str) -> dict:
    """Convertit le formulaire de candidature au format de schema.py."""
    country = form["country"]
    profiles = []
    for platform in ("linkedin", "github"):
        url = form.get(f"{platform}_url", "").strip()
        if url:
            prof = {"platform": platform, "url": url}
            if platform == "linkedin" and (info := _profile_lookup(url)):
                prof["created_at"] = info["profile_created"]
                prof["connections"] = info["profile_connections"]
            profiles.append(prof)
    candidate = {
        "id": app_id,
        "stage": "candidature",
        "applied_at": date.today().isoformat(),
        "hired_at": None,
        "full_name": f"{form['first_name'].strip()} {form['last_name'].strip()}",
        "email": form["email"].strip(),
        "phone": form["phone"].strip(),
        "declared_location": {"city": form["city"].strip(), "country": country,
                              "timezone": COUNTRY_TZ.get(country, "Europe/Paris"),
                              "utc_offset": COUNTRY_OFFSET.get(country, 2)},
        "cv": {
            "summary": form.get("summary", "").strip(),
            "years_experience": int(form.get("years_experience") or 0),
            "experiences": [{"company": e["company"], "title": e["title"], "start": _month(e["start"]),
                             "end": _month(e.get("end")), "description": e.get("description", "")}
                            for e in form.get("experiences", []) if e.get("company") and e.get("start")],
            "education": [e for e in form.get("education", []) if e.get("school")],
            "skills": [s.strip() for s in form.get("skills", "").split(",") if s.strip()],
            "file_name": form.get("cv_file_name"),
        },
        "profiles": profiles,
        "application": {"salary_expectation": form.get("salary_expectation"), "available_from": form.get("available_from"),
                        "source": form.get("source"), "message": form.get("message", "")},
        "interview": {"camera_refused": False},
        # Renseignés à l'onboarding seulement
        "payment": {"method": "", "account": ""},
        "shipping_addresses": [],
        "activity": [],
    }
    if session := _session_meta(form.get("meta", {}), country):
        candidate["interview_session"] = session
    return candidate


def apply_onboarding(c: dict, form: dict) -> None:
    """Ajoute au dossier les données d'onboarding : adresse, livraison de l'ordinateur, compte de paie."""
    today = date.today().isoformat()
    home = f"{form['address'].strip()}, {form['postcode'].strip()} {form['city'].strip()}, {c['declared_location']['country']}"
    shipping = form.get("shipping_address", "").strip()
    c["stage"] = "onboarding"
    c["hired_at"] = today
    c["home_address"] = home
    c["shipping_addresses"] = [{"from": c["applied_at"], "address": home}]
    if shipping and shipping.lower() != home.lower():
        c["shipping_addresses"].append({"from": today, "address": shipping})
    c["payment"] = {"method": "iban", "account": form["iban"].strip(), "holder": form.get("account_holder", "").strip()}
    c["onboarding"] = {"start_date": form.get("start_date")}


def _reanalyse() -> None:
    base = load_candidates(DATA_DIR / "candidates.json")
    apps = list(APPLICATIONS.values())
    report = analyse(base + apps, load_video_scores(DATA_DIR / "video_scores.json"))
    by_id = {c["id"]: c for c in base + apps}
    for r in report["results"]:
        if r["id"] in APPLICATIONS:
            net = next((n for n in report["networks"] if r["id"] in n), [])
            r["linked"] = [{"id": i, "name": by_id[i]["full_name"]} for i in net if i != r["id"]]
            RESULTS[r["id"]] = r


def submit(form: dict) -> str:
    with LOCK:
        app_id = "A" + "".join(random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(5))
        APPLICATIONS[app_id] = to_candidate(form, app_id)
        _save_store()
        _reanalyse()
        return app_id


def onboard(app_id: str, form: dict) -> bool:
    with LOCK:
        c = APPLICATIONS.get(app_id)
        if not c:
            return False
        apply_onboarding(c, form)
        _save_store()
        _reanalyse()
        return True


def decide(app_id: str, decision: str, analyst: str) -> int | None:
    """Enregistre la décision humaine sur une candidature ; renvoie le score au moment de la décision."""
    with LOCK:
        c, r = APPLICATIONS.get(app_id), RESULTS.get(app_id)
        if not c or not r:
            return None
        c["decision"] = {"decision": decision, "analyst": analyst, "at": date.today().isoformat()}
        _save_store()
        return r["score"]


def listing() -> list[dict]:
    with LOCK:
        out = []
        for app_id, c in APPLICATIONS.items():
            if r := RESULTS.get(app_id):
                out.append({"id": app_id, "name": c["full_name"], "city": c["declared_location"]["city"],
                            "country": c["declared_location"]["country"], "email": c["email"],
                            "applied_at": c["applied_at"], "stage": c.get("stage", "candidature"),
                            "decision": c.get("decision"), "result": r})
        return sorted(out, key=lambda a: -a["result"]["score"])


def public_info(app_id: str) -> dict | None:
    c = APPLICATIONS.get(app_id)
    if not c:
        return None
    return {"id": app_id, "first_name": c["full_name"].split(" ")[0], "name": c["full_name"],
            "city": c["declared_location"]["city"], "country": c["declared_location"]["country"],
            "stage": c.get("stage", "candidature")}


# --- Exemples pour la démo ------------------------------------------------------------

def _network_source() -> dict:
    """Un membre d'un réseau existant dans les dossiers synthétiques (de préférence payé en crypto)."""
    base = load_candidates(DATA_DIR / "candidates.json")
    labels = json.loads((DATA_DIR / "labels.json").read_text(encoding="utf-8"))
    members = [c for c in base if labels[c["id"]]["network"] and c["payment"]["method"] == "crypto"] or \
              [c for c in base if labels[c["id"]]["network"]]
    return members[0]


def demo_example(kind: str) -> dict:
    """Contenu des CV de démo (une candidate honnête, un fraudeur qui recycle un réseau existant)."""
    today = date.today()
    if kind == "honest":
        return {
            "first_name": "Camille", "last_name": "Laurent", "headline": "Développeuse Full-Stack Senior",
            "email": "camille.laurent@proton.me", "phone": "+33 6 48 21 77 90", "city": "Lyon", "country": "FR",
            "linkedin_url": "https://linkedin.com/in/camille-laurent", "github_url": "https://github.com/claurent",
            "years_experience": 7, "skills": "React, Node.js, TypeScript, AWS, PostgreSQL, Terraform",
            "summary": "Développeuse full-stack depuis 7 ans, passée par une fintech lyonnaise puis une scale-up "
                       "e-commerce. J'aime les produits bien finis, les revues de code bienveillantes et la "
                       "documentation claire.",
            "experiences": [
                {"company": "Brightloop", "title": "Senior Full-Stack Engineer", "start": "2022-02", "end": "",
                 "description": "Refonte du tunnel de paiement en React et Node.js, migration vers AWS Lambda."},
                {"company": "Kairo Tech", "title": "Full-Stack Developer", "start": "2019-01", "end": "2022-01",
                 "description": "API de facturation en Node.js et PostgreSQL, tableau de bord React."},
                {"company": "Orbis Data", "title": "Développeuse web", "start": "2018-09", "end": "2018-12",
                 "description": "Stage de fin d'études : outils internes de reporting."},
            ],
            "education": [{"school": "INSA Lyon", "degree": "Diplôme d'ingénieur", "year": 2018}],
            "profile_created": (today - timedelta(days=365 * 6)).isoformat(), "profile_connections": 412,
            "salary_expectation": 72, "available_from": (today + timedelta(days=60)).isoformat(), "source": "linkedin",
            "message": "Les paiements me passionnent : j'ai construit l'API de facturation de Kairo Tech et migré "
                       "le tunnel de paiement de Brightloop. Disponible pour échanger dès cette semaine.",
        }
    src = _network_source()
    return {
        "first_name": "Daniel", "last_name": "Kovac", "headline": "Senior Full-Stack Engineer",
        "email": "daniel.kovac.dev@tempmail.dev", "phone": src["phone"], "city": "Amsterdam", "country": "NL",
        "linkedin_url": "https://linkedin.com/in/daniel-kovac-dev", "github_url": "",
        "years_experience": src["cv"]["years_experience"] + 1, "skills": ", ".join(src["cv"]["skills"]),
        "summary": src["cv"]["summary"],
        "experiences": [{"company": e["company"], "title": e["title"], "start": e["start"], "end": e["end"] or "",
                         "description": e["description"]} for e in src["cv"]["experiences"][:3]],
        "education": src["cv"]["education"],
        "profile_created": (today - timedelta(days=41)).isoformat(), "profile_connections": 17,
        "salary_expectation": 55, "available_from": today.isoformat(), "source": "other",
        "message": "Available immediately, full-time, any time zone. Happy to start this week.",
    }


def demo_onboarding(kind: str) -> dict:
    d = date.today() + timedelta(days=30)
    start = (d + timedelta(days=(7 - d.weekday()) % 7)).isoformat()  # un lundi
    if kind == "honest":
        return {"address": "14 rue Sala", "postcode": "69002", "city": "Lyon", "shipping_address": "",
                "iban": "FR76 3000 4012 3400 0123 4567 890", "account_holder": "Camille Laurent", "start_date": start}
    # Le fraudeur fait livrer l'ordinateur chez le transitaire de son réseau, et verser
    # le salaire sur le compte d'un intermédiaire.
    src = _network_source()
    return {"address": "Keizersgracht 210", "postcode": "1016 DX", "city": "Amsterdam",
            "shipping_address": src["shipping_addresses"][0]["address"],
            "iban": "NL91 ABNA 0417 1643 00", "account_holder": "P. de Vries Services", "start_date": start}


_load_store()
if APPLICATIONS:
    _reanalyse()
