"""Allocate selected 2024 ordinary-road centreline lengths to target meshes.

Geometry-only worker: writes NumPy/JSON, isolating GDAL from Parquet writers.
Run with --tile 5030 for pilot validation, or without it for national preparation.
"""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import json
import math
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
from osgeo import osr

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/five-period-2024/road-cache'
DX, DY = 1/80, 1/120


def ref(code):
    r = osr.SpatialReference(); r.ImportFromEPSG(code)
    r.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return r


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(2**20), b''): h.update(b)
    return h.hexdigest()


def process(tile, expected_sha):
    osr.UseExceptions(); osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
    path = ROOT / f'data/raw/roads/n13_lines/2024/N13-24_{tile}_GEOJSON.zip'
    assert sha(path) == expected_sha
    geo = ref(4612); native = ref(6668)
    south, west = int(tile[:2])*2/3, int(tile[2:])+100
    datum = osr.CoordinateTransformation(native, geo)
    probes = np.array([[west, south], [west+1, south+2/3]])
    assert np.allclose(np.array(datum.TransformPoints(probes.tolist()))[:, :2], probes, atol=1e-12, rtol=0)
    metric = ref(2444) if tile == '5030' else ref(4612)
    if tile != '5030':
        metric.SetProjCS('Local mesh-centred transverse Mercator')
        metric.SetTM(south+1/3, west+.5, 1, 0, 0)
    measure = osr.CoordinateTransformation(geo, metric)
    gx, gy = np.meshgrid(west+np.arange(81)*DX, south+np.arange(81)*DY)
    projected = np.array(measure.TransformPoints(np.column_stack([gx.ravel(), gy.ravel()]).tolist()))[:, :2].reshape(81,81,2)
    origin=projected[:-1,:-1]; a=projected[:-1,1:]-origin; b=projected[1:,1:]-origin; c=projected[1:,:-1]-origin
    area=abs((a[:,:,0]*b[:,:,1]-a[:,:,1]*b[:,:,0]+b[:,:,0]*c[:,:,1]-b[:,:,1]*c[:,:,0])/2).ravel()/1e6
    lengths = np.zeros(6400); unknown = np.zeros(6400)
    counts=Counter(); seen=set(); segments=[]; flags=[]; total=0.; outside=0.

    def flush():
        nonlocal total, outside
        if not segments: return
        pairs=np.asarray(segments); n=len(pairs)
        # Bulk-transform endpoints into the common datum. Identity was checked
        # above, but the actual transformation is applied to every coordinate.
        pairs=np.array(datum.TransformPoints(pairs.reshape(-1,2).tolist()))[:,:2].reshape(n,2,2)
        a,b=pairs[:,0],pairs[:,1]; delta=b-a
        mids=(a+b)/2
        cr=np.floor((mids-np.array([west,south]))/np.array([DX,DY])+1e-10).astype(int)
        cr[:,0]=np.where((cr[:,0]==80)&(abs(mids[:,0]-(west+1))<1e-10),79,cr[:,0])
        cr[:,1]=np.where((cr[:,1]==80)&(abs(mids[:,1]-(south+2/3))<1e-10),79,cr[:,1])
        lo=np.floor((np.minimum(a,b)-[west,south])/[DX,DY]+1e-10).astype(int)
        hi=np.floor((np.maximum(a,b)-[west,south])/[DX,DY]+1e-10).astype(int)
        crossing=(lo!=hi).any(1)
        endpoints=np.array(measure.TransformPoints(pairs.reshape(-1,2).tolist()))[:,:2].reshape(n,2,2)
        full=np.linalg.norm(endpoints[:,1]-endpoints[:,0],axis=1)
        total+=float(full.sum())
        simple=~crossing
        inside=(cr[:,0]>=0)&(cr[:,0]<80)&(cr[:,1]>=0)&(cr[:,1]<80)
        keep=simple&inside
        owners=cr[keep,1]*80+cr[keep,0]
        lengths[:]+=np.bincount(owners,weights=full[keep],minlength=6400)
        unknown[:]+=np.bincount(owners,weights=full[keep]*np.asarray(flags)[keep],minlength=6400)
        outside+=float(full[simple&~inside].sum())
        # Split only segments crossing a mesh line; all pieces have one owner.
        pieces=[]; owners=[]; widths=[]
        for i in np.flatnonzero(crossing):
            ts=[0.,1.]
            for axis,step,start in [(0,DX,west),(1,DY,south)]:
                if delta[i,axis]==0: continue
                low=max(0,math.ceil((min(a[i,axis],b[i,axis])-start)/step))
                high=min(80,math.floor((max(a[i,axis],b[i,axis])-start)/step))
                for k in range(low,high+1):
                    t=(start+k*step-a[i,axis])/delta[i,axis]
                    if 1e-12<t<1-1e-12: ts.append(t)
            ts=sorted(set(ts))
            for t0,t1 in zip(ts,ts[1:]):
                midpoint=a[i]+delta[i]*(t0+t1)/2
                col,row=np.floor((midpoint-[west,south])/[DX,DY]+1e-10).astype(int)
                if col==80 and abs(midpoint[0]-(west+1))<1e-10: col=79
                if row==80 and abs(midpoint[1]-(south+2/3))<1e-10: row=79
                owners.append(row*80+col if 0<=row<80 and 0<=col<80 else -1)
                pieces.extend([a[i]+delta[i]*t0,a[i]+delta[i]*t1]); widths.append(flags[i])
        if pieces:
            q=np.array(measure.TransformPoints(np.asarray(pieces).tolist()))[:,:2].reshape(-1,2,2)
            distance=np.linalg.norm(q[:,1]-q[:,0],axis=1)
            owner=np.asarray(owners); valid=owner>=0
            lengths[:]+=np.bincount(owner[valid],weights=distance[valid],minlength=6400)
            unknown[:]+=np.bincount(owner[valid],weights=distance[valid]*np.asarray(widths)[valid],minlength=6400)
            outside+=float(distance[~valid].sum())
        counts['segments']+=n
        segments.clear(); flags.clear()

    with zipfile.ZipFile(path) as z:
        names=[n for n in z.namelist() if n.endswith('.geojson')]; assert len(names)==1
        with z.open(names[0]) as stream:
            header=[]
            for line in stream:
                s=line.decode('utf8').strip()
                if not s.startswith('{ "type": "Feature",'): header.append(s); continue
                feature=json.loads(s.rstrip(',')); counts['source_features']+=1
                p=feature['properties']
                if str(p['N13_002'])!='1': counts['excluded_nonordinary_type']+=1; continue
                if str(p['N13_004']) not in ('1','2','3','4'): counts['excluded_state']+=1; continue
                geometry=feature['geometry']
                if not geometry or not geometry['coordinates']: counts['empty_geometry']+=1; continue
                counts['included_features']+=1
                key=(hashlib.blake2b(json.dumps(geometry['coordinates'],separators=(',',':')).encode(),digest_size=16).digest(),p['N13_005'])
                if key in seen: counts['identical_geometry_same_level']+=1
                seen.add(key)
                kind=geometry['type']; assert kind in ('LineString','MultiLineString')
                lines=[geometry['coordinates']] if kind=='LineString' else geometry['coordinates']
                for points in lines:
                    xy=np.asarray(points)[:,:2]
                    segments.extend(zip(xy[:-1],xy[1:])); flags.extend([str(p['N13_006'])=='6']*(len(xy)-1))
                if len(segments)>=20000: flush()
            assert any('EPSG::6668' in h for h in header)
    flush(); assert counts['source_features']>0
    residual=float(lengths.sum()+outside-total)
    assert abs(residual)<=max(.02,total*1e-7), (tile,residual,total)
    assert (lengths>=0).all() and (area>0).all()
    OUT.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(OUT/f'{tile}.npz',length_km=lengths/1000,area_km2=area,unknown_width_km=unknown/1000)
    report={'tile':tile,'source_sha256':expected_sha,'counters':dict(counts),
            'source_projected_length_km':total/1000,'outside_target_tile_km':outside/1000,
            'allocated_length_km':float(lengths.sum()/1000),'conservation_residual_m':residual,
            'duplicates_removed':False,'source_comparability_established':False}
    (OUT/f'{tile}.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--tile'); parser.add_argument('--workers',type=int,default=3); args=parser.parse_args()
    osr.UseExceptions(); osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
    manifest=ROOT/'data/exp/data-organization/tables/download_manifest.csv'
    import csv
    with manifest.open() as f: entries={r['local_path']:r for r in csv.DictReader(f)}
    tiles=json.loads((ROOT/'data/exp/data-preprocessing/national/decisions.json').read_text())['national_primary_tiles']
    if args.tile: tiles=[args.tile]
    start=time.monotonic()
    pending=[]; completed=0
    for tile in tiles:
        path=ROOT/f'data/raw/roads/n13_lines/2024/N13-24_{tile}_GEOJSON.zip'
        if not path.exists(): print(f'2024 roads {tile}: source archive absent; retain missing',flush=True); continue
        entry=entries[str(path.relative_to(ROOT))]; assert entry['status']=='downloaded_verified'
        cached=OUT/f'{tile}.json'
        if cached.exists():
            old=json.loads(cached.read_text()); assert sha(path)==old['source_sha256']==entry['sha256']
            assert (OUT/f'{tile}.npz').exists()
            completed+=1
        else: pending.append((tile,entry['sha256']))
    if args.workers==1:
        for tile,digest in pending:
            process(tile,digest); completed+=1
            print(f'2024 roads {completed}/{len(tiles)} {tile}; {time.monotonic()-start:.1f}s',flush=True)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            tasks={pool.submit(process,tile,digest):tile for tile,digest in pending}
            for future in as_completed(tasks):
                future.result(); completed+=1
                print(f'2024 roads {completed}/{len(tiles)} {tasks[future]}; {time.monotonic()-start:.1f}s',flush=True)


if __name__=='__main__': main()
