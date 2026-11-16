"""Reproduce the human-approved UMD pooled and geographically weighted rerun.

Stages: prepare, pooled, search, local, finalize. Outputs are exploratory;
existing formal figures and tables retain their source identity.
"""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS'):
    os.environ[name] = '1'
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import time
import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from gwpr_pooled import RadiusIndex, mesh_centroids, bisquare_weights
from gwpr_umd_identified import fit, predict, expanded_reference

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/umd-four-layer'
SOURCE = ROOT / 'data/processed/national/modis_umd/association_candidate_panel_preprocessed.parquet'
DECISION = 'MILI-D-20261011-020'
CORE = ['Road Length Density', 'Population']
LAND = ['Urban Land Cover Share', 'Forest Land Cover Share', 'Cropland Land Cover Share',
        'Shrublands and Grasslands', 'Barren']
POI = ['Distance to Railway Station', 'Distance to Passenger Airport', 'School Facility Count',
       'Medical Facility Count', 'Logistics Facility Count', 'Visitor and Event Facility Count']
EXPLANATORY = CORE+LAND+POI
YEARS = [2002, 2003, 2004, 2010, 2024]
POP_YEARS = [2000, 2005, 2005, 2010, 2020]
INPUT = OUT / 'inputs/model_panel.parquet'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(value), indent=2, allow_nan=False)+'\n')


def load_panel():
    contract = json.loads((OUT/'execution_contract.json').read_text())
    assert contract['confirmed'] and sha(INPUT) == contract['panel_sha256']
    panel = pd.read_parquet(INPUT)
    assert len(panel) == contract['observations']
    return contract, panel


