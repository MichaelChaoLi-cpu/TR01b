"""Focused data briefing for the road-mismatch trial, without a whole-repo scan."""
from pathlib import Path
import json
import hashlib
import os
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/tr01b-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
TRIAL=ROOT/'data/exp/road-economy-mismatch-trial'
OUT=ROOT/'data/exp/data-briefing/road-economy-mismatch-trial'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    meshes=pd.read_parquet(TRIAL/'mesh_screen_2024.parquet')
    traffic=pd.read_parquet(TRIAL/'traffic_segment_reference_2021.parquet')
    fiscal=pd.read_csv(TRIAL/'prefecture_fiscal_reference_fy2023.csv')
    sources=[]
    for p in sorted((TRIAL/'source_snapshots').glob('*.metadata.json')):
        meta=json.loads(p.read_text());stem=p.name.removesuffix('.metadata.json')
        actual=[q for q in p.parent.glob(stem+'.*') if q!=p]
        assert len(actual)==1
        q=actual[0];assert hashlib.sha256(q.read_bytes()).hexdigest()==meta['sha256']
        sources.append({'file':str(q.relative_to(ROOT)),'url':meta['url'],'bytes':meta['bytes'],'sha256':meta['sha256'],
                        'retrieved_utc':meta['retrieved_utc'],'role':'Original official snapshot; exploratory reference'})
    pd.DataFrame(sources).to_csv(OUT/'source_inventory.csv',index=False)
    selected={'Mesh screen':(meshes,['Road Length Density','Nighttime Radiance','Population']),
              'Published traffic':(traffic,['Segment Length','Published 24h Volume']),
              'Fiscal reference':(fiscal,['Road Maintenance Thousand Yen','Bridge Maintenance Thousand Yen','Total Expenditure Thousand Yen',
                                          'Standard Fiscal Scale Thousand Yen','Maintenance Share of Expenditure',
                                          'Maintenance Share of Standard Fiscal Scale','Single Year Fiscal Revenue Need Ratio'])}
    stats=[]
    for label,(d,cols) in selected.items():
        for c in cols:
            x=d[c];valid=x.dropna()
            stats.append({'Dataset':label,'Variable':c,'Rows':len(x),'Missing':int(x.isna().sum()),'Zero':int(x.eq(0).sum()),
                          'Minimum':float(valid.min()),'Median':float(valid.median()),'Maximum':float(valid.max()),
                          'Role':'Existing substantive value or exploratory reference; no new final-model role'})
    pd.DataFrame(stats).to_csv(OUT/'variable_summary.csv',index=False)
    cand=meshes['Potential Mismatch Candidate'].fillna(False)
    groups=[]
    for label,z in [('All supported meshes',meshes[meshes['Supported Comparison']]),('Candidates',meshes[cand])]:
        for context,sub in z.groupby('Land Context'):
            groups.append({'Group':label,'Land Context':context,'Meshes':len(sub),'Radiance Zero Meshes':int(sub['Nighttime Radiance'].eq(0).sum()),
                           'Population Zero Meshes':int(sub['Population'].eq(0).sum()),'Road Length':float(sub['Road Length'].sum()),
                           'Median Radiance':float(sub['Nighttime Radiance'].median()),'Median Road Density':float(sub['Road Length Density'].median())})
    pd.DataFrame(groups).to_csv(OUT/'screen_context_summary.csv',index=False)
    fig,ax=plt.subplots(1,3,figsize=(13,4))
    ax[0].hist(meshes['Road Length Density'],bins=60,color='#397b92');ax[0].set_yscale('symlog')
    ax[0].set_xlabel('2024 road density (km/km2)');ax[0].set_ylabel('Meshes; symlog count axis')
    v=traffic['Published 24h Volume'].dropna();positive=v[v>0]
    ax[1].hist(positive,bins=np.geomspace(positive.min(),positive.max(),45),color='#397b92');ax[1].set_xscale('log')
    ax[1].set_xlabel('Published traffic (vehicles/24h); log-spaced bins');ax[1].set_ylabel('Basic road segments')
    ax[1].set_title(f'Zero: {int(v.eq(0).sum())}; unavailable: {int(traffic["Published 24h Volume"].isna().sum())}',fontsize=9)
    ax[2].hist(fiscal['Maintenance Share of Expenditure']*100,bins=12,color='#397b92')
    ax[2].set_xlabel('FY2023 maintenance / expenditure (%)');ax[2].set_ylabel('Prefecture governments')
    fig.suptitle('Focused source distributions; exploratory and coverage-limited',fontsize=12)
    fig.tight_layout();fig.savefig(OUT/'source_distributions.png',dpi=170);plt.close(fig)
    inventory=[{'Dataset':label,'Rows':len(d),'Columns':len(d.columns),'Year Scope':years} for label,d,years in
               [('2024 mesh screen',meshes,'2024 roads/lights; 2020 population; static facilities'),('Published basic road segments',traffic,'2021'),('Prefecture fiscal reference',fiscal,'FY2023')]]
    pd.DataFrame(inventory).to_csv(OUT/'dataset_inventory.csv',index=False)
    summary={'status':'passed','source_snapshots':len(sources),'source_bytes':sum(s['bytes'] for s in sources),'datasets':inventory,
             'variables_summarized':len(stats),'distribution_figures':1,'time_series_visualizations':0,
             'candidate_radiance_zero_fraction':float(meshes.loc[cand,'Nighttime Radiance'].eq(0).mean()),
             'candidate_forest_fraction':float(meshes.loc[cand,'Land Context'].eq('Forest').mean()),
             'candidate_population_zero_fraction':float(meshes.loc[cand,'Population'].eq(0).mean()),
             'limits':['Candidate screening is dominated by zero-radiance and forest meshes; zero radiance does not establish zero economic activity.',
                       'Traffic is a main-road survey and includes estimated values and 12-to-24-hour expansion.',
                       'Finance covers prefecture governments, not consolidated prefecture-wide municipal expenditure.',
                       'Actual fiscal year is 2023 despite catalog year 2024. No maintenance-cost obligation or excess-stock causal model is estimated.']}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    (OUT/'README.md').write_text('# Focused road-economy mismatch trial data briefing\n\n'
        'Reproduce with `python3 src/exp/brief_road_mismatch_trial.py` after the documented trial analyses. '
        'Original official snapshots are checksum-verified and remain in the trial source_snapshots folder. '
        'The source inventory, dataset inventory, variable summary, context summary and distribution figure accompany the JSON summary. '
        'No source or processed panel is changed. No time-series visualization is selected. '
        'The fiscal and traffic variables are exploratory references, not automatically selected new controls.\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
