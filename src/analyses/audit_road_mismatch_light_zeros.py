"""Audit source zeros and apply the approved all-zero-peer support rule.

Portable numpy/pandas/pyarrow/matplotlib plus Python stdlib; reads raw ZIP only.
Preserves prior trial and all original values. No new regression or cutoff.
"""
from pathlib import Path
import sys, os, json, hashlib, zipfile, struct, math
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/tr01b-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Patch

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'data/exp/road-economy-mismatch-trial'
OUT=ROOT/'data/exp/road-economy-mismatch-light-zero-audit'
BRIEF=ROOT/'data/exp/data-briefing/road-mismatch-light-zero-audit'
ARCHIVE=ROOT/'data/raw/nighttime_lights/viirs_like_v2/dataset_10.1/2024/2024_Version2.zip'
CACHE=ROOT/'data/exp/data-preprocessing/five-period-2024'
PEERS=['Region','Population Band','Land Context','Facility Presence','Rail Proximity Band']

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')

def read_ifd(f,pointer):
    # Header was independently read at stream start; move forward to BigTIFF IFD.
    f.seek(pointer);count=struct.unpack('<Q',f.read(8))[0];entries=f.read(count*20)
    kinds={1:('B',1),2:('s',1),3:('H',2),4:('I',4),12:('d',8),16:('Q',8)}
    allowed={256,257,258,259,273,277,278,279,322,323,324,325,339,33550,33922,34735,34736,34737,42113}
    wanted=[];tags={}
    for j in range(count):
        e=entries[j*20:(j+1)*20];tag,kind,n=struct.unpack_from('<HHQ',e)
        if tag not in allowed or kind not in kinds:continue
        fmt,size=kinds[kind];payload=e[12:20]
        if n*size>8:wanted.append((struct.unpack('<Q',payload)[0],tag,kind,n))
        else:tags[str(tag)]=payload[:n*size].decode('ascii').rstrip('\0') if kind==2 else list(struct.unpack('<'+fmt*n,payload[:n*size]))
    for offset,tag,kind,n in sorted(wanted):
        fmt,size=kinds[kind];f.seek(offset);p=f.read(n*size)
        tags[str(tag)]=p.decode('ascii').rstrip('\0') if kind==2 else list(struct.unpack('<'+fmt*n,p))
    # Read through EOF: ZipExtFile verifies uncompressed member CRC.
    while f.read(8*1024*1024):pass
    return tags

