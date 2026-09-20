#!/usr/bin/env python3
"""Validate a structured corpus file, optionally import into the local running server."""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from urllib.request import Request, build_opener
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.acquire import NoRedirect


def validate(records, taxonomy):
    ids=set(); factor_ids={f['id'] for f in taxonomy['factors']}
    if not isinstance(records,list) or not records: raise ValueError('Expected nonempty array of cases')
    for c in records:
        for key in ('id','case_id','name','citation','court','date','summary','opinion_text','source_url','outcome_evidence','factors','review_status'):
            if key not in c: raise ValueError('Missing '+key)
        if c['id'] in ids: raise ValueError('Duplicate id '+c['id'])
        ids.add(c['id'])
        if c.get('circuit') not in ('2','9'): raise ValueError('Unsupported circuit')
        if c.get('posture') not in ('motion_to_dismiss','appeal_of_dismissal','interlocutory_appeal'): raise ValueError('Unsupported posture')
        if c.get('defendant_scope') not in ('individual','corporate','both'): raise ValueError('Invalid defendant scope')
        if c.get('outcome') not in ('survived','dismissed','mixed','unresolved'): raise ValueError('Invalid ruling')
        if c.get('outcome_basis') not in ('scienter','other','mixed','unknown'): raise ValueError('Invalid ruling basis')
        if not isinstance(c.get('synthetic'),bool): raise ValueError('Explicit synthetic boolean required')
        if set(c['factors'])!=factor_ids: raise ValueError('Factor keys differ from taxonomy')
        evidence=[c['outcome_evidence']]
        for f in c['factors'].values():
            if f['status'] not in ('present','absent','unknown'): raise ValueError('Invalid factor status')
            if f['strength'] not in ('specific','general','mixed','unknown'): raise ValueError('Invalid factor strength')
            if f['status']!='unknown' and not f['evidence']: raise ValueError('Known factor requires evidence')
            evidence.extend(f['evidence'])
        for e in evidence:
            if not e.get('quote') or e['quote'] not in c['opinion_text']: raise ValueError('Unanchored quotation in '+c['id'])
            if not e.get('locator') or not e.get('characterization'): raise ValueError('Missing evidence context')
            if not c['synthetic'] and urlsplit(e.get('source_url','')).scheme!='https': raise ValueError('Real evidence requires HTTPS source')
        if not c['synthetic']: c['review_status']='needs_review'
    return records


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('file');p.add_argument('--server',help='Optional http://127.0.0.1:8765');args=p.parse_args()
    try:
        taxonomy=json.loads((Path(__file__).resolve().parents[1]/'data/taxonomy.json').read_text())
        cases=validate(json.loads(Path(args.file).read_text()),taxonomy)
        if args.server:
            u=urlsplit(args.server)
            if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost') or u.username or u.query or u.fragment or u.path not in ('','/'):
                raise ValueError('Only local HTTP server roots are permitted')
            request=Request(args.server.rstrip('/')+'/api/import',data=json.dumps({'cases':cases}).encode(),headers={'Content-Type':'application/json'},method='POST')
            with build_opener(NoRedirect()).open(request,timeout=30) as response: print(response.read().decode())
        else: print(f'Validated {len(cases)} records; no data written. Real records will enter as needs_review.')
    except (ValueError,OSError,KeyError,TypeError) as exc: print(str(exc),file=sys.stderr);return 2


if __name__=='__main__':sys.exit(main())