def plan():
    """Apply the responsible skills' narrow documentation revisions only."""
    path = ROOT/'docs/AnaSOP.md'
    original = path.read_text()
    (OUT/'AnaSOP_before_umd_analysis.txt').write_text(original)
    pieces = re.split(r'(?=^## [1-8]\. )', original, flags=re.M)
    sections = {int(re.match(r'## (\d)', s)[1]): s for s in pieces if s.startswith('## ')}
    section = sections[4]
    historical, candidate = section.split('### Confirmed UMD Land-Cover Reconstruction', 1)
    # Update the current-variable table while retaining preceding construction history.
    start = historical.index('### Confirmed Active Analytical Variables')
    old_part, active_part = historical[:start], historical[start:]
    active_part = active_part.replace('Cropland Mosaic Land Cover Share', 'Shrublands and Grasslands')
    active_part = active_part.replace('Other Land Cover Share', 'Barren')
    active_part = active_part.replace('confirmed cropland mosaic land-cover category', 'confirmed UMD classes 6-10')
    active_part = active_part.replace('confirmed other land-cover category', 'confirmed UMD class 15')
    active_part = active_part.replace('Barren | Barren | retained reference', 'Barren | Barren | control')
    active_part = active_part.replace('Water Land Cover Share | Water Land Cover Share | control',
                                    'Water Land Cover Share | Water Land Cover Share | omitted reference')
    active_part = active_part.replace('retain Other and incomplete coverage. Other is omitted from the focused equation.',
                                    'retain Barren and incomplete coverage. Water Land Cover Share is omitted from the focused equation.')
    active_part = active_part.replace('This subsection defines the active formal roles;',
                                    'UMD roles below revise the panel variables under the latest user decision. The descriptive mismatch and municipal constructs retain their earlier IGBP context until separately reconciled. This subsection defines the active formal roles;')
    candidate = candidate.replace('Candidate control; model role TBD', 'control')
    candidate = candidate.replace('Water Land Cover Share | Water Land Cover Share | control',
                                  'Water Land Cover Share | Water Land Cover Share | omitted reference')
    candidate = candidate.replace('Existing estimates, figure inputs and Sections 5-8 still document the earlier IGBP analysis. Model roles, a reference category and the handling of geographically constant controls require estimation-plan reconciliation before those outputs are recomputed. No regression or figure is regenerated by this preprocessing step.',
        'Water Land Cover Share is the confirmed reference in the UMD extension. The five other shares and the six previously selected facilities enter the equation. Constant or redundant added controls may be omitted while their slopes remain unavailable; unidentified mandatory roads or population invalidate a fit. Sections 5-7 describe the authorized rerun. Existing figures and the mismatch/municipal constructs retain their earlier IGBP inputs pending separate regeneration or reconciliation.')
    sections[4] = old_part+active_part+'### Confirmed UMD Land-Cover Reconstruction'+candidate
    s = sections[5]
    s = s.replace('Administrative extensions retain the complete-model rank rule. Constant predictors or deficient rank leave the vector unavailable. Existing Tokyo and Nara failures remain alongside their baseline estimates. The local model uses the approved expanded five-kilometre bisquare specification. Only locally constant added controls may be omitted; roads and population stay mandatory. Omitted slopes remain unavailable and constant contributions enter the intercept. Other rank failures remain unavailable. No ridge, fallback radius, other predictor deletion or local significance procedure is introduced.',
        'The UMD rerun uses Water Land Cover Share as the omitted reference. Administrative and local fits omit constant or redundant added controls only, retain their coefficient values as unavailable, and record the omitted terms. A nuisance-control basis preserves the complete supported control column space. Mandatory Road Length Density and Population must remain identifiable conditional on that space; otherwise the coefficient vector is unavailable. No arbitrary core slope is assigned by deleting a conflicting control. GWPR repeats the approved three-to-fifty-kilometre integer grouped holdout search and fits the selected fixed-distance bisquare radius. No ridge, fallback radius or local significance procedure is introduced.')
    s = s.replace('Existing validated estimates can support formal rendering after provenance checks.',
        'Earlier IGBP estimates are retained for provenance. New UMD regression estimates must pass validation before they supply formal regression figures and tables. Mismatch, land-context and municipal outputs still refer to the earlier IGBP screen; this four-layer rerun does not silently reinterpret them as UMD results.')
    sections[5] = s
    s = sections[6]
    s = s.replace('Urban Land Cover Share, Forest Land Cover Share, Cropland Land Cover Share, Cropland Mosaic Land Cover Share and Water Land Cover Share',
                  'Urban Land Cover Share, Forest Land Cover Share, Cropland Land Cover Share, Shrublands and Grasslands and Barren')
    s = s.replace('Other Land Cover Share is the omitted reference', 'Water Land Cover Share is the omitted reference')
    s = s.replace('parameter count including intercept: three or fourteen. Cluster all five mesh records together, use normal 95 percent intervals and preserve failed complete-model vectors.',
        'the actual retained parameter count including intercept: three in the baseline and at most fourteen in the extension. Cluster all five mesh records together, use normal 95 percent intervals and preserve unidentified core-model vectors. Omitted constant or redundant control slopes and their intervals remain unavailable.')
    s = s.replace('K_b', 'K_{a,b}')
    s = s.replace('Retain Tokyo and Nara with explanations.',
                  'Attempt all forty-seven Prefectures, including Tokyo and Nara, under the confirmed constant/redundant-control rule.')
    s = s.replace('Attempt all forty-seven Prefectures, including Tokyo and Nara, under the confirmed constant/redundant-control rule.',
        'Attempt all forty-seven Prefectures, including Tokyo and Nara, under the confirmed constant/redundant-control rule. When an additional control is redundant, retained nuisance coefficients are parameters of the selected basis and do not all have a common water-reference interpretation. Roads and population are reported only when uniquely identifiable against the complete nuisance span.')
    s = s.replace('An added control is constant when its range', 'An added control is constant when its range')
    s = s.replace('Constant mandatory predictors and other rank failures leave fits unavailable.',
        'Build a deterministic independent nuisance basis in the listed control order using twice-reorthogonalized residuals. A normalized residual norm at most \\(10^{-10}\\) denotes redundant information. Keep omitted slopes unavailable. Constant mandatory predictors or a rank-deficient retained design leave fits unavailable. This preserves the nuisance span rather than resolving core/control aliasing by dropping a substantive control.')
    s = s.replace('The completed integer search over three to fifty kilometres held out',
                  'Repeat the integer search over three to fifty kilometres, holding out')
    s = s.replace('validation mesh and compared:', 'validation mesh and comparing:')
    s = s.replace('A held-out control differing from an omitted training constant leaves prediction unavailable.',
        'A held-out control differing from an omitted training constant or affine redundancy relation leaves prediction unavailable. Use the same predictable center set for all radii, retain tile-expansion weights and report the fraction of validation support represented.')
    begin = s.index('Reuse the completed search:')
    end = s.index('### Accepted Comparable-Context Screen', begin)
    s = s[:begin]+('The earlier five-kilometre selection and IGBP support counts are historical. The UMD bandwidth and national coefficient surface are pending the authorized rerun. Retain all 383,386 focal meshes, including failures and fewer-than-thirty-record support flags; report positive-weight and effective-weight meshes separately. Local Road Associations across Japan uses coefficient and support panels. No local significance inference is selected. Local training fit differs from national pooled fit and validation error.\n\n')+s[end:]
    sections[6] = s
    s = sections[7]
    s = s.replace('Existing numerical evidence is available; formal review remains pending.',
                  'UMD regression evidence is being recomputed; earlier IGBP numerical evidence is historical and formal review remains pending.')
    s = s.replace('Variation supported descriptively; two extended fits unavailable; no formal difference test',
                  'UMD variation assessment pending; all forty-seven Prefectures attempted; no formal difference test')
    s = s.replace('Completed validation and five-kilometre local model',
                  'Repeated three-to-fifty-kilometre holdout validation and selected UMD local model')
    s = s.replace('Retain Tokyo and Nara failures and six-column tables.',
                  'Use UMD control bases for all Prefectures, including Tokyo and Nara; retain omission/failure records and six-column tables.')
    s = s.replace('The local map uses expanded five-kilometre coefficients, not the earlier core-only three-kilometre surface.',
                  'The next local map uses the newly validated expanded UMD surface at its selected radius. Earlier IGBP and core-only surfaces retain their original identity.')
    s = s.replace('No new briefing, estimator, control or search is needed.',
                  'The authorized UMD regression rerun must validate the nuisance-basis estimator and repeat the bandwidth search. Earlier mismatch and municipal context outputs require later UMD reconciliation and are outside this regression-only execution.')
    sections[7] = s
    s = sections[8]
    s = s.replace('Cropland Mosaic Land Cover Share', 'Shrublands and Grasslands')
    # Add Barren to regression variable lists without losing the retained water reference.
    s = s.replace('Shrublands and Grasslands, Water Land Cover Share',
                  'Shrublands and Grasslands, Barren, Water Land Cover Share')
    s = s.replace('Retain Tokyo and Nara with unavailable extended estimates and explain the constant-control limitations in table notes.',
                  'Attempt Tokyo and Nara under the approved UMD constant/redundant-control rule; disclose omitted controls and any remaining unavailable core estimates in table notes.')
    s = s.replace('verify the current extended five-kilometre fit',
                  'verify the newly selected extended UMD fit')
    s = s.replace('including Other Land Cover Share as a retained reference rather than an additional term in the extended equation.',
                  'including Barren as a control and Water Land Cover Share as the omitted reference. Earlier descriptive mismatch and municipal fields retain their IGBP context pending a separate update.')
    sections[8] = s
    updated = pieces[0]+''.join(sections[k] for k in range(1, 9))
    # Research objective, conceptual direction and data overview are untouched.
    assert all(re.split(r'(?=^## [1-8]\. )', updated, flags=re.M)[k] == pieces[k] for k in [1, 2, 3])
    assert '| done |' in sections[8]
    path.write_text(updated)
    dump(OUT/'planning_validation.json', dict(status='passed', decision_id=DECISION,
        sections_updated=[4, 5, 6, 7, 8], objective_and_data_overview_unchanged=True,
        existing_completed_basic_figure_preserved=True, new_reference='Water Land Cover Share',
        screened_and_municipal_evidence_not_reinterpreted_as_umd=True))


