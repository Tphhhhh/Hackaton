"""Single-user loopback demo: static frontend + explicit, bounded local analysis.

Start with the GPU venv. No external calls, cross-origin API or arbitrary paths.
Uploaded clips exist only in a private temporary directory during the request.
"""
import argparse
from collections import OrderedDict
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit
import uuid

from .core import DEFAULT_CACHE, DEFAULT_MANIFEST, ROOT, configuration
from .runner import analyze

MAX_UPLOAD = 50 * 1024**2
SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".avi"}


class DemoServer(ThreadingHTTPServer):
    daemon_threads = False

    def __init__(self, port=8765, frontend=None, analyzer=analyze, swapper=None):
        self.frontend = Path(frontend or ROOT.parent / "visio-demo/dist").resolve()
        self.analyzer = analyzer
        self.swapper = swapper
        self.config = configuration(ROOT / "config.gend.json")
        self.slot = threading.Lock()
        self.state_lock = threading.Lock()
        self.cancellations = OrderedDict()
        self.upload_root = DEFAULT_CACHE / "browser-uploads"
        self.upload_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        super().__init__(("127.0.0.1", port), Handler)

    def cancel_event(self, media_id):
        with self.state_lock:
            event = self.cancellations.setdefault(media_id, threading.Event())
            self.cancellations.move_to_end(media_id)
            # Includes pre-admission cancellations, for DELETE racing an upload.
            while len(self.cancellations) > 64:
                self.cancellations.popitem(last=False)
            return event


class Handler(SimpleHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(args[2].frontend), **kwargs)

    def log_message(self, format, *args):
        pass  # No clip names or result payloads in HTTP logs.

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        super().end_headers()

    def reply(self, status, value):
        payload = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def allowed(self, mutation=False):
        authority = f"127.0.0.1:{self.server.server_port}"
        origin = self.headers.get("Origin")
        valid = (self.headers.get("Host") == authority
                 and (origin is None or origin == f"http://{authority}")
                 and self.headers.get("Sec-Fetch-Site") != "cross-site")
        if mutation:
            valid &= self.headers.get("X-Visio-Request") == "1"
        if not valid:
            self.reply(403, {"error": "Requête locale de même origine requise."})
        return valid

    def media_id(self):
        path = urlsplit(self.path).path
        prefix = "/api/analyze/"
        if not path.startswith(prefix):
            raise ValueError("route")
        value = path[len(prefix):]
        if str(uuid.UUID(value)) != value:
            raise ValueError("media_id")
        return value

    def do_GET(self):
        if not self.allowed():
            return
        if self.path == "/api/status":
            return self.reply(200, {"backend": "gend", "mode": "local", "tracking_fps": 8,
                                    "analysis_fps": 2, "max_bytes": MAX_UPLOAD})
        if self.path == "/api/live/status":
            return self.reply(200, self.server.swapper.info if self.server.swapper else {
                "ready": False, "error": "Face swap indisponible. Démarrez le serveur avec --live-swap."})
        if urlsplit(self.path).path.startswith("/api/"):
            return self.reply(404, {"error": "Route inconnue."})
        super().do_GET()

    def do_HEAD(self):
        if self.allowed():
            super().do_HEAD()

    def do_DELETE(self):
        if not self.allowed(mutation=True):
            return
        try:
            self.server.cancel_event(self.media_id()).set()
        except ValueError:
            return self.reply(400, {"error": "Référence vidéo invalide."})
        self.reply(200, {"status": "cancelling"})

    def do_POST(self):
        if not self.allowed(mutation=True):
            return
        if self.path == "/api/live/swap":
            return self.live_swap()
        try:
            media_id = self.media_id()
            suffix = parse_qs(urlsplit(self.path).query).get("suffix", [""])[0].lower()
            length = int(self.headers.get("Content-Length", "0"))
            if (suffix not in SUFFIXES or not 0 < length <= MAX_UPLOAD
                    or self.headers.get("Transfer-Encoding")
                    or self.headers.get("Content-Type") != "application/octet-stream"):
                raise ValueError("upload")
        except ValueError:
            return self.reply(400, {"error": "Vidéo de 50 Mio maximum, format et taille explicites requis."})
        if not self.server.slot.acquire(blocking=False):
            return self.reply(409, {"error": "Une analyse se termine encore. Réessayez dans quelques secondes."})
        event = self.server.cancel_event(media_id)
        try:
            self.connection.settimeout(10)
            with tempfile.TemporaryDirectory(prefix="clip-", dir=self.server.upload_root) as folder:
                path = Path(folder) / ("input" + suffix)
                with path.open("xb") as stream:
                    remaining = length
                    while remaining:
                        if event.is_set():
                            return self.reply(409, {"error": "Analyse annulée."})
                        block = self.rfile.read(min(1024**2, remaining))
                        if not block:
                            return self.reply(400, {"error": "Vidéo incomplète."})
                        stream.write(block)
                        remaining -= len(block)
                tracking = {}
                result = self.server.analyzer(path, self.server.config, DEFAULT_CACHE, DEFAULT_MANIFEST,
                                              tracking_sink=tracking, media_id=media_id, cancel_event=event)
                self.reply(200, {"media_id": media_id, "result": result, "tracking": tracking.get("data")})
        except (socket.timeout, ConnectionResetError, BrokenPipeError):
            event.set()
            self.reply(408, {"error": "Transfert local interrompu."})
        except Exception:
            self.reply(500, {"error": "Analyse locale interrompue. Vérifiez le moteur et réessayez."})
        finally:
            self.server.slot.release()

    def live_swap(self):
        from .live_swap import MAX_FRAME_BYTES
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_FRAME_BYTES or self.headers.get("Content-Type") != "image/jpeg" or self.headers.get("Transfer-Encoding"):
                raise ValueError()
        except ValueError:
            return self.reply(400, {"error": "Image JPEG de 1 Mio maximum requise."})
        if not self.server.swapper:
            return self.reply(503, {"error": "Face swap indisponible. Démarrez le serveur avec --live-swap."})
        if not self.server.slot.acquire(blocking=False):
            return self.reply(409, {"error": "GPU occupé, image ignorée."})
        try:
            payload = self.rfile.read(length)
            if len(payload) != length:
                raise ValueError("Image incomplète.")
            jpeg, result = self.server.swapper.process(payload)
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(jpeg)))
            self.send_header("X-Visio-Swapped", "1" if result["applied"] else "0")
            self.send_header("X-Visio-Inference-Ms", str(result["inference_ms"]))
            self.end_headers()
            self.wfile.write(jpeg)
        except ValueError as error:
            self.reply(400, {"error": str(error)})
        except (socket.timeout, ConnectionResetError, BrokenPipeError):
            pass
        except Exception:
            self.reply(500, {"error": "Face swap interrompu. Relancez la caméra ou vérifiez le moteur local."})
        finally:
            self.server.slot.release()


def main():
    parser = argparse.ArgumentParser(description="Démo GenD locale, accessible uniquement sur 127.0.0.1.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--live-swap", action="store_true", help="Précharger InSwapper sur le GPU NVIDIA pour la webcam")
    args = parser.parse_args()
    if not (ROOT.parent / "visio-demo/dist/index.html").is_file():
        parser.error("Construire l'interface : cd visio-demo && npm ci && npm run build")
    swapper = None
    if args.live_swap:
        from .live_swap import LiveSwapper
        print("Chargement du face swap neuronal sur CUDA…", flush=True)
        swapper = LiveSwapper()
    server = DemoServer(args.port, swapper=swapper)
    print(f"Visio + GenD : http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        with server.state_lock:
            for event in server.cancellations.values():
                event.set()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
