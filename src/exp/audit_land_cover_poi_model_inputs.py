"""Screen existing land-cover/POI controls on the approved baseline cohort.

No coefficient estimation, variable transformation, source update or final variable
selection. Reproduce: python3 src/exp/audit_land_cover_poi_model_inputs.py
"""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'): os.environ[name]='1'
from pathlib import Path
import json,hashlib,importlib.util,sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/data-briefing/land-cover-poi-common-cohort'
sys.path.insert(0,str(ROOT/'src/analyses'))
from gwpr_pooled import RadiusIndex,mesh_centroids


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    pointer=json.loads((ROOT/'data/exp/data-preprocessing/active_panel.json').read_text())
    source=ROOT/pointer['core_balanced_panel']
    baseline=ROOT/pointer['active_baseline_panel']
    group=json.loads((ROOT/'data/exp/data-briefing/modis-water-retained-missingness/summary.json').read_text())['groups']
    poi=group['existing_facilities']+group['additional_ksj'];lc=group['land_cover']
    before={str(p.relative_to(ROOT)):sha(p) for p in [source,baseline,ROOT/'docs/AnaSOP.md']}
    codes=pd.read_parquet(baseline,columns=['Mesh Code'])['Mesh Code'].drop_duplicates().astype(str).to_numpy()
    assert len(codes)==383390
    # Source snapshots are already approved static values; 2024 is merely one
    # copy for auditing their spatial distribution, not a new source edition.
    static=pd.read_parquet(source,columns=['Mesh Code']+poi,filters=[('Road Year','==',2024),('Mesh Code','in',codes.tolist())]).sort_values('Mesh Code').reset_index(drop=True)
    assert np.array_equal(static['Mesh Code'].to_numpy(),codes)
    land=pd.read_parquet(source,columns=['Mesh Code','Road Year']+lc+['Land Cover Coverage','Land Cover Source Coverage','Land Cover Incomplete Coverage'],filters=[('Mesh Code','in',codes.tolist())]).sort_values(['Mesh Code','Road Year']).reset_index(drop=True)
    assert len(land)==len(codes)*5
    missing=land[lc].isna().any(axis=1)
    excluded=land.loc[missing,'Mesh Code'].unique().tolist()
    land.loc[missing,['Mesh Code','Road Year']].to_csv(OUT/'missing_land_cover_membership.csv',index=False)
    assert np.array_equal(land['Mesh Code'].drop_duplicates().to_numpy(),codes)
    assert np.array_equal(land['Road Year'].to_numpy().reshape(-1,5),np.tile([2002,2003,2004,2010,2024],(len(codes),1)))
    completeness=~missing.to_numpy().reshape(-1,5).any(axis=1)
    assert (land[lc].isna().sum(axis=1).isin([0,6])).all()
    # Use the skill's native summary/plot functions on this focused, full-cohort
    # audit, preserving unrelated AnaSOP sections and the existing briefing.
    spec=importlib.util.spec_from_file_location('mili_data_briefing',ROOT/'.codex/skills/data-briefing/scripts/create_data_briefing.py')
    skill=importlib.util.module_from_spec(spec);spec.loader.exec_module(skill)
    rows,screen=[],[]
    for name,frame in [('Static facility spatial distribution',static[poi]),('Five-period annual land cover',land[lc])]:
        a,b,_=skill.summarize_dataset(name,source,frame);rows+=a;screen+=b
    summary=pd.DataFrame(rows)
    lookup={c:float(static[c].eq(0).mean()) for c in poi}
    summary['zero_fraction']=summary['variable'].map(lookup)
    summary.to_csv(OUT/'variable_summary.csv',index=False)
    pd.DataFrame(screen).to_csv(OUT/'variable_screening.csv',index=False)
    # Verify four already documented exact total/category identities.
    original=group['existing_facilities']
    totals=['School Facility Count','Medical Facility Count','Logistics Facility Count','Visitor and Event Facility Count']
    boundaries=totals[1:]+['Railway Station Count']
    partitions=[(total,original[original.index(total)+1:original.index(end)]) for total,end in zip(totals,boundaries)]
    identities=[]
    for total,children in partitions:
        delta=(static[total]-static[children].sum(axis=1)).to_numpy()
        identities.append(dict(total=total,components=children,maximum_absolute_difference=float(abs(delta).max()),exact_on_all_common_meshes=bool((delta==0).all())))
    assert all(r['exact_on_all_common_meshes'] for r in identities)
    coordinates=mesh_centroids(codes);index=RadiusIndex(coordinates)
    centers=pd.read_csv(ROOT/'data/exp/gwpr-pooled-current-common-cohort/bandwidth-search-3-50km/validation_centers_input.csv',dtype={'Mesh Code':str})
    lookup_idx={c:i for i,c in enumerate(codes)}
    static_values=static[poi].to_numpy(float)
    design=[]
    for code in centers['Mesh Code']:
        ids,_=index.query(coordinates[lookup_idx[code]],3.)
        local=static_values[ids]
        constant=np.ptp(local,axis=0)==0
        design.append({'Mesh Code':code,'Local Spatial Meshes':len(ids),'Static Candidate Controls':len(poi),
            'Constant Static Candidates':int(constant.sum()),'All Candidate POI Model Full Rank Possible':not constant.any(),
            'Constant Candidates':'; '.join(np.array(poi)[constant])})
    pd.DataFrame(design).to_csv(OUT/'local_design_support_3km.csv',index=False)
    valid=~missing.to_numpy();share_sum=land[lc].sum(axis=1).to_numpy()
    coverage=land['Land Cover Coverage'].to_numpy()
    max_sum_difference=float(np.max(abs(share_sum[valid]-coverage[valid])))
    figures=OUT/'figures';figures.mkdir(exist_ok=True)
    chosen_for_display=['Distance to Railway Station','Distance to Passenger Airport','School Facility Count','Medical Facility Count','Logistics Facility Count','Visitor and Event Facility Count']
    plot_count=0
    for col in chosen_for_display:
        plot_count+=int(skill.plot_numeric_distribution(static[col],figures/(skill.safe_name(col)+'.png'),col+' (common cohort, static snapshot)'))
    for path,digest in before.items():assert sha(ROOT/path)==digest
    report=dict(status='passed',source=str(source.relative_to(ROOT)),source_sha256=sha(source),baseline_meshes=len(codes),baseline_observations=len(land),poi_candidates=len(poi),annual_land_cover_candidates=len(lc),
        poi_missing_values=int(static[poi].isna().sum().sum()),land_cover_missing_records=int(missing.sum()),land_cover_missing_meshes=len(excluded),
        complete_land_cover_meshes=int(completeness.sum()),complete_land_cover_observations=int(completeness.sum())*5,
        incomplete_coverage_records=int(land['Land Cover Incomplete Coverage'].sum()),coverage_minimum_finite=float(np.nanmin(coverage)),
        six_shares_partition_coverage_maximum_difference=max_sum_difference,full_coverage_valid_records=int((abs(coverage-1)<1e-8).sum()),
        total_category_identities=identities,local_audit_centers=len(design),local_centers_with_constant_poi_candidates=sum(r['Constant Static Candidates']>0 for r in design),
        all_poi_global_model_exactly_rank_deficient=True,all_poi_local_full_rank_not_possible_centers=sum(not r['All Candidate POI Model Full Rank Possible'] for r in design),
        distribution_plots_generated=plot_count,time_series_candidates=True,time_series_plots_generated=0,statistical_models_estimated=False,
        final_control_subset_selected=False,sample_selection_changed=False,source_inputs_unchanged=True,anasop_modified=False,protected_sha256=before)
    (OUT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    (OUT/'README.md').write_text('# Land-cover and POI model-input screening\n\n'
        'Reproduce `python3 src/exp/audit_land_cover_poi_model_inputs.py`. The audit covers all current baseline meshes, not a convenience sample. '
        'Static facility distributions use one replicated period; annual land-cover availability uses all five periods. '
        'Summary and screening use the data-briefing skill native local Python functions. '
        'Total/category identities are checked exactly. Local design support uses the existing 1,286 validation centers at 3 km and includes each focal mesh. '
        'This is design screening, without coefficient estimation or final selection. '
        'No data or AnaSOP is modified and no absent land-cover tile is recoded as zero.\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['protected_sha256','total_category_identities']},indent=2),flush=True)


if __name__=='__main__':main()
