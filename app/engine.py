"""Transparent draft extraction, comparison and case-level descriptive calibration."""
import math
import re
from collections import Counter
from urllib.parse import urlsplit

STATUSES = {'present', 'absent', 'unknown'}
STRENGTHS = {'specific', 'general', 'mixed', 'unknown'}

def validate_evidence(evidence, text):
    if not isinstance(evidence, dict) or not isinstance(evidence.get('quote'), str) or not evidence['quote'].strip() or evidence['quote'] not in text:
        raise ValueError('Every evidence quote must be an exact nonempty substring of the source text.')
    for field in ['locator','source_url','characterization']:
        if field in evidence and not isinstance(evidence[field],str):raise ValueError('Evidence metadata must be text.')
    url=evidence.get('source_url','')
    if url:
        try:
            parsed=urlsplit(url)
            valid=parsed.scheme in {'http','https'} and parsed.hostname and not parsed.username and not any(c.isspace() for c in url)
        except ValueError:valid=False
        if not valid:raise ValueError('Evidence URLs must be valid HTTP or HTTPS URLs.')


def validate_profile(profile, text, taxonomy):
    if not isinstance(text,str):raise ValueError('Source text must be a string.')
    if not isinstance(profile, dict) or not isinstance(profile.get('factors'), dict):
        raise ValueError('Profile must contain factors.')
    ids = {f['id'] for f in taxonomy['factors']}
    if set(profile['factors']) - ids:
        raise ValueError('Unknown factor IDs.')
    result = {}
    for fid in ids:
        f = profile['factors'].get(fid, {'status':'unknown','strength':'unknown','evidence':[]})
        if not isinstance(f, dict) or not isinstance(f.get('status'),str) or f['status'] not in STATUSES or not isinstance(f.get('strength','unknown'),str) or f.get('strength', 'unknown') not in STRENGTHS:
            raise ValueError('Invalid factor status or strength.')
        evidence = f.get('evidence', [])
        if not isinstance(evidence, list): raise ValueError('Evidence must be a list.')
        for e in evidence:validate_evidence(e,text)
        if f['status']!='unknown' and not evidence:raise ValueError('Present or absent factors require an exact supporting passage; attach evidence or choose unknown.')
        if 'needs_review' in f and type(f['needs_review']) is not bool:raise ValueError('needs_review must be a boolean.')
        result[fid] = {**f, 'evidence':evidence, 'strength':f.get('strength','unknown')}
    return {**profile, 'factors':result}

def draft(text, taxonomy):
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', text) if s.strip()]
    factors = {}
    for f in taxonomy['factors']:
        hits = []; positive = []; negative = []
        for sentence in sentences:
            matches = [m for key in f.get('keywords', []) for m in re.finditer(r'\b'+re.escape(key)+r'\b',sentence,re.I)]
            if not matches: continue
            hits.append(sentence)
            # A negation affects its nearby mention, not an unrelated later clause.
            # Keep negated-only mentions unknown; never infer factual absence.
            affirmative = False
            for match in matches:
                before = sentence[max(0,match.start()-55):match.start()]
                before = re.split(r'[;,:]|\b(?:but|although|whereas)\b',before,flags=re.I)[-1]
                words = re.findall(r"[a-z']+",before.lower())[-4:]
                negated = any(word in {'no','not','never','without','neither','denied','lacked',"didn't"} for word in words)
                if not negated: affirmative = True
            (positive if affirmative else negative).append(sentence)
        status = 'present' if positive else 'unknown'
        factors[f['id']] = {'status':status,'strength':('mixed' if positive and negative else 'general') if hits else 'unknown','needs_review':True,
            'evidence':[{'quote':s,'locator':'Submitted fact pattern','source_url':'','characterization':'Draft keyword match; assess context and negation.'} for s in hits[:3]]}
    return {'factors':factors,'method':'deterministic_draft','warnings':['Keyword extraction is a draft for attorney review. Negated or ambiguous mentions remain unknown; unmentioned factors are never assumed absent.']}

def narrative_similarity(text, docs):
    token = lambda s: Counter(re.findall(r'[a-z]{3,}',s.lower()))
    vectors = [token(text)] + [token(d) for d in docs]
    df = Counter(t for v in vectors for t in v)
    def weighted(v): return {t:(1+math.log(n))*(1+math.log((len(vectors)+1)/(df[t]+1))) for t,n in v.items()}
    vectors = [weighted(v) for v in vectors]
    q = vectors[0]; qnorm = math.sqrt(sum(x*x for x in q.values()))
    return [sum(q.get(t,0)*n for t,n in v.items())/(qnorm*math.sqrt(sum(x*x for x in v.values())) or 1) for v in vectors[1:]]

