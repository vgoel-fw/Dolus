"""Regression checks for sourced passage retrieval and the real-case preview boundary."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from app.passages import build_passages, search_passages
from app.source_catalog import SourceCatalog
from app.engine import analyze

ROOT=Path(__file__).resolve().parents[1]
TAX=json.loads((ROOT/'data/taxonomy.json').read_text())

class PassageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=SourceCatalog(ROOT/'data/flp_opinions.json',TAX)

    def test_acquired_texts_have_provenance_and_valid_checksums(self):
        docs=self.catalog.documents
        self.assertEqual(len(docs),5)
        self.assertEqual({d['circuit'] for d in docs},{'2','9'})
        for d in docs:
            self.assertGreater(len(d['text']),10000)
            self.assertNotIn('\ufffd',d['text'])
            self.assertEqual(d['sha256'],hashlib.sha256(d['text'].encode()).hexdigest())
            self.assertEqual(d['review_status'],'needs_review')
            self.assertIn('courtlistener.com/opinion/',d['source_url'])

    def test_every_passage_is_an_exact_source_span(self):
        self.assertGreater(len(self.catalog.passages),100)
        for p in self.catalog.passages:
            doc=self.catalog.by_document[p['document_id']]
            self.assertEqual(p['text'],doc['text'][p['start']:p['end']])
            self.assertEqual(p['review_status'],doc['review_status'])

    def test_context_preserves_neighboring_text_and_source(self):
        p=self.catalog.passages[20];doc=self.catalog.by_document[p['document_id']]
        c=self.catalog.context(p['id'])
        self.assertEqual(c['before']+p['text']+c['after'],doc['text'][max(0,p['start']-900):p['end']+900])
        self.assertEqual(c['source_url'],p['source_url'])
        with self.assertRaises(KeyError):self.catalog.context('invented')

    def test_tampered_source_rejected(self):
        docs=copy.deepcopy(self.catalog.documents);docs[0]['text']+=' invented'
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'sources.json';path.write_text(json.dumps(docs))
            with self.assertRaisesRegex(ValueError,'checksum'):SourceCatalog(path,TAX)

    def test_search_returns_exact_real_passages_and_distinctions(self):
        r=self.catalog.search({'query':'Confidential witnesses relied on hearsay without personal knowledge of the CFO.','limit':5})
        self.assertTrue(r['results']);self.assertLessEqual(len(r['results']),5)
        for p in r['results']:
            self.assertTrue(p['reasons'])
            self.assertIn('distinctions',p)
            self.assertEqual(p['data_kind'],'public_judicial_opinion')
            self.assertGreaterEqual(p['score'],0);self.assertLessEqual(p['score'],1)
            self.assertNotIn('outcome',p)

    def test_exact_circuit_filter(self):
        r=self.catalog.search({'query':'confidential witnesses personal knowledge','circuit':'2'})
        self.assertTrue(r['results'])
        self.assertEqual({p['circuit'] for p in r['results']},{'2'})

    def test_no_match_does_not_invent_results(self):
        self.assertEqual(self.catalog.search({'query':'zzzzqqqqxxxyy'})['results'],[])

    def test_invalid_requests_rejected(self):
        for payload in [{'query':''},{'query':['a']},{'query':'a'*10001},{'query':'a','circuit':[]},{'query':'a','limit':True},{'query':'a','limit':31}]:
            with self.assertRaises(ValueError):self.catalog.search(payload)

    def test_negation_and_pdf_wrap_are_visible_without_rewriting_quote(self):
        text='The confidential witness had no personal knowl-\nedge and relied on hearsay about the chief financial officer and company reports.'
        docs=[{'id':'x','name':'Test source','circuit':'9','source_url':'https://www.courtlistener.com/opinion/1/test/','text':text}]
        p=build_passages(docs,TAX)[0]
        self.assertEqual(p['text'],text)
        self.assertEqual(p['structure']['polarity'],'negation_present')
        self.assertIn('firsthand',p['structure']['evidence_bases']) # Mention only, not an affirmative legal finding.
        self.assertIn('hearsay',p['structure']['evidence_bases'])
        r=search_passages('The CFO had personal knowledge of the company reports.',[p])[0]
        self.assertTrue(any('Negation' in x for x in r['distinctions']))

    def test_preview_never_counts_unreviewed_sources(self):
        cases=json.loads((ROOT/'data/cases.json').read_text())
        payload={'text':'A GAAP restatement and stock sales.','mode':'preview','circuit':'9','posture':'appeal_of_dismissal','defendant_scope':'both'}
        r=analyze(payload,cases,TAX)
        self.assertTrue(r['results']);self.assertTrue(all(not x['case']['synthetic'] for x in r['results']))
        self.assertEqual(r['stats']['n'],0);self.assertIsNone(r['stats']['rate'])
        payload['mode']='real';self.assertEqual(analyze(payload,cases,TAX)['results'],[])

if __name__=='__main__':unittest.main()
