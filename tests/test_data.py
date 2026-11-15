import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
acquire=module('acquire')

class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=json.loads((ROOT/'data/cases.json').read_text());cls.tax=json.loads((ROOT/'data/taxonomy.json').read_text())

    def test_seed_integrity_and_evidence(self):
        self.assertEqual(len(self.tax['factors']),12)
        self.assertEqual(len({c['id'] for c in self.cases}),len(self.cases))
        expected={f['id'] for f in self.tax['factors']}
        for c in self.cases:
            self.assertEqual(set(c['factors']),expected)
            for e in [c['outcome_evidence']]+[e for f in c['factors'].values() for e in f['evidence']]:
                self.assertTrue(e['quote']);self.assertIn(e['quote'],c['opinion_text']);self.assertTrue(e['locator'])
            self.assertIs(c['synthetic'],False);self.assertTrue(c['source_url'].startswith('https://'))
            self.assertEqual(c['review_status'],'needs_review');self.assertEqual(c['source_provenance']['coverage'],'excerpts_only')
            self.assertEqual(c['case_outcome'],'unknown')

    def test_no_fictional_records_anywhere(self):
        self.assertFalse((ROOT/'data/examples.json').exists());self.assertFalse((ROOT/'data/synthetic_ground_truth.json').exists())
        from app.storage import validate_case
        with self.assertRaises(ValueError):validate_case({**self.cases[0],'synthetic':True},self.tax)

    def test_pagination_refuses_credential_exfiltration(self):
        for url in ('http://www.courtlistener.com/api/rest/v4/search/', 'https://evil.test/api/rest/v4/', 'https://www.courtlistener.com@evil.test/api/rest/v4/', 'https://www.courtlistener.com/api/rest/v3/'):
            with self.assertRaises(ValueError):acquire.safe_url(url)
        with tempfile.TemporaryDirectory() as d:
            with patch.object(acquire,'fetch',return_value={'results':[],'next':'https://evil.test/'}):
                with self.assertRaises(ValueError):acquire.collect(acquire.BASE+'search/', 'secret', Path(d))

    def test_crossref_preserves_motion_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); csv=d/'input.csv'; out=d/'links.json'
            csv.write_text('case_id,scac_id,case_outcome,source_url\nzucco-2009,example,settled,https://example.org\nnot-here,example2,dismissed,https://example.org\n')
            self.assertEqual(acquire.crossref(csv,ROOT/'data/cases.json',out),(1,1))
            result=json.loads(out.read_text());self.assertTrue(result['links'][0]['not_a_motion_outcome'])
            self.assertNotIn('outcome',result['links'][0])

if __name__=='__main__':unittest.main()
