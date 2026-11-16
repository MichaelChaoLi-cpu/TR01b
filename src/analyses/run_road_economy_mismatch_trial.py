"""Exploratory comparable-context screen and coverage-qualified evidence trial.

Run after src/exp/acquire_road_mismatch_trial_sources.py --traffic-all and the
documented fiscal downloads. Uses local numpy/pandas/matplotlib/pyarrow/openpyxl.
Original inputs, regression estimates and data/raw are never modified.
"""
from pathlib import Path
import sys
import os
import hashlib
import json
import warnings
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/tr01b-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
from matplotlib.patches import Patch
from gwpr_twoways import mesh_centroids

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/road-economy-mismatch-trial'
SOURCE = OUT / 'source_snapshots'
PANEL = ROOT / 'data/processed/national/land_cover_poi_extension/focused_extension_panel_preprocessed.parquet'
ROADS = ROOT / 'data/processed/national/road_density_zero/roads_2024_preprocessed.parquet'
LC = ['Urban', 'Forest', 'Cropland', 'Cropland Mosaic', 'Water', 'Other']
FACILITIES = ['School Facility Count','Medical Facility Count','Logistics Facility Count','Visitor and Event Facility Count']
PEERS = ['Region','Population Band','Land Context','Facility Presence','Rail Proximity Band']

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''): h.update(block)
    return h.hexdigest()

