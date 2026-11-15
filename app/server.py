"""Local-only HTTP application. Run: python3 -m app.server --port 8765."""
import argparse
import json
import mimetypes
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs, unquote
from .engine import analyze
from .storage import Store
from .llm import extract
from .source_catalog import SourceCatalog
from .fusion import analyze_intent, rules as signal_rules

def signal_catalog():
    r=signal_rules()
    return {'statutes':[{'id':s['id'],'label':s['label'],'scienter':s['scienter']} for s in r['statutes']],
            'signals':[{'id':s['id'],'label':s['label'],'family':s['family'],'description':s['description']} for s in r['signals']],'notice':r['notice']}
ROOT=Path(__file__).resolve().parent.parent
MAX_BODY=8*1024*1024
# fix: mimetypes reads the os registry, on some windows setups .js comes back text/plain
# and with nosniff the browser refuses to run the module, so the page stays blank
STATIC_TYPES={'.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.html':'text/html; charset=utf-8','.svg':'image/svg+xml','.json':'application/json'}

# fix: browsers drop the port from Host on port 80, which used to 403 every request
def allowed_host(host,port):
    names={'127.0.0.1','localhost','[::1]'}
    return host in {f'{n}:{port}' for n in names} or (port==80 and host in names)
def allowed_origin(origin,port):return origin is None or origin in {f'http://127.0.0.1:{port}',f'http://localhost:{port}',f'http://[::1]:{port}'}

