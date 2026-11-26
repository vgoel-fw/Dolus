#!/usr/bin/env python3
"""slowly pull published 2d/9th circuit scienter opinions from courtlistener into the corpus.

stays under the 5 requests/minute api limit, saves state after every request so it can be
stopped and restarted, and keeps only opinions that actually discuss scienter.

  python3 scripts/harvest.py run --target 100     # search + fetch, resumable
  python3 scripts/harvest.py merge                # fold harvested opinions into data/flp_opinions.json

auth: COURTLISTENER_TOKEN if set (sent as 'Authorization: Token ...'), otherwise no header, which
works when a proxy injects the credential.
"""
import argparse
import hashlib
import json
import os
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'var' / 'harvest'
BASE = 'https://www.courtlistener.com/api/rest/v4/'
DELAY = 13.0  # seconds between requests, about 4.6 per minute
QUERIES = [
    'scienter AND ("strong inference" OR "10b-5" OR "PSLRA")',
    '"deliberate recklessness" AND scienter',
    'scienter AND ("insider sales" OR "confidential witness" OR "restatement")',
    '"willful blindness" OR "conscious avoidance" AND securities',
]
FIELDS = 'id,absolute_url,plain_text,html_with_citations,html_lawbox,html,type'


def safe(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.netloc != 'www.courtlistener.com' or not p.path.startswith('/api/rest/v4/'):
        raise ValueError('refusing non-courtlistener url')
    return url


_last = [0.0]


def get(url):
    """one polite GET. returns parsed json, sleeping through 429s"""
    headers = {'Accept': 'application/json', 'User-Agent': 'dolus-harvest/0.1'}
    token = os.getenv('COURTLISTENER_TOKEN')
    if token:
        headers['Authorization'] = 'Token ' + token
    for attempt in range(6):
        wait = DELAY - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(safe(url), headers=headers), timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                m = re.search(r'(\d+) seconds', e.read().decode('utf-8', 'ignore'))
                time.sleep(int(m.group(1)) + 3 if m else 30)
                continue
            if e.code in (500, 502, 503, 504):
                time.sleep(20); continue
            raise
        except (urllib.error.URLError, TimeoutError):
            time.sleep(20)
    raise RuntimeError('gave up on ' + url)


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(); self.out = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'div', 'br', 'blockquote', 'h1', 'h2', 'h3', 'li', 'tr'):
            self.out.append('\n\n')
        if tag in ('script', 'style'):
            self.skip += 1
    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip -= 1
    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def to_text(html):
    p = _Text(); p.feed(html)
    t = ''.join(p.out)
    t = re.sub(r'[ \t\xa0]+', ' ', t); t = re.sub(r' *\n *', '\n', t); t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def load(name, default):
    p = STATE / name
    return json.loads(p.read_text()) if p.exists() else default


def save(name, data):
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = STATE / (name + '.tmp'); tmp.write_text(json.dumps(data, indent=1)); tmp.replace(STATE / name)


def known_cluster_ids():
    ids = set()
    corpus = ROOT / 'data/flp_opinions.json'
    if corpus.exists():
        for d in json.loads(corpus.read_text()):
            m = re.search(r'/opinion/(\d+)/', d['source_url'])
            if m:
                ids.add(m.group(1))
    return ids


def _norm(name):
    return re.sub(r'[^a-z]', '', name.lower())[:30]


def known_cases():
    """(normalized name, date) of everything we hold, to catch one opinion filed under two clusters"""
    from datetime import date
    out = []
    recs = []
    corpus = ROOT / 'data/flp_opinions.json'
    if corpus.exists():
        recs += json.loads(corpus.read_text())
    recs += [json.loads(p.read_text()) for p in (STATE / 'docs').glob('*.json')]
    for d in recs:
        try:
            out.append((_norm(d['name']), date.fromisoformat(d['date'][:10])))
        except ValueError:
            pass
    return out


def same_case(cases, name, day):
    from datetime import date
    try:
        dt = date.fromisoformat(day[:10])
    except ValueError:
        return False
    return any(n == _norm(name) and abs((dt - d).days) <= 1 for n, d in cases)


def known_shas():
    out = set()
    corpus = ROOT / 'data/flp_opinions.json'
    if corpus.exists():
        out |= {d['sha256'] for d in json.loads(corpus.read_text())}
    out |= {json.loads(p.read_text())['sha256'] for p in (STATE / 'docs').glob('*.json')}
    return out


def search_more(state, want):
    """advance the search cursor until enough candidates are queued"""
    while len(state['queue']) < want and state['query_i'] < len(QUERIES):
        url = state.get('next') or BASE + 'search/?' + urlencode({
            'q': QUERIES[state['query_i']], 'type': 'o', 'court': 'ca2 ca9', 'stat_Published': 'on', 'order_by': 'score desc'})
        page = get(url)
        have = {c['cluster_id'] for c in state['queue']} | set(state['done']) | set(state['rejected']) | state['known']
        for r in page.get('results', []):
            cid = str(r.get('cluster_id') or '')
            if not cid or cid in have or not r.get('opinions') or r.get('court_id') not in ('ca2', 'ca9'):
                continue
            have.add(cid)
            state['queue'].append({'cluster_id': cid, 'opinion_id': r['opinions'][0]['id'], 'name': r.get('caseName', ''),
                                   'circuit': '2' if r['court_id'] == 'ca2' else '9', 'date': r.get('dateFiled', ''),
                                   'citation': (r.get('citation') or [''])[0], 'docket': r.get('docketNumber', '')})
        state['next'] = page.get('next')
        if not state['next']:
            state['query_i'] += 1
        save_state(state)
        print(f"search: {len(state['queue'])} queued", flush=True)