def prepare():
    OUT.mkdir(parents=True, exist_ok=True); (OUT/'inputs').mkdir(exist_ok=True)
    delivery = json.loads((ROOT/'data/exp/data-preprocessing/modis-umd/delivery_validation.json').read_text())
    assert delivery['status'] == 'passed' and sha(SOURCE) == delivery['outputs'][2]['sha256']
    panel = pd.read_parquet(SOURCE).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    bad_codes = panel.loc[~np.isfinite(panel[EXPLANATORY+['Water Land Cover Share', 'Nighttime Radiance']]).all(axis=1), 'Mesh Code'].unique()
    assert set(bad_codes) == {'36533738', '36533747', '36533748', '36533758'}
    panel = panel.loc[~panel['Mesh Code'].isin(bad_codes)].reset_index(drop=True)
    n = panel['Mesh Code'].nunique()
    assert n == 383386 and len(panel) == n*5 == 1916930
    assert not panel.duplicated(['Mesh Code', 'Road Year']).any()
    assert np.array_equal(panel['Road Year'].to_numpy().reshape(n, 5), np.tile(YEARS, (n, 1)))
    assert np.array_equal(panel['Population Year'].to_numpy().reshape(n, 5), np.tile(POP_YEARS, (n, 1)))
    old = pd.read_parquet(ROOT/'data/processed/national/association_spatial_heterogeneity/panel_preprocessed.parquet').sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    compare = ['Mesh Code', 'Road Year', 'Nighttime Radiance']+CORE+POI+['Region', 'Prefecture Code', 'Prefecture']
    pd.testing.assert_frame_equal(panel[compare], old[compare])
    panel.to_parquet(INPUT, index=False, compression='zstd')
    pd.testing.assert_frame_equal(panel, pd.read_parquet(INPUT))
    contract = dict(confirmed=True, decision_id=DECISION, classification='UMD', outcome='Nighttime Radiance',
        source=str(SOURCE.relative_to(ROOT)), source_sha256=sha(SOURCE), input=str(INPUT.relative_to(ROOT)), panel_sha256=sha(INPUT),
        explanatory=EXPLANATORY, mandatory_explanatory=CORE, land_cover_reference='Water Land Cover Share',
        poi_controls=POI, effects=[], intercept=True, original_units=True, periods=YEARS, population_years=POP_YEARS,
        meshes=n, observations=len(panel), zero_population_observations=int(panel.Population.eq(0).sum()),
        excluded_missing_land_cover_meshes=sorted(bad_codes), excluded_records=20,
        same_sample_baseline_and_extension=True, original_umd_source_rows_not_deleted=True,
        exact_prior_non_land_cover_values_verified=True, constant_and_redundant_controls='omit_with_nan_coefficient',
        constant_tolerance=1e-12, nuisance_redundancy_tolerance=1e-10, retained_singular_square_tolerance=1e-12,
        redundancy_basis_order=LAND+POI, mandatory_core_aliasing='fit_unavailable',
        candidate_radii_km=list(range(3, 51)), kernel='Fixed-distance bisquare; great-circle mesh centroids',
        whole_mesh_holdout=True, identical_estimable_centers_for_bandwidth_comparison=True,
        full_national_local_fit_authorized=True, local_inference=False, covariance='Mesh-clustered CR1; normal 95 percent intervals',
        protected_source_sha256={str(SOURCE.relative_to(ROOT)): sha(SOURCE),
            'data/processed/national/association_spatial_heterogeneity/panel_preprocessed.parquet':
                sha(ROOT/'data/processed/national/association_spatial_heterogeneity/panel_preprocessed.parquet')})
    dump(OUT/'execution_contract.json', contract)
    plan()
    print('UMD execution prepared:', n, 'meshes;', len(panel), 'observations; water reference.', flush=True)


