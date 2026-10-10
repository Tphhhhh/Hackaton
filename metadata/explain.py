"""Explication du score et questions de vérification pour l'analyste.

Avec USE_BEDROCK=1, un LLM reformule les signaux et propose des questions. Le
prompt ne contient que les signaux factuels (pas le nom ni les données
personnelles du candidat). Sans Bedrock, un gabarit déterministe fait le travail.
"""
from __future__ import annotations

import json
import os

QUESTIONS = {
    "C1_TIMELINE": "Pouvez-vous détailler vos dates exactes chez chacun des deux employeurs qui se chevauchent ?",
    "C2_SENIORITY": "Pouvez-vous reconstituer année par année votre parcours depuis votre premier poste ?",
    "C3_YOUNG_PROFILE": "Pouvez-vous nous mettre en relation avec deux anciens collègues ou managers vérifiables ?",
    "C4_CAMERA": "Accepteriez-vous un court échange vidéo avec un second interlocuteur, caméra allumée ?",
    "C5_FORWARDER": "Pourquoi le matériel doit-il être livré à cette adresse plutôt qu'à votre domicile ?",
    "C6_ADDRESS_CHANGE": "Pouvez-vous fournir un justificatif de domicile à la nouvelle adresse ?",
    "C7_LOGIN_COUNTRIES": "Avez-vous voyagé ou utilisé un VPN depuis votre prise de poste ?",
    "C8_NIGHT_HOURS": "Quelles sont vos heures de travail habituelles et depuis quel fuseau horaire ?",
    "C9_CRYPTO": "Pouvez-vous fournir un RIB à votre nom dans une banque de votre pays de résidence ?",
    "C10_DISPOSABLE_EMAIL": "Pouvez-vous confirmer une adresse email personnelle durable ?",
    "S1_PERSONA_NETWORK": "Connaissez-vous les autres candidats qui partagent vos coordonnées ou votre CV ?",
}
DISCLAIMER = ("Aide à la décision uniquement : la décision finale revient à un humain. "
              "Aucun signal ne porte sur l'origine, la nationalité ou l'accent.")


def _template(result: dict) -> dict:
    sig = sorted(result["signals"], key=lambda s: -s["weight"])
    if not sig:
        summary = "Aucune incohérence factuelle détectée."
    else:
        summary = (f"Risque {result['level']} ({result['score']}/100) : "
                   + " ".join(s["evidence"] for s in sig[:3]))
    return {"summary": summary, "questions": [QUESTIONS[s["code"]] for s in sig if s["code"] in QUESTIONS][:4],
            "disclaimer": DISCLAIMER, "engine": "template"}


def _bedrock(result: dict) -> dict:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "eu-west-3"))
    model = os.getenv("BEDROCK_LLM_MODEL", "anthropic.claude-3-5-haiku-20241022-v1:0")
    facts = [{"code": s["code"], "evidence": s["evidence"]} for s in result["signals"]]
    prompt = (
        "Tu assistes un analyste conformité qui vérifie des candidatures à distance. Voici les signaux "
        f"factuels relevés sur un dossier (score {result['score']}/100) :\n{json.dumps(facts, ensure_ascii=False)}\n"
        "Rédige en français : 1) un résumé de 3 phrases maximum, neutre, qui cite uniquement ces faits ; "
        "2) trois questions de vérification à poser au candidat. N'invente aucun fait, ne fais aucune "
        "supposition sur l'origine, la nationalité ou la langue, et ne recommande pas de décision. "
        'Réponds en JSON : {"summary": "...", "questions": ["...", "...", "..."]}'
    )
    resp = client.converse(modelId=model, messages=[{"role": "user", "content": [{"text": prompt}]}],
                           inferenceConfig={"maxTokens": 600, "temperature": 0})
    text = resp["output"]["message"]["content"][0]["text"]
    data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    return {"summary": data["summary"], "questions": data["questions"], "disclaimer": DISCLAIMER, "engine": model}


def explain(result: dict) -> dict:
    if os.getenv("USE_BEDROCK") == "1" and result["signals"]:
        try:
            return _bedrock(result)
        except Exception as exc:  # le POC doit tourner même si Bedrock est indisponible
            out = _template(result)
            out["engine"] = f"template (Bedrock indisponible : {type(exc).__name__})"
            return out
    return _template(result)
