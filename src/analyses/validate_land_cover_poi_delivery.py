"""Validate the exploratory extension delivery without updating source data."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from run_gwpr_current_bandwidth_search import sha

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/land-cover-poi-extension'


def main():
    contract = json.loads((OUT / 'execution_contract.json').read_text())
    preparation = json.loads((OUT / 'preprocessing_validation.json').read_text())
    pooled = json.loads((OUT / 'pooled_validation.json').read_text())
    search = json.loads((OUT / 'gwpr-search-3-50km/search_validation.json').read_text())
    assert preparation['status'] == pooled['status'] == search['status'] == 'passed'
    assert pooled['model_counts'] == {'national': 1, 'regional': 9, 'prefecture': 47}
    assert pooled['estimable_model_counts'] == {'national': 1, 'regional': 9, 'prefecture': 45}
    assert sha(ROOT / contract['input']) == contract['panel_sha256']
    for path, digest in preparation['protected_sha256'].items():
        assert sha(ROOT / path) == digest
    for path, digest in pooled['protected_sha256'].items():
        if path != 'docs/AnaSOP.md':
            assert sha(ROOT / path) == digest
    comparison = pd.read_csv(OUT / 'pooled_road_comparison.csv')
    assert len(comparison) == 57 and comparison['Status'].eq('ok').sum() == 55
    for family in ['national', 'regional', 'prefecture']:
        area = comparison.loc[comparison.Family.eq(family)]
        assert area.Meshes.sum() == 383386 and area.Observations.sum() == 1916930
        identified = area.Status.eq('ok')
        assert (area.loc[identified, 'Extended R Squared'] >= area.loc[identified, 'Baseline R Squared'] - 1e-12).all()
    candidates = pd.read_csv(OUT / 'gwpr-search-3-50km/bandwidth_search.csv')
    assert np.array_equal(candidates['Bandwidth km'].to_numpy(), np.arange(3, 51))
    assert candidates['Common Validation Centers'].eq(9).all()
    assert candidates['Common Weight Coverage'].nunique() == 1
    text = (ROOT / 'docs/AnaSOP.md').read_text()
    assert text.isascii()
    assert all(text.count(f'## {number}. ') == 1 for number in range(1, 9))
    assert '\\beta_{D,a(i)}' in text and 'Focused Extension Execution Checkpoint' in text
    report = dict(status='passed', decision_id=contract['decision_id'],
        national_regression='complete', regional_regressions='complete',
        prefecture_attempts=47, estimable_prefectures=45,
        nonestimable_prefectures={'Tokyo': 'Cropland Mosaic Land Cover Share is constant zero', 'Nara': 'Water Land Cover Share is constant zero'},
        expanded_gwpr_bandwidth_candidates_completed=48, expanded_full_local_fit='pending_research_decision',
        pending_choice='Whether to omit only locally constant added controls, retain their coefficient as NaN and record the omission.',
        common_cv_centers=9, common_cv_weight_coverage=search['search_minimum']['common_weight_coverage'],
        conditional_minimum_km=13, accepted_national_bandwidth=None,
        source_and_baseline_outputs_preserved=True, anasop_sections_updated=[3, 4, 5, 6, 7],
        formal_output_plan_unchanged=True, formal_extension_plan='not_selected',
        anasop_english_ascii_and_sections_validated=True,
        artifacts={p.name: sha(p) for p in OUT.glob('*.csv')},
        workbook=str((OUT / 'pooled_land_cover_poi_extension.xlsx').relative_to(ROOT)))
    (OUT / 'delivery_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    (OUT / 'README.md').write_text('# Focused land-cover and POI extension\n\n'
        'Decision: MILI-D-20261010-033. Exploratory results; original baseline data, tables and maps are preserved.\n\n'
        '## Specification and sample\n\n'
        'Nighttime Radiance on an intercept, Road Length Density, Population, five annual land-cover shares (Urban, Forest, Cropland, Cropland Mosaic, Water), '
        'Distance to Railway Station, Distance to Passenger Airport, School Facility Count, Medical Facility Count, Logistics Facility Count, and Visitor and Event Facility Count. '
        'Other Land Cover Share is retained in data as the omitted reference. In incomplete-coverage records, the omitted remainder also includes unobserved area. '
        'All variables retain original units. Static facilities repeat their actual selected source editions across five periods under the approved assumption. '
        'There are no fixed effects, imputation, logarithms or calibration.\n\n'
        'The projection contains 383,386 meshes and 1,916,930 observations, retaining 1,048,757 zero-population records and 505 flagged partial-land-cover records. '
        'Four Minamitorishima meshes lack the original source tile and are excluded only from this projection; source data preserve them with NaN. '
        'Land shares are not normalized. Baseline and extended models use identical area-specific samples.\n\n'
        '## Ordered estimation and results\n\n'
        'National and all nine regional models pass full-rank checks. Forty-seven prefectures are attempted; forty-five pass. '
        'Tokyo has a constant-zero Cropland Mosaic Land Cover Share and Nara a constant-zero Water Land Cover Share. '
        'Under the current strict rule, both complete extended vectors are non-estimable; their baseline results remain available. '
        'No constant control is silently removed. Standard errors use mesh-clustered CR1 with N-K degrees adjustment and normal 95 percent intervals. '
        'Independent original-unit least squares, cluster-score algebra, residual orthogonality, exact geographic partitions and workbook readback pass.\n\n'
        'National road density is 0.0195578 (95 percent interval 0.0157564 to 0.0233592), compared with 0.226693 in the same-sample baseline. '
        'Joint ordinary R squared rises from 0.663260 to 0.756164. These are conditional associations; adding controls does not establish causation or a mechanism. '
        'The workbook has national, regional, prefecture, road-comparison and notes sheets. CSV files preserve all estimable coefficients; JSON files retain failed-area reasons.\n\n'
        '## Expanded GWPR status\n\n'
        'All 48 fixed bisquare radii from 3 to 50 km are scored with whole-mesh five-period holdout, 1,282 surviving stratified centers and unchanged surviving expansion weights. '
        'Direct locally centered weighted SVD determines rank and coefficients, checked against expanded intercept-plus-controls weighted least squares. '
        'The common estimable comparison contains only nine centers and 0.653627 percent weighted coverage. '
        'Its conditional minimum is 13 km (MSE 10.287032; RMSE 3.207340). This is not accepted as a national bandwidth. '
        'Available-center losses have changing supports and must not rank radii. Full expanded local estimation is pending the constant-control research choice and its bandwidth-support consequences. '
        'The existing three-kilometre baseline map remains a map of the baseline, not the extension.\n\n'
        '## Reproduce locally\n\n'
        '```sh\npython3 src/preprocessing/prepare_land_cover_poi_extension.py\npython3 src/analyses/run_land_cover_poi_pooled.py\npython3 src/analyses/run_land_cover_poi_gwpr_search.py\npython3 src/analyses/validate_land_cover_poi_delivery.py\n```\n\n'
        'AnaSOP Sections 3-7 record the data scope, selected roles, specification and exploratory checkpoints. '
        'Section 8 remains the baseline formal-output plan; formal extension tables require a later planning update. '
        'A future accepted change in constant-control handling must update the execution contract and decision log before reestimation.\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
