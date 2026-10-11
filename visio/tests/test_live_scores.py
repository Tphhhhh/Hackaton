import json
import threading
import uuid
from io import BytesIO

import pytest
from PIL import Image

from visio.live_scores import LivePEScorer
from visio.server import DemoServer
from visio.tests.test_live_swap import request, jpeg


def test_pair_uses_pixels_independently_and_preserves_abstention():
    class Detector:
        def predict_with_quality(self, image):
            brightness = float(image.mean())
            return (None, 'no_face') if brightness < 10 else (brightness / 255, None)
    model = LivePEScorer.__new__(LivePEScorer)
    model.engine = Detector()
    model.info = {'revision':'test'}
    black = BytesIO(); Image.new('RGB', (200,200)).save(black, format='JPEG')
    value = model.score_pair(jpeg(), black.getvalue())
    assert 0 < value['original']['score'] < 1
    assert value['filtered'] == {'score':None,'reason':'no_face'}
    assert value['simulation'] is False
    identical = model.score_pair(jpeg(),jpeg())
    assert identical['original'] == identical['filtered']


@pytest.fixture
def score_server(tmp_path):
    class Scorer:
        info = {'ready':True,'model':'gend_pe','simulation':False}
        calls = []
        def score_pair(self, left, right):
            from visio.live_swap import decode_frame
            decode_frame(left);decode_frame(right)
            self.calls.append((left,right))
            return dict(model='gend_pe', simulation=False, original={'score':.23,'reason':None},
                        filtered={'score':.41,'reason':None}, revision='test', inference_ms=42)
    app = DemoServer(0, frontend=tmp_path, scorer=Scorer())
    thread = threading.Thread(target=app.serve_forever,daemon=True);thread.start()
    yield app
    app.shutdown();app.server_close();thread.join()


def headers(image):
    return {'Content-Type':'application/octet-stream','X-Visio-Request':'1',
            'X-Visio-Original-Length':str(len(image)), 'X-Visio-Session':str(uuid.uuid4()),'X-Visio-Frame':'42'}


def test_live_score_binding_and_no_disk_capture(score_server):
    image = jpeg(); h = headers(image)
    before = set(score_server.upload_root.rglob('*'))
    code, _, raw = request(score_server,path='/api/live/score',body=image+image,headers=h)
    value = json.loads(raw)
    assert code == 200 and value['frame_id'] == 42 and value['session_id'] == h['X-Visio-Session']
    assert value['filtered']['score'] == .41
    assert score_server.scorer.calls == [(image,image)]
    assert set(score_server.upload_root.rglob('*')) == before


def test_live_score_rejects_bad_body_origin_and_references(score_server):
    image = jpeg(); h = headers(image)
    for key,value in [('Origin','https://outside.invalid'),('X-Visio-Frame','-1'),
                      ('X-Visio-Session','wrong'),('X-Visio-Original-Length','2000000')]:
        assert request(score_server,path='/api/live/score',body=image+image,headers={**h,key:value})[0] in (400,403)
    assert not score_server.scorer.calls
    assert request(score_server,path='/api/live/score',body=image+b'broken',headers=h)[0] == 400
    # A decode error cannot retain the slot or leak an old measurement.
    assert request(score_server,path='/api/live/score',body=image+image,headers=h)[0] == 200


def test_live_score_busy_and_unavailable_do_not_invent_scores(score_server):
    image=jpeg();h=headers(image)
    score_server.slot.acquire()
    try:
        assert request(score_server,path='/api/live/score',body=image+image,headers=h)[0] == 409
    finally: score_server.slot.release()
    assert not score_server.scorer.calls
    score_server.scorer=None
    assert request(score_server,path='/api/live/score',body=image+image,headers=h)[0] == 503
    code,_,raw=request(score_server,method='GET',path='/api/live/score/status')
    assert code == 200 and json.loads(raw)['ready'] is False
