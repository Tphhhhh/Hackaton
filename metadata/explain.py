"""Explication du score et questions de vérification pour l'analyste.

Avec USE_BEDROCK=1, un LLM reformule les signaux et propose des questions. Le
prompt ne contient que les signaux factuels (pas le nom ni les données
personnelles du candidat). Sans Bedrock, un gabarit déterministe fait le travail.
"""
from __future__ import annotations

import json
import os
import re

QUESTIONS = {
    "C1_TIMELINE": "Pouvez-vous détailler vos dates exactes chez chacun des deux employeurs qui se chevauchent ?",
    "C2_SENIORITY": "Pouvez-vous reconstituer année par année votre parcours depuis votre premier poste ?",
    "C3_YOUNG_PROFILE": "Pouvez-vous nous mettre en relation avec deux anciens collègues ou managers vérifiables ?",
    "C4_CAMERA": "Accepteriez-vous un court échange vidéo avec un second interlocuteur, caméra allumée ?",
    "C5_FORWARDER": "Pourquoi le matériel doit-il être livré à cette adresse plutôt qu'à votre domicile ?",
    "C6_ADDRESS_CHANGE": "Pourquoi le matériel doit-il être livré à cette adresse ? Pouvez-vous fournir un justificatif ?",
    "C7_LOGIN_COUNTRIES": "Avez-vous voyagé ou utilisé un VPN depuis votre prise de poste ?",
    "C8_NIGHT_HOURS": "Quelles sont vos heures de travail habituelles et depuis quel fuseau horaire ?",
    "C9_CRYPTO": "Pouvez-vous fournir un RIB à votre nom dans une banque de votre pays de résidence ?",
    "C11_PAYEE": "Pouvez-vous fournir un RIB à votre nom ? Qui est le titulaire du compte indiqué ?",
    "C10_DISPOSABLE_EMAIL": "Pouvez-vous confirmer une adresse email personnelle durable ?",
    "C12_PHONE_INVALID": "Pouvez-vous confirmer votre numéro ? Nous vous appelons pour le vérifier avant l'entretien.",
    "C13_PHONE_VOIP": "Avez-vous un numéro mobile personnel ? Celui indiqué est un numéro virtuel.",
    "C14_PHONE_COUNTRY": "Ce numéro est-il celui où vous joindre au quotidien ? (Garder un ancien numéro est fréquent.)",
    "C15_EMAIL_RANDOM": "Pouvez-vous confirmer votre adresse email ? Nous y envoyons un code de vérification.",
    "C16_EMAIL_NAME": "Pouvez-vous confirmer votre adresse email ? Nous y envoyons un code de vérification.",
    "C18_SHIPPING_COUNTRY": "Pourquoi le matériel doit-il être livré dans un autre pays que celui où vous résidez ?",
    "C17_PROFILE_NAME": "Le profil LinkedIn indiqué est-il le vôtre ? Pouvez-vous l'ouvrir pendant l'entretien ?",
    "S1_PERSONA_NETWORK": "Connaissez-vous les autres candidats qui partagent vos coordonnées ou votre CV ?",
    "I1_VIRTUAL_DEVICE": "Pouvez-vous refaire l'appel avec la webcam intégrée de votre ordinateur, sans logiciel ?",
    "I2_TIMEZONE": "Dans quel pays et quelle ville vous trouvez-vous en ce moment ?",
    "I3_VIRTUAL_MACHINE": "Utilisez-vous une machine virtuelle ou un bureau à distance pour cet entretien ?",
    "I4_INTERVIEW_IP": "Passez-vous par un VPN ou un serveur distant ? Pouvez-vous le couper pour l'entretien ?",
    "I5_LATENCY": "Pouvez-vous refaire un court appel depuis une connexion locale, sans VPN ?",
    "I6_VIDEO_SETTINGS": "Votre connexion est-elle instable ? Pouvez-vous fixer la qualité vidéo ?",
    "V1_CHALLENGE_ARTEFACTS": "Pouvez-vous refaire les gestes (main devant le visage, tête de profil) avec un second interlocuteur ?",
    "V2_LIPSYNC": "Pouvez-vous lire à voix haute une phrase choisie au hasard, caméra proche ?",
    "V3_TEMPORAL": "Accepteriez-vous un second entretien vidéo, à un horaire imposé ?",
    "V4_LIGHTING": "Pouvez-vous allumer une lampe face à vous et bouger lentement la tête ?",
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
    return {"summary": summary, "questions": list(dict.fromkeys(QUESTIONS[s["code"]] for s in sig if s["code"] in QUESTIONS))[:4],
            "disclaimer": DISCLAIMER, "engine": "template"}


# Avant d'envoyer une preuve au LLM, on masque ce qui identifie quelqu'un : emails, numéros,
# IBAN, noms cités entre guillemets, adresses. Le LLM reformule des faits, il n'a pas besoin de qui.
REDACT = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    (re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b"), "[IBAN]"),
    (re.compile(r"(?:\+|00)\d[\d ().-]{6,}\d"), "[téléphone]"),
]
NAMED = {"C11_PAYEE", "C17_PROFILE_NAME"}              # citent un nom ou un pseudo entre « »
ADDRESS = {"C5_FORWARDER", "C18_SHIPPING_COUNTRY"}     # finissent par une adresse postale


def redact(text: str, code: str = "") -> str:
    for pattern, repl in REDACT:
        text = pattern.sub(repl, text)
    if code in NAMED:
        text = re.sub(r"«[^»]*»", "« [masqué] »", text)
    if code in ADDRESS:
        text = re.sub(r" : [^:]*$", " : [adresse].", text)
    return text


def _bedrock(result: dict) -> dict:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    model = os.getenv("BEDROCK_LLM_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
    facts = [{"code": s["code"], "evidence": redact(s["evidence"], s["code"])} for s in result["signals"]]
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
