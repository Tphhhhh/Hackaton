"""Single-page Visio + selected metadata. No dossiers, persistence or signup."""
import argparse
from http.server import SimpleHTTPRequestHandler
import json
from urllib.parse import urlsplit
from visio.server import DemoServer, Handler as VisioHandler
from metadata.session import evaluate


class Server(DemoServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.RequestHandlerClass = Handler


class Handler(VisioHandler):
    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self' https://api.ipify.org https://ipapi.co https://www.cloudflare.com; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        SimpleHTTPRequestHandler.end_headers(self)

    def do_GET(self):
        if urlsplit(self.path).path in ('/recruiter','/apply','/offre','/onboarding','/entretien'):
            if not self.allowed(): return
            self.send_response(302); self.send_header('Location','/'); self.send_header('Content-Length','0'); self.end_headers(); return
        return super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path != '/api/session/analyze': return super().do_POST()
        if not self.allowed(mutation=True): return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16384 or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Type')!='application/json':
                raise ValueError('Objet JSON de 16 Kio maximum requis.')
            value=json.loads(self.rfile.read(length),parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nombre invalide.')))
            return self.reply(200,evaluate(value))
        except (ValueError,TypeError,OverflowError):
            return self.reply(400,{'error':'Mesures techniques invalides.'})


def main():
    parser=argparse.ArgumentParser(description='Sentinelle + Visio, serveur local intégré')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-models',action='store_true',help='Interface et métadonnées seules, aucun score vidéo simulé')
    args=parser.parse_args()
    swapper=None
    try:
        scorer=None
        if not args.no_models:
            from visio.live_swap_process import SwapProcess
            from visio.live_scores import LivePEScorer
            print('Chargement du filtre et de GenD PE…',flush=True)
            swapper=SwapProcess();scorer=LivePEScorer()
        server=Server(args.port,swapper=swapper,scorer=scorer)
        print(f'Visio + signaux : http://127.0.0.1:{server.server_port}/',flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass
        finally: server.server_close()
    finally:
        if swapper: swapper.close()


if __name__=='__main__': main()
