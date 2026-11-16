"""Connect official 2021 traffic geometry to a bounded 2024 Fukuoka mesh screen.

Pure local numpy/pandas implementation: clip to geographic tile rectangles,
split at actual mesh boundaries, and weight published volume by mapped length.
No geocoding, interpolation, zero filling, or source-network calibration.
"""
from pathlib import Path
import json
import hashlib
import math
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/road-economy-mismatch-trial'
PEERS=['Region','Population Band','Land Context','Facility Presence','Rail Proximity Band']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def clip(a,b,rect):
    # Liang-Barsky line/rectangle clipping in longitude-latitude coordinates.
    xmin,xmax,ymin,ymax=rect;dx=b[0]-a[0];dy=b[1]-a[1]
    lo,hi=0.,1.
    for p,q in [(-dx,a[0]-xmin),(dx,xmax-a[0]),(-dy,a[1]-ymin),(dy,ymax-a[1])]:
        if p==0:
            if q<0:return None
        elif p<0:lo=max(lo,q/p)
        else:hi=min(hi,q/p)
        if lo>=hi:return None
    delta=np.asarray(b)-a
    return np.asarray(a)+lo*delta,np.asarray(a)+hi*delta

def length(a,b):
    lat1,lon1=np.deg2rad([a[1],a[0]]);lat2,lon2=np.deg2rad([b[1],b[0]])
    h=np.sin((lat2-lat1)/2)**2+np.cos(lat1)*np.cos(lat2)*np.sin((lon2-lon1)/2)**2
    return float(6371.0088*2*np.arcsin(np.sqrt(np.clip(h,0,1))))

def mesh_code(i,j):
    # i=floor(latitude*120), j=floor((longitude-100)*80).
    return f'{i//80:02d}{j//80:02d}{(i%80)//10}{(j%80)//10}{i%10}{j%10}'

def allocate(a,b):
    delta=np.asarray(b)-a;cuts=[0.,1.]
    for axis,scale,offset in [(0,80,100),(1,120,0)]:
        if delta[axis]==0:continue
        u,v=(a[axis]-offset)*scale,(b[axis]-offset)*scale
        for k in range(math.floor(min(u,v))+1,math.ceil(max(u,v))):
            t=(offset+k/scale-a[axis])/delta[axis]
            if 1e-12<t<1-1e-12:cuts.append(t)
    cuts=sorted(set(cuts));rows=[]
    for t0,t1 in zip(cuts[:-1],cuts[1:]):
        p=np.asarray(a)+t0*delta;q=np.asarray(a)+t1*delta;mid=(p+q)/2
        i=math.floor(mid[1]*120);j=math.floor((mid[0]-100)*80)
        code=mesh_code(i,j);km=length(p,q)
        rect=(100+j/80,100+(j+1)/80,i/120,(i+1)/120)
        assert min(p[0],q[0])>=rect[0]-1e-10 and max(p[0],q[0])<=rect[1]+1e-10
        assert min(p[1],q[1])>=rect[2]-1e-10 and max(p[1],q[1])<=rect[3]+1e-10
        rows.append((code,km,rect))
    assert np.isclose(sum(r[1] for r in rows),length(a,b),rtol=2e-7,atol=1e-9)
    return rows

def tile_rect(z,x,y):
    n=2**z
    lon=lambda k:k/n*360-180
    lat=lambda k:math.degrees(math.atan(math.sinh(math.pi*(1-2*k/n))))
    return lon(x),lon(x+1),lat(y+1),lat(y)

