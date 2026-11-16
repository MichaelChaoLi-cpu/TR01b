"""Independent saved-output and source-preservation checks for focused GWPR."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from run_gwpr_current_bandwidth_search import sha

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / 'data/exp/land-cover-poi-extension'


def main():
    contract = json.loads((PLAN / 'gwpr_execution_contract.json').read_text())
    pointer = json.loads((PLAN / 'active_gwpr_extension.json').read_text())
    source = ROOT / contract['input']
    path = ROOT / pointer['local_coefficients']
    output = path.parent
    local = json.loads((output / 'local_fit_validation.json').read_text())
    search_directory = ROOT / pointer['search']
    search = json.loads((search_directory / 'search_validation.json').read_text())
    assert local['status'] == search['status'] == 'passed'
    assert contract['decision_id'] == local['decision_id'] == search['decision_id'] == 'MILI-D-20261010-034'
    assert sha(source) == contract['panel_sha256'] == local['source_sha256'] == search['source_sha256']
    assert sha(path) == local['output_sha256']
    for protected, digest in local['protected_sha256'].items():
        if protected != 'docs/AnaSOP.md':
            assert sha(ROOT / protected) == digest
    preparation = json.loads((PLAN / 'preprocessing_validation.json').read_text())
    for protected, digest in preparation['protected_sha256'].items():
        assert sha(ROOT / protected) == digest
    baseline = json.loads((PLAN / 'pooled_validation.json').read_text())
    for protected, digest in baseline['protected_sha256'].items():
        if protected != 'docs/AnaSOP.md':
            assert sha(ROOT / protected) == digest
    data = pd.read_parquet(path)
    source_keys = pd.read_parquet(source, columns=['Mesh Code', 'Road Year', 'Region', 'Prefecture Code', 'Prefecture', 'No Land Overlap']).sort_values(['Mesh Code', 'Road Year'])
    meshes = source_keys.drop_duplicates('Mesh Code').reset_index(drop=True)
    assert len(data) == len(meshes) == 383386
    for name in ['Mesh Code', 'Region', 'Prefecture Code', 'Prefecture', 'No Land Overlap']:
        assert np.array_equal(data[name].to_numpy(), meshes[name].to_numpy())
    good = data['Fit Status'].eq('ok').to_numpy()
    coefficients = ['Intercept', 'Road Density Coefficient', 'Population Coefficient'] + [name+' Coefficient' for name in contract['explanatory'][2:]]
    beta = data[coefficients].to_numpy(float)
    mask = data['Omitted Control Mask'].to_numpy()
    assert np.isfinite(beta[good, :3]).all() and np.isnan(beta[~good]).all()
    assert not ((mask & 3) != 0).any()
    number_omitted = np.zeros(len(data), dtype=int)
    for j in range(2, len(contract['explanatory'])):
        omitted = (mask & (1 << j)) != 0
        number_omitted += omitted
        assert np.isnan(beta[good & omitted, j+1]).all()
        assert np.isfinite(beta[good & ~omitted, j+1]).all()
        anchors = data[contract['explanatory'][j]+' Center Anchor'].to_numpy()
        offsets = data[contract['explanatory'][j]+' Center Offset'].to_numpy()
        assert np.isnan(anchors[good & omitted]).all() and np.isnan(offsets[good & omitted]).all()
    assert np.array_equal(data.loc[good, 'Retained Parameters'].to_numpy(), 14-number_omitted[good])
    assert np.array_equal(data.loc[good, 'Design Rank'].to_numpy(), 14-number_omitted[good])
    assert (data['Local Observations'] == data['Positive Weight Meshes']*5).all()
    assert (data['Below 30 Observations'] == (data['Local Observations'] < 30)).all()
    assert (data['Effective Weight Meshes'] <= data['Positive Weight Meshes']+1e-8).all()
    candidates = pd.read_csv(search_directory / 'bandwidth_search.csv')
    assert np.array_equal(candidates['Bandwidth km'].to_numpy(), np.arange(3, 51))
    selected = candidates.loc[candidates['Common Weighted Level MSE'].idxmin()]
    assert selected['Bandwidth km'] == pointer['bandwidth_km'] == 5
    assert selected['Common Validation Centers'] == 780
    assert len(search['expanded_weighted_reference_checks']) >= 100 and len(local['expanded_wls_reference_checks']) >= 10
    extremes = pd.read_csv(output / 'extreme_coefficient_reference_checks.csv')
    assert len(extremes) >= 3 and extremes['Reference Passed'].all()
    text = (ROOT / 'docs/AnaSOP.md').read_text()
    assert text.isascii() and all(text.count(f'## {i}. ') == 1 for i in range(1, 9))
    road = beta[good, 1]
    report = dict(status='passed', decision_id=contract['decision_id'], bandwidth_km=pointer['bandwidth_km'],
        meshes=len(data), estimable_meshes=int(good.sum()), failed_meshes=int((~good).sum()),
        estimable_fraction=float(good.mean()), all_target_meshes_represented=True,
        omitted_control_nan_and_mask_verified=True, mandatory_road_and_population_verified=True,
        frozen_geography_verified=True, support_and_parameter_counts_verified=True,
        source_and_pooled_outputs_preserved=True, bandwidth_candidates=48,
        common_cv_centers=780, common_cv_weight_coverage=search['search_minimum']['common_weight_coverage'],
        conditional_cv_rmse=search['search_minimum']['minimum']['Common Weighted Level RMSE'],
        road_positive=int((road > 0).sum()), road_negative=int((road < 0).sum()), road_zero=int((road == 0).sum()),
        independent_search_reference_checks=len(search['expanded_weighted_reference_checks']),
        independent_local_reference_checks=len(local['expanded_wls_reference_checks']),
        independent_extreme_reference_checks=len(extremes),
        no_local_significance_inference=True, no_causal_identification=True,
        formal_figure_table_plan_unchanged=True, anasop_sections_updated=[5, 6, 7], anasop_ascii_sections_validated=True,
        local_coefficients=pointer['local_coefficients'])
    (PLAN / 'gwpr_delivery_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    (PLAN / 'GWPR_README.md').write_text('# Completed focused GWPR extension\n\n'
        'Decision MILI-D-20261010-034. Outcome Nighttime Radiance; mandatory Road Length Density and Population; five annual land-cover shares and six static POI controls. '
        'Original units, all five periods, no fixed effects. Other Land Cover Share remains the omitted reference in data.\n\n'
        'Locally constant added controls are omitted from the numerical equation only; their coefficients remain NaN with a list and bit mask. '
        'Their constant contribution is absorbed by the local intercept. The numerical definition is range <= 1e-12 times max(1, maximum absolute training value), consistent with area-overlay precision. '
        'Source values are unchanged. Retained core predictors are never omitted. Other collinearities retain failed NaN vectors without ridge or radius fallback. '
        'Whole-mesh holdout prediction is allowed only when every omitted held-out control matches the training constant at the same tolerance.\n\n'
        f"The 3-50 km search selects 5 km on 780 common estimable centers, with weighted coverage {report['common_cv_weight_coverage']:.6%} and radiance-level RMSE {report['conditional_cv_rmse']:.6f}. "
        'This is an approximate conditional minimum. Available-center scores have changing supports and cannot rank radii. '
        'Its coverage is a sampling-weight diagnostic, not an exact nationwide fit fraction.\n\n'
        f"Final fits include each focal mesh. All {len(data):,} target meshes remain represented: {good.sum():,} estimable ({good.mean():.4%}) and {(~good).sum():,} failed. "
        'Failures and below-thirty-record flags are preserved. Local training R squared is not a national pooled or heldout fit measure. '
        'No local standard errors or significance claims are produced. Core coefficient directions are descriptive, not causal effects.\n\n'
        'Stable prediction uses Local Outcome Mean plus the sum of retained slopes times ((input - Center Anchor) - Center Offset). '
        'Anchor and offset columns are saved because adding a very small offset to a large mean can otherwise lose precision. '
        'Intercept and slope coefficients remain reported in original units.\n\n'
        'The active result paths are in `active_gwpr_extension.json`. Local failure and omission summaries accompany the coefficient parquet. '
        'Previous strict-search diagnostics, national/regional/prefecture outputs and the baseline map are preserved. '
        'The earlier map shows the baseline; a new expanded map has not been requested in this run.\n\n'
        '## Reproduce locally\n\n```sh\n'
        'python3 src/analyses/run_land_cover_poi_gwpr_search.py --contract data/exp/land-cover-poi-extension/gwpr_execution_contract.json\n'
        'python3 src/analyses/run_land_cover_poi_gwpr_local.py\n'
        'python3 src/analyses/check_gwpr_extreme_coefficients.py\n'
        'python3 src/analyses/validate_land_cover_poi_gwpr.py\n```\n\n'
        'AnaSOP Sections 5-7 record the revised local rule and execution checkpoint. These results remain exploratory outside the current formal Section 8 plan.\n')
    overview = PLAN / 'README.md'
    text = overview.read_text().replace('## Expanded GWPR status', '## Historical strict GWPR search')
    text = text.replace('Full expanded local estimation is pending the constant-control research choice and its bandwidth-support consequences.',
        'The later approved GWPR revision is complete at 5 km, with locally constant added controls unestimated and retained as NaN. See GWPR_README.md and active_gwpr_extension.json for current results.')
    text = text.replace('A future accepted change in constant-control handling must update the execution contract and decision log before reestimation.',
        'The GWPR-only constant-control revision is recorded as MILI-D-20261010-034; pooled results remain under their strict rule.')
    overview.write_text(text)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
