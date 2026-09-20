"""Durable local corpus, evidence graph, matters and review audit."""
import json
import sqlite3
from contextlib import contextmanager
import uuid
import re
from collections import Counter
from datetime import datetime, timezone
from .engine import validate_profile, validate_evidence, analyze

def validate_case(c, taxonomy):
    required = ['id','name','citation','circuit','court','date','posture','case_id','defendant_scope','outcome','outcome_basis','source_url','opinion_text','summary','synthetic','review_status','factors','outcome_evidence']
    if not isinstance(c,dict) or any(k not in c for k in required): raise ValueError('Case missing required fields.')
    if any(not isinstance(c[k],str) or not c[k].strip() for k in ['id','name','case_id','opinion_text','summary']): raise ValueError('Case identity and source text must be nonempty strings.')
    for field in ['citation','court','date','source_url']:
        if not isinstance(c[field],str):raise ValueError('Case '+field+' must be text.')
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}',c['id']):raise ValueError('Case ID must be a URL-safe identifier, at most 160 characters.')
    try:datetime.strptime(c['date'],'%Y-%m-%d')
    except ValueError:raise ValueError('Case date must be YYYY-MM-DD.')
    for key,choices in {'circuit':{'2','9'},'posture':{'motion_to_dismiss','appeal_of_dismissal','interlocutory_appeal'},'defendant_scope':{'individual','corporate','both'},'outcome':{'survived','dismissed','mixed','unresolved'},'outcome_basis':{'scienter','other','mixed','unknown'},'review_status':{'reviewed','needs_review'}}.items():
        if not isinstance(c[key],str) or c[key] not in choices: raise ValueError('Invalid case '+key)
    if type(c['synthetic']) is not bool: raise ValueError('synthetic must be a boolean.')
    if not c['synthetic'] and not c['source_url'].startswith(('https://','http://')): raise ValueError('Real cases require a source URL.')
    validate_profile({'factors':c['factors']},c['opinion_text'],taxonomy)
    validate_evidence(c['outcome_evidence'],c['opinion_text'])
    validate_evidence({'quote':c['opinion_text'],'source_url':c['source_url']},c['opinion_text'])
    return c