def revise():
    d=pd.read_parquet(OLD/'mesh_screen_2024.parquet');g=d.groupby(PEERS,observed=True)
    d['Peer Maximum Radiance']=g['Nighttime Radiance'].transform('max')
    d['Peer Minimum Radiance']=g['Nighttime Radiance'].transform('min')
    d['Peer Zero Radiance Fraction']=g['Nighttime Radiance'].transform(lambda x:x.eq(0).mean())
    d['Peer All Zero Radiance']=d['Peer Maximum Radiance'].eq(0)&d['Peer Minimum Radiance'].eq(0)
    d['Original Screen Status']=d['Screen Status']
    d['Original Potential Mismatch Candidate']=d['Potential Mismatch Candidate']
    small=d['Peer Meshes'].lt(30);az=d['Peer All Zero Radiance'];eligible=~small&~az
    d['Screen Support Reason']=np.select([small&az,small,az],['Insufficient peers and all-zero radiance','Insufficient peers','All-zero peer radiance'],default='Supported')
    d.loc[az,'Screen Status']='Information insufficient: all-zero peer radiance'
    d.loc[~eligible,'Potential Mismatch Candidate']=pd.NA
    d['Supported Comparison']=eligible
    c=d['Potential Mismatch Candidate'].fillna(False);d['Candidate Count']=c.astype(int);d['Candidate Road Length']=d['Road Length'].where(c,0)
    assert d.loc[~eligible,'Potential Mismatch Candidate'].isna().all()
    expected=(d['Road Length Density']>d['Peer Road Q75'])&d['Road Length Density'].gt(0)&(d['Nighttime Radiance']<=d['Peer Radiance Q25'])
    assert np.array_equal(d.loc[eligible,'Potential Mismatch Candidate'].to_numpy(dtype=bool),expected.loc[eligible].to_numpy())
    # Check every original column except explicitly authorized screening-derived fields.
    original=pd.read_parquet(OLD/'mesh_screen_2024.parquet')
    changes={'Screen Status','Potential Mismatch Candidate','Supported Comparison','Candidate Count','Candidate Road Length'}
    for col in original.columns.difference(list(changes)):pd.testing.assert_series_equal(d[col],original[col])
    original_candidate=original['Potential Mismatch Candidate'].fillna(False)
    stats={'meshes':len(d),'peer_groups':g.ngroups,'all_zero_peer_meshes':int(az.sum()),
           'all_zero_peer_groups':int(d.loc[az,PEERS].drop_duplicates().shape[0]),
           'all_zero_meshes_with_at_least_30_peers':int((az&~small).sum()),
           'insufficient_peer_meshes':int(small.sum()),'supported_meshes':int(eligible.sum()),
           'original_candidates':int(original_candidate.sum()),'revised_candidates':int(c.sum()),
           'candidates_reclassified':int((original_candidate&~c).sum()),
           'candidate_fraction_supported':float(c.sum()/eligible.sum()),
           'candidate_zero_radiance':int((c&d['Nighttime Radiance'].eq(0)).sum()),
           'candidate_zero_radiance_fraction':float(d.loc[c,'Nighttime Radiance'].eq(0).mean()),
           'candidate_forest_fraction':float(d.loc[c,'Land Context'].eq('Forest').mean()),
           'candidate_road_stock_km':float(d.loc[c,'Road Length'].sum()),
           'supported_meshes_with_radiance_q25_zero':int((eligible&d['Peer Radiance Q25'].eq(0)).sum()),
           'supported_groups_with_radiance_q25_zero':int(d.loc[eligible&d['Peer Radiance Q25'].eq(0),PEERS].drop_duplicates().shape[0]),
           'status_counts':d['Screen Status'].value_counts().to_dict()}
    peer=d.groupby(PEERS,observed=True).agg(**{'Meshes':('Mesh Code','size'),'Maximum Radiance':('Nighttime Radiance','max'),
        'Minimum Radiance':('Nighttime Radiance','min'),'Zero Radiance Fraction':('Nighttime Radiance',lambda x:x.eq(0).mean()),
        'Radiance Q25':('Peer Radiance Q25','first'),'Supported':('Supported Comparison','first'),'Candidates':('Candidate Count','sum')}).reset_index()
    peer.to_csv(OUT/'revised_peer_strata.csv',index=False)
    rows=[]
    for key,z in d.groupby(['Region','Land Context'],observed=True):
        cand=z['Potential Mismatch Candidate'].fillna(False);support=z['Supported Comparison']
        rows.append({'Region':key[0],'Land Context':key[1],'Cohort Meshes':len(z),'Supported Meshes':int(support.sum()),
            'Information Insufficient Meshes':int(z['Peer All Zero Radiance'].sum()),'Candidate Meshes':int(cand.sum()),
            'Candidate Fraction of Supported':float(cand.sum()/support.sum()) if support.any() else np.nan,
            'Zero Radiance Candidates':int((cand&z['Nighttime Radiance'].eq(0)).sum()),
            'Candidate Road Stock km':float(z.loc[cand,'Road Length'].sum())})
    pd.DataFrame(rows).to_csv(OUT/'regional_land_context_summary.csv',index=False)
    d.to_parquet(OUT/'revised_mesh_screen_2024.parquet',index=False)
    return d,stats

