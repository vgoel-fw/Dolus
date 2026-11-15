"""regressions for the bugs fixed in docs/BUGS.md"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from app.server import allowed_host, STATIC_TYPES
from app.llm import _json_body
from app.engine import wilson
from app.storage import Store

ROOT=Path(__file__).resolve().parents[1]
TAX=json.loads((ROOT/'data/taxonomy.json').read_text())
CASES=json.loads((ROOT/'data/cases.json').read_text())

class FixTests(unittest.TestCase):
    def test_port_80_host_without_port(self):
        self.assertTrue(allowed_host('localhost',80))
        self.assertFalse(allowed_host('localhost',8765))
        self.assertFalse(allowed_host('evil.test',80))

    def test_js_served_as_javascript(self):
        self.assertTrue(STATIC_TYPES['.js'].startswith('text/javascript'))

    def test_llm_json_in_code_fence(self):
        self.assertEqual(_json_body('```json\n{"factors": {}}\n```'),{'factors':{}})
        self.assertEqual(_json_body('{"a": 1}'),{'a':1})

    def test_wilson_zero(self):
        self.assertIsNone(wilson(0,0))

    def test_changed_seed_refreshes_unless_reviewed_locally(self):
        seed=copy.deepcopy(CASES[0])
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'db'; Store(path,TAX,[seed])
            changed={**seed,'summary':seed['summary']+' updated'}
            self.assertEqual(Store(path,TAX,[changed]).case(seed['id'])['summary'],changed['summary'])
            s=Store(path,TAX); stored=s.case(seed['id']); stored['review_attestation']={'reviewer':'x'}; s.put_case(stored)
            self.assertIn('review_attestation',Store(path,TAX,[seed]).case(seed['id']))

    def test_delete_missing_matter_is_404(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(KeyError):Store(Path(d)/'db',TAX).delete_matter('nope')
