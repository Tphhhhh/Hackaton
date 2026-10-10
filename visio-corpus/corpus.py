"""Local corpus admission; no download, prediction, consent inference or split inference."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent
MAX_MEDIA = 50 * 1024**2
KINDS = {
    None: ("bona_fide", "live_person"),
    "photo": ("physical_presentation", "paper"),
    "screen": ("physical_presentation", "display"),
    "face_swap": ("digital_manipulation", "none"),
    "reenactment": ("digital_manipulation", "none"),
    "digital_replay": ("digital_injection", "virtual_camera"),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check_date(value):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value), "Date ISO requise")
    date.fromisoformat(value)


def checked_file(root, relative, expected, folder, max_size=None):
    require(nonempty(relative), "Chemin manquant")
    rel = Path(relative)
    require(not rel.is_absolute() and ".." not in rel.parts, "Chemin non relatif ou traversée")
    require(rel.parts[0] == folder, f"Fichier attendu dans {folder}/")
    target = (root / rel).resolve()
    require(target.is_relative_to(root.resolve()), "Lien sortant du corpus")
    require(target.is_relative_to((root / folder).resolve()), "Fichier hors dossier prévu")
    require(target.is_file(), f"Fichier absent : {relative}")
    size = target.stat().st_size
    require(size > 0 and (max_size is None or size <= max_size), f"Taille invalide : {relative}")
    require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected), "SHA-256 manquant/invalide")
    require(sha256(target) == expected, f"SHA-256 différent : {relative}")
    return size


def validate(data, root=ROOT):
    require(isinstance(data, dict) and data.get("schema_version") == "1.0", "Schéma 1.0 requis")
    require(isinstance(data.get("clips"), list), "Liste clips requise")
    ids, hashes, groups = set(), set(), {}
    total_bytes = 0
    for c in data["clips"]:
        require(isinstance(c, dict), "Fiche non objet")
        for field in ("id", "permission", "person_id", "source_id"):
            require(nonempty(c.get(field)), f"Champ manquant : {field}")
        require(c["id"] not in ids, f"ID dupliqué : {c['id']}")
        ids.add(c["id"])
        require(c.get("authorized") is True, f"Non autorisé : {c['id']}")
        require(c.get("split") in ("dev", "test"), "Partition dev/test requise")
        require(c.get("label") in ("real", "attack"), "Label non vérifié ou invalide")
        require("attack_kind" in c, "attack_kind requis, même null")
        kind = c["attack_kind"]
        require(kind is None or isinstance(kind, str), "Type attack_kind invalide")
        require(kind in KINDS and ((c["label"] == "real") == (kind is None)), "Attaque incohérente")
        review = c.get("review")
        require(isinstance(review, dict), "Revue absente")
        for flag in ("label_verified", "permission_verified", "lineage_verified", "media_verified"):
            require(review.get(flag) is True, f"Revue incomplète : {flag}")
        require(nonempty(review.get("reviewer")), "Réviseur absent")
        check_date(review.get("reviewed_on"))
        prov = c.get("provenance")
        require(isinstance(prov, dict), "Provenance absente")
        for key in ("provider", "source_url", "original_id", "transformations"):
            require(nonempty(prov.get(key)), f"Provenance incomplète : {key}")
        check_date(prov.get("acquired_on"))
        require((prov.get("domain"), prov.get("presentation_medium")) == KINDS[kind],
                "Domaine/support incompatible avec le label")
        evidence = c.get("evidence")
        require(isinstance(evidence, dict), "Pièces absentes")
        for key in ("label", "permission", "lineage", "media"):
            item = evidence.get(key)
            require(isinstance(item, dict), f"Pièce absente : {key}")
            checked_file(root, item.get("path"), item.get("sha256"), "private")
        for plural, primary in (("person_ids", "person_id"), ("source_ids", "source_id")):
            values = c.get(plural)
            require(isinstance(values, list) and values and all(nonempty(v) for v in values),
                    f"Filiation complète requise : {plural}")
            require(len(set(values)) == len(values) and c[primary] in values, f"Filiation incohérente : {plural}")
            for value in values:
                key = (plural, value)
                require(key not in groups or groups[key] == c["split"], f"Fuite {plural} : {value}")
                groups[key] = c["split"]
        total_bytes += checked_file(root, c.get("path"), c.get("sha256"), "media", MAX_MEDIA)
        require(c["sha256"] not in hashes, "Contenu dupliqué, même dans une partition")
        hashes.add(c["sha256"])
    return {"clips": len(ids), "bytes": total_bytes,
            "dev": sum(c["split"] == "dev" for c in data["clips"]),
            "test": sum(c["split"] == "test" for c in data["clips"])}


def build_manifest(data, root=ROOT):
    validate(data, root)
    require(data["clips"], "Corpus vide : aucune évaluation possible")
    categories = sorted({c["attack_kind"] for c in data["clips"] if c["label"] == "attack"})
    require(categories, "Aucune attaque admise")
    for split in ("dev", "test"):
        clips = [c for c in data["clips"] if c["split"] == split]
        require(any(c["label"] == "real" for c in clips), f"Aucun vrai dans {split}")
        for kind in categories:
            require(any(c["attack_kind"] == kind for c in clips), f"Catégorie {kind} absente de {split}")
    return {"schema_version": "1.0", "claimed_categories": categories,
            "clips": sorted(data["clips"], key=lambda c: c["id"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit", "build", "verify"))
    args = parser.parse_args()
    try:
        data = json.loads((ROOT / "intake.json").read_text(encoding="utf-8"))
        if args.command == "audit":
            report = validate(data)
            report["benchmark_validated"] = False
            report["note"] = "Audit d'admission uniquement ; build/verify et gel du moteur restent nécessaires."
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        result = build_manifest(data)
        output = ROOT / "manifest.json"
        if args.command == "verify":
            require(json.loads(output.read_text(encoding="utf-8")) == result,
                    "Manifeste différent du registre validé")
            print("Manifeste, preuves, empreintes et partitions cohérents ; gel moteur encore nécessaire.")
        else:
            # No replacement of a previous manifest on failed validation.
            temporary = ROOT / "manifest.json.tmp"
            temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            temporary.replace(output)
            print(f"Manifeste écrit : {len(result['clips'])} clips ; aucune performance mesurée.")
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f"REFUS : {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
