"""Bounded, in-memory IPC to the isolated InSwapper environment.

GenD keeps its existing PyTorch/NumPy environment; InsightFace keeps its own
runtime. Neither process contacts the other app on port 8770.
"""
import base64
import contextlib
import json
import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import time

from .core import ROOT

MAX_PACKET = 2 * 1024**2


def read_exact(fd, length, deadline):
    result = bytearray()
    while len(result) < length:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
            raise TimeoutError("Face swap trop lent.")
        block = os.read(fd, length - len(result))
        if not block:
            raise RuntimeError("Processus face swap arrêté.")
        result.extend(block)
    return bytes(result)


def read_packet(fd, timeout):
    deadline = time.monotonic() + timeout
    length = struct.unpack("!I", read_exact(fd, 4, deadline))[0]
    if not 0 < length <= MAX_PACKET:
        raise ValueError("Réponse face swap invalide.")
    return read_exact(fd, length, deadline)


def write_packet(fd, payload, timeout=15):
    if not 0 < len(payload) <= MAX_PACKET:
        raise ValueError("Image trop volumineuse.")
    data = memoryview(struct.pack("!I", len(payload)) + payload)
    deadline = time.monotonic() + timeout
    while data:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([], [fd], [], remaining)[1]:
            raise TimeoutError("Face swap indisponible.")
        data = data[os.write(fd, data[:4096]):]


class SwapProcess:
    def __init__(self, python=None):
        python = Path(python or ROOT / ".cache/live-runtime/bin/python")
        if not python.is_file():
            raise RuntimeError("Installer l'environnement visio/.cache/live-runtime.")
        env = dict(os.environ, OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")
        self.process_handle = subprocess.Popen([str(python), "-m", "visio.live_swap_process"],
            cwd=ROOT.parent, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0, env=env)
        try:
            self.info = json.loads(read_packet(self.process_handle.stdout.fileno(), 120))
            if not self.info.get("ready"):
                raise RuntimeError(self.info.get("error", "Face swap indisponible."))
        except BaseException:
            self.close()
            raise

    def process(self, payload, portrait_id="brad-pitt"):
        from .live_swap import PORTRAITS
        if portrait_id not in PORTRAITS:
            raise ValueError("Portrait inconnu.")
        try:
            packet = json.dumps({"portrait_id": portrait_id,
                                 "image": base64.b64encode(payload).decode()}).encode()
            write_packet(self.process_handle.stdin.fileno(), packet)
            value = json.loads(read_packet(self.process_handle.stdout.fileno(), 15))
            if "error" in value:
                raise ValueError(value["error"])
            return base64.b64decode(value.pop("image"), validate=True), value
        except (TimeoutError, RuntimeError, BrokenPipeError):
            self.close()
            self.info = {"ready": False, "error": "Face swap arrêté. Relancer le serveur."}
            raise

    def close(self):
        child = self.process_handle
        if child.poll() is None:
            child.kill()
        child.wait(timeout=5)
        child.stdin.close()
        child.stdout.close()


def main():
    output = sys.stdout.fileno()
    def reply(value):
        write_packet(output, json.dumps(value, allow_nan=False).encode())
    try:
        # Third-party initialization messages must not enter the binary protocol.
        with contextlib.redirect_stdout(sys.stderr):
            from .live_swap import LiveSwapper
            engine = LiveSwapper()
        reply(engine.info)
    except Exception as exc:
        reply({"ready": False, "error": f"Chargement face swap échoué ({type(exc).__name__})."})
        return
    while True:
        try:
            payload = read_packet(sys.stdin.fileno(), 86400)
        except (RuntimeError, TimeoutError):
            return
        try:
            request = json.loads(payload)
            image, info = engine.process(base64.b64decode(request["image"], validate=True),
                                         portrait_id=request["portrait_id"])
            reply(dict(info, image=base64.b64encode(image).decode()))
        except ValueError as exc:
            reply({"error": str(exc)})
        except Exception:
            reply({"error": "Face swap interrompu."})


if __name__ == "__main__":
    main()
