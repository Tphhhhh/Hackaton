"""Export presentation statistics from a real, frozen 25+25 GenD PE benchmark."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .benchmark import rate


def summarize(report):
    if (report.get("kind") != "visio_benchmark" or report.get("split") != "test"
            or report["config"]["detectors"] != ["gend_pe"]):
        raise ValueError("Expected a frozen GenD PE test benchmark")
    samples = report["samples"]
    if (len(samples) != 50 or len({s["clip_id"] for s in samples}) != 50
            or any(sum(s["label"] == label for s in samples) != 25 for label in ("real", "attack"))):
        raise ValueError("Expected exactly 25 unique real and 25 unique attack clips")
    rows = []
    matrix = {label: {key: 0 for key in ("verify", "no_signal", "indeterminate", "error")}
              for label in ("real", "attack")}
    for s in samples:
        result = s["result"]
        if result.get("simulation") is not False:
            raise ValueError("Simulated results cannot be presented as measurements")
        if result["config"] != report["config"]:
            raise ValueError("Sample configuration differs from frozen benchmark")
        det = result["detectors"].get("gend_pe")
        outcome = "error" if det is None or det["status"] == "error" else det["conclusion"]
        correct = (s["label"], outcome) in (("attack", "verify"), ("real", "no_signal"))
        matrix[s["label"]][outcome] += 1
        rows.append(dict(clip_id=s["clip_id"], label=s["label"], outcome=outcome, correct=correct,
                         score=None if det is None else det["score"],
                         coverage=None if det is None else det["coverage"],
                         flagged_fraction=None if det is None else det["flagged_fraction"],
                         duration_seconds=result["duration_seconds"],
                         total_seconds=result["timing"]["total_seconds"],
                         error_codes=";".join(e["code"] for e in result["errors"])))
    if matrix != report["metrics"]["gend_pe"]["matrix"]:
        raise ValueError("Per-video results do not match benchmark metrics")
    tp, tn = matrix["attack"]["verify"], matrix["real"]["no_signal"]
    fp, fn = matrix["real"]["verify"], matrix["attack"]["no_signal"]
    decided = tp + tn + fp + fn
    return dict(
        model="gend_pe", total=50, matrix=matrix,
        correct_end_to_end=rate(tp + tn, 50),
        detected_deepfakes=rate(tp, 25), real_without_alert=rate(tn, 25),
        false_positives=rate(fp, 25), missed_deepfakes=rate(fn, 25),
        abstentions=rate(sum(m["indeterminate"] for m in matrix.values()), 50),
        technical_errors=rate(sum(m["error"] for m in matrix.values()), 50),
        precision=rate(tp, tp + fp), correct_conditional=rate(tp + tn, decided),
        config_sha256=report["config_sha256"], dataset_sha256=report["dataset_sha256"],
        models_manifest_sha256=report["models_manifest_sha256"], rows=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    summary = summarize(report)
    args.output.mkdir(parents=True, exist_ok=True)
    outputs = [args.output / name for name in ("summary.json", "results.csv", "results.md")]
    if any(p.exists() for p in outputs):
        raise SystemExit("An output exists; choose a new directory to preserve earlier experiments")
    outputs[0].write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    with outputs[1].open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary["rows"][0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary["rows"])

    def count(name):
        r = summary[name]
        return f"{r['count']}/{r['total']} ({100*r['rate']:.0f} %)" if r["rate"] is not None else "Non calculable"

    def interval(name):
        bounds = summary[name]["wilson95"]
        return "—" if bounds is None else f"{100*bounds[0]:.1f}–{100*bounds[1]:.1f} %"

    metrics = [("Décisions correctes sur les 50 vidéos", "correct_end_to_end"),
               ("Deepfakes détectés", "detected_deepfakes"),
               ("Authentiques sans alerte", "real_without_alert"),
               ("Fausses alertes", "false_positives"),
               ("Deepfakes sans alerte (manqués)", "missed_deepfakes"),
               ("Abstentions", "abstentions"), ("Erreurs techniques", "technical_errors")]
    metric_table = "\n".join(f"| {label} | {count(key)} | {interval(key)} |" for label, key in metrics)
    matrix = summary["matrix"]
    matrix_table = "\n".join(
        f"| {label} | {matrix[key]['verify']} | {matrix[key]['no_signal']} | "
        f"{matrix[key]['indeterminate']} | {matrix[key]['error']} |"
        for label, key in (("Deepfake", "attack"), ("Authentique", "real")))
    text = f"""# Test GenD PE — 25 deepfakes et 25 vidéos authentiques

