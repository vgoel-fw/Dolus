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
ROOT=Path(__file__).resolve().parent.parent
MAX_BODY=8*1024*1024

def allowed_host(host,port):return host in {f'127.0.0.1:{port}',f'localhost:{port}',f'[::1]:{port}'}
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
                length=int(self.headers.get('Content-Length','0'))
                if length<=0 or length>MAX_BODY:return self.send_json({'error':'Request body must be 1 byte to 8 MiB.'},413)
                p=json.loads(self.rfile.read(length))
                if not isinstance(p,dict):raise ValueError('JSON request must be an object.')
            if path=='/api/health' and method=='GET':return self.send_json({'status':'ok','storage':'sqlite','network_default':'off'})
            if method=='GET' and path=='/api/graph':return self.send_json(store.graph())
            if method=='GET' and path=='/api/bootstrap':
                cases=store.cases()
                return self.send_json({'taxonomy':taxonomy,'cases':cases,'examples':self.server.examples,'matters':store.matters(),'config':{'llm_enabled':bool(os.getenv('ANTHROPIC_API_KEY')),'corpus_mode':'separate_demo_and_real'},'corpus':{'real':sum(not c['synthetic'] for c in cases),'synthetic':sum(c['synthetic'] for c in cases),'reviewed':sum(c['review_status']=='reviewed' for c in cases)}})
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
                self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(target))[0] or 'application/octet-stream');self.end_headers();self.wfile.write(target.read_bytes());return
            raise KeyError('Endpoint not found.')
        except (ValueError,TypeError) as exc:self.send_json({'error':str(exc)},400)
        except KeyError as exc:self.send_json({'error':str(exc).strip("'")},404)
        except Exception:self.send_json({'error':'Internal server error. No source data was sent to an external service unless explicitly requested.'},500)

def create_server(port=8765,db_path=None):
    taxonomy=json.loads((ROOT/'data/taxonomy.json').read_text()); cases=json.loads((ROOT/'data/cases.json').read_text())
    examples_path=ROOT/'data/examples.json'; examples=json.loads(examples_path.read_text()) if examples_path.exists() else []
    state=ROOT/'var';state.mkdir(exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.taxonomy=taxonomy;server.examples=examples;server.store=Store(db_path or state/'scienter.sqlite3',taxonomy,cases)
    return server

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--db',default=None);args=parser.parse_args()
    server=create_server(args.port,args.db);print(f'Dolus: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
