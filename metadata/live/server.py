"""Mode en direct : surveillance des métadonnées pendant l'entretien.

    python -m metadata.live.server            # puis ouvrir http://localhost:8000

- http://localhost:8000/apply       offre d'emploi fictive : CV (pré-remplissage automatique), parcours, mission
- http://localhost:8000/onboarding  après sélection : adresse, livraison du matériel, versement
- http://localhost:8000/            page candidat : consentement, puis une mesure toutes les 5 s
- http://localhost:8000/recruiter   panneau recruteur : score, alertes, chronologie, décision

Aucune dépendance. Les sessions restent en mémoire et disparaissent à l'arrêt du serveur ;
seules les décisions du recruteur sont écrites dans le journal d'audit (out/audit.jsonl).
Le score réutilise exactement les contrôles I1 à I6 du pipeline par lots, plus des alertes
de changement en cours d'appel (caméra, IP, latence), souvent plus parlantes qu'une valeur isolée.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

from .. import audit, cv_parser
from . import applications
from ..checks import (Signal, check_browser_timezone, check_interview_ip, check_latency,
                      check_video_settings, check_virtual_camera, check_vm_gpu, combination_bonus)
from ..explain import explain
from ..scoring import HIGH, MEDIUM

HERE = Path(__file__).resolve().parent
LOG = Path("out/audit.jsonl")
# Décalage UTC en octobre (heure d'été) du pays déclaré.
COUNTRY_OFFSET = {"FR": 2, "DE": 2, "CH": 2, "BE": 2, "NL": 2, "ES": 2, "IT": 2, "PT": 1, "UK": 1, "GB": 1, "IE": 1}

DECISIONS = {"clear", "verify", "escalate", "reject"}
SESSIONS: dict[str, dict] = {}
LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _median(xs: list[float]) -> float | None:
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def _changes(prev: dict, cur: dict) -> list[str]:
    """Différences notables entre deux mesures successives."""
    out = []
    if prev["devices"]["video"] != cur["devices"]["video"]:
        out.append(f"Caméra changée : {', '.join(prev['devices']['video']) or '?'} → "
                   f"{', '.join(cur['devices']['video']) or '?'}")
    if prev.get("ip", {}).get("address") and prev["ip"].get("address") != cur.get("ip", {}).get("address"):
        out.append(f"IP changée : {prev['ip'].get('country', '?')} → {cur['ip'].get('country', '?')}"
                   f"{' (hébergeur)' if cur['ip'].get('type') == 'datacenter' else ''}")
    p, c = _median(prev.get("rtt_ms", [])), _median(cur.get("rtt_ms", []))
    if p is not None and c is not None and c > 2 * p and c - p > 60:
        out.append(f"Latence en hausse brutale : {p:.0f} → {c:.0f} ms")
    if prev.get("browser_timezone") != cur.get("browser_timezone"):
        out.append(f"Fuseau de l'ordinateur changé : {prev.get('browser_timezone')} → {cur.get('browser_timezone')}")
    if prev.get("gpu_renderer") != cur.get("gpu_renderer"):
        out.append(f"Moteur graphique changé : {cur.get('gpu_renderer')}")
    return out


def evaluate_session(sess: dict) -> dict:
    """Applique les contrôles d'entretien à l'état courant de la session."""
    snap = sess["snapshots"][-1]
    declared = sess["declared"]
    pseudo = {
        "declared_location": {"country": declared["country"], "city": declared["city"],
                              "utc_offset": datetime.now(ZoneInfo(applications.COUNTRY_TZ.get(declared["country"], "Europe/Paris"))).utcoffset().total_seconds() / 3600},
        "interview_session": {
            **snap,
            "device_changed_during_call": sess["camera_changes"] > 0,
            "ip_changed_during_call": sess["ip_changes"] > 0,
            "rtt_ms": [r for s in sess["snapshots"][-6:] for r in s.get("rtt_ms", [])],
            "video_settings_changes": sess["video_changes"],
        },
    }
    if not snap.get("ip", {}).get("country"):
        pseudo["interview_session"].pop("ip", None)  # géolocalisation indisponible : pas de faux signal
    checks = [check_virtual_camera, check_browser_timezone, check_vm_gpu, check_interview_ip,
              check_latency, check_video_settings]
    signals = [s for chk in checks if (s := chk(pseudo)) is not None]
    if sess["events"]:
        signals.append(Signal("L1_LIVE_CHANGE", min(10 * len(sess["events"]), 20),
                              f"{len(sess['events'])} changement(s) en cours d'appel : "
                              + " ; ".join(e["text"] for e in sess["events"][-3:]) + "."))
    if (bonus := combination_bonus(signals)) is not None:
        signals.append(bonus)
    total = min(sum(s.weight for s in signals), 100)
    result = {"score": total, "level": "élevé" if total >= HIGH else "moyen" if total >= MEDIUM else "faible",
              "flagged": total >= MEDIUM, "signals": [s.to_dict() for s in signals]}
    result["explanation"] = explain(result)
    return result


def ingest(payload: dict, client_ip: str) -> dict:
    sid = payload["session_id"]
    snap = {k: payload.get(k) for k in ("devices", "browser_timezone", "browser_utc_offset", "gpu_renderer",
                                        "video_settings", "rtt_ms", "ip", "simulated")}
    snap["ip"] = {**(snap.get("ip") or {}), "seen_by_server": client_ip}
    snap["at"] = _now()
    with LOCK:
        sess = SESSIONS.setdefault(sid, {"id": sid, "declared": payload["declared"], "started": _now(),
                                         "snapshots": [], "events": [], "camera_changes": 0,
                                         "ip_changes": 0, "video_changes": 0})
        if sess["snapshots"]:
            prev = sess["snapshots"][-1]
            for text in _changes(prev, snap):
                sess["events"].append({"at": snap["at"], "text": text})
                sess["camera_changes"] += text.startswith("Caméra")
                sess["ip_changes"] += text.startswith("IP")
            if prev.get("video_settings") and prev["video_settings"] != snap.get("video_settings"):
                sess["video_changes"] += 1
        sess["snapshots"] = (sess["snapshots"] + [snap])[-60:]
        sess["result"] = evaluate_session(sess)
        sess["last_seen"] = time.time()
        return sess["result"]


def public_view() -> list[dict]:
    with LOCK:
        out = []
        for s in SESSIONS.values():
            if time.time() - s["last_seen"] > 60:  # onglet fermé ou rechargé : on n'encombre pas le panneau
                continue
            snap = s["snapshots"][-1]
            info = applications.public_info(s["id"])
            out.append({"id": s["id"], "name": info["name"] if info else None, "declared": s["declared"], "started": s["started"],
                        "online": time.time() - s["last_seen"] < 15, "snapshot": snap,
                        "events": s["events"][-20:], "result": s["result"], "decision": s.get("decision")})
        return sorted(out, key=lambda s: (not s["online"], -s["result"]["score"]))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence
        pass

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _client_ip(self) -> str:
        return self.headers.get("X-Forwarded-For", self.client_address[0]).split(",")[0].strip()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/apply", "/offre"):
            self._send(200, (HERE / "apply.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/onboarding":
            self._send(200, (HERE / "onboarding.html").read_bytes(), "text/html; charset=utf-8")
        elif path.startswith(("/vendor/", "/demo-cvs/", "/assets/")):
            # Fichiers statiques : uniquement le nom de fichier, jamais de chemin relatif.
            folder, name = path.strip("/").split("/", 1)
            f = HERE / folder.replace("-", "_") / Path(name).name
            ctype = {".pdf": "application/pdf", ".css": "text/css; charset=utf-8",
                     ".svg": "image/svg+xml"}.get(f.suffix, "text/javascript; charset=utf-8")
            if f.is_file():
                self._send(200, f.read_bytes(), ctype)
            else:
                self._send(404, b"Not found", "text/plain")
        elif path == "/api/applications":
            self._json(applications.listing())
        elif path.startswith("/api/applications/"):
            info = applications.public_info(path.rsplit("/", 1)[-1])
            self._json(info or {"error": "inconnue"}, 200 if info else 404)
        elif path == "/api/demo-example":
            kind = "fraud" if "fraud" in self.path else "honest"
            self._json(applications.demo_example(kind))
        elif path == "/api/demo-onboarding":
            kind = "fraud" if "fraud" in self.path else "honest"
            self._json(applications.demo_onboarding(kind))
        elif path in ("/", "/candidate"):
            self._send(200, (HERE / "candidate.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/recruiter":
            self._send(200, (HERE / "recruiter.html").read_bytes(), "text/html; charset=utf-8")
        elif path == "/api/ping":
            self._json({"t": time.time()})
        elif path == "/api/sessions":
            self._json(public_view())
        else:
            self._send(404, b"Not found", "text/plain")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "JSON invalide"}, 400)
        if self.path == "/api/apply":
            payload.setdefault("meta", {}).setdefault("ip", {})["seen_by_server"] = self._client_ip()
            try:
                app_id = applications.submit(payload)
            except (KeyError, ValueError) as exc:
                return self._json({"error": f"champ manquant ou invalide : {exc}"}, 400)
            return self._json({"id": app_id})
        if self.path == "/api/parse-cv":
            return self._json(cv_parser.parse_cv(str(payload.get("text", ""))[:50000]))
        if self.path == "/api/onboarding":
            try:
                ok = applications.onboard(str(payload.get("app_id", "")), payload)
            except (KeyError, ValueError) as exc:
                return self._json({"error": f"champ manquant ou invalide : {exc}"}, 400)
            return self._json({"ok": True} if ok else {"error": "candidature inconnue"}, 200 if ok else 404)
        if self.path == "/api/snapshot":
            return self._json(ingest(payload, self._client_ip()))
        if self.path == "/api/decision" and payload.get("app_id"):
            if payload.get("decision") not in DECISIONS or not payload.get("analyst"):
                return self._json({"error": "décision ou analyste manquant"}, 400)
            score = applications.decide(payload["app_id"], payload["decision"], payload["analyst"])
            if score is None:
                return self._json({"error": "candidature inconnue"}, 404)
            entry = audit.append("human_decision", {"id": f"app:{payload['app_id']}", "decision": payload["decision"],
                                                    "note": payload.get("note", ""), "score": score},
                                 actor=payload["analyst"], log=LOG)
            return self._json({"ok": True, "hash": entry["hash"]})
        if self.path == "/api/decision":
            with LOCK:
                sess = SESSIONS.get(payload.get("session_id"))
                if not sess or not payload.get("analyst"):
                    return self._json({"error": "session ou analyste manquant"}, 400)
                sess["decision"] = payload["decision"]
                score = sess["result"]["score"]
            entry = audit.append("human_decision", {"id": f"live:{payload['session_id']}", "decision": payload["decision"],
                                                    "note": payload.get("note", ""), "score": score},
                                 actor=payload["analyst"], log=LOG)
            return self._json({"ok": True, "hash": entry["hash"]})
        self._json({"error": "inconnu"}, 404)


def main():
    p = argparse.ArgumentParser(description="Mode en direct : surveillance des métadonnées d'entretien.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = p.parse_args()
    print(f"Offre d'emploi : http://localhost:{args.port}/apply\n"
          f"Entretien (candidat) : http://localhost:{args.port}/\n"
          f"Panneau recruteur : http://localhost:{args.port}/recruiter")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
