#!/usr/bin/env python3
"""Auditable fixed-distance GWPR search and nationwide two-way FE fitting.

Use --stage search to evaluate the approved 5-50 km grid; --stage fit uses
the selected distance only after the common-validation policy is confirmed.
Outputs here are auditable analysis data, not additional regression models.
"""
import argparse
from pathlib import Path
import hashlib
import json
import time

import numpy as np
import pandas as pd

from gwpr_twoways import PanelMoments,RadiusIndex,mesh_centroids,bisquare_weights,result_row

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/gwpr-twoways'
PLAN=ROOT/'data/exp/estimation-framework-planning/gwpr-twoways'


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(4*1024*1024),b''): h.update(data)
    return h.hexdigest()


def load_panel():
    contract=json.loads((ROOT/'data/exp/estimation-framework-planning/national-fixed-effects/estimation_decisions.json').read_text())
    variables=[contract['outcome']]+contract['explanatory']
    identifiers=['Mesh Code','Road Year','Population Year','Nighttime Light Year']
    membership=pd.read_csv(ROOT/'data/exp/figure-table-generation/national-fixed-effects/sample_membership.csv',dtype={'Mesh Code':'string'})
    codes=sorted(membership['Mesh Code'].unique().tolist())
    source_path=ROOT/contract['input']
    source=pd.read_parquet(source_path,columns=identifiers+variables)
    sample=source[source['Mesh Code'].isin(codes)].sort_values(['Mesh Code','Road Year'])
    assert len(sample)==len(membership)==539320 and len(codes)==134830
    for col in identifiers: assert np.array_equal(sample[col].to_numpy(),membership[col].to_numpy())
    values=sample[variables].to_numpy().reshape(len(codes),4,3)
    assert np.isfinite(values).all()
    assert np.array_equal(sample['Road Year'].to_numpy().reshape(len(codes),4),np.tile(contract['periods'],(len(codes),1)))
    return codes,sample[identifiers].copy(),PanelMoments(values),RadiusIndex(mesh_centroids(codes)),contract,source_path


