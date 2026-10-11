"""Selected rules and HTTP contract; no GPU needed."""
import http.client
import json
import threading
import uuid
import pytest
from metadata.session import evaluate
from sentinelle.server import Server


def by_code(result): return {r['code']:r for r in result['rows']}


def test_missing_data_is_not_a_clear_verdict():
    result=evaluate({})
    assert result['points']==0 and result['measured_count']==0
    assert all(r['state']=='unavailable' for r in result['rows'])
    assert 'probabilité' in result['limit']


def test_selected_rules_combination_and_no_country_risk():
    value={'active':True,'camera':'OBS Virtual Camera','gpu_renderer':'SwiftShader',
           'network_enabled':True,'ip':'203.0.113.2','org':'Example hosting','rtt_ms':[200,180,190],
           'camera_changes':1,'settings_changes':3,'camera_refused':True,
           'declared_timezone':'Asia/Tokyo','browser_timezone':'Europe/Paris','browser_utc_offset':2}
    r=by_code(evaluate(value))
    assert all(r[k]['state']=='flag' for k in ['I1','L1','I3','I4','I5','I2','I6','C4','X1'])
    assert r['X1']['weight']==25 and r['C4']['weight']==5
    assert 'heuristique' in r['I4']['detail']
    assert 'pas le participant' in r['I5']['detail']
    two=by_code(evaluate({'active':True,'camera':'OBS','gpu_renderer':'VMware'}))
    assert two['X1']['weight']==15
    assert by_code(evaluate({'active':True,'camera':'webcam','country':'JP'}))['I2']['state']=='unavailable'
    stopped=by_code(evaluate({**value,'active':False,'camera_refused':False}))
    assert all(stopped[k]['state']=='unavailable' for k in ['I1','I3','I4','I5','I2','I6'])


def test_contacts_are_optional_and_local_only():
    rows=by_code(evaluate({'email':'abc123456789@mailinator.com','phone':'bad'}))
    assert rows['C10']['state']=='flag' and rows['C12']['state']=='flag'
    assert set(rows)=={'I1','L1','I3','I4','I5','I2','I6','C4','C10','C15','C12','C13','X1'}
    rows=by_code(evaluate({'active':True,'network_enabled':False,'ip':'203.0.113.5','org':'AWS','rtt_ms':[200]}))
    assert rows['I4']['state']==rows['I5']['state']=='unavailable'


@pytest.mark.parametrize('payload',[{'active':'yes'},{'settings_changes':float('nan')},{'rtt_ms':[True]}, {'declared_timezone':'garbage'}, {'camera':'x'*301}, {'camera_changes':.5}])
def test_input_validation(payload):
    with pytest.raises(ValueError): evaluate(payload)


@pytest.fixture
def server():
    class Scorer:
        info={'ready':True,'model':'gend_pe','simulation':False}
        def score_pair(self,a,b):return {'model':'gend_pe','simulation':False,'revision':'TEST',
                                        'original':{'score':.2,'reason':None},'filtered':{'score':.8,'reason':None}}
    server=Server(0,scorer=Scorer());thread=threading.Thread(target=server.serve_forever);thread.start()
    yield server
    server.shutdown();server.server_close();thread.join()


def request(server,path,payload=None,headers=None,raw=None):
    conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=20)
    h={'Content-Type':'application/json','X-Visio-Request':'1',**(headers or {})}
    data=raw if raw is not None else json.dumps(payload) if payload is not None else None
    conn.request('POST' if data is not None else 'GET',path,data,h)
    r=conn.getresponse();body=r.read();out=(r.status,dict(r.getheaders()),body);conn.close();return out


def test_http_bounds_removed_flow_and_video_route(server):
    status,headers,body=request(server,'/')
    assert status==200 and body==(server.frontend/'index.html').read_bytes()
    assert b'Un visage. Deux versions.' not in body
    assert "frame-ancestors 'none'" in headers['Content-Security-Policy']
    assert request(server,'/recruiter')[1]['Location']=='/'
    assert request(server,'/apply')[0]==302
    assert request(server,'/api/applications')[0]==404
    assert request(server,'/api/session/analyze',{},headers={'Origin':'https://foreign.example'})[0]==403
    assert request(server,'/api/session/analyze',{},headers={'X-Visio-Request':''})[0]==403
    assert request(server,'/api/session/analyze',raw=b'x'*17000)[0]==400
    assert request(server,'/api/session/analyze',raw=b'{"rtt_ms":[NaN]}')[0]==400
    assert request(server,'/api/session/analyze',{})[0]==200
    status,_,data=request(server,'/api/live/score',raw=b'ab',headers={'Content-Type':'application/octet-stream',
      'X-Visio-Original-Length':'1','X-Visio-Session':str(uuid.uuid4()),'X-Visio-Frame':'1'})
    assert status==200 and json.loads(data)['original']['score']==.2
