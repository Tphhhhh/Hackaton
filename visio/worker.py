"""Internal subprocess entry point. JSON in, bounded JSON out. No network."""
import json
import os
import resource
import sys

from .core import GEND_DETECTORS, VisioError, error_result


def main():
    request = json.loads(sys.stdin.buffer.read(65536))
    # Hard local limits before importing native runtimes. RSS is also watched by parent.
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024**2, 2 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (240, 240))
    # CUDA reserves a large virtual address space; physical RSS is still bounded
    # to 4 GiB by the supervisor. The GPU worker exits after each clip.
    if not any(key in GEND_DETECTORS for key in request["config"]["detectors"]):
        resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[key] = str(request["config"]["threads"])
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    try:
        from .pipeline import run
        value = run(request)
    except VisioError as exc:
        value = error_result(request["config"], exc, session_id=request["session_id"], generation=request["generation"])
    except Exception as exc:
        value = error_result(request["config"], VisioError("WorkerFailed", f"Worker arrêté ({type(exc).__name__}).",
                             "Vérifier dépendances, mémoire et diagnostic local."),
                             session_id=request["session_id"], generation=request["generation"])
    sys.stdout.write(json.dumps(value, allow_nan=False))


if __name__ == "__main__":
    main()
