#!/usr/bin/env python3
"""Conservative public-page change monitor; Python standard library only."""
import argparse, datetime, hashlib, html, json, pathlib, re, urllib.parse, urllib.request, urllib.robotparser
from html.parser import HTMLParser

class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','noscript','svg'): self.skip+=1
    def handle_endtag(self, tag):
        if tag in ('script','style','noscript','svg') and self.skip: self.skip-=1
    def handle_data(self, data):
        if not self.skip: self.parts.append(data)

def fetch(url):
    ua='PREVA-Revenue-Radar/1.0 (public monitoring; contact site owner)'
    parsed=urllib.parse.urlparse(url)
    robots=urllib.parse.urlunparse((parsed.scheme,parsed.netloc,'/robots.txt','','',''))
    rp=urllib.robotparser.RobotFileParser()
    try:
        req=urllib.request.Request(robots,headers={'User-Agent':ua})
        with urllib.request.urlopen(req,timeout=10) as res: rules=res.read(300000).decode('utf-8','replace')
        rp.parse(rules.splitlines())
        if not rp.can_fetch(ua,url): return {'status':'blocked_by_robots'}
    except Exception:
        return {'status':'robots_unavailable','detail':'Robots policy could not be verified; skipped automatically'}
    try:
        req=urllib.request.Request(url,headers={'User-Agent':ua,'Accept':'text/html'})
        with urllib.request.urlopen(req,timeout=15) as res:
            if 'text/html' not in res.headers.get('Content-Type',''): return {'status':'not_html'}
            body=res.read(1500000).decode('utf-8','replace')
        parser=VisibleText(); parser.feed(body)
        txt=re.sub(r'\s+',' ',' '.join(parser.parts)).strip()[:100000]
        if len(txt)<120: return {'status':'insufficient_visible_content'}
        return {'status':'ok','hash':hashlib.sha256(txt.encode()).hexdigest(),'length':len(txt),'excerpt':txt[:320],'signals':sorted(set(re.findall(r'\$\s?\d+(?:\.\d{2})?',txt)))[:30]}
    except Exception as exc:
        return {'status':'fetch_failed','detail':str(exc)[:160]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',default='config.json'); ap.add_argument('--output',default='dashboard'); args=ap.parse_args()
    config=json.loads(pathlib.Path(args.config).read_text()); out=pathlib.Path(args.output); out.mkdir(parents=True,exist_ok=True)
    prev_path=out/'latest.json'; prev=json.loads(prev_path.read_text()) if prev_path.exists() else {'sources':[]}
    old={s['name']:s for s in prev['sources']}; rows=[]
    for source in config['sources']:
        observation=fetch(source['url']); prior=old.get(source['name'],{})
        change='first_observation' if not prior else ('unavailable' if observation['status']!='ok' else ('changed' if prior.get('hash') and prior['hash']!=observation['hash'] else 'unchanged' if prior.get('hash') else 'newly_accessible'))
        rows.append({**source,**observation,'change':change})
    now=datetime.datetime.now(datetime.timezone.utc).isoformat(); report={'brand':config['brand'],'timestamp_utc':now,'sources':rows,'note':'Public page text change detection only; not sales or conversion measurement.'}
    (out/'history.jsonl').open('a').write(json.dumps(report)+'\n'); prev_path.write_text(json.dumps(report,indent=2))
    cards=''.join('<article><h2>'+html.escape(r['name'])+'</h2><p><b>'+html.escape(r['status'])+'</b> · '+html.escape(r['change'])+'</p><p>'+html.escape(r.get('excerpt',r.get('detail','No verified visible text'))[:260])+'</p><a href="'+html.escape(r['url'],quote=True)+'">Source</a></article>' for r in rows)
    page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PREVA Revenue Radar</title><style>body{font:16px system-ui;background:#101b20;color:#f3f5f4;margin:0;padding:36px;max-width:1100px}h1{color:#e8b968}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}article{background:#203038;border:1px solid #42535b;border-radius:14px;padding:20px}a{color:#f0c77c}small{color:#b9c4c7}</style><h1>PREVA Revenue Radar</h1><p>Public website change monitor</p><small>Snapshot: '''+html.escape(now)+''' · No sales data connected. Competitors require verified URLs.</small><main>'''+cards+'''</main><p>Prioritize changes by manual review. A page-text change does not prove a price or promotion change.</p></html>'''
    (out/'index.html').write_text(page)
    print(json.dumps({'timestamp':now,'results':[(r['name'],r['status'],r['change']) for r in rows]},indent=2))
if __name__=='__main__': main()
