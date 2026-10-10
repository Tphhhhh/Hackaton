"""Interface de démo pour l'analyste.

    pip install streamlit
    streamlit run metadata/app.py

File des dossiers triée par risque, graphe des réseaux de personas, fiche détaillée
avec signaux et questions de vérification, et décision humaine tracée dans le
journal d'audit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from metadata import audit  # noqa: E402
from metadata.decide import DECISIONS  # noqa: E402
from metadata.evaluate import evaluate  # noqa: E402
from metadata.run import analyse, load_dotenv  # noqa: E402
from metadata.schema import load_candidates  # noqa: E402
from metadata.video import load_video_scores  # noqa: E402

DATA_DIR = ROOT / "metadata" / "data" / "synthetic"
LOG = ROOT / "out" / "audit.jsonl"
LEVEL_COLOR = {"élevé": "🔴", "moyen": "🟠", "faible": "🟢"}
DECISION_LABEL = {"clear": "Valider le dossier", "verify": "Demander une vérification",
                  "escalate": "Escalader à la conformité", "reject": "Refuser la candidature"}

st.set_page_config(page_title="Vérification des candidatures", page_icon="🛡️", layout="wide")
load_dotenv(str(ROOT / ".env"))


@st.cache_data(show_spinner="Analyse des dossiers…")
def run(data_path: str, video_path: str) -> tuple[list[dict], dict]:
    candidates = load_candidates(data_path)
    return candidates, analyse(candidates, load_video_scores(video_path))


def decisions_for(cid: str) -> list[dict]:
    if not LOG.exists():
        return []
    entries = [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [e for e in entries if e["event"] == "human_decision" and e["payload"]["id"] == cid]


# --- Barre latérale ---------------------------------------------------------------
st.sidebar.title("🛡️ Know Your Freelancer")
data_path = st.sidebar.text_input("Fichier de dossiers", str(DATA_DIR / "candidates.json"))
labels_path = Path(data_path).with_name("labels.json")
video_path = st.sidebar.text_input("Scores du module vidéo", str(Path(data_path).with_name("video_scores.json")))
show_truth = st.sidebar.toggle("Mode démo : afficher la vérité terrain", value=False,
                               disabled=not labels_path.exists())
if st.sidebar.button("Relancer l'analyse"):
    run.clear()
st.sidebar.caption("Aide à la décision uniquement. Aucun signal ne porte sur l'origine, "
                   "la nationalité ou l'accent. La décision finale revient à un humain.")

candidates, report = run(data_path, video_path)
by_id = {c["id"]: c for c in candidates}
results = report["results"]
labels = json.loads(labels_path.read_text(encoding="utf-8")) if show_truth else {}

# --- Indicateurs ------------------------------------------------------------------
st.title("Vérification des candidatures à distance")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Dossiers analysés", len(results))
k2.metric("À vérifier", sum(r["flagged"] for r in results))
k3.metric("Réseaux de personas", len(report["networks"]))
k4.metric("Temps d'analyse", f"{report['total_seconds']} s")

if show_truth:
    m = evaluate(report, labels)
    st.info(f"**Vérité terrain** : détection {m['detection_rate']:.0%}, faux positifs "
            f"{m['false_positive_rate']:.0%}, réseaux retrouvés {m['networks_recovered']}, "
            f"fraudes manquées : {', '.join(m['missed']) or 'aucune'}.")

tab_queue, tab_networks, tab_detail, tab_audit = st.tabs(
    ["📋 File de revue", "🕸️ Réseaux", "🔎 Fiche dossier", "🧾 Journal d'audit"])

# --- File de revue ----------------------------------------------------------------
with tab_queue:
    only_flagged = st.checkbox("Seulement les dossiers à vérifier", value=True)
    rows = []
    for r in results:
        if only_flagged and not r["flagged"]:
            continue
        c = by_id[r["id"]]
        last = decisions_for(r["id"])
        row = {"Dossier": r["id"], "Risque": f"{LEVEL_COLOR[r['level']]} {r['score']}",
               "Candidat": c["full_name"], "Lieu déclaré": c["declared_location"]["city"],
               "Signaux": ", ".join(s["code"].split("_", 1)[1].replace("_", " ").lower() for s in r["signals"]),
               "Décision": last[-1]["payload"]["decision"] if last else "—"}
        if show_truth:
            row["Vérité"] = "fraude" if labels[r["id"]]["is_fraud"] else "légitime"
        rows.append(row)
    st.dataframe(rows, width="stretch", hide_index=True)

# --- Réseaux ----------------------------------------------------------------------
with tab_networks:
    if not report["networks"]:
        st.write("Aucun réseau détecté.")
    else:
        edges = []
        for link in report["links"]:
            label = "\\n".join(link["reasons"]).replace('"', "'")
            edges.append(f'"{link["a"]}" -- "{link["b"]}" [label="{label}", fontsize=9];')
        nodes = []
        score_of = {r["id"]: r["score"] for r in results}
        for net in report["networks"]:
            for cid in net:
                color = "#e5484d" if score_of[cid] >= 50 else "#f5a524" if score_of[cid] >= 25 else "#46a758"
                nodes.append(f'"{cid}" [label="{cid}\\n{by_id[cid]["full_name"]}\\n{score_of[cid]}/100", '
                             f'style=filled, fillcolor="{color}", fontcolor=white, shape=box];')
        st.graphviz_chart("graph { rankdir=LR; " + " ".join(nodes + edges) + " }")
        st.caption("Chaque groupe relie des candidatures qui partagent un identifiant (téléphone, compte de "
                   "paiement, email, profil) ou un CV quasi identique. Un lien n'est pas une preuve : "
                   "deux anciens élèves d'un même bootcamp peuvent avoir des CV proches.")

# --- Fiche dossier ----------------------------------------------------------------
with tab_detail:
    ids = [r["id"] for r in results]
    cid = st.selectbox("Dossier", ids, format_func=lambda i: f"{i} · {by_id[i]['full_name']}")
    r = next(x for x in results if x["id"] == cid)
    c = by_id[cid]
    left, right = st.columns([1, 1])
    with left:
        st.subheader(f"{LEVEL_COLOR[r['level']]} {c['full_name']} · {r['score']}/100")
        loc = c["declared_location"]
        st.write(f"**Lieu déclaré** : {loc['city']} ({loc['country']}, {loc['timezone']})")
        st.write(f"**Email** : {c['email']}  \n**Téléphone** : {c['phone']}")
        st.write(f"**Candidature** : {c['applied_at']} · **Embauche** : {c.get('hired_at') or '—'}")
        st.write(f"**Expérience revendiquée** : {c['cv']['years_experience']} ans")
        with st.expander("CV"):
            st.write(c["cv"]["summary"])
            for e in c["cv"]["experiences"]:
                st.write(f"- {e['start']} → {e['end'] or 'aujourd’hui'} · {e['title']} chez {e['company']}")
    with right:
        st.subheader("Signaux")
        if not r["signals"]:
            st.success("Aucune incohérence factuelle détectée.")
        for s in sorted(r["signals"], key=lambda s: -s["weight"]):
            st.write(f"**+{s['weight']} · {s['code']}** {('(' + s['mitre'] + ')') if s['mitre'] else ''}  \n{s['evidence']}")
        st.subheader("Explication")
        st.write(r["explanation"]["summary"])
        if r["explanation"]["questions"]:
            st.write("**Questions de vérification**")
            for q in r["explanation"]["questions"]:
                st.write(f"- {q}")
        st.caption(f"{r['explanation']['disclaimer']} Moteur : {r['explanation']['engine']}.")

    st.divider()
    st.subheader("Décision de l'analyste")
    with st.form(f"decision-{cid}"):
        decision = st.radio("Décision", DECISIONS, format_func=DECISION_LABEL.get, horizontal=True,
                            index=1 if r["flagged"] else 0)
        analyst = st.text_input("Analyste")
        note = st.text_area("Justification")
        if st.form_submit_button("Enregistrer la décision"):
            if not analyst.strip():
                st.error("Indiquez le nom de l'analyste : chaque décision doit être attribuée.")
            else:
                entry = audit.append("human_decision", {"id": cid, "decision": decision, "note": note,
                                                        "score": r["score"]}, actor=analyst.strip(), log=LOG)
                st.success(f"Décision enregistrée (hash {entry['hash'][:12]}…).")
    for d in decisions_for(cid):
        st.write(f"- {d['ts']} · **{d['actor']}** : {DECISION_LABEL[d['payload']['decision']]}"
                 f"{' · ' + d['payload']['note'] if d['payload']['note'] else ''}")

# --- Journal d'audit --------------------------------------------------------------
with tab_audit:
    if not LOG.exists():
        st.write("Aucune décision enregistrée pour l'instant.")
    else:
        ok, msg = audit.verify(LOG)
        (st.success if ok else st.error)(f"Intégrité du journal : {msg}")
        entries = [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
        st.dataframe([{"Horodatage": e["ts"], "Événement": e["event"], "Acteur": e["actor"],
                       "Dossier": e["payload"].get("id"), "Décision": e["payload"].get("decision", ""),
                       "Hash": e["hash"][:16] + "…"} for e in reversed(entries)],
                     width="stretch", hide_index=True)
        st.caption("Chaque entrée contient le hash de la précédente : toute modification a posteriori "
                   "est détectée (piste d'audit, AI Act).")
