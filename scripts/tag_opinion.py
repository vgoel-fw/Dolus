#!/usr/bin/env python3
"""Convert a local opinion text and explicit ruling metadata into a reviewable record.
Default is a conservative local draft; --llm explicitly sends opinion text to Anthropic.
No ruling outcome is inferred or predicted by the tagger.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.engine import draft, validate_profile
from app.storage import validate_case
from app.llm import extract
ROOT=Path(__file__).resolve().parents[1]

def tag(text,metadata,taxonomy,use_llm=False):
    if not isinstance(text,str) or not text.strip() or len(text)>100000:
        raise ValueError('Opinion text must contain 1–100,000 characters; use a documented relevant excerpt if longer.')
    if metadata.get('synthetic') is not False:
        raise ValueError('Opinion tagging requires explicit synthetic:false metadata; fictional fixtures use the separate generator.')
    profile=extract(text,taxonomy) if use_llm else draft(text,taxonomy)
    profile=validate_profile(profile,text,taxonomy)
    for factor in profile['factors'].values():
        for evidence in factor['evidence']:
            start=text.index(evidence['quote'])
            evidence['locator']=f'Normalized source text, characters {start+1}–{start+len(evidence["quote"])}; legal pinpoint requires review'
            evidence['source_url']=metadata.get('source_url','')
            evidence['characterization']='Unreviewed extraction: '+evidence.get('characterization','')
    record={**metadata,'opinion_text':text,'factors':profile['factors'],'review_status':'needs_review',
            'tagging':{'method':profile['method'],'taxonomy_version':taxonomy['version'],'requires_full_source_review':True}}
    validate_case(record,taxonomy)
    return record

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--text',required=True,help='UTF-8 normalized opinion text')
    p.add_argument('--metadata',required=True,help='JSON with case metadata and exact outcome evidence')
    p.add_argument('--out',required=True,help='New JSON path containing a one-record import array')
    p.add_argument('--llm',action='store_true',help='Explicitly send source text to Anthropic')
    args=p.parse_args()
    try:
        taxonomy=json.loads((ROOT/'data/taxonomy.json').read_text())
        record=tag(Path(args.text).read_text(),json.loads(Path(args.metadata).read_text()),taxonomy,args.llm)
        path=Path(args.out);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x') as f:json.dump([record],f,indent=2)
        print(f'Wrote draft to {path}. Attorney source/ruling review is required before admission.')
    except (ValueError,OSError,KeyError,TypeError) as e:p.exit(2,str(e)+'\n')
if __name__=='__main__':main()