**{count('correct_end_to_end')} décisions correctes** sur ce corpus figé.
Deepfakes repérés : **{count('detected_deepfakes')}**.
Authentiques sans alerte : **{count('real_without_alert')}**.

## Chiffres pour la présentation

| Mesure | Résultat | Intervalle Wilson 95 % descriptif |
| --- | ---: | ---: |
{metric_table}

| Vérité du corpus | Alerte deepfake | Aucun indice | Abstention | Erreur |
| --- | ---: | ---: | ---: | ---: |
{matrix_table}

Les abstentions et erreurs restent dans le dénominateur de 50. Une sortie
« aucun indice » compte comme une décision correcte uniquement pour les clips
étiquetés authentiques ; elle ne prouve pas l'authenticité d'une vidéo inconnue.
La précision des alertes est {count('precision')}. Le taux de décisions correctes
conditionnel aux vidéos ayant reçu une décision est {count('correct_conditional')}.

## Phrase utilisable sur une diapositive

« Sur un test exploratoire de 50 vidéos (25 authentiques et 25 deepfakes),
GenD PE a détecté {summary['detected_deepfakes']['count']} deepfakes sur 25,
avec {summary['false_positives']['count']} fausse(s) alerte(s) sur 25 authentiques,
{summary['abstentions']['count']} abstention(s) et {summary['technical_errors']['count']} erreur(s).
Résultats limités à VidTIMIT/DeepfakeTIMIT, sans garantie sur les deepfakes récents. »

## Protocole et limites

- 25 personnes, une phrase `sa1` par personne et sa version face swap `higher_quality`.
- Sélection déterministe (graine 20261011) avant inférence ; six identités du pilote exclues.
- GenD PE, configuration de l'application inchangée : 2 images/s, seuil 0,5 ;
  alerte si au moins 50 % des images utilisables atteignent ce seuil.
- Couverture minimale 80 %, intervalle maximal sans observation 2 s.
- Corpus/configuration/manifeste des modèles gelés avant le test. Aucun entraînement
  ni réglage de seuil à partir de ces 50 vidéos. Sept anciens clips restent en `dev`
  et ne contribuent à aucun chiffre ci-dessus.
- Même encodage final pour les deux classes : MP4 H264 CRF18, 512×384, 25 fps,
  séquence complète, audio retiré. Les compressions antérieures restent différentes.
- Corpus ancien, une famille de manipulation, conditions contrôlées : pas une mesure
  représentative de tous les deepfakes, ni un benchmark de liveness ou de métadonnées.
- Les vrais/truqués sont appariés et certains échanges d'identité sont réciproques.
  Les 50 clips ne sont pas 50 observations indépendantes. Les intervalles Wilson
  ci-dessus sont descriptifs et ne corrigent pas cette dépendance.
- Le modèle a déjà été choisi sur un pilote comprenant d'autres DeepfakeTIMIT :
  nouvelles identités et nouvelles vidéos, mais **pas un nouveau domaine** de validation.

## Sources et attribution

- [DeepfakeTIMIT — dépôt officiel](https://zenodo.org/records/4068245),
  P. Korshunov et S. Marcel, *DeepFakes: a New Threat to Face Recognition?
  Assessment and Detection*, 2018. [Publication](https://arxiv.org/abs/1812.08685).
- [VidTIMIT — dépôt officiel](https://zenodo.org/records/158963),
  C. Sanderson et B. C. Lovell, *Multi-Region Probabilistic Histograms for Robust
  and Scalable Identity Inference*, LNCS 5558, pp. 199–208, 2009.
- Les métadonnées des deux dépôts indiquent CC BY-NC-ND 4.0. Les vidéos converties
  restent locales et ne sont pas redistribuées dans Git.

## Vérifiabilité

Le détail des 50 décisions est dans [results.csv](results.csv), les ratios et
empreintes dans [summary.json](summary.json), les sorties complètes dans
[benchmark.json](benchmark.json). Voir [README.md](README.md) pour relancer.

- Corpus : `{report['dataset_sha256']}`
- Configuration : `{report['config_sha256']}`
- Manifeste modèles : `{report['models_manifest_sha256']}`
"""
    outputs[2].write_text(text)
    print(count("correct_end_to_end"))


if __name__ == "__main__":
    main()