class Store:
    def __init__(self,path,taxonomy,seeds=()):
        self.path=str(path); self.taxonomy=taxonomy
        with self.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS evidence(case_id TEXT, factor_id TEXT, status TEXT, quote TEXT, locator TEXT);
            CREATE TABLE IF NOT EXISTS narrative_vectors(case_id TEXT PRIMARY KEY, term_counts TEXT);
            CREATE TABLE IF NOT EXISTS matters(id TEXT PRIMARY KEY, document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, case_id TEXT, reviewer TEXT, note TEXT, reviewed_at TEXT);''')
        for c in seeds:
            validate_case(c,taxonomy)
            if not self.case(c['id']): self.put_case(c)
    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        try:
            with db:
                yield db
        finally:
            db.close()
    def cases(self):
        with self.connect() as db:return [json.loads(r[0]) for r in db.execute('SELECT document FROM cases ORDER BY id')]
    def case(self,id):
        with self.connect() as db:r=db.execute('SELECT document FROM cases WHERE id=?',(id,)).fetchone()
        return json.loads(r[0]) if r else None
    def _write_case(self,db,c,replace=False):
        db.execute(('INSERT OR REPLACE' if replace else 'INSERT')+' INTO cases VALUES (?,?)',(c['id'],json.dumps(c)))
        db.execute('DELETE FROM evidence WHERE case_id=?',(c['id'],))
        db.execute('INSERT OR REPLACE INTO narrative_vectors VALUES (?,?)',(c['id'],json.dumps(Counter(re.findall(r'[a-z]{3,}',c['summary'].lower())))))
        for fid,f in c['factors'].items():
            for e in f.get('evidence',[]):db.execute('INSERT INTO evidence VALUES (?,?,?,?,?)',(c['id'],fid,f['status'],e['quote'],e.get('locator','')))
    def put_case(self,c):
        with self.connect() as db:self._write_case(db,c,replace=True)
    def import_cases(self, cases):
        if not isinstance(cases,list) or not 0<len(cases)<=500:raise ValueError('Import 1–500 cases per request.')
        for c in cases:validate_case(c,self.taxonomy)
        if len({c['id'] for c in cases}) != len(cases):raise ValueError('Duplicate case IDs in import.')
        try:
            with self.connect() as db:
                for c in cases:self._write_case(db,{**c,'review_status':'needs_review'})
        except sqlite3.IntegrityError as exc:raise ValueError('Case ID already exists; imports cannot overwrite records. No records imported.') from exc
        return {'imported':len(cases),'review_status':'needs_review'}
    def review(self,id,payload):
        c=self.case(id)
        if not c:raise KeyError('Case not found.')
        if not isinstance(payload,dict) or not isinstance(payload.get('reviewer'),str) or not isinstance(payload.get('note'),str):raise ValueError('Reviewer and note must be text.')
        if not c['synthetic'] and payload.get('source_verified') is not True:raise ValueError('Real records require source_verified:true: attest that you checked the original opinion, legal characterizations, posture and scienter outcome. Exact-text validation alone does not authenticate an opinion.')
        reviewer=payload['reviewer'].strip(); note=payload['note'].strip()
        if not reviewer or not note:raise ValueError('Reviewer name and evidence review note are required.')
        validate_case(c,self.taxonomy)
        c['review_status']='reviewed'
        c['review_attestation']={'reviewer':reviewer,'note':note,'source_verified':payload.get('source_verified') is True,'reviewed_at':datetime.now(timezone.utc).isoformat(),'verification_method':'manual_attestation; exact quote consistency checked locally, external authenticity not independently verified'}
        with self.connect() as db:
            self._write_case(db,c,replace=True)
            db.execute('INSERT INTO reviews(case_id,reviewer,note,reviewed_at) VALUES (?,?,?,?)',(id,reviewer,note,datetime.now(timezone.utc).isoformat()))
        return c
    def matters(self):
        with self.connect() as db:return [json.loads(r[0]) for r in db.execute('SELECT document FROM matters ORDER BY rowid DESC')]
    def matter(self,id):
        with self.connect() as db:r=db.execute('SELECT document FROM matters WHERE id=?',(id,)).fetchone()
        return json.loads(r[0]) if r else None
    def save_matter(self,p):
        analyze(p,[],self.taxonomy)
        if not isinstance(p.get('title'),str) or not p['title'].strip():raise ValueError('Matter title is required.')
        if not isinstance(p.get('text'),str) or not p['text'].strip():raise ValueError('Matter text is required.')
        profile=validate_profile(p.get('profile',{}),p['text'],self.taxonomy)
        m={**p,'profile':profile,'id':uuid.uuid4().hex,'created_at':datetime.now(timezone.utc).isoformat()}
        with self.connect() as db:db.execute('INSERT INTO matters VALUES (?,?)',(m['id'],json.dumps(m)))
        return m
    def delete_matter(self,id):
        with self.connect() as db:db.execute('DELETE FROM matters WHERE id=?',(id,))
        return {'deleted':id}

    def graph(self):
        cases=self.cases()
        nodes=[{'id':'factor:'+f['id'],'type':'factor','label':f['label']} for f in self.taxonomy['factors']]
        nodes += [{'id':'outcome:'+o,'type':'ruling_outcome','label':o} for o in ['survived','dismissed','mixed','unresolved']]
        edges=[]
        for c in cases:
            nodes.append({'id':'case:'+c['id'],'type':'opinion','label':c['name'],'synthetic':c['synthetic'],'review_status':c['review_status']})
            edges.append({'source':'case:'+c['id'],'target':'outcome:'+c['outcome'],'relation':'ruling','basis':c['outcome_basis'],'evidence':c['outcome_evidence']})
            for fid,f in c['factors'].items():
                if f['status']!='unknown':edges.append({'source':'case:'+c['id'],'target':'factor:'+fid,'relation':f['status'],'evidence':f['evidence']})
        return {'nodes':nodes,'edges':edges,'notice':'Graph includes unreviewed records for inspection; only reviewed records enter retrieval and statistics.'}
