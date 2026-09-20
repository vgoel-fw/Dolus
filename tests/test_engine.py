import copy
import tempfile
import unittest
import io
import json
from email.message import Message
from types import SimpleNamespace
from pathlib import Path
from app.engine import analyze, calibrate, draft, validate_profile
from app.storage import Store, validate_case
from app.server import Handler, allowed_host, allowed_origin

TAX={'version':'test','factors':[{'id':'insider_trading','label':'Insider trading','keywords':['stock sales'],'weight':1},{'id':'accounting','label':'Accounting','keywords':['restatement'],'weight':2}], 'doctrine':{'9':{},'2':{}}}
TEXT='Stock sales preceded a restatement.'
def case(i=0,**kwargs):
    c={'id':str(i),'name':'Fictional case','citation':'fictional','circuit':'9','court':'fictional','date':'2020-01-01','posture':'motion_to_dismiss','case_id':str(i),'defendant_scope':'both','outcome':'survived','outcome_basis':'scienter','source_url':'','opinion_text':TEXT,'summary':TEXT,'synthetic':True,'review_status':'reviewed','factors':{'insider_trading':{'status':'present','strength':'general','evidence':[{'quote':TEXT}]},'accounting':{'status':'unknown','strength':'unknown','evidence':[]}},'outcome_evidence':{'quote':TEXT}}
    c.update(kwargs);return c