def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def screen():
    d=pd.read_parquet(PANEL,filters=[('Road Year','==',2024)])
    assert len(d)==383386 and d['Mesh Code'].is_unique
    assert (d['Population Year']==2020).all() and (d['Nighttime Light Year']==2024).all()
    r=pd.read_parquet(ROADS)
    d=d.merge(r[['Mesh Code','Road Length','Mesh Area','Road Density Originally Missing','Road Density Source Status']],on='Mesh Code',how='left',validate='one_to_one')
    assert d[['Road Length','Mesh Area']].notna().all().all() and (d['Mesh Area']>0).all()
    assert np.allclose(d['Road Length Density'],d['Road Length']/d['Mesh Area'],rtol=1e-10,atol=1e-10)
    d['Population Band']=pd.cut(d['Population'],[-1,0,9,49,199,999,4999,np.inf],labels=['0','1-9','10-49','50-199','200-999','1000-4999','5000+']).astype(str)
    shares=d[[n+' Land Cover Share' for n in LC]].to_numpy()
    dominant=shares.argmax(axis=1)
    tied=np.sum(np.isclose(shares,shares.max(axis=1)[:,None],rtol=0,atol=1e-12),axis=1)>1
    d['Land Context']=np.asarray(LC,dtype=object)[dominant]
    d.loc[tied,'Land Context']='Tied dominant classes'
    d.loc[d['Land Cover Incomplete Coverage'].astype(bool),'Land Context']='Incomplete coverage'
    d['Facility Presence']=np.where(d[FACILITIES].sum(axis=1)>0,'At least one selected facility','No selected facility')
    d['Rail Proximity Band']=pd.cut(d['Distance to Railway Station'],[-np.inf,1,5,np.inf],right=False,labels=['<1 km','1-5 km','>=5 km']).astype(str)
    g=d.groupby(PEERS,observed=True,sort=True)
    d['Peer Meshes']=g['Mesh Code'].transform('size')
    d['Peer Road Q75']=g['Road Length Density'].transform(lambda x:x.quantile(.75))
    d['Peer Radiance Q25']=g['Nighttime Radiance'].transform(lambda x:x.quantile(.25))
    d['Peer Road Percentile']=g['Road Length Density'].rank(method='average',pct=True)
    d['Peer Radiance Percentile']=g['Nighttime Radiance'].rank(method='average',pct=True)
    eligible=d['Peer Meshes']>=30
    high=(d['Road Length Density']>d['Peer Road Q75']) & (d['Road Length Density']>0)
    low=d['Nighttime Radiance']<=d['Peer Radiance Q25']
    d['Screen Status']='Other supported comparison'
    d.loc[eligible & high & ~low,'Screen Status']='Higher roads; other radiance'
    d.loc[eligible & ~high & low,'Screen Status']='Other roads; lower radiance'
    d.loc[eligible & high & low,'Screen Status']='Potential mismatch candidate'
    d.loc[~eligible,'Screen Status']='Insufficient peers'
    candidate=pd.Series(pd.NA,index=d.index,dtype='boolean')
    candidate.loc[eligible]=(high & low).loc[eligible]
    d['Potential Mismatch Candidate']=candidate
    coords=mesh_centroids(d['Mesh Code'].astype(str).to_numpy())
    d['Latitude']=coords[:,0];d['Longitude']=coords[:,1]
    # Independent direct quantiles and membership checks in selected peer strata.
    checks=0
    sizes=g.size().sort_values()
    keys=list(sizes.index[:6])+list(sizes.index[-6:])
    for key in keys:
        z=g.get_group(key)
        qd=np.quantile(z['Road Length Density'],.75,method='linear')
        qr=np.quantile(z['Nighttime Radiance'],.25,method='linear')
        assert np.allclose(z['Peer Road Q75'],qd) and np.allclose(z['Peer Radiance Q25'],qr)
        if len(z)>=30:
            expected=(z['Road Length Density'].to_numpy()>qd)&(z['Road Length Density'].to_numpy()>0)&(z['Nighttime Radiance'].to_numpy()<=qr)
            assert np.array_equal(z['Potential Mismatch Candidate'].to_numpy(dtype=bool),expected)
        else: assert z['Potential Mismatch Candidate'].isna().all()
        checks+=1
    assert d.loc[~eligible,'Potential Mismatch Candidate'].isna().all()
    cand=d['Potential Mismatch Candidate'].fillna(False)
    d['Candidate Road Length']=d['Road Length'].where(cand,0)
    d['Supported Comparison']=eligible
    d['Candidate Count']=cand.astype(int)
    bypref=d.groupby(['Prefecture Code','Prefecture'],observed=True).agg(
        **{'Cohort Meshes':('Mesh Code','size'),'Supported Meshes':('Supported Comparison','sum'),
           'Candidate Meshes':('Candidate Count','sum'),'Cohort Road Length':('Road Length','sum'),
           'Candidate Road Length':('Candidate Road Length','sum')}).reset_index()
    region_context=d.groupby(['Prefecture Code','Prefecture'],observed=True)['Region'].agg(lambda x:'; '.join(sorted(x.unique()))).rename('Peer Region Contexts').reset_index()
    bypref=bypref.merge(region_context,on=['Prefecture Code','Prefecture'],validate='one_to_one')
    bypref['Candidate Fraction of Supported Meshes']=bypref['Candidate Meshes']/bypref['Supported Meshes']
    bypref['Candidate Road Stock Share']=bypref['Candidate Road Length']/bypref['Cohort Road Length']
    assert len(bypref)==47 and bypref['Candidate Meshes'].sum()==int(cand.sum())
    assert np.isclose(bypref['Candidate Road Length'].sum(),d.loc[cand,'Road Length'].sum())
    d.to_parquet(OUT/'mesh_screen_2024.parquet',index=False)
    bypref.to_csv(OUT/'prefecture_mismatch_summary.csv',index=False)
    peer_summary=g.agg(**{'Meshes':('Mesh Code','size'),'Road Q75':('Road Length Density',lambda x:x.quantile(.75)),
                          'Radiance Q25':('Nighttime Radiance',lambda x:x.quantile(.25))}).reset_index()
    peer_summary.to_csv(OUT/'peer_strata.csv',index=False)
    stats={'meshes':len(d),'supported_meshes':int(eligible.sum()),'unsupported_meshes':int((~eligible).sum()),
           'candidate_meshes':int(cand.sum()),'candidate_fraction_supported':float(cand.sum()/eligible.sum()),
           'candidate_road_length_km':float(d.loc[cand,'Road Length'].sum()),'cohort_road_length_km':float(d['Road Length'].sum()),
           'candidate_road_stock_share':float(d.loc[cand,'Road Length'].sum()/d['Road Length'].sum()),
           'candidate_population_zero_meshes':int((cand & d['Population'].eq(0)).sum()),
           'candidate_radiance_zero_meshes':int((cand & d['Nighttime Radiance'].eq(0)).sum()),
           'partial_land_cover_meshes_retained':int(d['Land Cover Incomplete Coverage'].sum()),
           'peer_strata':len(peer_summary),'independent_peer_checks':checks,
           'status_counts':{str(k):int(v) for k,v in d['Screen Status'].value_counts().items()}}
    return d,bypref,stats

