"""CLI stays dependency-free until actual inference (inside the worker)."""
import argparse
import json
from pathlib import Path
import sys

from .core import (AVAILABLE_DETECTORS, DEFAULT_CACHE, DEFAULT_CONFIG, DEFAULT_MANIFEST, ROOT, VisioError,
                   configuration, error_result, exit_code, fail, read_json)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Benchmark vidéo local, signaux exploratoires uniquement.")
    subs = parser.add_subparsers(dest="command", required=True)
    ex = subs.add_parser("example", help="JSON simulé, sans modèles ni dépendances")
    ex.add_argument("case", choices=["no_signal", "verify", "indeterminate", "failed", "cancelled", "partial"], nargs="?", default="indeterminate")
    for command in ("fetch-models", "analyze", "benchmark", "freeze"):
        p = subs.add_parser(command)
        p.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
        p.add_argument("--config", type=Path)
        p.add_argument("--detectors", nargs="+", choices=AVAILABLE_DETECTORS)
        p.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
        if command == "analyze":
            p.add_argument("--input", type=Path, required=True)
        if command in ("benchmark", "freeze"):
            p.add_argument("--dataset", type=Path, required=True)
            p.add_argument("--output", type=Path, required=True)
        if command == "benchmark":
            p.add_argument("--split", choices=["dev", "test"], default="dev")
            p.add_argument("--evaluation-lock", type=Path)
    args = parser.parse_args(argv)
    config = DEFAULT_CONFIG.copy()
    try:
        if args.command == "example":
            output = read_json(ROOT / "examples" / f"{args.case}.json")
            code = 0
        else:
            config = configuration(args.config, args.detectors)
            if args.command == "fetch-models":
                from .models import download, manifest
                models = manifest(args.manifest)
                selected = (["yunet"] if any(k != "gend" for k in config["detectors"]) else []) + config["detectors"]
                for name in selected:
                    print(f"Téléchargement/vérification : {name}", file=sys.stderr)
                    download(args.cache, name, models["models"][name])
                output, code = {"status": "ready", "models": selected}, 0
            elif args.command == "analyze":
                from .runner import analyze
                output = analyze(args.input, config, args.cache, args.manifest)
                code = exit_code(output)
            else:
                from .benchmark import benchmark, freeze
                if args.output.exists():
                    fail("InvalidConfiguration", "Le fichier de sortie existe déjà.", "Choisir un nouveau nom pour conserver les expériences précédentes.")
                output = (freeze(args.dataset, config, args.manifest) if args.command == "freeze" else
                          benchmark(args.dataset, config, args.manifest, args.cache, args.split, args.evaluation_lock))
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open("x") as f:
                    json.dump(output, f, indent=2, allow_nan=False)
                    f.write("\n")
                code = 0
        print(json.dumps(output, indent=2, allow_nan=False))
        return code
    except VisioError as exc:
        value = error_result(config, exc)
        print(json.dumps(value, indent=2, allow_nan=False))
        return exit_code(value)
    except (OSError, KeyError) as exc:
        value = error_result(config, VisioError("InvalidConfiguration", f"Accès ou configuration invalide ({type(exc).__name__}).",
                                               "Vérifier les chemins et les permissions."))
        print(json.dumps(value, indent=2))
        return 2


if __name__ == "__main__":
    sys.exit(main())