def audit_pixels(d):
    tags=json.loads((ROOT/'data/exp/data-organization/nighttime-pilot/2024_tiff_index.json').read_text())['tags']
    tw,th=tags['322'][0],tags['323'][0];across=math.ceil(tags['256'][0]/tw)
    dx,dy=tags['33550'][:2];x0,y0=tags['33922'][3:5];nodata=float(tags['42113'])
    c=d['Original Potential Mismatch Candidate'].fillna(False)
    case=np.select([c&d['Nighttime Radiance'].eq(0),c,d['Nighttime Radiance'].eq(0)],['Candidate zero','Candidate positive','Noncandidate zero'],default='Noncandidate positive')
    sample=d.assign(**{'Audit Case':case})
    # Agent-specified deterministic diagnostic sample, not a probability survey.
    sample['Selection Hash']=sample['Mesh Code'].map(lambda x:hashlib.sha256(('20261011:'+str(x)).encode()).hexdigest())
    sample=sample.sort_values('Selection Hash').groupby(['Region','Land Context','Audit Case'],observed=True).head(2)
    extra=d[d['Peer All Zero Radiance']].sort_values('Mesh Code').groupby('Land Context',observed=True).head(2).copy()
    extra['Audit Case']='All-zero peer group';extra['Selection Hash']='explicit all-zero support audit'
    sample=pd.concat([sample,extra]).drop_duplicates('Mesh Code').sort_values('Mesh Code').copy()
    rawlights=pd.read_parquet(ROOT/'data/processed/national/five_period/lights_2024_preprocessed.parquet').set_index('Mesh Code')
    np.testing.assert_array_equal(sample['Nighttime Radiance'],rawlights.loc[sample['Mesh Code'],'Nighttime Radiance'])
    jobs=[];needed=set();weights={};geometry_checks=0
    geom=json.loads((CACHE/'geometry_validation.json').read_text());expected_weights={i['primary_tile']:i['weight_sha256'] for i in geom['tiles']}
    for code in sample['Mesh Code']:
        code=str(code);tile=code[:4]
        p=CACHE/f'overlap-cache/{tile}.npz'
        if tile not in weights:
            assert sha(p)==expected_weights[tile]
            with np.load(p) as w:weights[tile]={k:w[k].copy() for k in w.files}
        w=weights[tile];mi=(int(code[4])*10+int(code[6]))*80+int(code[5])*10+int(code[7]);hit=w['mesh']==mi
        rr=w['raster_row'][hit];cc=w['raster_column'][hit];area=w['area'][hit]
        assert len(area)>0 and (area>0).all()
        # Independently derive intersecting native pixel coordinates from mesh code.
        south=int(tile[:2])*2/3+(mi//80)/120;west=int(tile[2:])+100+(mi%80)/80
        independent=set()
        for r in range(math.floor((y0-south-1/120)/dy),math.ceil((y0-south)/dy)):
            for col in range(math.floor((west-x0)/dx),math.ceil((west+1/80-x0)/dx)):
                if min(west+1/80,x0+(col+1)*dx)-max(west,x0+col*dx)>1e-10 and min(south+1/120,y0-r*dy)-max(south,y0-(r+1)*dy)>1e-10:independent.add((r,col))
        assert set(zip(rr,cc))==independent,(code,set(zip(rr,cc)),independent)
        geometry_checks+=1
        jobs.append((code,rr,cc,area,float(w['mesh_area'][mi])))
        needed.update((int(r)//th,int(col)//tw) for r,col in zip(rr,cc))
    blocks=sorted((tags['324'][r*across+col],tags['325'][r*across+col],r,col) for r,col in needed)
    archive_before=sha(ARCHIVE);manifest=pd.read_csv(ROOT/'data/exp/data-organization/tables/download_manifest.csv')
    source_record=manifest[manifest['local_path'].eq(str(ARCHIVE.relative_to(ROOT)))].iloc[0]
    assert source_record['sha256']==archive_before and source_record['status']=='downloaded_verified'
    pixels={};print(f'Source audit: {len(sample)} meshes, {len(blocks)} TIFF blocks; forward ZIP streaming',flush=True)
    with zipfile.ZipFile(ARCHIVE) as z:
        name=next(n for n in z.namelist() if n.endswith('.tif'))
        with z.open(name) as f:
            head=f.read(16);assert head[:8]==b'II+\x00\x08\x00\x00\x00';pointer=struct.unpack_from('<Q',head,8)[0]
            for j,(offset,size,r,col) in enumerate(blocks,1):
                f.seek(offset);buf=f.read(size);assert len(buf)==size
                pixels[(r,col)]=np.frombuffer(buf,dtype='<f4').reshape(th,tw)
                if j%50==0:print(f'Source TIFF blocks {j}/{len(blocks)}',flush=True)
            actual=read_ifd(f,pointer);assert actual==tags,'Source TIFF metadata differs from existing layout'
    records=[];rows=[]
    indexed=sample.set_index('Mesh Code')
    for code,rr,cc,area,mesharea in jobs:
        values=np.array([pixels[(int(r)//th,int(col)//tw)][int(r)%th,int(col)%tw] for r,col in zip(rr,cc)],dtype=np.float64)
        valid=np.isfinite(values)&(values!=nodata);assert values[valid].min()>=0
        total=float(area[valid].sum());mean=float(np.dot(area[valid],values[valid])/total) if total>0 else np.nan
        stored=float(indexed.loc[code,'Nighttime Radiance']);coverage=min(total/mesharea,1.)
        assert np.isclose(mean,stored,rtol=1e-10,atol=1e-10),(code,mean,stored)
        assert np.isclose(coverage,rawlights.loc[code,'Nighttime Light Coverage'],rtol=0,atol=1e-10)
        if stored==0:assert valid.all() and (values[valid]==0).all()
        for r,col,a,v,ok in zip(rr,cc,area,values,valid):
            records.append({'Mesh Code':code,'Raster Row':int(r),'Raster Column':int(col),'Intersection Area m2':float(a),
                'Source Radiance':float(v),'Valid Pixel':bool(ok)})
        rows.append({'Mesh Code':code,'Region':indexed.loc[code,'Region'],'Land Context':indexed.loc[code,'Land Context'],
            'Audit Case':indexed.loc[code,'Audit Case'],'Stored Radiance':stored,'Recomputed Radiance':mean,
            'Absolute Difference':abs(mean-stored),'Source Pixels':len(values),'Valid Pixels':int(valid.sum()),
            'Zero Pixels':int((valid&(values==0)).sum()),'Declared NoData Pixels':int((~valid).sum()),'Coverage':coverage})
    result=pd.DataFrame(rows);result.to_csv(OUT/'source_mesh_recomputation.csv',index=False)
    pd.DataFrame(records).to_parquet(OUT/'audited_native_pixel_intersections.parquet',index=False)
    save(OUT/'source_raster_metadata.json',{'member':name,'tags':{k:v for k,v in tags.items() if k not in ['324','325']}})
    assert sha(ARCHIVE)==archive_before
    return {'sample_meshes':len(result),'sample_zero_meshes':int(result['Stored Radiance'].eq(0).sum()),
        'sample_positive_meshes':int(result['Stored Radiance'].gt(0).sum()),'pixel_intersections':len(records),
        'declared_nodata_intersections':int(result['Declared NoData Pixels'].sum()),'max_absolute_radiance_difference':float(result['Absolute Difference'].max()),
        'independent_pixel_mesh_overlap_checks':geometry_checks,'source_metadata_matches_cache':True,'source_member_crc_verified':True,
        'archive_sha256':archive_before,'source_archive_unchanged':True,'original_light_values_unchanged':True,
        'sampling':'Up to two hash-selected meshes per Region x Land Context x candidate/zero state; additional all-zero peer contexts; deterministic diagnostic, not national error-rate inference'},result

def outputs(d,stats,audit,result):
    c=d['Potential Mismatch Candidate'].fillna(False)
    context=d.groupby('Land Context').agg(**{'Cohort Meshes':('Mesh Code','size'),'Supported Meshes':('Supported Comparison','sum'),
        'Candidate Meshes':('Candidate Count','sum'),'All Zero Peer Meshes':('Peer All Zero Radiance','sum')})
    context['Zero Radiance Candidates']=d.loc[c&d['Nighttime Radiance'].eq(0)].groupby('Land Context').size().reindex(context.index,fill_value=0)
    context['Candidate Fraction of Supported']=context['Candidate Meshes']/context['Supported Meshes']
    context['Candidate Zero Radiance Fraction']=context['Zero Radiance Candidates']/context['Candidate Meshes']
    context.to_csv(OUT/'land_context_summary.csv');context.to_csv(BRIEF/'land_context_summary.csv')
    variables=['Nighttime Radiance','Road Length Density','Population'];summary=[]
    for name in variables:
        x=d[name];summary.append({'Variable':name,'Rows':len(x),'Missing':int(x.isna().sum()),'Zero':int(x.eq(0).sum()),
            'Min':float(x.min()),'Median':float(x.median()),'Mean':float(x.mean()),'Max':float(x.max())})
    pd.DataFrame(summary).to_csv(BRIEF/'variable_summary.csv',index=False)
    fig,axs=plt.subplots(1,2,figsize=(12,5),layout='constrained');labels=context.index.tolist();xx=np.arange(len(labels))
    axs[0].bar(xx,context['Candidate Meshes'],color='#d94723');axs[0].set_ylabel('Candidate meshes');axs[0].set_title('Revised candidates by land context')
    axs[1].bar(xx,context['Candidate Zero Radiance Fraction']*100,color='#7ba6bd');axs[1].set_ylim(0,105);axs[1].set_ylabel('Zero-radiance share (%)');axs[1].set_title('Ties at zero remain prevalent')
    for ax in axs:ax.set_xticks(xx,labels,rotation=35,ha='right');ax.grid(axis='y',alpha=.2)
    fig.savefig(BRIEF/'candidate_context_distributions.png',dpi=160);plt.close(fig)
    # Actual mesh rectangles, same national extent as original trial, no interpolation.
    colors={'Potential mismatch candidate':'#d94723','Higher roads; other radiance':'#7ba6bd','Other roads; lower radiance':'#c7d3db',
        'Other supported comparison':'#e5e8e9','Insufficient peers':'#6c7279','Information insufficient: all-zero peer radiance':'#9a64ad'}
    lon=d['Longitude'].to_numpy();lat=d['Latitude'].to_numpy();v=np.empty((len(d),4,2));v[:,:,0]=lon[:,None]+np.array([-1,1,1,-1])/160;v[:,:,1]=lat[:,None]+np.array([-1,-1,1,1])/240
    fig=plt.figure(figsize=(13,11));fig.text(.04,.965,'Road-economy mismatch screen: light-support audit',fontsize=17,weight='bold')
    fig.text(.04,.936,'2024 roads/lights, 2020 population | All meshes and source zeros retained | Potential mismatch, not confirmed excess',fontsize=9)
    groups=[('Main islands',lat>=30,[.05,.15,.66,.75],(128,146.5),(29.95,46),36),
        ('Southwest islands',(lat<30)&(lon<135),[.74,.58,.24,.28],(122.5,132),(23.7,30.1),27),
        ('Ogasawara islands',(lat<30)&(lon>=135),[.75,.20,.16,.32],(140.9,142.65),(24.5,27.4),26)]
    assert np.all(np.stack([g[1] for g in groups]).sum(axis=0)==1)
    for name,mask,pos,xlim,ylim,ref in groups:
        ax=fig.add_axes(pos);ax.set_xlim(*xlim);ax.set_ylim(*ylim);ax.set_aspect(1/np.cos(np.deg2rad(ref)));ax.set_title(name,fontsize=10)
        for status,color in colors.items():
            sel=mask&d['Screen Status'].eq(status).to_numpy()
            ax.add_collection(PolyCollection(v[sel],facecolors=color,edgecolors='none',rasterized=True))
        ax.tick_params(labelsize=8)
    fig.legend(handles=[Patch(color=color,label=f'{s} ({int(d["Screen Status"].eq(s).sum()):,})') for s,color in colors.items()],loc='lower center',ncol=2,fontsize=9)
    fig.savefig(OUT/'revised_mismatch_mesh_map.png',dpi=180);plt.close(fig)
    save(OUT/'screening_contract.json',{'decision':'MILI-D-20261011-001','original_trial':'data/exp/road-economy-mismatch-trial',
        'unchanged_rules':'Original peer strata, 30-mesh support, road > Q75 and >0, light <= Q25',
        'new_rule':'All-zero-radiance peer groups have unavailable candidate status and explicit information insufficiency; simultaneous small-peer failure retained',
        'no_new_rule':'Positive-constant groups and zero-Q25 groups are diagnosed only; no additional cutoff or exclusion',
        'original_values_and_meshes_retained':True,'regressions_refitted':False})
    report={'status':'passed_numerical_audit_substantive_boundary_limited','screen':stats,'source_audit':audit,
        'original_trial_sha256':sha(OLD/'mesh_screen_2024.parquet'),'revised_screen_sha256':sha(OUT/'revised_mesh_screen_2024.parquet'),
        'formal_outputs_changed':False,'raw_inputs_modified':False}
    save(OUT/'validation.json',report);save(BRIEF/'summary.json',report)
    pd.DataFrame([{'Dataset':'Original 2024 screen','Rows':len(d),'Columns':58},{'Dataset':'Revised 2024 screen','Rows':len(d),'Columns':len(d.columns)},
        {'Dataset':'Source mesh recomputation','Rows':len(result),'Columns':len(result.columns)}]).to_csv(BRIEF/'dataset_inventory.csv',index=False)
    note=f'''# Light-zero audit and revised mismatch support\n\nDecision: MILI-D-20261011-001. Exploratory; no regression, final outputs or source values changed.\n\n## Results\n\nAll {len(d):,} meshes are retained. {stats['all_zero_peer_meshes']:,} meshes belong to {stats['all_zero_peer_groups']} all-zero-radiance peer groups; all already had fewer than 30 peers. Their information-support reason is now explicit. Candidate count remains {stats['revised_candidates']:,}, or {stats['candidate_fraction_supported']:.4%} of {stats['supported_meshes']:,} supported meshes. {stats['candidate_zero_radiance_fraction']:.4%} of candidates are zero-radiance and {stats['candidate_forest_fraction']:.4%} forest-context. The approved rule makes no change to candidate geography, road stock or previous prefecture correlations.\n\n{audit['sample_meshes']} deterministic diagnostic meshes ({audit['sample_zero_meshes']} zero, {audit['sample_positive_meshes']} positive) were recomputed from raw 2024 TIFF bytes; {audit['pixel_intersections']} pixel intersections, maximum radiance difference {audit['max_absolute_radiance_difference']:.3g}. Every audited zero mesh contains only valid source-zero pixels; none was created by filling nodata. This sample does not establish a nationwide error rate. The source TIFF declares extreme negative nodata, separate from zero. Its metadata match the cached index and the ZIP member CRC passes. Original archive hash, overlap-weight hashes, pixel/mesh coordinate intersections and processed coverage pass.\n\n## Measurement limits\n\nNumerical source zeros do not prove the absence of economic activity. Upstream product filtering, detection limits and treatment of weak lights have not been independently audited here. The source is the supplied VIIRS-like Version 2 product, not a new raw-satellite measurement. The mesh footprint is the existing full mesh, including water where present. {stats['supported_meshes_with_radiance_q25_zero']:,} supported meshes have a peer light Q25 of zero; inclusive ties remain a major limitation. Urban, agricultural and forest context summaries are reported separately. Forest roads can serve forestry, access or through traffic. No mesh is classified as confirmed road overprovision. No positive-constant group, zero-NTL mesh, forest mesh or island is silently excluded.\n\n## Reproduction and files\n\nRun `python3 src/analyses/audit_road_mismatch_light_zeros.py` from the project root. Required local libraries: numpy, pandas, pyarrow, matplotlib. No extra install or host-only API. Original source ZIP is read only and global TIFF is streamed without disk extraction. Sampling: up to two SHA256-ranked mesh codes in each Region x Land Context x original-candidate/zero-state cell plus up to two all-zero-peer meshes per land context. This diagnostic sample is specified by the agent, not a human-selected final survey design. Exact area weights reuse independently checked original metric intersection caches; pixel-coordinate intersection membership is independently verified from mesh codes.\n\n`source_mesh_recomputation.csv` and `audited_native_pixel_intersections.parquet` preserve source-level checks. `revised_mesh_screen_2024.parquet` preserves original screening labels in explicit Original columns and adds peer light support. `land_context_summary.csv`, `regional_land_context_summary.csv` and `revised_peer_strata.csv` describe coverage and ties. `revised_mismatch_mesh_map.png` uses actual standard mesh rectangles. Briefing inventory, three numerical-variable summaries and one two-panel context distribution figure are saved separately under data/exp/data-briefing/road-mismatch-light-zero-audit. Single 2024 cross-section, no time-series view generated.\n\n## Next evidence need\n\nSource auditing removes an aggregation-error explanation for audited zeros, but does not validate excess roads. Broader traffic comparisons within land contexts, road class and relevant network functions remain future work. Fiscal comparisons remain contextual until utilization and ownership attribution are supported.\n'''
    (OUT/'README.md').write_text(note);(BRIEF/'README.md').write_text(note)
    print(json.dumps({'screen':stats,'source_audit':audit},indent=2),flush=True)

def main():
    OUT.mkdir(parents=True,exist_ok=True);BRIEF.mkdir(parents=True,exist_ok=True)
    oldhash=sha(OLD/'mesh_screen_2024.parquet');d,stats=revise();audit,result=audit_pixels(d)
    assert sha(OLD/'mesh_screen_2024.parquet')==oldhash
    outputs(d,stats,audit,result)

if __name__=='__main__':main()
