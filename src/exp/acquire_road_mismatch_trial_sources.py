"""Preserve official source snapshots for the exploratory road-mismatch trial.

No writes to data/raw or existing processed inputs. Reruns reuse checksum-verified
downloads. Custom URLs must be on an official MLIT or e-Stat host.
"""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
import argparse
import hashlib
import json
import csv
import time
import re
import math
from concurrent.futures import ThreadPoolExecutor
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/road-economy-mismatch-trial'
SOURCES = OUT / 'source_snapshots'
INDEX = {
    'traffic_index': 'https://www.mlit.go.jp/road/census/r3/',
    'fiscal_prefecture_index': 'https://www.e-stat.go.jp/stat-search/files?cycle=7&layout=dataset&result_back=1&tclass1=000001078091&tclass2=000001078092&toukei=00200251&tstat=000001077755&year=20240',
}

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.active = None
    def handle_starttag(self, tag, attrs):
        if tag == 'a': self.active = [dict(attrs).get('href', ''), '']
    def handle_data(self, text):
        if self.active is not None: self.active[1] += text
    def handle_endtag(self, tag):
        if tag == 'a' and self.active is not None:
            self.links.append(self.active); self.active = None

def sha(content):
    return hashlib.sha256(content).hexdigest()

def fetch(name, url, suffix):
    host = urlparse(url).hostname or ''
    if not (host.endswith('.mlit.go.jp') or host == 'www.e-stat.go.jp'):
        raise ValueError('Only official MLIT/e-Stat URLs are allowed')
    if Path(name).name != name: raise ValueError('Invalid snapshot name')
    SOURCES.mkdir(parents=True, exist_ok=True)
    path = SOURCES / (name + suffix)
    meta = SOURCES / (name + '.metadata.json')
    if path.exists():
        m = json.loads(meta.read_text())
        assert m['url'] == url and m['sha256'] == sha(path.read_bytes())
        return path
    r = requests.get(url, timeout=(15, 90)); r.raise_for_status()
    body = r.content
    if suffix != '.html' and 'text/html' in r.headers.get('Content-Type', ''):
        raise ValueError('Download returned HTML rather than a data file')
    path.write_bytes(body)
    meta.write_text(json.dumps({'url': url, 'retrieved_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                               'bytes': len(body), 'sha256': sha(body), 'content_type': r.headers.get('Content-Type')}, indent=2)+'\n')
    return path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--name'); parser.add_argument('--url'); parser.add_argument('--suffix', default='.csv')
    parser.add_argument('--traffic-all', action='store_true')
    parser.add_argument('--geometry-pilot', action='store_true')
    args = parser.parse_args()
    if args.geometry_pilot:
        # A bounded Fukuoka-area feasibility window, not a nationwide geometry crawl.
        west,east,south,north=130.35,130.70,33.35,33.70
        z=12;n=2**z
        tx=lambda lon:int((lon+180)/360*n)
        ty=lambda lat:int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)
        layers=['drm10','drm20','drm31','drm32','drm40_50','drm60_70']
        script=(SOURCES/'traffic_webmap.html').read_text()
        assert all("./"+layer+"/{z}/{x}/{y}.geojson" in script for layer in layers)
        jobs=[(layer,x,y) for layer in layers for x in range(tx(west),tx(east)+1) for y in range(ty(north),ty(south)+1)]
        def get_tile(job):
            layer,x,y=job
            name=f'traffic_{layer}_z{z}_{x}_{y}'
            url=f'https://www.mlit.go.jp/road/ir/ir-data/census_visualizationR3/{layer}/{z}/{x}/{y}.geojson'
            row={'layer':layer,'z':z,'x':x,'y':y,'url':url}
            try:
                p=fetch(name,url,'.geojson')
                d=json.loads(p.read_text()); assert d['type']=='FeatureCollection'
                row.update(status='downloaded',features=len(d['features']),path=str(p.relative_to(ROOT)))
            except requests.HTTPError as e:
                if e.response.status_code!=404:raise
                row.update(status='HTTP 404',features='',path='')
            return row
        with ThreadPoolExecutor(max_workers=4) as pool: rows=list(pool.map(get_tile,jobs))
        with (OUT/'pilot_geometry_download_manifest.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['layer','z','x','y','url','status','features','path']);w.writeheader();w.writerows(rows)
        print(json.dumps({'requests':len(rows),'downloaded':sum(r['status']=='downloaded' for r in rows),'missing_tiles':sum(r['status']=='HTTP 404' for r in rows)},indent=2));return
    if args.traffic_all:
        with (OUT / 'traffic_index_links.csv').open() as f:
            links = list(csv.DictReader(f))
        selected = {m.group(1): r['url'] for r in links if (m := re.search(r'/csv/kasyo(\d{2})\.csv$', r['url']))}
        assert set(selected) == {f'{i:02d}' for i in range(1,48)}
        def get(item):
            code, url = item
            name = 'traffic_2021_fukuoka' if code == '40' else 'traffic_2021_prefecture_'+code
            return str(fetch(name,url,'.csv').relative_to(ROOT))
        with ThreadPoolExecutor(max_workers=4) as pool:
            files = list(pool.map(get, sorted(selected.items())))
        print(json.dumps({'traffic_files':len(files)},indent=2)); return
    if args.url:
        print(fetch(args.name, args.url, args.suffix).relative_to(ROOT)); return
    for name, url in INDEX.items():
        path = fetch(name, url, '.html')
        links = Links(); links.feed(path.read_text(encoding='utf-8'))
        rows = [{'label': t.strip(), 'url': urljoin(url, h)} for h, t in links.links if h]
        with (OUT / (name+'_links.csv')).open('w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['label','url']); w.writeheader(); w.writerows(rows)
        selected = [x for x in rows if (name == 'traffic_index' and any(s in x['url'] for s in ['csv','xlsx','xls']))
                    or (name.startswith('fiscal') and ('file-download' in x['url'] or any(s in x['label'] for s in ['維持補修','道路関係','財政状況','歳入歳出'])))]
        print(name, json.dumps({'selected_links':len(selected),'first_links':selected[:3]}, ensure_ascii=False))

if __name__ == '__main__': main()
