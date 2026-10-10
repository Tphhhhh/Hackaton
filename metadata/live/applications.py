"""Candidatures déposées via la page d'offre d'emploi de démo.

Chaque dépôt est converti au format de `schema.py`, puis analysé AVEC le jeu de
dossiers existant : une candidature qui recycle le téléphone, le compte de paiement ou
le CV d'un dossier déjà reçu est immédiatement reliée à son réseau.
"""
from __future__ import annotations

import json
import random
import re
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


def to_candidate(form: dict, app_id: str) -> dict:
    """Convertit le formulaire de candidature au format de schema.py."""
    country = form["country"]
    today = date.today().isoformat()
    home = f"{form.get('address', '').strip()}, {form['city']}, {country}"
    shipping = form.get("shipping_address", "").strip() or home
    profiles = []
    for platform in ("linkedin", "github"):
        url = form.get(f"{platform}_url", "").strip()
        if url:
            prof = {"platform": platform, "url": url}
            # Simulation de l'enrichissement de profil (API LinkedIn / GitHub en production).
            if platform == "linkedin" and form.get("profile_created"):
                prof["created_at"] = form["profile_created"]
                prof["connections"] = int(form.get("profile_connections") or 0)
            profiles.append(prof)
    meta = form.get("meta", {})
    return {
        "id": app_id,
        "applied_at": today,
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
        "interview": {"camera_refused": False},
        "payment": {"method": form["payment_method"], "account": form.get("payment_account", "").strip()},
        "shipping_addresses": [{"from": today, "address": shipping}],
        "activity": [],
        # Métadonnées lues par le navigateur au moment du dépôt (consentement affiché sur le formulaire).
        "interview_session": {
            "devices": {"video": [], "audio": []},
            "browser_timezone": meta.get("browser_timezone"),
            "browser_utc_offset": meta.get("browser_utc_offset", COUNTRY_OFFSET.get(country, 2)),
            "gpu_renderer": meta.get("gpu_renderer", ""),
            "ip": {k: v for k, v in (meta.get("ip") or {}).items() if k in ("country", "type", "org", "address")},
            "rtt_ms": meta.get("rtt_ms", []),
        } if meta else None,
        "source": "formulaire",
    }


def _reanalyse() -> None:
    base = load_candidates(DATA_DIR / "candidates.json")
    apps = list(APPLICATIONS.values())
    for a in apps:  # pas de géolocalisation disponible : on ne fabrique pas de signal IP
        if a.get("interview_session") and not a["interview_session"].get("ip", {}).get("country"):
            a["interview_session"].pop("ip", None)
        if "interview_session" in a and a["interview_session"] is None:
            a.pop("interview_session")
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


def listing() -> list[dict]:
    with LOCK:
        out = []
        for app_id, c in APPLICATIONS.items():
            r = RESULTS.get(app_id)
            if r:
                out.append({"id": app_id, "name": c["full_name"], "city": c["declared_location"]["city"],
                            "country": c["declared_location"]["country"], "email": c["email"],
                            "applied_at": c["applied_at"], "result": r})
        return sorted(out, key=lambda a: -a["result"]["score"])


def public_info(app_id: str) -> dict | None:
    c = APPLICATIONS.get(app_id)
    if not c:
        return None
    return {"id": app_id, "first_name": c["full_name"].split(" ")[0], "name": c["full_name"],
            "city": c["declared_location"]["city"], "country": c["declared_location"]["country"]}


def demo_example(kind: str) -> dict:
    """Pré-remplit le formulaire pour la démo : un candidat honnête, ou un membre d'un réseau existant."""
    hired = date.today()
    if kind == "honest":
        return {
            "first_name": "Camille", "last_name": "Laurent", "email": "camille.laurent@proton.me",
            "phone": "+33 6 48 21 77 90", "city": "Lyon", "country": "FR", "address": "14 rue Sala",
            "linkedin_url": "https://linkedin.example/in/camille-laurent", "github_url": "https://github.example/claurent",
            "years_experience": 7, "skills": "React, Node.js, TypeScript, AWS, PostgreSQL",
            "summary": "Développeuse full-stack depuis 7 ans, passée par une fintech lyonnaise puis une scale-up "
                       "e-commerce. J'aime les produits bien finis, les revues de code bienveillantes et la "
                       "documentation claire.",
            "experiences": [
                {"company": "Brightloop", "title": "Senior Full-Stack Engineer", "start": "2022-02", "end": "",
                 "description": "Refonte du tunnel de paiement en React et Node.js, migration vers AWS Lambda."},
                {"company": "Kairo Tech", "title": "Full-Stack Developer", "start": "2019-01", "end": "2022-01",
                 "description": "API de facturation en Node.js et PostgreSQL, tableau de bord React."},
            ],
            "education": [{"school": "INSA Lyon", "degree": "Diplôme d'ingénieur", "year": 2018}],
            "payment_method": "iban", "payment_account": "FR76 3000 4012 3400 0123 4567 890",
            "profile_created": (hired - timedelta(days=365 * 6)).isoformat(), "profile_connections": 412,
        }
    # Fraudeur : reprend le compte de paiement et l'adresse de livraison d'un réseau déjà présent
    # dans les dossiers, avec un CV reformulé. Le pipeline doit le relier au réseau.
    base = load_candidates(DATA_DIR / "candidates.json")
    labels = json.loads((DATA_DIR / "labels.json").read_text(encoding="utf-8"))
    members = [c for c in base if labels[c["id"]]["network"] and c["payment"]["method"] == "crypto"] or \
              [c for c in base if labels[c["id"]]["network"]]
    src = members[0]
    return {
        "first_name": "Daniel", "last_name": "Kovac", "email": "daniel.kovac.dev@tempmail.dev",
        "phone": src["phone"], "city": "Amsterdam", "country": "NL", "address": "Keizersgracht 210",
        "shipping_address": src["shipping_addresses"][0]["address"],
        "linkedin_url": "https://linkedin.example/in/daniel-kovac-dev", "github_url": "",
        "years_experience": src["cv"]["years_experience"] + 1, "skills": ", ".join(src["cv"]["skills"]),
        "summary": src["cv"]["summary"],
        "experiences": [{"company": e["company"], "title": e["title"], "start": e["start"], "end": e["end"] or "",
                         "description": e["description"]} for e in src["cv"]["experiences"][:3]],
        "education": src["cv"]["education"],
        "payment_method": src["payment"]["method"], "payment_account": src["payment"]["account"],
        "profile_created": (hired - timedelta(days=41)).isoformat(), "profile_connections": 17,
    }


_load_store()
if APPLICATIONS:
    _reanalyse()