def pooled_fit(sample, names):
    raw = sample[['Nighttime Radiance']+names].to_numpy(float)
    g, t = sample['Mesh Code'].nunique(), 5
    fitted = fit(raw, np.ones(g), t)
    result = dict(status=fitted.status, reason=fitted.reason, meshes=g, observations=len(sample),
        omitted_constant_controls=np.asarray(names)[fitted.constant].tolist(),
        omitted_redundant_controls=np.asarray(names)[fitted.redundant].tolist(), rank=fitted.rank,
        coefficients=[], ordinary_pooled_r_squared=None)
    if fitted.status != 'ok':
        return result
    active = fitted.active; k = len(active)+1; n = len(raw)
    centered = (raw[:, 1:][:, active]-fitted.anchor[active])-fitted.offset[active]
    prediction = fitted.center_y+centered@fitted.beta[active+1]
    residual = raw[:, 0]-prediction
    x = np.column_stack([np.ones(n), centered/fitted.norms[active]])
    bread = np.linalg.inv(x.T@x)
    scores = np.einsum('gtk,gt->gk', x.reshape(g, t, k), residual.reshape(g, t))
    cr1 = g/(g-1)*(n-1)/(n-k)
    covariance = cr1*bread@(scores.T@scores)@bread
    transform = np.eye(k)
    transform[0, 1:] = -(fitted.anchor[active]+fitted.offset[active])/fitted.norms[active]
    transform[1:, 1:] = np.diag(1/fitted.norms[active])
    covariance = transform@covariance@transform.T
    se = np.sqrt(np.maximum(np.diag(covariance), 0))
    assert np.isfinite(se).all() and (se > 0).all()
    reference_prediction, reference_slopes = expanded_reference(raw, np.ones(g), fitted)
    np.testing.assert_allclose(reference_prediction, prediction, rtol=1e-7, atol=1e-7)
    np.testing.assert_allclose(reference_slopes, fitted.beta[active+1], rtol=1e-6, atol=1e-8)
    orthogonality = float(np.max(abs(x.T@residual)/(np.linalg.norm(x, axis=0)*np.linalg.norm(residual))))
    assert orthogonality < 1e-9
    beta = fitted.beta[np.r_[0, active+1]]
    for name in ['Intercept']+names:
        j = (['Intercept']+names).index(name)
        retained_position = np.flatnonzero(np.r_[0, active+1] == j)
        if len(retained_position):
            pos = retained_position[0]; b, s = float(beta[pos]), float(se[pos])
            result['coefficients'].append(dict(variable=name, coefficient=b, clustered_standard_error=s,
                confidence_lower=b-1.959963984540054*s, confidence_upper=b+1.959963984540054*s,
                p_value=math.erfc(abs(b/s)/np.sqrt(2)), status='estimated'))
        else:
            result['coefficients'].append(dict(variable=name, coefficient=None, clustered_standard_error=None,
                confidence_lower=None, confidence_upper=None, p_value=None, status='omitted_unidentified_control'))
    tss = float(((raw[:, 0]-raw[:, 0].mean())**2).sum()); rss = float(residual@residual)
    result.update(parameters=k, scaled_design_condition=fitted.condition, cr1_factor=cr1,
        rss=rss, outcome_tss=tss, ordinary_pooled_r_squared=1-rss/tss,
        covariance_retained=covariance.tolist(), retained_terms=np.asarray(['Intercept']+names)[np.r_[0, active+1]].tolist(),
        original_unit_wls_prediction_maximum_difference=float(abs(reference_prediction-prediction).max()),
        residual_orthogonality=orthogonality)
    return result


def pooled():
    contract, panel = load_panel()
    families = [('national', [('Japan', panel)]), ('regional', list(panel.groupby('Region', sort=True))),
                ('prefecture', list(panel.groupby(['Prefecture Code', 'Prefecture'], sort=True)))]
    comparisons, summaries, frames = [], {}, {}
    wb = Workbook(); wb.remove(wb.active)
    for family, groups in families:
        results, rows = [], []
        for label, subset in groups:
            subset = subset.sort_values(['Mesh Code', 'Road Year'])
            label = ' / '.join(map(str, label)) if isinstance(label, tuple) else str(label)
            baseline, extended = pooled_fit(subset, CORE), pooled_fit(subset, EXPLANATORY)
            assert baseline['status'] == 'ok'
            results.append(dict(group=label, baseline_same_sample=baseline, extended=extended))
            for spec, estimate in [('Baseline', baseline), ('Extended', extended)]:
                for coefficient in estimate['coefficients']:
                    rows.append(dict(Group=label, Specification=spec, **coefficient,
                        Meshes=estimate['meshes'], Observations=estimate['observations'],
                        **{'R Squared': estimate['ordinary_pooled_r_squared']}))
            b = next(c for c in baseline['coefficients'] if c['variable']=='Road Length Density')
            e = next((c for c in extended['coefficients'] if c['variable']=='Road Length Density'), {})
            comparisons.append(dict(Family=family, Group=label, Status=extended['status'], Meshes=extended['meshes'],
                Observations=extended['observations'], **{'Baseline Road Coefficient': b['coefficient'],
                'Baseline Road SE': b['clustered_standard_error'], 'Baseline Road Lower 95': b['confidence_lower'],
                'Baseline Road Upper 95': b['confidence_upper'], 'Baseline R Squared': baseline['ordinary_pooled_r_squared'],
                'Extended Road Coefficient': e.get('coefficient'), 'Extended Road SE': e.get('clustered_standard_error'),
                'Extended Road Lower 95': e.get('confidence_lower'), 'Extended Road Upper 95': e.get('confidence_upper'),
                'Extended Road p Value': e.get('p_value'), 'Extended R Squared': extended['ordinary_pooled_r_squared'],
                'Omitted Constant Controls': '; '.join(extended['omitted_constant_controls']),
                'Omitted Redundant Controls': '; '.join(extended['omitted_redundant_controls'])}))
            print(f"UMD {family}: {label}; {extended['status']}; road={e.get('coefficient')}; R2={extended['ordinary_pooled_r_squared']}", flush=True)
        assert len(results) == {'national': 1, 'regional': 9, 'prefecture': 47}[family]
        assert sum(r['extended']['meshes'] for r in results) == contract['meshes']
        assert sum(r['extended']['observations'] for r in results) == contract['observations']
        frame = pd.DataFrame(rows)
        frames[family] = frame
        frame.to_csv(OUT/f'{family}_coefficients.csv', index=False)
        dump(OUT/f'{family}_validation.json', dict(status='passed', results=results))
        summaries[family] = dict(attempted=len(results), estimated=sum(r['extended']['status']=='ok' for r in results))
        ws = wb.create_sheet(family)
        ws.append(frame.columns.tolist())
        for row in frame.itertuples(index=False, name=None):
            ws.append([None if pd.isna(v) else v for v in row])
        ws.freeze_panes='C2'; ws.auto_filter.ref=ws.dimensions
    comparison = pd.DataFrame(comparisons)
    frames['road comparison'] = comparison
    comparison.to_csv(OUT/'pooled_road_comparison.csv', index=False)
    ws = wb.create_sheet('road comparison'); ws.append(comparison.columns.tolist())
    for row in comparison.itertuples(index=False, name=None):
        ws.append([None if pd.isna(v) else v for v in row])
    notes = wb.create_sheet('Notes')
    for line in ['UMD; Water Land Cover Share omitted; five land shares and six focused POI controls.',
        'Five periods: 2002, 2003, 2004, 2010, 2024; census: 2000, 2005, 2005, 2010, 2020.',
        'Original-unit pooled OLS with intercept; no mesh or time fixed effects.',
        'Identical baseline/extended complete-case cohort. Four source-unavailable meshes excluded from estimation only.',
        'Mesh-clustered CR1 with actual retained rank; normal 95% intervals; no multiple-testing adjustment.',
        'Omitted constant/redundant control coefficients are unavailable, never estimated zeros.',
        'Mandatory road and population identifiability is checked against the complete nuisance span.',
        'UMD proportions remain unnormalized when source coverage is partial; conditional association, no causal effect.']:
        notes.append([line])
    path = OUT/'pooled_umd_results.xlsx'; wb.save(path)
    check = load_workbook(path, data_only=True)
    for family in ['national', 'regional', 'prefecture', 'road comparison']:
        frame = frames[family]
        assert check[family].max_row == len(frame)+1
        assert next(check[family].values) == tuple(frame.columns)
        for expected, actual in zip(frame.itertuples(index=False, name=None),
                                    check[family].iter_rows(min_row=2, values_only=True), strict=True):
            for a, b in zip(expected, actual, strict=True):
                if pd.isna(a):
                    assert b is None
                elif isinstance(a, (int, float)):
                    assert np.isclose(a, b, rtol=1e-12, atol=1e-12)
                else:
                    assert a == b
    dump(OUT/'pooled_validation.json', dict(status='passed', decision_id=DECISION, model_counts=summaries,
        meshes=contract['meshes'], observations=contract['observations'], effects=[], same_sample_verified=True,
        clustered_covariance_with_actual_parameter_count=True, expanded_wls_reference_verified=True,
        exact_region_and_prefecture_partitions_verified=True, workbook_readback_verified=True,
        input_sha256=sha(INPUT)))