def traffic():
    cols=['交通調査基本区間番号','世代管理番号（十の位）','世代管理番号（一の位）','道路種別','管理区分','市区町村コード',
          '区間延長（ｋｍ）','２４時間自動車類交通量（上下合計）／合計（台）',
          '上り／令和３年度調査交通量観測・非観測の別','下り／令和３年度調査交通量観測・非観測の別',
          '上り／１２時間・２４時間観測の別','下り／１２時間・２４時間観測の別']
    names=['Basic Segment Code','Generation Tens','Generation Units','Road Type','Road Manager','Municipality Code',
           'Segment Length','Published 24h Volume','Up Observation Status','Down Observation Status','Up Observation Hours Code','Down Observation Hours Code']
    frames=[]
    for i in range(1,48):
        name='traffic_2021_fukuoka.csv' if i==40 else f'traffic_2021_prefecture_{i:02d}.csv'
        x=pd.read_csv(SOURCE/name,encoding='cp932',usecols=cols,dtype=str)
        x=x[cols].rename(columns=dict(zip(cols,names)))
        x['Prefecture Code']=f'{i:02d}';x['Traffic Year']=2021
        for c in names[1:]:
            if c!='Municipality Code':x[c]=pd.to_numeric(x[c],errors='raise')
        assert not x.duplicated(['Basic Segment Code','Generation Tens','Generation Units']).any()
        assert (x['Segment Length']>=0).all()
        assert x['Municipality Code'].str.zfill(5).str[:2].eq(f'{i:02d}').all()
        assert x['Published 24h Volume'].dropna().ge(0).all()
        flags=x[['Up Observation Status','Down Observation Status']]
        assert flags.stack().dropna().isin([1,2]).all()
        x['Volume Status']=np.select([x['Published 24h Volume'].isna(),flags.eq(2).any(axis=1),flags.eq(1).any(axis=1)],
                                    ['Unavailable','Includes estimated direction','Observed direction; no estimated direction'],default='Status unavailable')
        frames.append(x)
    d=pd.concat(frames,ignore_index=True)
    assert len(d['Prefecture Code'].unique())==47
    d.to_parquet(OUT/'traffic_segment_reference_2021.parquet',index=False)
    rows=[]
    for key,z in d.groupby(['Prefecture Code','Road Manager','Road Type'],dropna=False):
        valid=z['Published 24h Volume'].notna() & z['Segment Length'].gt(0)
        observed=valid & z['Volume Status'].eq('Observed direction; no estimated direction')
        length=float(z.loc[valid,'Segment Length'].sum())
        rows.append({'Prefecture Code':key[0],'Road Manager':key[1],'Road Type':key[2],
                     'Segments':len(z),'Published Volume Segments':int(valid.sum()),'Surveyed Segment Length':float(z['Segment Length'].sum()),
                     'Published Volume Length':length,'Observed Direction Length':float(z.loc[observed,'Segment Length'].sum()),
                     'Includes Estimated Direction Length':float(z.loc[valid & z['Volume Status'].eq('Includes estimated direction'),'Segment Length'].sum()),
                     'Length Weighted 24h Volume':float(np.average(z.loc[valid,'Published 24h Volume'],weights=z.loc[valid,'Segment Length'])) if length>0 else np.nan})
    summary=pd.DataFrame(rows)
    summary.to_csv(OUT/'traffic_manager_type_summary.csv',index=False)
    pref=[]
    for code,z in d[d['Road Manager'].eq(2)].groupby('Prefecture Code'):
        v=z['Published 24h Volume'].notna() & z['Segment Length'].gt(0)
        pref.append({'Prefecture Code':code,'Prefecture Managed Survey Length':float(z['Segment Length'].sum()),
                     'Prefecture Managed Volume Coverage':float(z.loc[v,'Segment Length'].sum()/z['Segment Length'].sum()),
                     'Prefecture Managed Length Weighted 24h Volume':float(np.average(z.loc[v,'Published 24h Volume'],weights=z.loc[v,'Segment Length']))})
    return pd.DataFrame(pref),{'prefectures':47,'segments':len(d),'volume_missing_segments':int(d['Published 24h Volume'].isna().sum()),
                              'volume_status_counts':{str(k):int(v) for k,v in d['Volume Status'].value_counts().items()},
                              'mesh_linkage':'Unavailable: downloaded CSVs have no mesh identifiers or coordinates',
                              'survey_scope':'Main roads and selected designated-city roads; not all local roads',
                              'year':2021,'length_weighting':'Basic-segment lengths; repeated volume estimates describe different segment lengths'}

