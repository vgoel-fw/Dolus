"""signal layer: spans are exact, negation holds, rules beat similarity, statutes change the read"""
import copy
import json
from pathlib import Path
import unittest
from app.fusion import analyze_intent, rules
from app.signals import load_rules, validate_rules, sentences, parse_dates, relative_offsets, detect
from app.encoder import HashingEncoder
from app.engine import analyze
from app.source_catalog import SourceCatalog

ROOT = Path(__file__).resolve().parents[1]
TAX = json.loads((ROOT / 'data/taxonomy.json').read_text())
OSTRICH = 'In March 2021 the controller warned the CFO about the reserve releases. The CFO told her he did not want to know and stopped attending the monthly close meetings.'


def ids(text, **kw):
    return {s['id']: s for s in analyze_intent(text, **kw)['signals']}


class SignalTests(unittest.TestCase):
    def test_every_binding_is_an_exact_span(self):
        text = OSTRICH + ' On May 2, 2022 the CFO sold 64% of his shares. On June 10, 2022 the company announced the restatement.'
        for s in analyze_intent(text)['signals']:
            for b in s['bindings'].values():
                self.assertEqual(text[b['start']:b['end']], b['quote'])
            if s['semantic_match']:
                m = s['semantic_match']; self.assertEqual(text[m['start']:m['end']], m['text'])

    def test_ostrich_needs_warning_and_avoidance(self):
        self.assertEqual(ids(OSTRICH)['conscious_avoidance']['status'], 'supported')
        alone = ids('The CFO said he did not want to know how the reserves were set.')
        self.assertEqual(alone['conscious_avoidance']['status'], 'partial')
        self.assertIn('red_flag', alone['conscious_avoidance']['missing_roles'])

    def test_negated_allegation_is_not_a_hit(self):
        got = ids('There is no allegation that the CEO declined to review any report or was warned of any problem.')
        self.assertNotIn(got.get('conscious_avoidance', {}).get('status'), {'supported', 'partial'})

    def test_pleading_language_is_not_a_red_flag(self):
        got = ids('The district court dismissed the complaint. Plaintiffs fail to allege that any defendant received a warning.')
        self.assertFalse([s for s in got.values() if s['status'] in ('supported', 'partial')])

    def test_dated_trade_before_disclosure_counts_days(self):
        s = ids('On May 2, 2022 the CFO sold 64% of his shares. On June 10, 2022 the company announced the restatement.')['suspicious_trading_timing']
        self.assertEqual(s['status'], 'supported')
        self.assertEqual(s['intervals'][0]['days'], 39)
        self.assertEqual(s['intervals'][0]['basis'], 'dates')

    def test_trade_after_disclosure_is_not_timing(self):
        got = ids('On June 10, 2022 the company announced the restatement. On August 2, 2022 the CFO sold 64% of his shares.')
        self.assertNotEqual(got.get('suspicious_trading_timing', {}).get('status'), 'supported')

    def test_counter_signals_listed_not_netted(self):
        s = ids('The CFO sold stock three weeks before the corrective disclosure. The sales were made pursuant to a pre-existing 10b5-1 plan.')['suspicious_trading_timing']
        self.assertEqual(s['status'], 'supported')
        self.assertIn('preplanned_trading', [c['id'] for c in s['opposing']])

    def test_generic_motive_flagged(self):
        s = ids('Defendants had incentive compensation and wanted to maintain a high stock price.').get('concrete_personal_motive')
        self.assertTrue(s is None or s['status'] != 'supported')

    def test_statute_changes_relevance(self):
        a = ids(OSTRICH, statute='11')['conscious_avoidance']
        self.assertIn('not an element', a['statute_note'])
        b = ids(OSTRICH, statute='criminal')['conscious_avoidance']
        self.assertEqual(b['statute_note'], '')
        self.assertGreater(b['rank_score'], ids(OSTRICH)['conscious_avoidance']['rank_score'])
        with self.assertRaises(ValueError):analyze_intent(OSTRICH, statute='nope')

    def test_semantic_only_is_marked_and_never_called_supported(self):
        enc = HashingEncoder(); enc.threshold = 0.0
        out = analyze_intent('Senior management chose to overlook repeated alerts from compliance.', encoder=enc)['signals']
        sem = [s for s in out if s['status'] == 'semantic_only']
        self.assertTrue(sem)
        self.assertTrue(all(s['needs_review'] and s['coverage'] == 0 for s in sem))

    def test_no_signals_on_plain_business_text(self):
        self.assertEqual(analyze_intent('The company designs industrial sensors and sells them through distributors in Europe.')['signals'], [])

    def test_sentence_split_keeps_case_names_together(self):
        s = sentences('See Zucco Partners, LLC v. Digimarc Corp., 552 F.3d 981. Next sentence here.')
        self.assertEqual(len(s), 2)

    def test_date_and_offset_parsing(self):
        self.assertEqual([d['date'].isoformat() for d in parse_dates('on Sept. 4, 2020 and 2021-01-02 and 3/7/2019')], ['2020-09-04', '2021-01-02', '2019-03-07'])
        self.assertEqual(relative_offsets('two weeks before the call')[0]['days'], -14)

    def test_bad_rules_rejected(self):
        r = copy.deepcopy(json.loads((ROOT / 'data/scienter_signals.json').read_text()))
        r['signals'][0]['rule']['all'].append('ghost')
        with self.assertRaises(ValueError):validate_rules(r)
        r = copy.deepcopy(json.loads((ROOT / 'data/scienter_signals.json').read_text()))
        r['statutes'][0]['emphasis'] = {'ghost': 2}
        with self.assertRaises(ValueError):validate_rules(r)

    def test_symbolic_detect_matches_fused_rule_status(self):
        sym = {s['id']: s['status'] for s in detect(OSTRICH, rules())['signals']}
        fused = {s['id']: s['status'] for s in analyze_intent(OSTRICH)['signals'] if s['status'] != 'semantic_only'}
        self.assertEqual(sym, fused)

    def test_analyze_returns_intent_without_touching_cohort(self):
        cases = json.loads((ROOT / 'data/cases.json').read_text())
        r = analyze({'text': OSTRICH, 'mode': 'demo', 'circuit': '9'}, cases, TAX)
        self.assertIn('conscious_avoidance', [s['id'] for s in r['intent']['signals']])
        self.assertNotIn('intent', r['stats'])

    def test_passages_get_intent_tags_and_hide_vectors(self):
        cat = SourceCatalog(ROOT / 'data/flp_opinions.json', TAX)
        self.assertTrue(any(p['structure']['intent_signals'] for p in cat.passages))
        r = cat.search({'query': 'The CFO resigned shortly before the restatement was announced.', 'limit': 5})['results']
        self.assertTrue(r)
        for p in r:
            self.assertNotIn('_vec', p); self.assertIn('semantic_score', p)
        self.assertNotIn('_vec', cat.context(r[0]['id'])['passage'])

    def test_eval_floor(self):
        from scripts.evaluate_signals import evaluate
        e = evaluate()
        self.assertGreaterEqual(e['fused']['recall'], 0.9)
        self.assertGreaterEqual(e['fused']['precision'], 0.8)


if __name__ == '__main__':
    unittest.main()