def spatial_input():
    contract, panel = load_panel()
    meshes = panel.drop_duplicates('Mesh Code')[['Mesh Code', 'Region', 'Prefecture Code', 'Prefecture', 'No Land Overlap']].reset_index(drop=True)
    values = panel[['Nighttime Radiance']+EXPLANATORY].to_numpy(float).reshape(len(meshes), 5, 14)
    coordinates = mesh_centroids(meshes['Mesh Code'].astype(str).to_numpy())
    return contract, meshes, values, coordinates, RadiusIndex(coordinates)


def search():
    assert json.loads((OUT/'pooled_validation.json').read_text())['status']=='passed'
    start = time.monotonic(); output=OUT/'bandwidth-search-3-50km'; output.mkdir(exist_ok=True)
    contract, meshes, values, coordinates, index = spatial_input()
    centers_source = ROOT/'data/exp/gwpr-pooled-current-common-cohort/bandwidth-search-3-50km/validation_centers_input.csv'
    centers = pd.read_csv(centers_source, dtype={'Mesh Code': str})
    centers = centers.loc[centers['Mesh Code'].isin(meshes['Mesh Code'])].reset_index(drop=True)
    assert len(centers)==1282
    expansion = centers['Validation Weight'].to_numpy(float)
    assert np.isclose(expansion.sum(),len(meshes))
    centers.to_csv(output/'validation_centers_input.csv', index=False)
    lookup = {code:i for i,code in enumerate(meshes['Mesh Code'])}
    radii = np.asarray(contract['candidate_radii_km'], float)
    losses = np.full((len(centers), len(radii)), np.nan)
    ledger, references = [], []
    for row, code in enumerate(centers['Mesh Code']):
        focus=lookup[code]
        ids, distances=index.query(coordinates[focus],50,exclude=focus)
        assert focus not in ids
        order=np.argsort(distances,kind='stable'); ids,distances=ids[order],distances[order]
        for j,radius in enumerate(radii):
            count=np.searchsorted(distances,radius,side='left')
            local_ids=ids[:count]; weights=bisquare_weights(distances[:count],radius)
            raw=values[local_ids].reshape(-1,14)
            fitted=fit(raw,weights)
            prediction=predict(values[focus,:,1:],fitted)
            status,reason=fitted.status,fitted.reason
            if fitted.status=='ok' and prediction is None:
                status,reason='unpredictable','heldout_control_outside_training_constant_or_affine_relation'
            elif prediction is not None:
                losses[row,j]=float(np.mean((values[focus,:,0]-prediction)**2))
                if row%100==0 and radius in [3,10,25,50]:
                    reference,slopes=expanded_reference(raw,weights,fitted)
                    np.testing.assert_allclose(slopes,fitted.beta[fitted.active+1],rtol=1e-5,atol=1e-8)
                    fitted_prediction=fitted.center_y+((raw[:,1:][:,fitted.active]-fitted.anchor[fitted.active])-fitted.offset[fitted.active])@fitted.beta[fitted.active+1]
                    np.testing.assert_allclose(reference,fitted_prediction,rtol=1e-7,atol=1e-7)
                    references.append(dict(mesh=code,bandwidth_km=radius,maximum_prediction_difference=float(abs(reference-fitted_prediction).max())))
            ledger.append({'Mesh Code':code,'Bandwidth km':radius,'Fit Status':status,'Failure Reason':reason,
                'Level Prediction MSE':losses[row,j],'Training Meshes':count,'Training Records':count*5,
                'Below 30 Records':count*5<30,'Retained Parameters':len(fitted.active)+1,'Design Rank':fitted.rank,
                'Omitted Constant Controls':'; '.join(np.asarray(EXPLANATORY)[fitted.constant]),
                'Omitted Redundant Controls':'; '.join(np.asarray(EXPLANATORY)[fitted.redundant])})
        if (row+1)%50==0 or row+1==len(centers):
            print(f'UMD bandwidth search: {row+1}/{len(centers)} centers; {time.monotonic()-start:.1f}s',flush=True)
    common=np.isfinite(losses).all(1); coverage=float(expansion[common].sum()/expansion.sum())
    assert common.any()
    summary=[]
    for j,radius in enumerate(radii):
        valid=np.isfinite(losses[:,j]); mse=float(np.average(losses[common,j],weights=expansion[common]))
        summary.append({'Bandwidth km':radius,'Validation Centers':len(centers),'Successful Centers':int(valid.sum()),
            'Successful Weight Coverage':float(expansion[valid].sum()/expansion.sum()),
            'Common Validation Centers':int(common.sum()),'Common Weight Coverage':coverage,
            'Common Weighted Level MSE':mse,'Common Weighted Level RMSE':np.sqrt(mse),
            'Available Center Weighted Level MSE':float(np.average(losses[valid,j],weights=expansion[valid]))})
    table=pd.DataFrame(summary); table.to_csv(output/'bandwidth_search.csv',index=False)
    detail=pd.DataFrame(ledger); detail.to_parquet(output/'center_radius_validation.parquet',index=False)
    pd.testing.assert_frame_equal(detail,pd.read_parquet(output/'center_radius_validation.parquet'))
    centers['Common Estimable Support']=common; centers.to_csv(output/'validation_centers.csv',index=False)
    np.save(output/'validation_mse.npy',losses)
    best=table.loc[table['Common Weighted Level MSE'].idxmin()].to_dict()
    selection=dict(status='completed',minimum=best,candidate_radii_km=radii,
        common_validation_centers=int(common.sum()),common_weight_coverage=coverage,
        at_search_boundary=bool(best['Bandwidth km'] in [3,50]),approximate_conditional_cv=True,
        national_optimum_established=False)
    dump(output/'search_minimum.json',selection)
    dump(output/'search_validation.json',dict(status='passed',decision_id=DECISION,seconds=time.monotonic()-start,
        input_sha256=sha(INPUT),centers_source_sha256=sha(centers_source),whole_mesh_holdout_verified=True,
        identical_estimable_support_verified=True,constant_and_affine_holdout_checks=True,
        expanded_wls_reference_checks=references,readback_verified=True))
    print('UMD selected bandwidth',best['Bandwidth km'],'km; common weight coverage',coverage,flush=True)