def main():
    screen=OUT/'mesh_screen_2024.parquet';before=sha(screen)
    d=pd.read_parquet(screen)
    d=d[d['Prefecture Code'].eq('40')&d['Longitude'].between(130.35,130.70)&d['Latitude'].between(33.35,33.70)].copy()
    ids=set(d['Mesh Code']);assert len(ids)==len(d)==1008
    csv=pd.read_parquet(OUT/'traffic_segment_reference_2021.parquet')
    assert csv['Basic Segment Code'].is_unique
    csv=csv.set_index('Basic Segment Code')
    manifest=pd.read_csv(OUT/'pilot_geometry_download_manifest.csv')
    rows=[];seen=set();unknown=set();checked=set();duplicate_edges=0;reference_checks=0;volume_checks=[]
    for tile in manifest[manifest['status'].eq('downloaded')].to_dict('records'):
        path=ROOT/tile['path'];meta=json.loads(path.with_name(path.stem+'.metadata.json').read_text())
        assert sha(path)==meta['sha256']
        data=json.loads(path.read_text());rect=tile_rect(tile['z'],tile['x'],tile['y'])
        for feature in data['features']:
            props=feature['properties'];code=str(props.get('census',''))
            if code not in csv.index:unknown.add(code);continue
            ref=csv.loc[code]
            assert int(props['color'])//10==int(ref['Road Type']), (code,props['color'],ref['Road Type'])
            if code not in checked:
                pv=props.get('24H_trf');cv=ref['Published 24h Volume']
                # Missing volume in GeoJSON and CSV remains missing, never traffic zero.
                same=pd.notna(cv) and pv is not None and np.isclose(float(pv),cv)
                volume_checks.append({'Basic Segment Code':code,'Map Published 24h Volume':pv,'CSV Published 24h Volume':None if pd.isna(cv) else float(cv),
                                      'Both Available':bool(pd.notna(cv) and pv is not None),'Values Agree':bool(same),
                                      'Absolute Difference':float(abs(float(pv)-cv)) if pd.notna(cv) and pv is not None else None})
                checked.add(code)
            geom=feature['geometry'];assert geom['type'] in ['LineString','MultiLineString']
            lines=[geom['coordinates']] if geom['type']=='LineString' else geom['coordinates']
            for line in lines:
                for a,b in zip(line[:-1],line[1:]):
                    if a==b:continue
                    key=(tile['layer'],tile['x'],tile['y'],code,tuple(sorted([tuple(a),tuple(b)])))
                    if key in seen:duplicate_edges+=1;continue
                    seen.add(key)
                    clipped=clip(a,b,rect)
                    if clipped is None:continue
                    a,b=clipped;mid=(a+b)/2;n=2**tile['z']
                    owner_x=math.floor((mid[0]+180)/360*n)
                    owner_y=math.floor((1-math.asinh(math.tan(math.radians(mid[1])))/math.pi)/2*n)
                    if owner_x!=tile['x'] or owner_y!=tile['y']:continue
                    parts=allocate(a,b)
                    if reference_checks<30 and len(parts)>1 and any(r[0] in ids for r in parts):
                        # Independently clip the source edge to each assigned mesh rectangle.
                        for _,km,mrect in parts:
                            pair=clip(a,b,mrect);assert pair is not None
                            assert np.isclose(km,length(*pair),rtol=1e-7,atol=1e-9)
                        reference_checks+=1
                    for mesh,km,_ in parts:
                        if mesh in ids and km>1e-10:
                            rows.append({'Mesh Code':mesh,'Basic Segment Code':code,'Mapped Length':km,
                                         'Published 24h Volume':ref['Published 24h Volume'],'Road Manager':ref['Road Manager'],
                                         'Road Type':ref['Road Type'],'Volume Status':ref['Volume Status'],
                                         'Road Governing Prefecture Code':ref['Prefecture Code']})
    assert reference_checks==30 and len(rows)>0
    edge=pd.DataFrame(rows)
    allocation=edge.groupby(['Mesh Code','Basic Segment Code','Road Manager','Road Type','Volume Status','Road Governing Prefecture Code'],dropna=False).agg(
        **{'Mapped Length':('Mapped Length','sum'),'Published 24h Volume':('Published 24h Volume','first')}).reset_index()
    allocation.to_parquet(OUT/'pilot_mesh_segment_allocations.parquet',index=False)
    # All-road and prefecture-managed summaries remain separate.
    for name,subset in [('Surveyed',allocation),('Prefecture Managed',allocation[allocation['Road Manager'].eq(2)&allocation['Road Governing Prefecture Code'].eq('40')])]:
        total=subset.groupby('Mesh Code')['Mapped Length'].sum()
        v=subset[subset['Published 24h Volume'].notna()].copy()
        v['Volume Times Length']=v['Mapped Length']*v['Published 24h Volume']
        sums=v.groupby('Mesh Code')[['Mapped Length','Volume Times Length']].sum()
        d[name+' Mapped Length']=d['Mesh Code'].map(total)
        d[name+' Volume Length']=d['Mesh Code'].map(sums['Mapped Length'])
        d[name+' Weighted 24h Volume']=d['Mesh Code'].map(sums['Volume Times Length']/sums['Mapped Length'])
    d.to_parquet(OUT/'pilot_mesh_traffic_comparison.parquet',index=False)
    d['Comparison Group']=np.select([d['Potential Mismatch Candidate'].fillna(False),d['Potential Mismatch Candidate'].isna()],
                                    ['Candidate','Insufficient peers'],default='Supported noncandidate')
    summary=[]
    for label,z in d.groupby('Comparison Group'):
        for scope in ['Surveyed','Prefecture Managed']:
            valid=z[scope+' Weighted 24h Volume'].notna()
            summary.append({'Comparison Group':label,'Traffic Scope':scope,'Meshes':len(z),'Volume Matched Meshes':int(valid.sum()),
                            'Median Mesh Weighted 24h Volume':float(z.loc[valid,scope+' Weighted 24h Volume'].median()) if valid.any() else None,
                            'Mapped Length Weighted 24h Volume':float(np.average(z.loc[valid,scope+' Weighted 24h Volume'],weights=z.loc[valid,scope+' Volume Length'])) if valid.any() else None})
    pd.DataFrame(summary).to_csv(OUT/'pilot_traffic_group_summary.csv',index=False)
    pd.DataFrame(volume_checks).to_csv(OUT/'pilot_map_csv_volume_checks.csv',index=False)
    pairs=[]
    for key,z in d[d['Comparison Group'].ne('Insufficient peers')].groupby(PEERS,observed=True):
        for scope in ['Surveyed','Prefecture Managed']:
            a=z[z['Comparison Group'].eq('Candidate')][scope+' Weighted 24h Volume'].dropna()
            b=z[z['Comparison Group'].eq('Supported noncandidate')][scope+' Weighted 24h Volume'].dropna()
            if len(a)>=3 and len(b)>=3:
                pairs.append(dict(zip(PEERS,key))|{'Traffic Scope':scope,'Mapped Candidates':len(a),'Mapped Noncandidates':len(b),
                              'Candidate Median 24h Volume':float(a.median()),'Noncandidate Median 24h Volume':float(b.median()),
                              'Candidate Minus Noncandidate Median':float(a.median()-b.median())})
    pd.DataFrame(pairs,columns=PEERS+['Traffic Scope','Mapped Candidates','Mapped Noncandidates','Candidate Median 24h Volume',
                                    'Noncandidate Median 24h Volume','Candidate Minus Noncandidate Median']).to_csv(OUT/'pilot_within_peer_traffic_comparison.csv',index=False)
    assert sha(screen)==before
    report={'status':'passed_boundary_limited_pilot','window':{'west':130.35,'east':130.70,'south':33.35,'north':33.70},
            'target_prefecture':'40','meshes':len(d),'candidate_meshes':int(d['Potential Mismatch Candidate'].sum()),
            'tiles_requested':len(manifest),'tiles_downloaded':int(manifest['status'].eq('downloaded').sum()),
            'tiles_HTTP404':int(manifest['status'].eq('HTTP 404').sum()),'mapped_segment_mesh_pairs':len(allocation),
            'unique_csv_linked_segments':len(checked),'unknown_geometry_segment_codes':sorted(unknown),
            'map_csv_volume_differences':sum(x['Both Available'] and not x['Values Agree'] for x in volume_checks),
            'map_csv_max_absolute_volume_difference':max(x['Absolute Difference'] or 0 for x in volume_checks),
            'traffic_value_authority':'Archived official CSV; map geometry is linked by Basic Segment Code, map volumes are audited but never substituted',
            'manager_scope':'Prefecture Managed pilot summaries require manager code 2 and governing prefecture code 40; neighboring-governor roads are not attributed to Fukuoka',
            'duplicate_exact_edges_removed':duplicate_edges,'independent_rectangle_clip_checks':reference_checks,
            'screen_unchanged':True,'source_grid_year':2024,'traffic_year':2021,
            'geometry_role':'Published zoom-12 map representation, not a complete road inventory or authoritative legal road length',
            'missing_rule':'No mapped valid traffic remains NaN; absence of a tile or mapped line does not establish zero demand',
            'group_comparisons':summary,'within_peer_comparisons':pairs,
            'interpretation':'Bounded cross-year published-road utilization check; no causal, overprovision or national generalization claim'}
    (OUT/'pilot_traffic_validation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:report[k] for k in ['meshes','candidate_meshes','tiles_requested','tiles_downloaded','tiles_HTTP404','group_comparisons','within_peer_comparisons']},indent=2))

if __name__=='__main__':main()
