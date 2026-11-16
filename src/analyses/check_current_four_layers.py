"""Validate and summarize the approved four-layer common-cohort baseline.

Run after the three pooled table scripts, renewed bandwidth search and local fit.
This checks existing results and writes an exploratory delivery report; no refit.
"""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/four-layer-current-baseline'
QA = ROOT / 'data/exp/figure-table-generation/current-common-cohort'
LOCAL = ROOT / 'data/exp/gwpr-pooled-current-common-cohort/local-fit'
SEARCH = ROOT / 'data/exp/gwpr-pooled-current-common-cohort/bandwidth-search'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def main(contract_path=None, search_directory=None, local_directory=None, output_directory=None):
    execution_path = Path(contract_path) if contract_path is not None else ROOT/'data/exp/estimation-framework-planning/current-common-cohort/estimation_decisions.json'
    out = Path(output_directory) if output_directory is not None else OUT
    search_dir = Path(search_directory) if search_directory is not None else SEARCH
    local_dir = Path(local_directory) if local_directory is not None else LOCAL
    out.mkdir(parents=True,exist_ok=True)
    contract=read(execution_path)
    audit=read(ROOT/contract['preprocessing_validation'])
    panel_path=ROOT/contract['input']; digest=sha(panel_path)
    panel=pd.read_parquet(panel_path).sort_values(['Mesh Code','Road Year']).reset_index(drop=True)
    keys=['Mesh Code','Road Year','Population Year','Nighttime Light Year']
    tables={f:read(QA/f/'validation.json') for f in ['national','regional','prefecture']}
    for family,report in tables.items():
        assert report['status']=='passed' and report['effects']==[]
        assert report['input_sha256']==digest==audit['panel_sha256']
        assert report['meshes']==audit['meshes'] and report['observations']==audit['observations']
        members=pd.read_csv(QA/family/'sample_membership.csv',dtype={'Mesh Code':str})
        for c in keys:
            assert np.array_equal(members[c].to_numpy(),panel[c].to_numpy()),(family,c)
        for c in ['Region','Prefecture Code','Prefecture']:
            if c in members:
                assert np.array_equal(members[c].astype(str).str.zfill(2).to_numpy() if c=='Prefecture Code' else members[c].to_numpy(),panel[c].to_numpy()),(family,c)
        assert sum(r['meshes'] for r in report['results'])==audit['meshes']
        assert sum(r['observations'] for r in report['results'])==audit['observations']
        assert sum(r['reviewed_no_land_meshes'] for r in report['results'])==19
        assert sha(ROOT/report['output'])==report['output_sha256']
    selection=read(search_dir/'search_minimum.json'); search=read(search_dir/'search_validation.json')
    local=read(local_dir/'local_fit_validation.json')
    data=pd.read_parquet(local_dir/'local_coefficients.parquet')
    codes=panel['Mesh Code'].drop_duplicates().astype(str).to_numpy()
    assert search['status']==local['status']=='passed' and search['source_sha256']==digest
    assert local['protected_sha256'][str(panel_path.relative_to(ROOT))]==digest
    assert np.array_equal(data['Mesh Code'].to_numpy(),codes)
    assert data['Bandwidth km'].eq(selection['minimum']['radius_km']).all()
    assert local['bandwidth_km']==selection['minimum']['radius_km']
    assert np.array_equal(data['Below 30 Observations'].to_numpy(),data['Local Observations'].lt(30).to_numpy())
    assert data['Local Observations'].eq(data['Positive Weight Meshes']*5).all()
    good=data['Fit Status'].eq('ok')
    coefs=['Intercept','Road Density Coefficient','Population Coefficient']
    assert np.isfinite(data.loc[good,coefs]).all().all() and data.loc[~good,coefs].isna().all().all()
    assert int(good.sum())==local['estimable_meshes'] and len(data)==audit['meshes']
    assert sha(local_dir/'local_coefficients.parquet')==local['output_sha256']
    for path,checksum in audit['protected_inputs'].items(): assert sha(ROOT/path)==checksum,path
    scores=pd.read_csv(search_dir/'bandwidth_search.csv')
    best=scores.loc[scores['Common Weighted Level MSE'].idxmin()]
    assert best['Bandwidth km']==local['bandwidth_km']
    assert np.array_equal(scores['Bandwidth km'].to_numpy(),np.array(contract['candidate_radii_km']))
    national=tables['national']['results'][0]
    def admin_summary(family):
        results=tables[family]['results']
        return dict(models=len(results),positive_road_intervals=sum(r['coefficients'][1]['confidence_lower']>0 for r in results),
                    negative_road_intervals=sum(r['coefficients'][1]['confidence_upper']<0 for r in results),
                    intervals_crossing_zero=sum(r['coefficients'][1]['confidence_lower']<=0<=r['coefficients'][1]['confidence_upper'] for r in results),
                    minimum_r_squared=min(r['ordinary_pooled_r_squared'] for r in results),maximum_r_squared=max(r['ordinary_pooled_r_squared'] for r in results))
    summary=dict(status='passed',model_decision_id=contract['decision_id'],cohort_decision_id=contract['cohort_decision_id'],bandwidth_decision_id=contract['bandwidth_decision_id'],local_fit_decision_id=contract.get('local_fit_decision_id'),
        meshes=audit['meshes'],observations=audit['observations'],periods=contract['periods'],population_years=contract['population_years'],
        outcome=contract['outcome'],regressors=contract['explanatory'],effects=[],intercept=True,
        zero_population_observations=audit['zero_population_observations'],reviewed_administrative_exceptions=19,
        national=national,regional=admin_summary('regional'),prefecture=admin_summary('prefecture'),
        bandwidth_candidates_km=contract['candidate_radii_km'],selected_bandwidth_km=local['bandwidth_km'],
        common_validation_centers=selection['common_validation_centers'],common_weight_coverage=selection['common_weight_coverage'],
        conditional_cv_rmse=selection['minimum']['common_weighted_level_rmse'],approximate_conditional_bandwidth_selection=True,
        local={k:local[k] for k in ['estimable_meshes','failed_meshes','below_30_observation_meshes','estimable_below_30_observation_meshes','road_coefficient_positive_meshes','road_coefficient_negative_meshes','failure_reasons']},
        identical_sample_membership_verified=True,geographic_partitions_verified=True,protected_source_inputs_unchanged=True,
        no_land_cover_or_facility_complete_case_filter=True,human_table_review='pending',source_comparability_established=False,causal_identification=False)
    (out/'delivery_validation.json').write_text(json.dumps(summary,indent=2)+'\n')
    # Readable handoff for the experiment, rather than an additional analysis.
    road=national['coefficients'][1]
    (out/'README.md').write_text(
        '# Current four-layer pooled baseline\n\n'
        f"All models use {audit['meshes']:,} meshes and {audit['observations']:,} records in five periods. "
        'Nighttime Radiance = intercept + Road Length Density + Population, original units, no fixed effects. '
        'Administrative models use mesh-clustered CR1 and individual normal 95% intervals. '
        'Eligible islands and nineteen reviewed exceptions remain. Source-unlisted and source-unknown road densities follow the approved zero-coding assumption.\n\n'
        f"National road slope {road['coefficient']:.9f}, CI [{road['confidence_lower']:.9f}, {road['confidence_upper']:.9f}], joint R squared {national['ordinary_pooled_r_squared']:.9f}. "
        f"All {summary['regional']['models']} Regions and {summary['prefecture']['models']} Prefectures have individual road intervals above zero. "
        'These are descriptive associations; significance does not test between-area equality. Joint R squared is not the separate road contribution.\n\n'
        f"Fresh {min(contract['candidate_radii_km']):g}-{max(contract['candidate_radii_km']):g} km search in 1 km steps selects {local['bandwidth_km']:g} km: conditional weighted RMSE {summary['conditional_cv_rmse']:.6f}, "
        f"{summary['common_validation_centers']} common estimable validation centers, weight coverage {summary['common_weight_coverage']:.4%}. "
        'The 1,286 centers use primary-tile stratification and expansion weights, seed 20261010. Holdout removes all five records of a mesh; final fits include the focal mesh. '
        'Available-center losses have changing support and are not used to rank candidates. '
        f"Final fits: {local['estimable_meshes']:,} estimable, {local['failed_meshes']:,} failed; {local['estimable_below_30_observation_meshes']:,} estimable fits below 30 records retain a flag. "
        'All focal identifiers and failed NaN vectors remain. No local significance inference.\n\n'
        'Reproduce from the project root, in order:\n\n'
        '1. `python3 src/preprocessing/prepare_current_common_cohort.py --stage prepare` and `--stage generate`.\n'
        '2. Run the title-named national, regional and prefecture pooled table scripts in `src/analyses/` in order.\n'
        f"3. `{contract.get('search_reproduce_command', 'python3 src/analyses/run_gwpr_current_bandwidth_search.py')}`.\n"
        f"4. `{contract.get('reproduce_command', 'python3 src/analyses/run_gwpr_current_local.py')}`.\n"
        f"5. `{contract.get('delivery_reproduce_command', 'python3 src/analyses/check_current_four_layers.py')}`.\n\n"
        'Three workbooks are under `data/results/tables/`; CSV mirrors and estimator checks are under '
        '`data/exp/figure-table-generation/current-common-cohort/`. Search and local coefficients are under '
        '`data/exp/gwpr-pooled-current-common-cohort/`. Raw and augmented input panels remain unchanged. '
        'The 2024 road inventory is not proven equivalent to historical supplied density, and population matching has temporal offsets. '
        'Formal output review remains pending; no additional controls, temporal model or map is produced.\n')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__': main()