def fetch_one(cand):
    d = get(f"{BASE}opinions/{cand['opinion_id']}/?" + urlencode({'fields': FIELDS}))
    src = d.get('html_with_citations') or d.get('html_lawbox') or d.get('html') or ''
    text = to_text(src) if src else (d.get('plain_text') or '').strip()
    return d, src, text


def run(target):
    state = load('state.json', {'queue': [], 'done': [], 'rejected': [], 'next': None, 'query_i': 0})
    state['known'] = known_cluster_ids()
    docs_dir = STATE / 'docs'; docs_dir.mkdir(parents=True, exist_ok=True)
    # known covers merged opinions and done covers harvested ones, they overlap after a merge
    have_total = len(state['known'] | set(state['done']))
    shas = known_shas(); cases = known_cases()
    print(f"corpus {len(state['known'])} + harvested {len(state['done'])}; target {target}", flush=True)
    while have_total < target:
        search_more(state, want=3)
        if not state['queue']:
            print('no more candidates'); break
        cand = state['queue'].pop(0)
        if same_case(cases, cand['name'], cand['date']):
            state['rejected'].append(cand['cluster_id']); print('same case already held', cand['name'], flush=True); save_state(state); continue
        try:
            d, src, text = fetch_one(cand)
        except Exception as exc:
            print('skip', cand['name'], exc, flush=True); state['rejected'].append(cand['cluster_id']); save_state(state); continue
        if len(text) < 8000 or len(re.findall(r'scienter', text, re.I)) < 3:
            state['rejected'].append(cand['cluster_id']); print('reject', cand['name'], len(text), flush=True); save_state(state); continue
        sha = hashlib.sha256(text.encode()).hexdigest()
        if sha in shas:  # same opinion filed under a second cluster
            state['rejected'].append(cand['cluster_id']); print('duplicate text', cand['name'], flush=True); save_state(state); continue
        shas.add(sha); cases.append((_norm(cand['name']), __import__('datetime').date.fromisoformat(cand['date'][:10])))
        rec = {'id': 'cl-' + cand['cluster_id'], 'name': cand['name'], 'circuit': cand['circuit'],
               'source_url': 'https://www.courtlistener.com' + d['absolute_url'], 'citation': cand['citation'] or cand['docket'],
               'date': cand['date'][:10], 'posture': 'unknown', 'text': text, 'provider': 'Free Law Project / CourtListener',
               'retrieved_on': time.strftime('%Y-%m-%d'), 'capture_method': 'courtlistener_api_v4_html_with_citations_to_text',
               'coverage': 'full_opinion_text_as_served_by_api', 'review_status': 'needs_review',
               'sha256': hashlib.sha256(text.encode()).hexdigest(), 'data_kind': 'public_judicial_opinion',
               'capture_sha256': hashlib.sha256(src.encode()).hexdigest(),
               'annotation_notice': 'Source text captured from CourtListener API; structural tags are draft heuristics, not attorney review or subsequent-treatment verification.'}
        (docs_dir / (rec['id'] + '.json')).write_text(json.dumps(rec))
        state['done'].append(cand['cluster_id']); have_total += 1
        save_state(state)
        print(f"got {have_total}/{target}: {cand['name']} ({cand['circuit']}) {len(text):,} chars", flush=True)


def save_state(state):
    s = dict(state); s.pop('known', None); save('state.json', s)


def merge():
    corpus_path = ROOT / 'data/flp_opinions.json'
    corpus = json.loads(corpus_path.read_text())
    have = {d['id'] for d in corpus}
    added = 0
    for p in sorted((STATE / 'docs').glob('*.json')):
        rec = json.loads(p.read_text())
        if rec['id'] in have or hashlib.sha256(rec['text'].encode()).hexdigest() != rec['sha256']:
            continue
        corpus.append(rec); have.add(rec['id']); added += 1
    corpus_path.write_text(json.dumps(corpus, indent=2))
    man_path = ROOT / 'data/flp_manifest.json'
    man = json.loads(man_path.read_text())
    man['documents'] = [{k: d.get(k, '') for k in ('id', 'name', 'circuit', 'source_url', 'citation', 'date', 'sha256', 'retrieved_on', 'capture_method')} for d in corpus]
    man['document_count'] = len(corpus); man['characters'] = sum(len(d['text']) for d in corpus)
    man['scope'] = f"{len(corpus)} Second and Ninth Circuit appellate opinions from CourtListener (earliest five captured 2026-09, the rest via API v4 harvest); not a representative corpus. Source text may contain OCR or line-wrap artifacts."
    man_path.write_text(json.dumps(man, indent=2))
    print(f'merged {added}; corpus now {len(corpus)} opinions')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('run'); r.add_argument('--target', type=int, default=100)
    sub.add_parser('merge')
    a = ap.parse_args()
    run(a.target) if a.cmd == 'run' else merge()
