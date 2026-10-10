import http.client
import json
from pathlib import Path
import sys
import threading
import uuid
import shutil
import subprocess

import numpy as np
import pytest

from visio.core import DEFAULT_CONFIG, DEFAULT_MANIFEST, result
from visio.tracking import frame_result
from visio import runner, server


def test_tracking_preserves_real_pixels_and_normalizes_oriented_image():
    boxes = np.array([[-5, 20, 120, 80, .9]])
    points = np.array([[[10,30], [90,30], [50,50], [25,70], [75,70]]])
    frame = frame_result(.125, (100,200,3), (boxes,points))
    face = frame['faces'][0]
    assert face['box'] == dict(x=0, y=.2, width=.6, height=.6)
    assert face['landmarks'] == [dict(x=x/200,y=y/100) for x,y in points[0]]
    assert frame_result(.25, (100,200,3), (np.empty((0,5)),None))['faces'] == []
    # No clamping an invalid landmark into a fabricated point at the border.
    points[0,0] = [-10,30]
    assert len(frame_result(0,(100,200,3),(boxes,points))['faces'][0]['landmarks']) == 4


def test_dense_sampling_preserves_analysis_instants(tmp_path):
    from visio.pipeline import sampled_frames
    from visio.tests.test_media_models import make_clip
    p = tmp_path/'clip.mp4'
    make_clip(p,seconds=2,fps=30)
    sparse = [t for t,_ in sampled_frames(p,2,{})]
    dense = [t for t,_ in sampled_frames(p,8,{},160)]
    assert len(dense) == 16
    assert set(sparse) <= set(dense)


def test_rotated_frame_matches_ffmpeg_display_orientation(tmp_path):
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg required for independent display-matrix reference')
    import av
    from visio.pipeline import sampled_frames
    original=tmp_path/'original.mp4';rotated=tmp_path/'rotated.mp4'
    image=np.zeros((120,160,3),dtype=np.uint8)
    image[:60,:80]=[10,40,230];image[:60,80:]=[20,220,30]
    image[60:,:80]=[200,30,10];image[60:,80:]=[100,180,210]
    with av.open(str(original),'w') as output:
        stream=output.add_stream('libx264',rate=10)
        stream.width=160;stream.height=120;stream.pix_fmt='yuv420p'
        for _ in range(20):
            for packet in stream.encode(av.VideoFrame.from_ndarray(image,format='bgr24')):output.mux(packet)
        for packet in stream.encode():output.mux(packet)
    subprocess.run(['ffmpeg','-v','error','-display_rotation','90','-i',str(original),'-c','copy',str(rotated)],check=True)
    reference=subprocess.run(['ffmpeg','-v','error','-i',str(rotated),'-frames:v','1','-f','rawvideo','-pix_fmt','bgr24','-'],check=True,capture_output=True).stdout
    generator=sampled_frames(rotated,2,{})
    _,actual=next(generator);generator.close()
    assert actual.shape==(160,120,3)
    expected=np.frombuffer(reference,dtype=np.uint8).reshape(160,120,3)
    assert np.abs(actual.astype(float)-expected).mean()<1


def test_cancel_kills_worker_and_clears_tracking(tmp_path, monkeypatch):
    monkeypatch.setattr(runner,'DEFAULT_CACHE',tmp_path)
    event = threading.Event()
    timer = threading.Timer(.2,event.set)
    timer.start()
    tracking = {'data': 'stale'}
    try:
        r = runner.analyze('missing.mp4',DEFAULT_CONFIG,tmp_path,DEFAULT_MANIFEST,
            cancel_event=event, tracking_sink=tracking, media_id='test',
            worker_command=[sys.executable,'-c','import sys,time;sys.stdin.read();time.sleep(30)'])
    finally:
        timer.cancel()
    assert r['status'] == 'cancelled'
    assert r['errors'][0]['code'] == 'AnalysisCancelled'
    assert not tracking
    assert not list((tmp_path/'state').glob('job-*'))


@pytest.fixture
def http_demo(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'DEFAULT_CACHE',tmp_path/'cache')
    (tmp_path/'index.html').write_text('frontend')
    seen = []
    def analyze(path,config,*args,tracking_sink,media_id,cancel_event):
        seen.append((path,path.read_bytes()))
        tracking_sink['data'] = dict(schema_version='1.0', media_id=media_id, source='test fixture',
                                    simulation=False,coordinate_space='normalized',frames=[])
        return result(config)
    app = server.DemoServer(0,tmp_path,analyzer=analyze)
    thread = threading.Thread(target=app.serve_forever,daemon=True)
    thread.start()
    yield app, seen
    app.shutdown(); app.server_close(); thread.join()


def request(app,method,path,body=None,headers=None):
    conn=http.client.HTTPConnection('127.0.0.1',app.server_port,timeout=5)
    try:
        conn.request(method,path,body,headers or {})
        response=conn.getresponse()
        return response.status,json.loads(response.read())
    finally:
        conn.close()


def test_local_upload_binding_and_cleanup(http_demo):
    app,seen=http_demo
    media_id=str(uuid.uuid4())
    status,data=request(app,'POST',f'/api/analyze/{media_id}?suffix=.mp4',b'authorized test bytes',
                        {'X-Visio-Request':'1','Content-Type':'application/octet-stream'})
    assert status==200 and data['media_id']==media_id==data['tracking']['media_id']
    assert seen[0][1]==b'authorized test bytes'
    # Handler cleans after sending; wait for handler completion via slot.
    with app.slot:
        assert not seen[0][0].exists()
        assert not list(app.upload_root.iterdir())


def test_server_announces_the_selected_pe_model(http_demo):
    app, _ = http_demo
    status, data = request(app, 'GET', '/api/status')
    assert status == 200
    assert data['backend'] == 'gend' and data['model'] == 'gend_pe'
    assert app.config['detectors'] == ['gend_pe']


def test_cross_origin_and_oversized_requests_never_run_engine(http_demo):
    app,seen=http_demo
    path=f'/api/analyze/{uuid.uuid4()}?suffix=.mp4'
    for headers in [{}, {'X-Visio-Request':'1','Origin':'https://example.invalid'},
                    {'X-Visio-Request':'1','Host':'example.invalid'}]:
        assert request(app,'POST',path,b'x',headers)[0]==403
    headers={'X-Visio-Request':'1','Content-Type':'application/octet-stream','Content-Length':str(server.MAX_UPLOAD+1)}
    assert request(app,'POST',path,b'',headers)[0]==400
    assert not seen


def test_cancellation_before_upload_and_invalid_reference(http_demo):
    app,seen=http_demo
    media_id=str(uuid.uuid4());path=f'/api/analyze/{media_id}'
    assert request(app,'DELETE',path,headers={'X-Visio-Request':'1'})[0]==200
    headers={'X-Visio-Request':'1','Content-Type':'application/octet-stream'}
    assert request(app,'POST',path+'?suffix=.mp4',b'x',headers)[0]==409
    assert request(app,'POST','/api/analyze/../../private?suffix=.mp4',b'x',headers)[0]==400
    assert not seen
