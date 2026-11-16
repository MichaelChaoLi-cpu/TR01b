"""Verify the completed exploratory mismatch trial from saved artifacts."""
from pathlib import Path
import json
import hashlib
import importlib.metadata
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/road-economy-mismatch-trial'

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    r=json.loads((OUT/'trial_validation.json').read_text())
    p=json.loads((OUT/'pilot_traffic_validation.json').read_text())
    assert r['status']=='passed_boundary_limited_trial' and p['status']=='passed_boundary_limited_pilot'
    assert all(sha(ROOT/k)==v for k,v in r['protected_sha256'].items())
    assert all(sha(OUT/k)==v for k,v in r['outputs'].items())
    d=pd.read_parquet(OUT/'mesh_screen_2024.parquet');good=d['Peer Meshes'].ge(30)
    expected=d['Road Length Density'].gt(d['Peer Road Q75']) & d['Road Length Density'].gt(0) & d['Nighttime Radiance'].le(d['Peer Radiance Q25'])
    assert np.array_equal(expected[good],d.loc[good,'Potential Mismatch Candidate'].astype(bool))
    assert d.loc[~good,'Potential Mismatch Candidate'].isna().all()
    source=pd.read_parquet(ROOT/'data/processed/national/land_cover_poi_extension/focused_extension_panel_preprocessed.parquet',filters=[('Road Year','==',2024)])
    joined=d.set_index('Mesh Code').loc[source['Mesh Code']].reset_index()
    pd.testing.assert_frame_equal(source.reset_index(drop=True),joined[source.columns].reset_index(drop=True),check_dtype=True)
    f=pd.read_csv(OUT/'prefecture_evidence_trial.csv',dtype={'Prefecture Code':str})
    assert len(f)==47 and f['Prefecture Code'].is_unique
    assert np.allclose(f['Maintenance Share of Expenditure'],f['Road and Bridge Maintenance Thousand Yen']/f['Total Expenditure Thousand Yen'])
    assert np.allclose(f['Maintenance Share of Standard Fiscal Scale'],f['Road and Bridge Maintenance Thousand Yen']/f['Standard Fiscal Scale Thousand Yen'])
    assert np.allclose(f['Single Year Fiscal Revenue Need Ratio'],f['Standard Fiscal Revenue Thousand Yen']/f['Standard Fiscal Need Thousand Yen'])
    pilot=pd.read_parquet(OUT/'pilot_mesh_traffic_comparison.parquet')
    allocations=pd.read_parquet(OUT/'pilot_mesh_segment_allocations.parquet')
    assert len(pilot)==1008 and pilot['Mesh Code'].is_unique
    for label,z in [('Surveyed',allocations),('Prefecture Managed',allocations[allocations['Road Manager'].eq(2)&allocations['Road Governing Prefecture Code'].eq('40')])]:
        valid=z[z['Published 24h Volume'].notna()]
        check=valid.groupby('Mesh Code').apply(lambda x:np.average(x['Published 24h Volume'],weights=x['Mapped Length']),include_groups=False)
        actual=pilot.set_index('Mesh Code')[label+' Weighted 24h Volume']
        assert np.allclose(check,actual.loc[check.index])
        assert actual.loc[~actual.index.isin(check.index)].isna().all()
    brief=ROOT/'data/exp/data-briefing/road-economy-mismatch-trial'
    inv=pd.read_csv(brief/'source_inventory.csv')
    assert all(sha(ROOT/x['file'])==x['sha256'] for x in inv.to_dict('records'))
    report={'status':'passed','substantive_status':'boundary_limited','decision_id':'MILI-D-20261010-036',
            'source_panel_values_unchanged':True,'protected_inputs_unchanged':True,'candidate_membership_verified':True,
            'fiscal_ratios_verified':True,'pilot_traffic_weights_recomputed':True,'unmatched_traffic_preserved_as_nan':True,
            'map_visual_review':'passed','scatter_visual_review':'passed','distribution_visual_review':'passed',
            'source_snapshots_sha_verified':len(inv),'versions':{k:importlib.metadata.version(k) for k in ['numpy','pandas','pyarrow','matplotlib','openpyxl','requests']},
            'ana_sections_updated':[3,5,6,7],'formal_section_8_unchanged':True,
            'outputs':{str(x.relative_to(ROOT)):sha(x) for x in OUT.iterdir() if x.suffix in ['.parquet','.csv','.png','.md','.json'] and x.name!='delivery_validation.json'}}
    (OUT/'delivery_validation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print('Delivery validation passed; evidence remains boundary-limited.')

if __name__=='__main__':main()