class AnalysisTests(unittest.TestCase):
    def test_unmentioned_and_negation_unknown(self):
        p=draft('No stock sales occurred.',TAX)
        self.assertEqual(p['factors']['insider_trading']['status'],'unknown')
        self.assertEqual(p['factors']['accounting']['status'],'unknown')
    def test_exact_quotes(self):
        with self.assertRaises(ValueError):validate_profile({'factors':{'accounting':{'status':'present','evidence':[{'quote':'invented'}]}}},TEXT,TAX)
    def test_separate_demo_and_real(self):
        results=analyze({'text':'stock sales','mode':'real'},[case()],TAX)
        self.assertEqual(results['results'],[]);self.assertEqual(results['stats']['n'],0)
    def test_dedup_and_conflicting_outcomes(self):
        stats=calibrate([case(),case(1,case_id='0',outcome='dismissed')],{'insider_trading'},'demo')
        self.assertEqual(stats['n'],1);self.assertEqual(stats['mixed'],1);self.assertIsNone(stats['rate'])
    def test_cohort_not_top_k(self):
        out=analyze({'text':'stock sales'},[case(i) for i in range(30)],TAX)
        self.assertEqual(len(out['results']),12);self.assertEqual(out['stats']['n'],30)
        self.assertEqual(out['stats']['rate'],100);self.assertGreater(out['stats']['interval'][0],80)
    def test_posture_scope_circuit(self):
        data=[case(0,circuit='2'),case(1,posture='appeal_of_dismissal'),case(2,defendant_scope='individual'),case(3)]
        out=analyze({'text':'stock sales','cross_circuit':True},data,TAX)
        self.assertEqual([r['case']['id'] for r in out['results']],['3','0'])
        self.assertEqual(out['stats']['n'],1)
    def test_conjunction(self):
        out=analyze({'text':TEXT},[case()],TAX)
        self.assertEqual(out['stats']['n'],0)
    def test_non_scienter_excluded(self):
        self.assertEqual(calibrate([case(outcome_basis='other')],set(),'demo')['n'],0)
    def test_import_review_gate_and_durable_storage(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'db';s=Store(path,TAX)
            s.import_cases([case()]);self.assertEqual(s.case('0')['review_status'],'needs_review')
            with self.assertRaises(ValueError):s.review('0',{'reviewer':'Reviewer','note':''})
            s.review('0',{'reviewer':'Reviewer','note':'Verified quotes and outcome.'})
            self.assertEqual(Store(path,TAX).case('0')['review_status'],'reviewed')
    def test_graph_and_vector_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'db',TAX,[case()])
            graph=s.graph()
            self.assertTrue(any(e['target']=='factor:insider_trading' for e in graph['edges']))
            with s.connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM narrative_vectors').fetchone()[0],1)
    def test_unknown_is_not_factor_match(self):
        p=draft('restatement',TAX)
        out=analyze({'text':'restatement','profile':p},[case()],TAX)
        self.assertEqual(out['results'][0]['matched_factors'],[])
        self.assertEqual(out['stats']['n'],0)
    def test_invalid_types_fail_as_validation_errors(self):
        for patch in [{'circuit':[]},{'cross_circuit':'false'},{'use_llm':1},{'text':{}},{'mode':None}]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):analyze({'text':TEXT,**patch},[],TAX)
        for patch in [{'status':[]},{'evidence':{}},{'strength':{}},{'evidence':[{'quote':TEXT,'locator':[]}]}]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                validate_profile({'factors':{'accounting':{'status':'present','strength':'general','evidence':[{'quote':TEXT}],**patch}}},TEXT,TAX)
    def test_known_profile_requires_support(self):
        with self.assertRaises(ValueError):validate_profile({'factors':{'accounting':{'status':'present'}}},TEXT,TAX)
    def test_poisoned_evidence_urls_rejected(self):
        for url in ['javascript:alert(1)','https://','https://user:password@example.com','https://example.com/ bad']:
            c=case();c['outcome_evidence']['source_url']=url
            with self.subTest(url=url),self.assertRaises(ValueError):validate_case(c,TAX)
    def test_import_transaction_no_overwrite_or_partial_success(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'db',TAX,[case()])
            with self.assertRaises(ValueError):s.import_cases([case(1),case(0)])
            self.assertIsNone(s.case('1'))
            self.assertEqual(s.case('0')['review_status'],'reviewed')
            with self.assertRaises(ValueError):s.import_cases([case(2),case(2)])
            self.assertIsNone(s.case('2'))
    def test_real_review_requires_manual_source_attestation(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'db',TAX)
            # Locally self-consistent quotes do not prove external source authenticity.
            s.import_cases([case(synthetic=False,source_url='https://example.com/opinion')])
            with self.assertRaises(ValueError):s.review('0',{'reviewer':'Counsel','note':'Checked local text'})
            self.assertEqual(s.case('0')['review_status'],'needs_review')
            record=s.review('0',{'reviewer':'Counsel','note':'Checked original opinion and posture.','source_verified':True})
            self.assertIn('external authenticity not independently verified',record['review_attestation']['verification_method'])
    def test_save_preserves_profile_and_selection_fields(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'db',TAX)
            p={'title':'Matter','text':TEXT,'profile':draft(TEXT,TAX),'mode':'real','circuit':'2','posture':'appeal_of_dismissal','defendant_scope':'individual','cross_circuit':True}
            saved=s.save_matter(p); loaded=Store(Path(d)/'db',TAX).matter(saved['id'])
            for key,value in p.items():self.assertEqual(loaded[key],value)
    def request_without_socket(self,path,method='POST',payload=None,origin=None):
        handler=object.__new__(Handler);handler.path=path;handler.server=SimpleNamespace(server_port=8765,store=None,taxonomy=TAX)
        handler.headers=Message();handler.headers['Host']='127.0.0.1:8765';handler.headers['Content-Type']='application/json'
        body=json.dumps(payload or {}).encode();handler.headers['Content-Length']=str(len(body));handler.rfile=io.BytesIO(body)
        if origin:handler.headers['Origin']=origin
        captured=[];handler.send_json=lambda data,status=200:captured.append((status,data))
        handler.dispatch(method);return captured[0]
    def test_unsupported_post_and_cross_origin(self):
        self.assertEqual(self.request_without_socket('/api/health')[0],404)
        self.assertEqual(self.request_without_socket('/api/analyze',payload={'text':TEXT,'use_llm':'true'})[0],400)
        self.assertEqual(self.request_without_socket('/api/matters',origin='https://evil.example')[0],403)
    def test_local_security_policy(self):
        self.assertTrue(allowed_host('127.0.0.1:8765',8765));self.assertFalse(allowed_host('evil.test:8765',8765))
        self.assertFalse(allowed_origin('https://evil.test',8765));self.assertFalse(allowed_origin('null',8765))
if __name__=='__main__':unittest.main()
