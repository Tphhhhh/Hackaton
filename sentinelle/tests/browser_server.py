"""Test-only HTTP service with stub inference; never used by the demo launcher."""
from sentinelle.server import Server
class Swap:
    info={'ready':True,'model':'test transport'}
    def process(self,payload,portrait_id='brad-pitt'):
        return payload,{'applied':True,'inference_ms':1}
class Score:
    info={'ready':True,'model':'gend_pe','simulation':False}
    def score_pair(self,a,b):
        return {'model':'gend_pe','simulation':False,'revision':'TEST_ONLY','inference_ms':1,
                'original':{'score':.2,'reason':None},'filtered':{'score':.8,'reason':None}}
Server(8891,swapper=Swap(),scorer=Score()).serve_forever()