def fiscal():
    paths={k:SOURCE/f'prefecture_{k}_2024_label.csv' for k in ['maintenance','balance','overview']}
    data={k:pd.read_csv(p,encoding='cp932',dtype=str) for k,p in paths.items()}
    removed={}
    for k,d in data.items():
        keep=d['決算年度'].eq('2023');removed[k]=int((~keep).sum())
        d=d.loc[keep].copy();d['Prefecture Code']=d['団体コード '].str.strip().str.zfill(6).str[:2]
        # Keep only the 47 governments, not national totals or repeated headers.
        d=d[d['Prefecture Code'].isin([f'{i:02d}' for i in range(1,48)])]
        data[k]=d
    m=data['maintenance'];road=m[m['行名称'].eq('道路')].set_index('Prefecture Code');bridge=m[m['行名称'].eq('橋りょう')].set_index('Prefecture Code')
    b=data['balance'];b=b[b['行名称'].eq('令和5年度')].set_index('Prefecture Code')
    o=data['overview'].set_index('Prefecture Code')
    assert len(road)==len(bridge)==len(b)==len(o)==47
    value=lambda df,col:pd.to_numeric(df[col],errors='raise')
    f=pd.DataFrame({'Road Maintenance Thousand Yen':value(road,'001:維持補修費'),
                    'Bridge Maintenance Thousand Yen':value(bridge,'001:維持補修費'),
                    'Total Expenditure Thousand Yen':value(b,'002:歳出総額'),
                    'Standard Fiscal Scale Thousand Yen':value(o,'004:標準財政規模（千円）'),
                    'Standard Fiscal Revenue Thousand Yen':value(o,'001:基準財政収入額（千円）'),
                    'Standard Fiscal Need Thousand Yen':value(o,'002:基準財政需要額（千円）')}).reset_index()
    f['Fiscal Year']=2023
    f['Road and Bridge Maintenance Thousand Yen']=f['Road Maintenance Thousand Yen']+f['Bridge Maintenance Thousand Yen']
    f['Maintenance Share of Expenditure']=f['Road and Bridge Maintenance Thousand Yen']/f['Total Expenditure Thousand Yen']
    f['Maintenance Share of Standard Fiscal Scale']=f['Road and Bridge Maintenance Thousand Yen']/f['Standard Fiscal Scale Thousand Yen']
    f['Single Year Fiscal Revenue Need Ratio']=f['Standard Fiscal Revenue Thousand Yen']/f['Standard Fiscal Need Thousand Yen']
    assert f.drop(columns=['Prefecture Code']).notna().all().all()
    assert f['Maintenance Share of Expenditure'].between(0,1).all()
    # Verify units from official survey-form workbook, independent of CSV labels.
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        for sh in ['02','20']:
            cells=pd.read_excel(SOURCE/'fiscal_prefecture_template.xlsx',sheet_name=sh,header=None).astype(str)
            assert cells.apply(lambda c:c.str.contains('千円')).any().any()
    f.to_csv(OUT/'prefecture_fiscal_reference_fy2023.csv',index=False)
    return f,{'prefectures':47,'fiscal_year':2023,'catalog_year':2024,'repeated_header_or_non_year_rows_removed':removed,
              'units_verified_from_official_template':True,'amount_unit':'Thousand JPY',
              'maintenance_scope':'Table 20 Road plus Bridge maintenance; excludes other purpose rows and capital entrusted-project columns',
              'capacity_measure':'Single-year standard fiscal revenue / standard fiscal need; not the three-year fiscal strength index',
              'managed_stock_attribution':'Not established: mesh roads are not classified by maintenance-responsible government'}