def wilson(success, n):
    z = 1.959963984540054; p = success/n; d=1+z*z/n
    center=(p+z*z/(2*n))/d; delta=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [100*(center-delta),100*(center+delta)]

def calibrate(cases, present, mode):
    # A case contributes once, including when it has repeated opinions. Conflicting rulings are mixed.
    groups = {}
    for c in cases:
        if c['outcome_basis'] != 'scienter': continue
        if not all(c['factors'].get(fid,{}).get('status')=='present' for fid in present): continue
        groups.setdefault(c['case_id'],set()).add(c['outcome'])
    counts = Counter(next(iter(v)) if len(v)==1 else 'mixed' for v in groups.values())
    n=len(groups); binary=counts['survived']+counts['dismissed']
    suppressed = n < 20 or binary < 20
    return {'n':n, **{k:counts[k] for k in ['survived','dismissed','mixed','unresolved']},
        'rate':None if suppressed else round(100*counts['survived']/binary,1),
        'interval':None if suppressed else wilson(counts['survived'],binary),'suppressed':suppressed,
        'reason':'Fewer than 20 distinct cases with binary scienter outcomes; rate withheld.' if suppressed else 'Descriptive observed survival fraction among binary scienter rulings; mixed/unresolved excluded from denominator. Not a prediction.',
        'unit':'distinct case_id','mode':mode,'binary_n':binary,'cohort_factors':sorted(present),
        'selection_note':'All eligible cases matching every present factor, exact circuit, posture and defendant scope; independent of retrieval rank. Unknown factors are unconstrained.'}

def analyze(payload, cases, taxonomy):
    if not isinstance(payload,dict):raise ValueError('Analysis payload must be an object.')
    for field in ['cross_circuit','use_llm']:
        if field in payload and type(payload[field]) is not bool:raise ValueError(field+' must be a boolean.')
    text=payload.get('text','')
    if not isinstance(text,str) or not text.strip() or len(text)>100000: raise ValueError('Supply a fact pattern of 1–100,000 characters.')
    for key, choices, default in [('circuit',{'2','9'},'9'),('mode',{'real','demo'},'demo'),('posture',{'motion_to_dismiss','appeal_of_dismissal','interlocutory_appeal'},'motion_to_dismiss'),('defendant_scope',{'individual','corporate','both'},'both')]:
        if not isinstance(payload.get(key,default),str) or payload.get(key,default) not in choices: raise ValueError('Invalid '+key)
    circuit=payload.get('circuit','9'); mode=payload.get('mode','demo'); scope=payload.get('defendant_scope','both'); posture=payload.get('posture','motion_to_dismiss')
    profile=validate_profile(payload['profile'],text,taxonomy) if 'profile' in payload else draft(text,taxonomy)
    eligible=[c for c in cases if c['synthetic']==(mode=='demo') and c['review_status']=='reviewed' and c['posture']==posture and c['defendant_scope']==scope]
    cohort=[c for c in eligible if c['circuit']==circuit]
    candidates=[c for c in eligible if payload.get('cross_circuit',False) or c['circuit']==circuit]
    present={fid for fid,f in profile['factors'].items() if f['status']=='present'}
    known={fid:f['status'] for fid,f in profile['factors'].items() if f['status']!='unknown'}
    weights={f['id']:f.get('weight',1) for f in taxonomy['factors']}
    similarities=narrative_similarity(text,[c['summary'] for c in candidates]); results=[]
    for c,similarity in zip(candidates,similarities):
        matches=[fid for fid,s in known.items() if c['factors'].get(fid,{}).get('status')==s]
        differences=[fid for fid,s in known.items() if c['factors'].get(fid,{}).get('status','unknown') not in {s,'unknown'}]
        overlap=sum(weights[fid] for fid in matches)/(sum(weights[fid] for fid in known) or 1)
        results.append({'case':c,'score':round(100*(.8*overlap+.2*similarity),1),'matched_factors':matches,'differences':differences,'same_circuit':c['circuit']==circuit})
    results.sort(key=lambda r:(not r['same_circuit'],-r['score'],r['case']['id']))
    return {'profile':profile,'results':results[:12],'stats':calibrate(cohort,present,mode),'doctrine':taxonomy.get('doctrine',{}).get(circuit,{}),'warnings':(['DEMONSTRATION: all cases and statistics in this mode are fictional.'] if mode=='demo' else []) + ['Similarity scores measure profile overlap and narrative similarity, not likelihood of scienter.']}