class Handler(BaseHTTPRequestHandler):
    server_version='Dolus/1.0'
    def setup(self):
        super().setup()
        self.connection.settimeout(30)
    def log_message(self,format,*args): pass # Matter text and query strings are not logged.
    def send_json(self,data,status=200):
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(json.dumps(data).encode())
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        super().end_headers()
    def do_GET(self):self.dispatch('GET')
    def do_POST(self):self.dispatch('POST')
    def do_DELETE(self):self.dispatch('DELETE')
    def dispatch(self,method):
        try:
            port=self.server.server_port
            if not allowed_host(self.headers.get('Host',''),port):return self.send_json({'error':'Invalid local Host header.'},403)
            if method!='GET' and (not allowed_origin(self.headers.get('Origin'),port) or self.headers.get('Sec-Fetch-Site')=='cross-site'):
                return self.send_json({'error':'Cross-origin writes are forbidden.'},403)
            parsed=urlsplit(self.path); path=unquote(parsed.path); store=self.server.store; taxonomy=self.server.taxonomy
            p={}
            if method=='POST':
                if self.headers.get('Transfer-Encoding'):return self.send_json({'error':'Transfer-Encoding is unsupported; supply Content-Length.'},400)
                if self.headers.get_content_type()!='application/json':return self.send_json({'error':'Content-Type application/json is required.'},415)
                try:length=int(self.headers.get('Content-Length','0'))
                except ValueError:return self.send_json({'error':'Content-Length must be an integer.'},400)
                if length<=0 or length>MAX_BODY:return self.send_json({'error':'Request body must be 1 byte to 8 MiB.'},413)
                p=json.loads(self.rfile.read(length))
                if not isinstance(p,dict):raise ValueError('JSON request must be an object.')
            if path=='/api/passages/search' and method=='POST':
                return self.send_json(self.server.source_catalog.search(p))
            if path=='/api/passages/context' and method=='GET':
                return self.send_json(self.server.source_catalog.context(parse_qs(parsed.query).get('id',[''])[0]))
            if path=='/api/signals' and method=='POST':
                return self.send_json(analyze_intent(p.get('text'),p.get('statute','10b'),p.get('circuit','9') if p.get('circuit') in ('2','9') else '9'))
            if path=='/api/health' and method=='GET':return self.send_json({'status':'ok','storage':'sqlite','network_default':'off'})
            if method=='GET' and path=='/api/graph':return self.send_json(store.graph())
            if method=='GET' and path=='/api/bootstrap':
                cases=store.cases()
                return self.send_json({'taxonomy':taxonomy,'cases':cases,'matters':store.matters(),'config':{'llm_enabled':bool(os.getenv('ANTHROPIC_API_KEY')),'corpus_mode':'separate_demo_and_real'},'signals':signal_catalog(),'sources':{'opinions':[{k:d.get(k,'') for k in ('id','name','circuit','citation','date','source_url')} for d in self.server.source_catalog.documents],'passages':len(self.server.source_catalog.passages)},'corpus':{'real':sum(not c['synthetic'] for c in cases),'synthetic':sum(c['synthetic'] for c in cases),'reviewed':sum(c['review_status']=='reviewed' for c in cases)}})
            if method=='POST' and path in {'/api/analyze','/api/compare'}:
                if 'use_llm' in p and type(p['use_llm']) is not bool:raise ValueError('use_llm must be a boolean.')
                if p.get('use_llm'):
                    if not isinstance(p.get('text'),str) or not 0<len(p['text'])<=100000:raise ValueError('Invalid input text length.')
                    p['profile']=extract(p['text'],taxonomy)
                return self.send_json(analyze(p,store.cases(),taxonomy))
            if path=='/api/matters':
                if method=='GET':return self.send_json(store.matters())
                if method=='POST':
                    analyze(p,[],taxonomy)
                    return self.send_json(store.save_matter(p),201)
            if path.startswith('/api/matters/'):
                id=path.split('/')[-1]
                if method=='DELETE':return self.send_json(store.delete_matter(id))
                if method=='GET':
                    result=store.matter(id)
                    if not result:raise KeyError('Matter not found.')
                    return self.send_json(result)
            if method=='POST' and path=='/api/import':return self.send_json(store.import_cases(p.get('cases')),201)
            if path.startswith('/api/cases/'):
                parts=path.strip('/').split('/')
                if len(parts)==4 and parts[-1]=='review' and method=='POST':return self.send_json(store.review(parts[2],p))
                if len(parts)==3 and method=='GET':
                    c=store.case(parts[2])
                    if not c:raise KeyError('Case not found.')
                    return self.send_json(c)
            if method=='GET' and path=='/api/export':
                id=parse_qs(parsed.query).get('matter_id',[''])[0]; m=store.matter(id)
                if not m:raise KeyError('Matter not found.')
                return self.send_json({'matter':m,'analysis':analyze(m,store.cases(),taxonomy),'taxonomy_version':taxonomy['version']})
            if method=='GET' and not path.startswith('/api/'):
                web=(ROOT/'web').resolve(); target=(web/('index.html' if path=='/' else path.lstrip('/'))).resolve()
                if not target.is_relative_to(web) or not target.is_file():raise KeyError('File not found.')
                self.send_response(200);self.send_header('Content-Type',STATIC_TYPES.get(target.suffix) or mimetypes.guess_type(str(target))[0] or 'application/octet-stream');self.end_headers();self.wfile.write(target.read_bytes());return
            raise KeyError('Endpoint not found.')
        except (ValueError,TypeError) as exc:self.send_json({'error':str(exc)},400)
        except KeyError as exc:self.send_json({'error':str(exc).strip("'")},404)
        except Exception:self.send_json({'error':'Internal server error. No source data was sent to an external service unless explicitly requested.'},500)

def create_server(port=8765,db_path=None):
    taxonomy=json.loads((ROOT/'data/taxonomy.json').read_text()); cases=json.loads((ROOT/'data/cases.json').read_text())
    state=ROOT/'var';state.mkdir(exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.taxonomy=taxonomy;server.store=Store(db_path or state/'scienter.sqlite3',taxonomy,cases)
    server.source_catalog=SourceCatalog(ROOT/'data/flp_opinions.json',taxonomy)
    return server

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--db',default=None);args=parser.parse_args()
    server=create_server(args.port,args.db);print(f'Dolus: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
