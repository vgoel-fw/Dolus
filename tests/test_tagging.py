import json
from pathlib import Path
import unittest
from scripts.tag_opinion import tag
from scripts.generate_synthetic import generate
ROOT=Path(__file__).resolve().parents[1]
class TaggingTests(unittest.TestCase):
    def test_corpus_tagging_never_admits_or_infers_ruling(self):
        taxonomy=json.loads((ROOT/'data/taxonomy.json').read_text())
        c=next(c for c in json.loads((ROOT/'data/cases.json').read_text()) if not c['synthetic'])
        tagged=tag(c['opinion_text'],c,taxonomy)
        self.assertEqual(tagged['review_status'],'needs_review')
        self.assertEqual(tagged['outcome'],c['outcome'])
        for factor in tagged['factors'].values():
            for evidence in factor['evidence']:
                self.assertIn(evidence['quote'],c['opinion_text'])
                self.assertEqual(evidence['source_url'],c['source_url'])
    def test_fixture_generator_deterministic(self):
        self.assertEqual(generate(4,7),generate(4,7))
        self.assertTrue(all(x['synthetic'] for x in generate(4,7)))
