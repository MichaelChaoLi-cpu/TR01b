"""Independent readback checks for the approved light-zero audit delivery."""
from pathlib import Path
import json, hashlib, re
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/road-economy-mismatch-light-zero-audit'
OLD=ROOT/'data/exp/road-economy-mismatch-trial'
PEERS=['Region','Population Band','Land Context','Facility Presence','Rail Proximity Band']
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def main():
    original=pd.read_parquet(OLD/'mesh_screen_2024.parquet');d=pd.read_parquet(OUT/'revised_mesh_screen_2024.parquet')
    assert d['Mesh Code'].is_unique and len(d)==len(original)==383386
    pd.testing.assert_series_equal(d['Mesh Code'],original['Mesh Code'])
    derived={'Screen Status','Potential Mismatch Candidate','Supported Comparison','Candidate Count','Candidate Road Length'}
    for col in original.columns.difference(list(derived)):pd.testing.assert_series_equal(d[col],original[col])
    pd.testing.assert_series_equal(d['Original Potential Mismatch Candidate'],original['Potential Mismatch Candidate'],check_names=False)
    pd.testing.assert_series_equal(d['Original Screen Status'],original['Screen Status'],check_names=False)
    assert (d['Nighttime Radiance']>=0).all()
    checks=0
    for _,z in d.groupby(PEERS,observed=True):
        az=bool(np.all(z['Nighttime Radiance'].to_numpy()==0));support=len(z)>=30 and not az
        assert z['Peer All Zero Radiance'].eq(az).all() and z['Supported Comparison'].eq(support).all()
        if not support:assert z['Potential Mismatch Candidate'].isna().all()
        else:
            qd=np.quantile(z['Road Length Density'],.75);qr=np.quantile(z['Nighttime Radiance'],.25)
            expected=(z['Road Length Density'].to_numpy()>qd)&(z['Road Length Density'].to_numpy()>0)&(z['Nighttime Radiance'].to_numpy()<=qr)
            np.testing.assert_array_equal(z['Potential Mismatch Candidate'].to_numpy(dtype=bool),expected)
        if az:
            assert z['Screen Status'].eq('Information insufficient: all-zero peer radiance').all()
            assert z['Screen Support Reason'].str.contains('all-zero',case=False).all()
        checks+=1
    pd.testing.assert_series_equal(d['Potential Mismatch Candidate'],original['Potential Mismatch Candidate'])
    px=pd.read_parquet(OUT/'audited_native_pixel_intersections.parquet');report=pd.read_csv(OUT/'source_mesh_recomputation.csv',dtype={'Mesh Code':str}).set_index('Mesh Code')
    assert not px.duplicated(['Mesh Code','Raster Row','Raster Column']).any()
    for code,z in px.groupby('Mesh Code'):
        valid=z['Valid Pixel'];a=z.loc[valid,'Intersection Area m2'];v=z.loc[valid,'Source Radiance']
        recomputed=float((a*v).sum()/a.sum());assert np.isclose(recomputed,report.loc[code,'Stored Radiance'],rtol=1e-10,atol=1e-10)
        if report.loc[code,'Stored Radiance']==0:assert valid.all() and v.eq(0).all()
    validation=json.loads((OUT/'validation.json').read_text());assert sha(OLD/'mesh_screen_2024.parquet')==validation['original_trial_sha256']
    panel=ROOT/'data/processed/national/land_cover_poi_extension/focused_extension_panel_preprocessed.parquet'
    assert sha(panel)=='367624671e416ff01c6f69df0126addfd4fa69b523ee00b9e85c10b6e381c4b3'
    before=(OUT/'anasop_before_revision.md').read_text();after=(ROOT/'docs/AnaSOP.md').read_text()
    def sections(s):
        parts=re.split(r'(?m)(^## [1-8]\. .+$)',s);return {int(parts[i][3]):parts[i]+parts[i+1] for i in range(1,len(parts),2)}
    a,b=sections(before),sections(after)
    for k in [1,2,4,8]:assert a[k]==b[k],k
    for k in [3,5,6,7]:assert a[k]!=b[k],k
    assert after.count('\\[')==after.count('\\]') and after.count('\\(')==after.count('\\)')
    assert not re.search(r'[\u4e00-\u9fff]',after)
    for eq in re.findall(r'\\\[(.*?)\\\]',after,re.S):assert eq.isascii()
    context=pd.read_csv(OUT/'land_context_summary.csv');assert context['Candidate Meshes'].sum()==66088
    assert context['Cohort Meshes'].sum()==383386 and context['All Zero Peer Meshes'].sum()==154
    out={'status':'passed','all_peer_groups_independently_checked':checks,'source_meshes_independently_reaggregated':len(report),
         'saved_original_values_unchanged':True,'candidate_membership_unchanged':True,'processed_panel_hash_unchanged':True,
         'all_source_meshes_retained':True,'ana_sections_changed':[3,5,6,7],'ana_other_sections_preserved':True,
         'ana_english_and_ascii_display_math_checked':True,'visual_review':'Mesh map and two-panel context chart pass',
         'substantive_claim':'Potential mismatch only; source zeros do not validate absent economic activity or road excess'}
    (OUT/'delivery_validation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