def local():
    selection=json.loads((OUT/'bandwidth-search-3-50km/search_minimum.json').read_text())
    assert selection['status']=='completed'
    radius=float(selection['minimum']['Bandwidth km'])
    output=OUT/f'local-fit-{radius:g}km'; output.mkdir(exist_ok=True)
    start=time.monotonic()
    contract,meshes,values,coordinates,index=spatial_input()
    n=len(meshes); beta=np.full((n,14),np.nan); outcome=np.full(n,np.nan)
    anchors=np.full((n,13),np.nan); offsets=np.full((n,13),np.nan)
    support=np.zeros(n,np.int32); ranks=np.zeros(n,np.int8); retained=np.zeros(n,np.int8)
    effective=np.full(n,np.nan); conditions=np.full(n,np.nan); r2=np.full(n,np.nan)
    statuses=[]; reasons=[]; constants=[]; redundants=[]; references=[]
    for i in range(n):
        ids,distances=index.query(coordinates[i],radius)
        assert i in ids
        weights=bisquare_weights(distances,radius); raw=values[ids].reshape(-1,14)
        fitted=fit(raw,weights)
        beta[i]=fitted.beta; support[i]=fitted.positive_meshes; effective[i]=fitted.effective_meshes
        ranks[i]=fitted.rank; retained[i]=len(fitted.active)+1; conditions[i]=fitted.condition
        statuses.append(fitted.status); reasons.append(fitted.reason)
        constants.append('; '.join(np.asarray(EXPLANATORY)[fitted.constant]))
        redundants.append('; '.join(np.asarray(EXPLANATORY)[fitted.redundant]))
        if fitted.status=='ok':
            assert predict(values[i,:,1:],fitted) is not None
            active=fitted.active
            prediction=fitted.center_y+((raw[:,1:][:,active]-fitted.anchor[active])-fitted.offset[active])@fitted.beta[active+1]
            anchors[i],offsets[i],outcome[i]=fitted.anchor,fitted.offset,fitted.center_y
            w=np.repeat(weights,5); tss=float(w@((raw[:,0]-fitted.center_y)**2))
            if tss>0:
                r2[i]=1-float(w@((raw[:,0]-prediction)**2))/tss
                assert -1e-8 <= r2[i] <= 1+1e-8
            if i%5000==0 or len(references)<10:
                reference,slopes=expanded_reference(raw,weights,fitted)
                np.testing.assert_allclose(slopes,fitted.beta[active+1],rtol=1e-5,atol=1e-8)
                np.testing.assert_allclose(reference,prediction,rtol=1e-7,atol=1e-7)
                references.append(dict(mesh=str(meshes.iloc[i]['Mesh Code']),maximum_prediction_difference=float(abs(reference-prediction).max())))
        else:
            assert np.isnan(fitted.beta).all()
        if (i+1)%10000==0 or i+1==n:
            print(f'UMD local {radius:g} km: {i+1:,}/{n:,}; {time.monotonic()-start:.1f}s',flush=True)
    data=meshes.copy(); data['Latitude']=coordinates[:,0]; data['Longitude']=coordinates[:,1]
    data['Bandwidth km']=radius
    names=['Intercept','Road Density Coefficient','Population Coefficient']+[name+' Coefficient' for name in EXPLANATORY[2:]]
    for j,name in enumerate(names):data[name]=beta[:,j]
    for j,name in enumerate(EXPLANATORY):
        data[name+' Center Anchor']=anchors[:,j]; data[name+' Center Offset']=offsets[:,j]
    data['Local Outcome Mean']=outcome
    data['Positive Weight Meshes']=support; data['Local Observations']=support*5
    data['Effective Weight Meshes']=effective; data['Design Rank']=ranks; data['Retained Parameters']=retained
    data['Scaled Design Condition']=conditions; data['Fit Status']=statuses; data['Failure Reason']=reasons
    data['Omitted Constant Controls']=constants; data['Omitted Redundant Controls']=redundants
    data['Below 30 Observations']=support*5<30; data['Weighted Local Training R Squared']=r2
    data['All Period Population Zero']=(values[:,:,2]==0).all(1)
    good=data['Fit Status'].eq('ok').to_numpy()
    assert data['Mesh Code'].is_unique and len(data)==contract['meshes']
    assert np.isfinite(beta[good,:3]).all() and np.isnan(beta[~good]).all()
    assert np.array_equal(ranks[good],retained[good])
    path=output/'local_coefficients.parquet';data.to_parquet(path,index=False)
    pd.testing.assert_frame_equal(data,pd.read_parquet(path))
    data.loc[~good].groupby('Failure Reason').size().rename('Meshes').to_csv(output/'failure_reasons.csv')
    pd.DataFrame([dict(Control=name,Estimated=int(np.isfinite(beta[good,j+1]).sum()),
        Omitted=int(np.isnan(beta[good,j+1]).sum())) for j,name in enumerate(EXPLANATORY[2:],start=2)]).to_csv(output/'omitted_control_summary.csv',index=False)
    road=beta[good,1]
    report=dict(status='passed',decision_id=DECISION,classification='UMD',effects=[],bandwidth_km=radius,
        meshes=n,observations=n*5,estimable_meshes=int(good.sum()),failed_meshes=int((~good).sum()),
        estimable_fraction=float(good.mean()),failure_reasons=data.loc[~good,'Failure Reason'].value_counts().to_dict(),
        road_positive_meshes=int((road>0).sum()),road_negative_meshes=int((road<0).sum()),
        road_zero_meshes=int((road==0).sum()),
        road_coefficient_quantiles=dict(zip(['min','p01','p05','median','p95','p99','max'],np.quantile(road,[0,.01,.05,.5,.95,.99,1]))),
        median_local_training_r_squared=float(np.nanmedian(r2[good])),
        median_positive_weight_meshes=float(np.median(support[good])),
        median_effective_weight_meshes=float(np.median(effective[good])),
        below_30_meshes=int((support*5<30).sum()),estimable_below_30_meshes=int((good & (support*5<30)).sum()),
        mandatory_core_identifiability_verified=True,omitted_coefficients_nan=True,all_focal_meshes_retained=True,
        focal_mesh_included_verified=True,local_significance_produced=False,expanded_wls_reference_checks=references,
        common_cv_weight_coverage=selection['common_weight_coverage'],conditional_cv_rmse=selection['minimum']['Common Weighted Level RMSE'],
        output=str(path.relative_to(ROOT)),output_sha256=sha(path),input_sha256=sha(INPUT),seconds=time.monotonic()-start)
    dump(output/'local_fit_validation.json',report)
    dump(OUT/'active_local_result.json',dict(bandwidth_km=radius,output=report['output'],
        validation=str((output/'local_fit_validation.json').relative_to(ROOT))))
    print('UMD local fit complete:',int(good.sum()),'estimated;',int((~good).sum()),'failed.',flush=True)