def map_screen(d):
    vertices=np.empty((len(d),4,2))
    vertices[:,:,0]=d['Longitude'].to_numpy()[:,None]+np.array([-1,1,1,-1])[None,:]/160
    vertices[:,:,1]=d['Latitude'].to_numpy()[:,None]+np.array([-1,-1,1,1])[None,:]/240
    colors={'Potential mismatch candidate':'#d94723','Higher roads; other radiance':'#7ba6bd',
            'Other roads; lower radiance':'#c7d3db','Other supported comparison':'#e5e8e9','Insufficient peers':'#6c7279'}
    lat=d['Latitude'].to_numpy();lon=d['Longitude'].to_numpy()
    groups=[('Main islands',lat>=30,[.05,.15,.66,.75],(128,146.5),(29.95,46),36),
            ('Southwest islands',(lat<30)&(lon<135),[.74,.58,.24,.28],(122.5,132),(23.7,30.1),27),
            ('Ogasawara islands',(lat<30)&(lon>=135),[.75,.20,.16,.32],(140.9,142.65),(24.5,27.4),26)]
    assert np.all(np.stack([g[1] for g in groups]).sum(axis=0)==1)
    fig=plt.figure(figsize=(13,11),facecolor='white')
    fig.text(.05,.96,'Potential road-economy mismatch: comparable-context screen',fontsize=17,weight='bold')
    fig.text(.05,.932,'Roads and radiance: 2024 | Population: 2020 | Coarse peer strata | Exploratory, not an excess-road classification',fontsize=9)
    boundary=ROOT/'data/exp/gwpr-twoways/map_reference_lines.json'
    context=[np.asarray(v) for v in json.loads(boundary.read_text())['lines']] if boundary.exists() else []
    panel_counts={}
    for name,mask,pos,xlim,ylim,ref in groups:
        ax=fig.add_axes(pos);ax.set_xlim(xlim);ax.set_ylim(ylim);ax.set_aspect(1/np.cos(np.deg2rad(ref)))
        nearby=[v for v in context if v[:,0].max()>=xlim[0] and v[:,0].min()<=xlim[1] and v[:,1].max()>=ylim[0] and v[:,1].min()<=ylim[1]]
        if nearby:ax.add_collection(PolyCollection(nearby,facecolors='#f4f4f4',edgecolors='#bfc5c8',linewidths=.15))
        for status,color in colors.items():
            show=mask & d['Screen Status'].eq(status).to_numpy()
            ax.add_collection(PolyCollection(vertices[show],facecolors=color,edgecolors='none',zorder=3 if status.startswith('Potential') else 2))
        assert (vertices[mask,:,0]>=xlim[0]).all() and (vertices[mask,:,0]<=xlim[1]).all()
        assert (vertices[mask,:,1]>=ylim[0]).all() and (vertices[mask,:,1]<=ylim[1]).all()
        ax.set_title(name,loc='left',fontsize=10);ax.tick_params(labelsize=8)
        panel_counts[name]=int(mask.sum())
    fig.legend(handles=[Patch(facecolor=c,label=s) for s,c in colors.items()],loc='lower left',bbox_to_anchor=(.05,.025),ncol=2,frameon=False,fontsize=9)
    fig.text(.05,.014,'Red: road density above peer Q75 and radiance at/below peer Q25. Gray: fewer than 30 peers. Actual mesh extents; no interpolation.',fontsize=8)
    fig.savefig(OUT/'potential_mismatch_mesh_map.png',dpi=220)
    plt.close(fig)
    return {'polygons':len(d),'panel_mesh_counts':panel_counts,'all_meshes_inside_axes':True,'geometry':'1/120 degree latitude by 1/80 degree longitude',
            'excluded_from_extension':'Four unavailable-land-cover Minamitorishima meshes remain excluded by the existing extension contract'}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    protected={str(p.relative_to(ROOT)):sha(p) for p in [PANEL,ROADS,ROOT/'data/exp/land-cover-poi-extension/active_gwpr_extension.json']}
    contract=json.loads((ROOT/'data/exp/land-cover-poi-extension/execution_contract.json').read_text())
    assert protected[str(PANEL.relative_to(ROOT))]==contract['panel_sha256']
    for m in SOURCE.glob('*.metadata.json'):
        meta=json.loads(m.read_text());stem=m.name.removesuffix('.metadata.json')
        files=[p for p in SOURCE.glob(stem+'.*') if p!=m]
        assert len(files)==1 and sha(files[0])==meta['sha256']
    d,pref,screen_stats=screen();tr,trstats=traffic();fi,fistats=fiscal()
    joined=pref.merge(tr,on='Prefecture Code',validate='one_to_one',how='left').merge(fi,on='Prefecture Code',validate='one_to_one',how='left')
    assert len(joined)==47 and joined['Fiscal Year'].eq(2023).all()
    joined.to_csv(OUT/'prefecture_evidence_trial.csv',index=False)
    x='Candidate Fraction of Supported Meshes'
    ys=['Prefecture Managed Length Weighted 24h Volume','Maintenance Share of Expenditure',
        'Maintenance Share of Standard Fiscal Scale','Single Year Fiscal Revenue Need Ratio']
    correlations=[]
    for y in ys:
        z=joined[[x,y]].dropna();a=z[x].rank(method='average').to_numpy();b=z[y].rank(method='average').to_numpy()
        rho=float(np.corrcoef(a,b)[0,1])
        assert np.isclose(rho,z[x].rank().corr(z[y].rank()))
        correlations.append({'Comparison':y,'Prefectures':len(z),'Spearman Rho':rho,'Inference':'Descriptive; no significance or causal claim'})
    pd.DataFrame(correlations).to_csv(OUT/'prefecture_context_rank_correlations.csv',index=False)
    fig,axes=plt.subplots(1,3,figsize=(14,4.5))
    labels=['Published traffic volume (vehicles / 24h)','Road + bridge maintenance / expenditure (%)','Maintenance / standard fiscal scale (%)']
    for ax,y,label in zip(axes,ys[:3],labels):
        scale=1 if y==ys[0] else 100
        ax.scatter(joined[x]*100,joined[y]*scale,s=25,color='#32718c',alpha=.8)
        ax.set_xlabel('Candidate fraction among supported meshes (%)');ax.set_ylabel(label);ax.grid(alpha=.15)
        rho=next(r['Spearman Rho'] for r in correlations if r['Comparison']==y)
        ax.set_title(f'Prefecture context: rank correlation {rho:.3f}',fontsize=10)
    fig.suptitle('Exploratory administrative comparison; road ownership and mesh utilization are not linked',fontsize=11)
    fig.text(.02,.012,'Traffic: 2021, prefecture-managed surveyed roads. Finance: FY2023 prefecture governments. Mesh screen: 2024 roads/lights, 2020 population.',fontsize=8)
    fig.tight_layout(rect=[0,.06,1,.94]);fig.savefig(OUT/'prefecture_evidence_scatter.png',dpi=180);plt.close(fig)
    map_stats=map_screen(d)
    assert all(sha(ROOT/k)==v for k,v in protected.items())
    # Re-read parquet and administrative exports to verify counts and values.
    saved=pd.read_parquet(OUT/'mesh_screen_2024.parquet',columns=['Mesh Code','Potential Mismatch Candidate','Road Length'])
    assert len(saved)==len(d) and saved['Mesh Code'].is_unique
    assert int(saved['Potential Mismatch Candidate'].sum())==screen_stats['candidate_meshes']
    assert saved['Potential Mismatch Candidate'].isna().sum()==screen_stats['unsupported_meshes']
    export=pd.read_csv(OUT/'prefecture_evidence_trial.csv',dtype={'Prefecture Code':str})
    assert export['Prefecture Code'].is_unique and len(export)==47
    report={'status':'passed_boundary_limited_trial','decision_id':'MILI-D-20261010-036','screen':screen_stats,
            'traffic':trstats,'fiscal':fistats,'context_correlations':correlations,'map':map_stats,
            'protected_sha256':protected,'inputs_unchanged':True,'sources_sha_verified':True,
            'interpretation':'Candidate mismatch and administrative context only; excess roads, mesh underutilization, and causal fiscal pressure not established',
            'outputs':{p.name:sha(p) for p in OUT.iterdir() if p.suffix in ['.parquet','.csv','.png']}}
    write_json(OUT/'trial_validation.json',report)
    write_json(OUT/'screening_contract.json',{'decision_id':'MILI-D-20261010-036','screen_year':2024,'population_year':2020,'peer_keys':PEERS,
          'population_edges':[-1,0,9,49,199,999,4999,'infinity'],'rail_edges_km':[1,5],
          'facility_context':'Any of four approved facility totals >0','land_context':'Dominant of six accepted categories; ties and incomplete coverage separate',
          'minimum_peer_meshes':30,'road_rule':'Strictly above peer Q75 and >0','radiance_rule':'At or below peer Q25',
          'rules_status':'Agent-specified exploratory conventions; not a final excess-road benchmark','airport_distance_matched':False,
          'source_fiscal_year':2023,'source_traffic_year':2021,'effects':[],'historical_change_analysis':False})
    print(json.dumps({'screen':screen_stats,'context_correlations':correlations},indent=2))

if __name__=='__main__': main()
