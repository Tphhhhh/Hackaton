"""HTTP transport tests use a stub; decoding tests use real JPEG buffers."""
import http.client
from io import BytesIO
import json
import threading

from PIL import Image
import pytest

from visio.live_swap import decode_frame, MAX_FRAME_BYTES
from visio.server import DemoServer


def jpeg(size=(640, 480)):
    buffer = BytesIO()
    Image.new('RGB', size, (25, 50, 75)).save(buffer, format='JPEG')
    return buffer.getvalue()


@pytest.mark.parametrize('payload', [b'', b'not an image', jpeg((2000, 1000)), b'x' * (MAX_FRAME_BYTES + 1)])
def test_reject_invalid_or_oversized_frames(payload):
    with pytest.raises(ValueError):
        decode_frame(payload)


def test_decode_valid_jpeg_in_memory():
    assert decode_frame(jpeg()).shape == (480, 640, 3)


@pytest.fixture
def live_server(tmp_path):
    class Swapper:
        info = {'ready': True, 'model': 'stub', 'provider': 'test'}
        calls = []

        def process(self, payload, portrait_id="brad-pitt"):
            decode_frame(payload)
            self.calls.append((portrait_id, payload))
            return payload, {'applied': True, 'inference_ms': 38.2}
    server = DemoServer(0, frontend=tmp_path, swapper=Swapper())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join()


def request(server, method='POST', path='/api/live/swap', body=None, headers=None):
    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
    conn.request(method, path, body=body, headers=headers or {'X-Visio-Request': '1', 'Content-Type': 'image/jpeg'})
    response = conn.getresponse()
    value = response.read()
    conn.close()
    return response.status, dict(response.getheaders()), value


def test_status_jpeg_and_no_recordings(live_server):
    status, _, data = request(live_server, 'GET', '/api/live/status')
    assert status == 200 and json.loads(data)['ready']
    before = set(live_server.upload_root.rglob('*'))
    image = jpeg()
    status, headers, output = request(live_server, body=image)
    assert status == 200 and headers['Content-Type'] == 'image/jpeg'
    assert headers['X-Visio-Swapped'] == '1' and headers['X-Visio-Inference-Ms'] == '38.2'
    assert output == image and set(live_server.upload_root.rglob('*')) == before


def test_busy_gpu_drops_frame_and_releases_slot_on_decode_error(live_server):
    live_server.slot.acquire()
    try:
        assert request(live_server, body=jpeg())[0] == 409
    finally:
        live_server.slot.release()
    assert not live_server.swapper.calls
    assert request(live_server, body=b'broken')[0] == 400
    assert request(live_server, body=jpeg())[0] == 200


def test_origin_content_type_and_length_guards(live_server):
    assert request(live_server, body=jpeg(), headers={'Content-Type': 'image/jpeg'})[0] == 403
    headers = {'Content-Type': 'image/jpeg', 'X-Visio-Request': '1', 'Origin': 'https://external.example'}
    assert request(live_server, body=jpeg(), headers=headers)[0] == 403
    headers = {'Content-Type': 'application/octet-stream', 'X-Visio-Request': '1'}
    assert request(live_server, body=jpeg(), headers=headers)[0] == 400
    assert request(live_server, body=b'')[0] == 400
    assert not live_server.swapper.calls


def test_engine_unavailable_does_not_generate_a_result(live_server):
    live_server.swapper = None
    assert not json.loads(request(live_server, 'GET', '/api/live/status')[2])['ready']
    assert request(live_server, body=jpeg())[0] == 503


def test_portrait_is_bound_to_each_request_and_unknown_ids_are_rejected(live_server):
    headers = {'Content-Type': 'image/jpeg', 'X-Visio-Request': '1'}
    for portrait in ('sam-altman', 'brad-pitt', 'emmanuel-macron'):
        status, returned, _ = request(live_server, body=jpeg(), headers={**headers, 'X-Visio-Portrait': portrait})
        assert status == 200 and returned['X-Visio-Portrait'] == portrait
    assert [identity for identity, _ in live_server.swapper.calls] == ['sam-altman', 'brad-pitt', 'emmanuel-macron']
    assert request(live_server, body=jpeg(), headers={**headers, 'X-Visio-Portrait': '../other'})[0] == 400
    assert len(live_server.swapper.calls) == 3