def search():
    start=time.monotonic(); OUT.mkdir(parents=True,exist_ok=True)
    codes,membership,panel,index,contract,source=load_panel()
    protected=[source,ROOT/'data/exp/figure-table-generation/national-fixed-effects/sample_membership.csv']+sorted((ROOT/'data/results/tables').glob('*.xlsx'))
    before={str(p.relative_to(ROOT)):sha(p) for p in protected}
    centers=pd.read_csv(PLAN/'validation_centers.csv',dtype={'Mesh Code':'string','Primary Tile':'string'})
    code_index={code:i for i,code in enumerate(codes)}
    focus_ids=[code_index[c] for c in centers['Mesh Code']]
    assert len(focus_ids)==1286 and centers['Mesh Code'].is_unique
    assert np.isclose(centers['Validation Weight'].sum(),len(codes))
    radii=np.arange(5.,51.)
    scores=np.full((len(centers),len(radii)),np.nan)
    records=[]; references=[]
    # Pre-query each validation neighborhood once at the largest approved radius.
    for i,focus in enumerate(focus_ids):
        ids,distance=index.query(index.coordinates[focus],50,exclude=focus)
        assert focus not in ids
        for j,radius in enumerate(radii):
            inside=distance<radius
            local_ids,d=ids[inside],distance[inside]
            weights=bisquare_weights(d,radius)
            fit=panel.fit(local_ids,weights)
            if fit.status=='ok':
                error=panel.within_residual(focus,fit)
                scores[i,j]=float(error@error/panel.t)
                if i%100==0 and j in [0,20,45]:
                    q,t=panel.qr_reference(local_ids,weights)
                    delta=float(np.max(abs(fit.beta-q)))
                    assert np.allclose(fit.beta,q,rtol=1e-7,atol=1e-8)
                    assert np.allclose(fit.time_effect,t,rtol=1e-7,atol=1e-8)
                    references.append(dict(mesh=codes[focus],radius_km=float(radius),coefficient_max_difference=delta))
            records.append({'Mesh Code':codes[focus],'Primary Tile':centers.iloc[i]['Primary Tile'],
                'Validation Weight':float(centers.iloc[i]['Validation Weight']),'Bandwidth km':float(radius),
                'Within Change MSE':float(scores[i,j]),'Training Meshes':fit.positive_meshes,
                'Effective Training Meshes':fit.effective_meshes,'Fit Status':fit.status,'Failure Reason':fit.reason})
        if (i+1)%100==0 or i==len(focus_ids)-1:
            print(f'Search centers {i+1}/{len(focus_ids)}; elapsed {time.monotonic()-start:.1f}s',flush=True)
    ledger=pd.DataFrame(records); ledger.to_parquet(OUT/'bandwidth_center_ledger.parquet',index=False)
    common=np.isfinite(scores).all(axis=1)
    centers['Common Estimable']=common
    centers.to_csv(OUT/'validation_centers.csv',index=False)
    np.save(OUT/'validation_mse.npy',scores)
    rows=[]
    sw=centers['Validation Weight'].to_numpy()
    for j,radius in enumerate(radii):
        complete=np.isfinite(scores[:,j])
        rows.append({'Bandwidth km':radius,'Validation Centers':len(centers),
            'Successful Centers':int(complete.sum()),'Failed Centers':int((~complete).sum()),
            'Common Validation Centers':int(common.sum()),
            'Common Weighted Within MSE':float(np.average(scores[common,j],weights=sw[common])) if common.any() else np.nan,
            'Common Weight Coverage':float(sw[common].sum()/sw.sum()),
            'All Center Score Valid':bool(complete.all())})
    summary=pd.DataFrame(rows); summary.to_csv(OUT/'bandwidth_search.csv',index=False)
    assert all(sha(ROOT/p)==h for p,h in before.items())
    report=dict(status='passed',phase='search',periods=contract['periods'],national_meshes=len(codes),
        validation_centers=len(centers),validation_primary_tiles=int(centers['Primary Tile'].nunique()),
        candidate_radii_km=radii.tolist(),common_validation_centers=int(common.sum()),
        common_weight_coverage=float(sw[common].sum()/sw.sum()),
        whole_mesh_leave_out=True,training_only_local_time_absorption=True,approximate_cv=True,
        sampling='fixed seed 20261009, primary-tile strata, at least four centers per populated tile when available, proportional allocation',
        score_weights='tile mesh count divided by selected tile center count; common-set score is conditional on retained centers',
        separate_candidate_failure_counts=True,selection_pending_common_validation_policy=True,
        empirical_nationwide_fits_started=False,qr_reference_checks=references,
        protected_sha256=before,protected_files_unchanged=True,elapsed_seconds=time.monotonic()-start)
    (OUT/'search_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(summary.to_string(index=False),flush=True)
    print('Saved search ledger; no bandwidth selected until failure policy confirmation.',flush=True)


def select():
    policy=json.loads((PLAN/'execution_contract.json').read_text())
    assert policy['common_validation_policy_confirmed']
    summary=pd.read_csv(ROOT/policy.get('bandwidth_search_input','data/exp/gwpr-twoways/bandwidth_search.csv'))
    expanded='Expanded Common Validation Centers' in summary.columns
    count_column='Expanded Common Validation Centers' if expanded else 'Common Validation Centers'
    score_column='Expanded Common Weighted Within MSE' if expanded else 'Common Weighted Within MSE'
    coverage_column='Expanded Common Weight Coverage' if expanded else 'Common Weight Coverage'
    assert summary[count_column].min()>0
    values=summary[score_column].to_numpy()
    assert np.isfinite(values).all()
    human_radius=policy.get('human_selected_bandwidth_km')
    if human_radius is None:
        j=int(np.argmin(values))
    else:
        matching=np.flatnonzero(summary['Bandwidth km'].to_numpy()==human_radius)
        assert len(matching)==1
        j=int(matching[0])
    best=float(summary.iloc[j]['Bandwidth km'])
    selected=dict(bandwidth_km=best,selection='human-confirmed fixed distance after common-center CV' if human_radius is not None else 'minimum fixed-common-center design-weighted whole-mesh within-change CV',
        candidate_range_km=[float(summary['Bandwidth km'].min()),float(summary['Bandwidth km'].max())],step_km=1,cv_mse=float(values[j]),
        common_validation_centers=int(summary.iloc[j][count_column]),
        common_weight_coverage=float(summary.iloc[j][coverage_column]),
        search_boundary_optimum=bool(j in [0,len(values)-1]),approximate_cv=True,
        conditional_validation_support=True,original_meshes_retained=True,
        minimum_on_evaluated_grid=bool(values[j]==values.min()),
        selection_decision_id=policy.get('bandwidth_selection_decision_id',policy['common_validation_decision_id']))
    selection_path=ROOT/policy.get('selected_bandwidth_metadata','data/exp/gwpr-twoways/selected_bandwidth.json')
    selection_path.parent.mkdir(parents=True,exist_ok=True)
    selection_path.write_text(json.dumps(selected,indent=2)+'\n')
    print(json.dumps(selected,indent=2),flush=True)


def fit(candidate_radius=None, candidate_phase="candidate_computational_benchmark"):
    policy=json.loads((PLAN/'execution_contract.json').read_text())
    if candidate_radius is None:
        assert policy['common_validation_policy_confirmed']
        selection_path=ROOT/policy.get('selected_bandwidth_metadata','data/exp/gwpr-twoways/selected_bandwidth.json')
        selected=json.loads(selection_path.read_text())
        radius=selected['bandwidth_km']
        destination=ROOT/policy.get('selected_output_directory','data/exp/gwpr-twoways')
    else:
        radius=float(candidate_radius)
        assert radius in policy['candidate_distances_km'] + policy.get('additional_candidate_distances_km', [])
        destination=OUT/f'candidate_{int(radius)}km'
    destination.mkdir(parents=True,exist_ok=True)
    start=time.monotonic()
    codes,membership,panel,index,contract,source=load_panel()
    protected=sorted((ROOT/'data/processed').rglob('*.parquet'))+sorted((ROOT/'data/results/tables').glob('*.xlsx'))
    before={str(p.relative_to(ROOT)):sha(p) for p in protected}
    batch=2000; parts=destination/'coefficient_parts'; parts.mkdir(parents=True,exist_ok=True)
    residual=np.full((len(codes),panel.t),np.nan); checks=[]; statuses={}
    for begin in range(0,len(codes),batch):
        end=min(len(codes),begin+batch); rows=[]
        for i in range(begin,end):
            ids,d=index.query(index.coordinates[i],radius)
            weights=bisquare_weights(d,radius)
            local=panel.fit(ids,weights)
            row=result_row(codes[i],index.coordinates[i],radius,local)
            rows.append(row); statuses[local.status]=statuses.get(local.status,0)+1
            if local.status=='ok':
                residual[i]=panel.within_residual(i,local)
                if i%5000==0:
                    q,t=panel.qr_reference(ids,weights)
                    assert np.allclose(local.beta,q,rtol=1e-7,atol=1e-8)
                    assert np.allclose(local.time_effect,t,rtol=1e-7,atol=1e-8)
                    checks.append(dict(mesh=codes[i],coefficient_max_difference=float(np.max(abs(local.beta-q)))))
        pd.DataFrame(rows).to_parquet(parts/f'part_{begin:06d}.parquet',index=False)
        if begin%10000==0 or end==len(codes):
            print(f'National fits {end:,}/{len(codes):,}; successes {statuses.get("ok",0):,}; elapsed {time.monotonic()-start:.1f}s',flush=True)
    paths=[parts/f'part_{begin:06d}.parquet' for begin in range(0,len(codes),batch)]
    result=pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)
    assert len(result)==len(codes) and result['Mesh Code'].tolist()==codes
    good=result['Fit Status'].eq('ok')
    assert np.isfinite(result.loc[good,['Road Density Coefficient','Population Coefficient']].to_numpy()).all()
    assert result.loc[~good,['Road Density Coefficient','Population Coefficient']].isna().all().all()
    assert result.loc[~good,'Failure Reason'].str.len().gt(0).all()
    result.to_parquet(destination/'local_coefficients.parquet',index=False)
    result.to_csv(destination/'local_coefficients.csv',index=False)
    membership['GWPR Within Residual']=residual.reshape(-1)
    membership.to_parquet(destination/'focal_residuals.parquet',index=False)
    assert all(sha(ROOT/p)==h for p,h in before.items())
    report=dict(status='passed',phase='national_fit' if candidate_radius is None else candidate_phase,national_meshes=len(codes),observations=len(membership),
        periods=contract['periods'],bandwidth_km=radius,kernel='bisquare',effects=['mesh','local time'],
        successes=int(good.sum()),failures=int((~good).sum()),failure_reasons=result.loc[~good,'Failure Reason'].value_counts().to_dict(),
        bandwidth_formally_selected=candidate_radius is None,original_meshes_retained=True,failed_coefficients_nan=True,one_radius_for_all_centers=True,
        no_radius_fallback=True,no_ridge=True,no_local_significance_test=True,
        references=checks,protected_sha256=before,protected_files_unchanged=True,
        radius_index='sorted latitude and spherical cap bounds, exact haversine radius query',
        earth_radius_km=6371.0088,dense_distance_matrix_constructed=False,
        elapsed_seconds=time.monotonic()-start)
    if candidate_radius is None:
        report['selection_metadata_path']=str(selection_path.relative_to(ROOT))
        report['selection_decision_id']=selected['selection_decision_id']
    (destination/'fit_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['references','protected_sha256']},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--stage',choices=['search','select','fit','benchmark'],required=True)
    parser.add_argument('--radius',type=float,default=5)
    args=parser.parse_args()
    if args.stage=='benchmark': fit(candidate_radius=args.radius)
    else: {'search':search,'select':select,'fit':fit}[args.stage]()
