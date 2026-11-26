"""Read-only CourtListener source catalog, independent of case outcome cohorts."""
import hashlib
import json
from pathlib import Path
from .encoder import get_encoder
from urllib.parse import urlsplit
from .passages import build_passages, search_passages, public

class SourceCatalog:
    def __init__(self, path, taxonomy, cache_dir=None):
        self.documents = json.loads(Path(path).read_text()) if Path(path).exists() else []
        if not isinstance(self.documents, list):
            raise ValueError('Source catalog must be a list.')
        seen = set()
        for document in self.documents:
            required = ('id','name','circuit','source_url','text','sha256','review_status')
            if not isinstance(document, dict) or any(not isinstance(document.get(k),str) for k in required):
                raise ValueError('Invalid source record.')
            if document['id'] in seen or document['circuit'] not in {'2','9'}:
                raise ValueError('Duplicate source or unsupported circuit.')
            seen.add(document['id'])
            url = urlsplit(document['source_url'])
            if url.scheme!='https' or url.netloc!='www.courtlistener.com' or not url.path.startswith('/opinion/'):
                raise ValueError('Source must link to a CourtListener opinion.')
            if hashlib.sha256(document['text'].encode()).hexdigest()!=document['sha256']:
                raise ValueError('Source text checksum mismatch.')
        self.by_document = {d['id']: d for d in self.documents}
        self.passages = self._load_or_build(taxonomy, cache_dir)
        self.by_passage = {p['id']: p for p in self.passages}

    def _load_or_build(self, taxonomy, cache_dir):
        # building tags + vectors costs ~6ms per passage, so a 100 opinion corpus would add a
        # minute to every start. cache keyed on corpus, rules, taxonomy, encoder and code.
        root = Path(__file__).resolve().parent
        h = hashlib.sha256()
        for d in self.documents:
            h.update(d['sha256'].encode())
        h.update(json.dumps(taxonomy, sort_keys=True).encode())
        h.update(get_encoder().name.encode())
        for f in ('passages.py', 'signals.py', 'fusion.py', 'encoder.py', '../data/scienter_signals.json'):
            h.update((root / f).read_bytes())
        key = h.hexdigest()
        path = Path(cache_dir) / 'passages-cache.json' if cache_dir else None
        if path and path.exists():
            try:
                blob = json.loads(path.read_text())
                if blob.get('key') == key:
                    for p in blob['passages']:
                        v = p.get('_vec')
                        if isinstance(v, dict) and 'd' in v:
                            p['_vec'] = {int(k): x for k, x in v['d'].items()}
                        elif isinstance(v, dict) and 'l' in v:
                            p['_vec'] = v['l']
                    return blob['passages']
            except (ValueError, KeyError, OSError):
                pass
        passages = build_passages(self.documents, taxonomy)
        if path:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                out = []
                for p in passages:
                    q = dict(p); v = q.get('_vec')
                    q['_vec'] = {'d': {str(k): x for k, x in v.items()}} if isinstance(v, dict) else {'l': list(v)} if v is not None else None
                    out.append(q)
                tmp = path.with_suffix('.tmp'); tmp.write_text(json.dumps({'key': key, 'passages': out})); tmp.replace(path)
            except OSError:
                pass
        return passages

    def search(self, payload):
        query = payload.get('query')
        if not isinstance(query,str) or not query.strip() or len(query)>10000:
            raise ValueError('Supply a passage of 1–10,000 characters.')
        circuit=payload.get('circuit')
        if circuit not in (None,'2','9'):
            raise ValueError('Select Second Circuit, Ninth Circuit, or both.')
        limit=payload.get('limit',12)
        if type(limit) is not int or not 1<=limit<=30:
            raise ValueError('Result limit must be 1–30.')
        results=search_passages(query,self.passages,circuit,limit)
        return {'results':results,'documents':len(self.documents),'passages':len(self.passages),
                'notice':'Draft structural tags; compare context and verify subsequent treatment. No case outcomes inferred.'}

    def context(self, passage_id):
        passage=self.by_passage.get(passage_id)
        if passage is None:
            raise KeyError('Passage not found.')
        doc=self.by_document[passage['document_id']]
        return {'passage':public(passage),
                'before':doc['text'][max(0,passage['start']-900):passage['start']],
                'after':doc['text'][passage['end']:passage['end']+900],
                'citation':doc.get('citation',''),'date':doc.get('date',''),
                'source_url':doc['source_url'],'ocr_warning':doc.get('ocr_warning',False)}
