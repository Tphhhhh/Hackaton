"""Format d'un dossier candidat.

Un dossier est un dict JSON. Les champs sont volontairement factuels : aucun champ
ne porte l'origine, la nationalité, la langue ou l'accent du candidat, et aucun
contrôle ne doit en utiliser.

{
  "id": "C001",
  "applied_at": "2026-09-01",            # date de candidature (ISO)
  "hired_at": "2026-09-20" | null,       # date d'embauche, si embauché
  "full_name": "...",
  "email": "...",
  "phone": "+33...",
  "declared_location": {"city": "...", "country": "FR", "timezone": "Europe/Paris"},
  "cv": {
    "summary": "...",
    "years_experience": 7,
    "experiences": [{"company", "title", "start": "YYYY-MM", "end": "YYYY-MM" | null, "description"}],
    "education": [{"school", "degree", "year"}],
    "skills": ["..."]
  },
  "profiles": [{"platform": "linkedin|github|...", "url": "...", "created_at": "YYYY-MM-DD", "connections": 120}],
  "interview": {"camera_refused": false},
  "payment": {"method": "iban|crypto|paypal", "account": "..."},
  "shipping_addresses": [{"from": "YYYY-MM-DD", "address": "..."}],   # adresse d'envoi du matériel
  "activity": [{"ts": "2026-09-21T08:12:00Z", "ip_country": "FR"}]      # connexions après embauche
}

La vérité terrain (fraude ou non, réseau) est stockée À PART dans labels.json et
n'est lue que par evaluate.py.
"""
from __future__ import annotations

import json
from pathlib import Path

REQUIRED_FIELDS = (
    "id", "applied_at", "full_name", "email", "phone", "declared_location",
    "cv", "profiles", "interview", "payment", "shipping_addresses", "activity",
)


def validate(candidate: dict) -> list[str]:
    """Retourne la liste des champs manquants (vide si le dossier est complet)."""
    return [f for f in REQUIRED_FIELDS if f not in candidate]


def load_candidates(path: str | Path) -> list[dict]:
    candidates = json.loads(Path(path).read_text(encoding="utf-8"))
    for c in candidates:
        missing = validate(c)
        if missing:
            raise ValueError(f"Dossier {c.get('id', '?')} incomplet : {missing}")
    return candidates
