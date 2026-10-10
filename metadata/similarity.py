"""Similarité entre candidatures pour repérer une même personne derrière plusieurs profils.

Deux sources de liens :
1. Identifiants recyclés : même téléphone, même compte de paiement, même email ou
   même profil. Une adresse de livraison partagée ne suffit pas seule (deux fraudeurs
   indépendants peuvent utiliser le même transitaire) : elle doit s'ajouter à une
   similarité de texte.
2. Texte du CV quasi identique : embeddings Bedrock (Titan) si USE_BEDROCK=1,
   sinon TF-IDF sur n-grammes de caractères, calculé en local sans dépendance.

Les liens forment un graphe ; ses composantes connexes de taille >= 2 sont les
réseaux de personas présumés.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from collections import Counter
from itertools import combinations
from pathlib import Path

TEXT_THRESHOLD = 0.80        # texte seul suffisant pour lier deux dossiers
TEXT_WITH_ADDRESS = 0.50     # seuil abaissé si l'adresse de livraison est aussi partagée


def cv_text(c: dict) -> str:
    parts = [c["cv"]["summary"]] + [e["description"] for e in c["cv"]["experiences"]]
    return " ".join(parts)


def _ngrams(text: str, n: int = 4) -> Counter:
    t = re.sub(r"\s+", " ", text.lower())
    return Counter(t[i:i + n] for i in range(len(t) - n + 1))


def _tfidf_vectors(texts: list[str]) -> list[dict]:
    grams = [_ngrams(t) for t in texts]
    df = Counter(g for gs in grams for g in gs)
    n = len(texts)
    vecs = []
    for gs in grams:
        v = {g: tf * math.log((1 + n) / (1 + df[g])) for g, tf in gs.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({g: x / norm for g, x in v.items()})
    return vecs


def _bedrock_vectors(texts: list[str]) -> list[dict]:
    import boto3  # importé seulement si Bedrock est activé

    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    model = os.getenv("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0")
    # Cache disque : le hackathon limite Bedrock à ~1 requête/s, on ne recalcule jamais un CV déjà vu.
    cache_path = Path("out/embeddings_cache.json")
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    vecs = []
    for t in texts:
        key = hashlib.sha256(f"{model}:{t}".encode()).hexdigest()
        if key not in cache:
            resp = client.invoke_model(modelId=model, body=json.dumps({"inputText": t[:8000], "normalize": True}))
            cache[key] = json.loads(resp["body"].read())["embedding"]
            time.sleep(1)
        vecs.append(dict(enumerate(cache[key])))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache), encoding="utf-8")
    return vecs


def _cosine(a: dict, b: dict) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(k, 0.0) for k, x in a.items())


def _identifiers(c: dict) -> dict[str, set[str]]:
    norm = lambda s: re.sub(r"[\s\-.]", "", s.lower())
    return {
        "téléphone": {norm(c["phone"])},
        "compte de paiement": {norm(c["payment"]["account"])},
        "email": {c["email"].lower()},
        "profil": {p["url"].lower() for p in c["profiles"]},
    }


def find_links(candidates: list[dict]) -> list[dict]:
    """Renvoie les paires liées avec la raison du lien."""
    use_bedrock = os.getenv("USE_BEDROCK") == "1"
    texts = [cv_text(c) for c in candidates]
    vecs = _bedrock_vectors(texts) if use_bedrock else _tfidf_vectors(texts)
    ids = [_identifiers(c) for c in candidates]
    addrs = [{s["address"].lower() for s in c["shipping_addresses"]} for c in candidates]

    links = []
    for i, j in combinations(range(len(candidates)), 2):
        reasons = [f"même {k}" for k in ids[i] if ids[i][k] & ids[j][k]]
        sim = _cosine(vecs[i], vecs[j])
        shared_addr = bool(addrs[i] & addrs[j])
        if sim >= TEXT_THRESHOLD:
            reasons.append(f"CV quasi identiques (similarité {sim:.2f})")
        elif shared_addr and sim >= TEXT_WITH_ADDRESS:
            reasons.append(f"même adresse de livraison et CV proches (similarité {sim:.2f})")
        if reasons:
            links.append({"a": candidates[i]["id"], "b": candidates[j]["id"], "similarity": round(sim, 3),
                          "reasons": reasons})
    return links


def find_networks(candidates: list[dict], links: list[dict]) -> list[list[str]]:
    """Composantes connexes (union-find) de taille >= 2."""
    parent = {c["id"]: c["id"] for c in candidates}

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for link in links:
        parent[root(link["a"])] = root(link["b"])
    groups: dict[str, list[str]] = {}
    for cid in parent:
        groups.setdefault(root(cid), []).append(cid)
    return sorted((sorted(g) for g in groups.values() if len(g) >= 2), key=lambda g: g[0])