def finalize():
    contract=json.loads((OUT/'execution_contract.json').read_text())
    pooled_report=json.loads((OUT/'pooled_validation.json').read_text())
    pointer=json.loads((OUT/'active_local_result.json').read_text())
    local_report=json.loads((ROOT/pointer['validation']).read_text())
    search_report=json.loads((OUT/'bandwidth-search-3-50km/search_validation.json').read_text())
    independent=json.loads((OUT/'independent_delivery_validation.json').read_text())
    assert independent['status']=='passed'
    assert pooled_report['status']==local_report['status']==search_report['status']=='passed'
    assert sha(INPUT)==contract['panel_sha256']==pooled_report['input_sha256']==local_report['input_sha256']==search_report['input_sha256']
    assert all(sha(ROOT/path)==digest for path,digest in contract['protected_source_sha256'].items())
    report=dict(status='passed',decision_id=DECISION,classification='UMD',land_cover_reference='Water Land Cover Share',
        meshes=contract['meshes'],observations=contract['observations'],pooled_models=pooled_report['model_counts'],
        gwpr_bandwidth_km=pointer['bandwidth_km'],gwpr_estimable_meshes=local_report['estimable_meshes'],
        gwpr_failed_meshes=local_report['failed_meshes'],local_validation=pointer['validation'],
        source_inputs_unchanged=True,effects=[],old_formal_outputs_not_overwritten=True,
        mismatch_and_municipal_outputs_not_refitted=True,independent_delivery_validation_passed=True)
    dump(OUT/'delivery_validation.json',report)
    # Reconcile construction-role metadata through the selected preprocessing
    # decision; numerical source values and source identity remain unchanged.
    metadata=ROOT/'data/exp/data-preprocessing/modis-umd'
    role_path=metadata/'decisions.json';roles=json.loads(role_path.read_text())
    roles['analysis_role_decision_id']=DECISION
    roles['land_cover_reference']='Water Land Cover Share'
    roles['analytical_roles']={name:'omitted reference' if name=='Water Land Cover Share' else 'control'
                              for name in LAND+['Water Land Cover Share']}
    roles['regressions_refitted']=True
    dump(role_path,roles)
    group_path=metadata/'grouping_decisions.json';groups=json.loads(group_path.read_text())
    groups.update(model_reference_category_pending=False,land_cover_reference='Water Land Cover Share',
        analysis_role_decision_id=DECISION,regressions_refitted=True)
    dump(group_path,groups)
    umd_pointer_path=metadata/'active_panel.json';umd_pointer=json.loads(umd_pointer_path.read_text())
    umd_pointer.update(analysis_role_selection_pending=False,regressions_refitted=True,
        analysis_role_decision_id=DECISION,model_status='Four-layer UMD regression rerun numerically validated.',
        regression_delivery=str((OUT/'delivery_validation.json').relative_to(ROOT)))
    dump(umd_pointer_path,umd_pointer)
    ppath=ROOT/'data/exp/data-preprocessing/active_panel.json'
    previous=json.loads(ppath.read_text())
    previous.update(active_umd_regression_delivery=str((OUT/'delivery_validation.json').relative_to(ROOT)),
        umd_regression_refitted=True,completed_extended_model_classification='UMD',
        active_umd_regression_decision_id=DECISION,regression_refitted=True,
        active_umd_model_panel=str(INPUT.relative_to(ROOT)),active_umd_local_coefficients=pointer['output'],
        active_umd_local_bandwidth_km=pointer['bandwidth_km'])
    dump(ppath,previous)
    text=(ROOT/'docs/AnaSOP.md').read_text()
    sections=re.split(r'(?=^## [1-8]\. )',text,flags=re.M)
    old_checkpoint=('The earlier five-kilometre selection and IGBP support counts are historical. '
        'The UMD bandwidth and national coefficient surface are pending the authorized rerun.')
    selected=json.loads((OUT/'bandwidth-search-3-50km/search_minimum.json').read_text())
    new_checkpoint=(f'The completed UMD search evaluates forty-eight integer radii using '
        f'{selected["common_validation_centers"]:,} identical predictable validation centers, representing '
        f'{100*selected["common_weight_coverage"]:.6f} percent of tile-expansion weight. '
        f'The conditional minimum is {pointer["bandwidth_km"]:g} kilometres with radiance-level RMSE '
        f'{selected["minimum"]["Common Weighted Level RMSE"]:.6f}; this is not a proven national optimum. '
        f'The full UMD surface contains {local_report["estimable_meshes"]:,} estimable and '
        f'{local_report["failed_meshes"]:,} unavailable focal vectors. Earlier IGBP estimates retain their source identity.')
    sections[6]=sections[6].replace(old_checkpoint,new_checkpoint)
    sections[7]=sections[7].replace('UMD variation assessment pending; all forty-seven Prefectures attempted; no formal difference test',
        'UMD geographic variation described; all forty-seven Prefectures estimable; no formal difference test')
    qualifier=('When an additional control is redundant, retained nuisance coefficients are parameters of the selected basis '
               'and do not all have a common water-reference interpretation. Roads and population are reported only '
               'when uniquely identifiable against the complete nuisance span.')
    if qualifier not in sections[6]:
        sections[6]=sections[6].replace('### Extended Geographically Weighted Pooled Model',
            qualifier+'\n\n### Extended Geographically Weighted Pooled Model')
    addition=(f'\n### Validated UMD Regression Checkpoint\n\nThe UMD rerun retains {contract["meshes"]:,} meshes and '
        f'{contract["observations"]:,} records. National, nine regional and forty-seven Prefecture comparisons '
        'use the same baseline and extended area samples, the confirmed Water Land Cover Share reference and '
        'mesh-clustered CR1 with actual retained rank. The grouped holdout search selects '
        f'{pointer["bandwidth_km"]:g} kilometres on identical estimable validation support. The local result retains '
        f'{local_report["estimable_meshes"]:,} estimable and {local_report["failed_meshes"]:,} unavailable focal vectors. '
        'All focal identifiers, omitted-control references and small-neighborhood flags are preserved. Numerical '
        'verification passes; formal output review remains pending. Existing formal regression figures and '
        'tables require regeneration from these UMD results. Earlier mismatch and municipal analyses retain '
        'their IGBP context and are not updated by this checkpoint.\n\n')
    sections[7]=sections[7].rstrip()+'\n'+addition
    (ROOT/'docs/AnaSOP.md').write_text(''.join(sections))
    lines=['# UMD four-layer regression rerun','',f'Human decision: {DECISION}.',
        '',f'{contract["meshes"]:,} meshes; {contract["observations"]:,} records; five periods.',
        'Pooled OLS with intercept, no fixed effects. Water is the UMD reference. Five remaining land shares and six focused POI controls.',
        'Constant/redundant added controls are omitted with unavailable slopes; mandatory roads/population must be identified conditional on the full nuisance span.',
        'Retained nuisance coefficients in redundant designs are basis-dependent; their interpretation is not uniformly a water contrast. Core slope identification is checked independently.',
        '',f'GWPR selected radius: {pointer["bandwidth_km"]:g} km; {local_report["estimable_meshes"]:,} estimable meshes; '
        f'{local_report["failed_meshes"]:,} unavailable meshes.',
        'Grouped holdout selection is approximate and conditional on the same estimable validation centers at every radius. No local significance inference.',
        '', '## Outputs','', '- pooled_umd_results.xlsx: coefficient, confidence-interval and fit comparisons.',
        '- pooled_road_comparison.csv: national, nine-region and forty-seven-Prefecture road summaries.',
        '- bandwidth-search-3-50km: all 48 candidate scores, support and failure ledger.',
        '- '+pointer['output']+': local coefficients, omissions, failures and support.',
        '', 'Prior formal figures/tables and descriptive mismatch/municipal results are not overwritten. The latter still use IGBP context.',
        '', '## Reproduce', '', '```sh']
    lines += [f'python3 src/analyses/run_umd_four_layers.py --stage {s}' for s in ['prepare','pooled','search','local','finalize']]
    lines[-1:-1]=['python3 src/analyses/validate_umd_rerun.py']
    lines += ['```','']
    (OUT/'README.md').write_text('\n'.join(lines))
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--stage',required=True,choices=['prepare','pooled','search','local','finalize'])
    args=parser.parse_args();globals()[args.stage]()
