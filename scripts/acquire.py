#!/usr/bin/env python3
"""Stage CourtListener API data without converting case-level metadata into rulings."""
import argparse
import csv
import datetime
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

BASE = 'https://www.courtlistener.com/api/rest/v4/'


def safe_url(url):
    p = urlsplit(url)
    if p.scheme != 'https' or p.netloc != 'www.courtlistener.com' or not p.path.startswith('/api/rest/v4/') or p.username or p.fragment:
        raise ValueError('Refusing non-CourtListener v4 URL')
    return url


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect refused to protect API credentials')


def fetch(url, token):
    request = Request(safe_url(url), headers={'Authorization': 'Token '+token, 'Accept': 'application/json', 'User-Agent': 'ScienterAtlasResearch/0.1'})
    with build_opener(NoRedirect()).open(request, timeout=45) as response:
        return json.load(response)


def collect(url, token, directory, max_pages=1, delay=13):
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError('Staging directory must be empty; use a new directory for each run')
    seen = set()
    manifest = {'source': 'CourtListener v4', 'retrieved_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'pages': [], 'next': url, 'review_status': 'needs_review'}
    try:
        for n in range(max_pages):
            if not url: break
            safe_url(url)
            if url in seen: raise ValueError('Pagination cycle refused')
            seen.add(url)
            if n: time.sleep(delay)
            page = fetch(url, token)
            if not isinstance(page, dict): raise ValueError('Unexpected API response')
            filename = f'page-{n+1:04d}.json'
            destination = directory / filename
            if destination.exists(): raise ValueError('Output exists; use a new staging directory')
            destination.write_text(json.dumps(page, indent=2)+'\n')
            manifest['pages'].append({'path':filename,'url':url})
            url = page.get('next')
            if url: safe_url(url)
            manifest['next'] = url
    finally:
        (directory/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def crossref(csv_path, cases_path, out):
    """Exact user-curated IDs only; preserve provenance and avoid fuzzy false joins."""
    cases = json.loads(Path(cases_path).read_text())
    by_id = {c['case_id']: c for c in cases}
    links, unmatched, seen = [], [], set()
    with Path(csv_path).open(newline='', encoding='utf-8-sig') as source:
        reader = csv.DictReader(source)
        required = {'case_id','scac_id','case_outcome','source_url'}
        if not required.issubset(reader.fieldnames or []): raise ValueError('CSV requires case_id,scac_id,case_outcome,source_url')
        for row in reader:
            key = (row['case_id'], row['scac_id'])
            if key in seen: raise ValueError('Duplicate cross-reference row')
            seen.add(key)
            record = {k:row[k] for k in required}
            record.update({'review_status':'needs_review','join_method':'user_supplied_exact_case_id','not_a_motion_outcome':True})
            if row['case_id'] not in by_id: unmatched.append(record)
            elif by_id[row['case_id']].get('synthetic'): raise ValueError('Refusing to link real SCAC metadata to synthetic cases')
            else: links.append(record)
    Path(out).write_text(json.dumps({'links':links,'unmatched':unmatched,'notice':'Separate case-level metadata. Never use settlement or case dismissal to infer scienter or a motion ruling.'},indent=2)+'\n')
    return len(links), len(unmatched)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    search=sub.add_parser('search',help='Stage opinion search results; does not tag or import')
    search.add_argument('--query',default='scienter AND ("10b-5" OR "10(b)")')
    search.add_argument('--out',required=True)
    search.add_argument('--pages',type=int,default=1)
    search.add_argument('--delay',type=float,default=13)
    search.add_argument('--resume-url',help='Use manifest next URL in a NEW output directory')
    opinion=sub.add_parser('opinion',help='Fetch a specific opinion ID selected from search results')
    opinion.add_argument('id',type=int); opinion.add_argument('--out',required=True)
    join=sub.add_parser('crossref',help='Cross-reference a lawfully supplied SCAC CSV by exact case_id')
    join.add_argument('--csv',required=True);join.add_argument('--cases',default='data/cases.json');join.add_argument('--out',required=True)
    args=p.parse_args()
    try:
        if args.command=='crossref':
            linked,unmatched=crossref(args.csv,args.cases,args.out)
            print(f'Staged {linked} links and {unmatched} unmatched rows; no opinion outcome changed.'); return
        token=os.getenv('COURTLISTENER_TOKEN','')
        if not token: raise ValueError('Set COURTLISTENER_TOKEN in your environment; do not commit it.')
        if args.command=='search':
            if not 1<=args.pages<=20 or args.delay<13: raise ValueError('Use 1–20 pages and delay >=13 seconds; account limits still apply.')
            url=args.resume_url or BASE+'search/?'+urlencode({'q':args.query,'type':'o'})
            result=collect(url,token,Path(args.out),args.pages,args.delay)
        else:
            if args.id<=0: raise ValueError('Opinion ID must be positive')
            result=collect(BASE+f'opinions/{args.id}/',token,Path(args.out))
        print(f'Staged {len(result["pages"])} page(s). Review manifest and raw data before tagging.')
    except HTTPError as exc:
        print(f'CourtListener HTTP {exc.code}. Check API permissions/rate limits; resume using saved manifest. No automatic retry.',file=sys.stderr);return 2
    except (ValueError,OSError) as exc:
        print(str(exc),file=sys.stderr);return 2


if __name__=='__main__': sys.exit(main())
