"""Single-flight local supervisor. Does not expose a network service."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid

from .core import DEFAULT_CACHE, ROOT, VisioError, canonical_hash, error_result, fail


@contextmanager
def admission():
    # A single state directory even when model-cache location changes.
    state = DEFAULT_CACHE / "state"
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state / "admission.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fail("AnalysisBusy", "Une analyse est déjà active.", "Attendre sa fin puis réessayer.")
        try:
            # Previous supervised crashes can only leave JSON/logs, never copied videos.
            for old in state.glob("job-*"):
                if old.is_symlink() or not stat.S_ISDIR(old.lstat().st_mode) or old.stat().st_uid != os.getuid():
                    fail("CleanupFailed", "Répertoire temporaire inattendu.", "Vérifier manuellement le dossier state.")
                shutil.rmtree(old)
            yield state
        except OSError as exc:
            raise VisioError("CleanupFailed", "Nettoyage ou accès temporaire impossible.",
                             "Fermer le worker et vérifier les permissions du dossier state.") from exc
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def rss_bytes(pid):
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except FileNotFoundError:
        return 0
    return 0


def terminate(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait(timeout=5)


def analyze(path, config, cache, model_manifest, *, worker_command=None,
            tracking_sink=None, media_id=None, cancel_event=None):
    """One call owns its generation; only returns after exit and successful cleanup.

    There is no asynchronous publication shared with a retry. Killing and joining
    the previous worker precedes release of the admission lock.
    """
    session_id = str(uuid.uuid4())
    request = dict(input=str(Path(path).resolve()), config=config, cache=str(Path(cache).resolve()),
                   manifest=str(Path(model_manifest).resolve()), session_id=session_id, generation=1)
    started = time.monotonic()
    value = None
    try:
        with admission() as state:
            temp = Path(tempfile.mkdtemp(prefix="job-", dir=state))
            process = None
            try:
                if tracking_sink is not None:
                    request.update(tracking_file=str(temp / "tracking.json"), media_id=media_id)
                if cancel_event is not None and cancel_event.is_set():
                    fail("AnalysisCancelled", "Analyse annulée.", "Relancer si nécessaire.")
                with (temp / "result.json").open("wb") as out, (temp / "stderr.log").open("wb") as err:
                    process = subprocess.Popen(worker_command or [sys.executable, "-m", "visio.worker"],
                                               stdin=subprocess.PIPE, stdout=out, stderr=err,
                                               start_new_session=True, cwd=ROOT.parent)
                    process.stdin.write(json.dumps(request).encode())
                    process.stdin.close()
                    while process.poll() is None:
                        if cancel_event is not None and cancel_event.is_set():
                            fail("AnalysisCancelled", "Analyse annulée.", "Relancer si nécessaire.")
                        if time.monotonic() - started > config["timeout_seconds"]:
                            fail("AnalysisTimeout", "Délai de traitement dépassé.", "Réduire les détecteurs ou la durée du clip.")
                        if rss_bytes(process.pid) > 4 * 1024**3:
                            fail("ResourceLimit", "Mémoire worker supérieure à 4 Gio.", "Sélectionner moins de modèles.")
                        if sum(f.stat().st_size for f in temp.iterdir()) > 4 * 1024**2:
                            fail("ResourceLimit", "Sortie worker trop volumineuse.", "Vérifier le runtime.")
                        time.sleep(0.02)
                if process.returncode:
                    fail("WorkerFailed", f"Worker interrompu (code {process.returncode}).", "Vérifier ressources et installation.")
                raw = (temp / "result.json").read_bytes()
                if len(raw) > 2 * 1024**2:
                    fail("WorkerFailed", "Réponse trop volumineuse.", "Vérifier le worker.")
                value = json.loads(raw, parse_constant=lambda _: fail(
                    "WorkerFailed", "Valeur JSON non finie.", "Vérifier le worker."))
                from jsonschema import Draft202012Validator
                schema = json.loads((ROOT / "schema.json").read_text())
                if not Draft202012Validator(schema).is_valid(value):
                    fail("WorkerFailed", "Réponse hors contrat JSON.", "Vérifier le worker et la version du schéma.")
                if value["session_id"] != session_id or value["generation"] != 1:
                    fail("WorkerFailed", "Résultat d'une autre tentative.", "Relancer une analyse.")
                if (value["simulation"] or value["config"] != config
                        or value["config_sha256"] != canonical_hash(config)
                        or (value["status"] in ("completed", "partial")
                            and set(value["detectors"]) != set(config["detectors"]))):
                    fail("WorkerFailed", "Résultat incompatible avec la requête.", "Vérifier le worker.")
                if tracking_sink is not None and (temp / "tracking.json").is_file():
                    tracking = json.loads((temp / "tracking.json").read_text())
                    tracking_schema = json.loads((ROOT / "tracking.schema.json").read_text())
                    if (not Draft202012Validator(tracking_schema).is_valid(tracking)
                            or tracking["media_id"] != media_id):
                        fail("WorkerFailed", "Coordonnées hors contrat.", "Vérifier l'adaptateur de suivi.")
                    tracking_sink["data"] = tracking
            finally:
                if process is not None:
                    terminate(process)
                shutil.rmtree(temp)
    except KeyboardInterrupt:
        value = error_result(config, VisioError("AnalysisCancelled", "Analyse annulée.", "Relancer si nécessaire."),
                             status="cancelled", session_id=session_id)
    except VisioError as exc:
        value = error_result(config, exc, session_id=session_id,
                             status="cancelled" if exc.code == "AnalysisCancelled" else "failed")
    except (ValueError, KeyError, BrokenPipeError, OSError, subprocess.SubprocessError) as exc:
        value = error_result(config, VisioError("WorkerFailed", f"Protocole worker invalide ({type(exc).__name__}).",
                             "Vérifier installation et runtime."), session_id=session_id)
    value["timing"]["total_seconds"] = time.monotonic() - started
    if value["status"] in ("failed", "cancelled") and tracking_sink is not None:
        tracking_sink.clear()
    return value
