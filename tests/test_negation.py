import json
import unittest
from pathlib import Path
from app.engine import draft
TAXONOMY=json.loads((Path(__file__).resolve().parents[1]/'data/taxonomy.json').read_text())
class NegationTests(unittest.TestCase):
    def status(self,text,factor):return draft(text,TAXONOMY)['factors'][factor]['status']
    def test_no_sales_abstains(self):
        self.assertEqual(self.status('There were no stock sales.','insider_trading'),'unknown')
    def test_baseline_does_not_erase_sales(self):
        self.assertEqual(self.status('The CFO sold shares before disclosure, compared with no stock sales in the prior year.','insider_trading'),'present')
    def test_no_charges_does_not_erase_inquiry(self):
        self.assertEqual(self.status('An SEC investigation was disclosed; no charges were announced.','regulatory_action'),'present')
    def test_weak_witness_still_present(self):
        self.assertEqual(self.status('A confidential witness is alleged but no job title or tenure is provided.','cw_reliability'),'present')
    def test_exculpatory_statement_retained(self):
        self.assertEqual(self.status('The defense offers an innocent explanation: an error without executive awareness.','opposing_inferences'),'present')
