"""Acquire approved single-edition facility archives and candidate airport context.

Read only official catalogue links. Preserve raw archives; no variable/model changes.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin, urlparse
import argparse
import hashlib
import json
import re
import struct
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-augmentation-screening/mlit-facilities'
SOURCES = {
    'schools': ('P29', 2023, 'KsjTmplt-P29-2023.html', '2023 edition'),
    'medical': ('P04', 2020, 'KsjTmplt-P04-2020.html', '2020 creation edition'),
    'logistics': ('P31', 2013, 'KsjTmplt-P31.html', '2013-07'),
    'visitor_facilities': ('P33', 2014, 'KsjTmplt-P33.html', '2014-11-30'),
    'airports': ('C28', 2021, 'KsjTmplt-C28-2021.html', '2021-12-31'),
    'highway_bus_stops': ('P36', 2023, 'KsjTmplt-P36-2023.html', 'approximately 2023-11; source dates vary'),
    'bus_stops': ('P11', 2022, 'KsjTmplt-P11-2022.html', 'approximately 2022-08; source dates vary'),
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''): h.update(block)
    return h.hexdigest()


def inspect(path):
    tables, metadata = [], []
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        members = archive.namelist()
        assert members and any(n.lower().endswith(('.shp','.gml','.xml','.geojson')) for n in members)
        for name in members:
            if name.lower().endswith('.dbf'):
                with archive.open(name) as stream:
                    header = stream.read(32); count = struct.unpack('<I', header[4:8])[0]
                    header_length = struct.unpack('<H',header[8:10])[0]; fields = []
                    for _ in range((header_length-33)//32):
                        descriptor=stream.read(32)
                        fields.append(descriptor[:11].split(b'\0')[0].decode('ascii'))
                tables.append(dict(member=name,records=count,fields=fields))
            if 'meta' in name.lower() and name.lower().endswith(('.xml','.html','.htm')):
                payload=archive.read(name)
                for encoding in ['utf-8-sig','cp932']:
                    try: content=payload.decode(encoding); break
                    except UnicodeDecodeError: content=None
                if content is not None:
                    dates=sorted(set(re.findall(r'20\d{2}[-/]\d{2}[-/]\d{2}',content)))
                    metadata.append(dict(member=name,dates_seen=dates))
    return members,tables,metadata


def prepare(kind):
    code, year, page_name, reference = SOURCES[kind]
    page='https://nlftp.mlit.go.jp/ksj/gml/datalist/'+page_name
    html=urlopen(page,timeout=45).read().decode('utf-8-sig')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/(kind+'_source_page.html')).write_text(html)
    pattern=re.compile(r'^'+re.escape(code)+r'-'+str(year)[2:]+r'(?:_\d{2})?(?:_GML)?\.zip$')
    links={}
    for size,name,href in re.findall(r"DownLd\('([^']*)','([^']*)','([^']*)'",html):
        if pattern.fullmatch(name):
            if code in ['P29','P04','P31','P33','P36','P11']:
                match=re.search(r'_(\d{2})(?:_GML)?\.zip$',name)
                # Prefer the disjoint prefectural archives over national/regional copies.
                if match is None or not 1 <= int(match.group(1)) <= 47: continue
            url=urljoin(page,href); assert urlparse(url).hostname=='nlftp.mlit.go.jp'
            assert name not in links or links[name]==url
            links[name]=url
    assert links, f'No selected {kind} links in official catalogue'
    if code in ['P29','P04','P31','P33','P36','P11']:
        prefectures=[re.search(r'_(\d{2})(?:_GML)?\.zip$',name).group(1) for name in links]
        assert len(prefectures)==len(set(prefectures))
        assert set(prefectures)=={f'{i:02d}' for i in range(1,48)}, (kind,prefectures)
    else:
        assert len(links)==1
    return [dict(kind=kind,code=code,year=year,reference=reference,page=page,name=name,url=url) for name,url in sorted(links.items())]


def download(job):
    folder=ROOT/'data/raw'/('airports' if job['kind']=='airports' else 'poi')/job['code'].lower()/str(job['year'])
    path=folder/job['name']; reused=path.exists()
    if not reused:
        with tempfile.TemporaryDirectory(prefix='tr01b-mlit-') as scratch:
            temporary=Path(scratch)/job['name']
            for attempt in range(3):
                try:
                    with urlopen(job['url'],timeout=60) as response, temporary.open('wb') as target:
                        length=response.headers.get('Content-Length')
                        while block:=response.read(2**20): target.write(block)
                    assert length is None or temporary.stat().st_size==int(length)
                    inspect(temporary)
                    break
                except Exception:
                    if attempt==2: raise
                    time.sleep(attempt+1)
            folder.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as target,temporary.open('rb') as source:
                while block:=source.read(2**20): target.write(block)
    members,tables,metadata=inspect(path)
    return dict(**job,path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,sha256=digest(path),
                reused_existing_archive=reused,zip_crc_passed=True,members=members,attribute_tables=tables,metadata_date_inventory=metadata)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--categories',nargs='+',choices=list(SOURCES),default=['schools','medical','logistics','visitor_facilities','airports'])
    parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--decision-id',default='MILI-D-20261010-013')
    args=parser.parse_args();jobs=[]
    for kind in args.categories: jobs+=prepare(kind)
    records=[];errors=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        tasks={pool.submit(download,j):j for j in jobs}
        for task in as_completed(tasks):
            try: records.append(task.result())
            except Exception as error: errors.append(dict(job=tasks[task],error=str(error)))
            if (len(records)+len(errors))%10==0 or len(records)+len(errors)==len(jobs):
                print(f'Archives checked: {len(records)}/{len(jobs)}; errors {len(errors)}',flush=True)
    records.sort(key=lambda r:(r['kind'],r['name']))
    report=dict(status='passed' if not errors else 'incomplete',decision_id=args.decision_id,
                selected_categories=args.categories,expected_archives=len(jobs),validated_archives=len(records),
                total_bytes=sum(r['bytes'] for r in records),errors=errors,records=records,
                no_existing_raw_file_overwritten=True,scientific_variable_construction='pending',regression_changed=False)
    suffix='_'+'_'.join(args.categories) if args.categories!=['schools','medical','logistics','visitor_facilities','airports'] else ''
    path=OUT/('facility_download_manifest'+suffix+'.json');path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='records'},indent=2),flush=True)
    assert not errors


if __name__=='__main__':main()
