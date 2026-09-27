"""Read-only CourtListener source catalog, independent of case outcome cohorts."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from .passages import build_passages, search_passages

class SourceCatalog:
    def __init__(self, path, taxonomy):
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
        self.passages = build_passages(self.documents, taxonomy)
        self.by_passage = {p['id']: p for p in self.passages}

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
        return {'passage':{k:v for k,v in passage.items() if k!='factor_keywords'},
                'before':doc['text'][max(0,passage['start']-900):passage['start']],
                'after':doc['text'][passage['end']:passage['end']+900],
                'citation':doc.get('citation',''),'date':doc.get('date',''),
                'source_url':doc['source_url'],'ocr_warning':doc.get('ocr_warning',False)}
