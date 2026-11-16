#!/usr/bin/env python3
"""Validate corrected prefecture assignments after explicit exception approval.

No scientific variable changes. Stage readable classification inputs and the
data-preprocessing contract; keep the raw geometric ledger unchanged.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from prepare_prefecture_confirmed_input import PREFECTURE_NAMES
from prepare_regional_confirmed_input import sha

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/prefecture-population-zero-corrected'


def main():
    geometry = json.loads((OUT / 'geometry_validation.json').read_text())
    decision = json.loads((OUT / 'allocation_decision.json').read_text())
    assert decision['confirmed'] and decision['mode'] == 'reviewed_nearest_land'
    frame = pd.read_csv(OUT / 'mesh_prefecture_confirmed_input.csv', dtype={'mesh_code': 'string', 'prefecture_code': 'string'})
    overlap = pd.read_csv(OUT / 'mesh_prefecture_overlaps.csv', dtype={'mesh_code': 'string', 'prefecture_code': 'string'})
    assert len(frame) == 228988 and frame.mesh_code.is_unique
    unresolved = frame.assignment_status.eq('no_land_overlap')
    assert set(frame.loc[unresolved, 'mesh_code']) == set(geometry['unassigned_meshes']) == set(decision['mesh_codes'])
    assert int(unresolved.sum()) == 19 and not frame.assignment_status.eq('area_tie').any()
    assert frame.loc[unresolved, 'total_land_overlap'].eq(0).all()
    assert not overlap.duplicated(['mesh_code', 'prefecture_code']).any() and overlap.land_overlap_m2.gt(0).all()
    normal = frame.loc[~unresolved].set_index('mesh_code')
    winner = overlap.sort_values(['mesh_code', 'land_overlap_m2'], ascending=[True, False]).drop_duplicates('mesh_code').set_index('mesh_code')
    assert winner.prefecture_code.reindex(normal.index).equals(normal.prefecture_code)
    totals = overlap.groupby('mesh_code').land_overlap_m2.sum().reindex(normal.index)
    np.testing.assert_allclose(totals / 1e6, normal.total_land_overlap, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(winner.land_overlap_m2.reindex(normal.index) / 1e6, normal.prefecture_land_area, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(normal.prefecture_land_area / normal.total_land_overlap, normal.prefecture_land_share, rtol=1e-12, atol=1e-12)
    assert overlap.groupby('mesh_code').size().gt(1).reindex(normal.index).equals(normal.cross_prefecture_mesh)
    proposal_path = ROOT / decision['proposal_path']
    assert sha(proposal_path) == decision['proposal_sha256']
    proposals = pd.read_csv(proposal_path, dtype={'mesh_code': 'string', 'nearest_prefecture_code': 'string'}).set_index('mesh_code')
    assert set(proposals.index) == set(decision['mesh_codes'])
    assert proposals.minimum_land_distance_m.between(0, 1500, inclusive='both').all()
    assert proposals.nearest_prefecture_code.value_counts().to_dict() == decision['approved_prefecture_counts']
    frame['no_land_overlap'] = unresolved
    frame['prefecture_assignment_method'] = 'positive_land_area'
    frame['nearest_land_distance'] = np.nan
    for index in frame.index[unresolved]:
        proposal = proposals.loc[frame.at[index, 'mesh_code']]
        frame.at[index, 'prefecture_code'] = proposal.nearest_prefecture_code
        frame.at[index, 'assignment_status'] = 'reviewed_no_land_overlap'
        frame.at[index, 'prefecture_assignment_method'] = 'reviewed_nearest_land'
        frame.at[index, 'nearest_land_distance'] = proposal.minimum_land_distance_m
    assert frame.loc[unresolved, ['prefecture_land_area', 'prefecture_land_share']].isna().all().all()
    assert frame.prefecture_code.notna().all() and set(frame.prefecture_code) == set(PREFECTURE_NAMES)
    frame['prefecture'] = frame.prefecture_code.map(PREFECTURE_NAMES).astype('string')
    region_geometry = json.loads((ROOT / 'data/exp/data-preprocessing/regional-population-zero-corrected/geometry_validation.json').read_text())
    region_lookup = {f'{p:02d}': r for r, codes in region_geometry['regions'].items() for p in codes}
    regions = pd.read_parquet(ROOT / 'data/processed/national/population_zero_corrected/mesh_region_national_preprocessed.parquet').set_index('Mesh Code')
    frame['region_from_prefecture'] = frame.prefecture_code.map(region_lookup).astype('string')
    frame['prior_region'] = frame.mesh_code.map(regions.Region).astype('string')
    frame['region_assignment_differs'] = frame.region_from_prefecture.ne(frame.prior_region)
    assert frame.prior_region.notna().all()
    differences = frame.loc[frame.region_assignment_differs]
    assert set(differences.mesh_code).issubset(set(regions.index[regions['Cross Region Mesh']]))
    differences.to_csv(OUT / 'prefecture_region_boundary_differences.csv', index=False)
    grouped = overlap.assign(region=overlap.prefecture_code.map(region_lookup)).groupby(['mesh_code', 'region']).land_overlap_m2.sum()
    reference = pd.read_csv(ROOT / 'data/exp/data-preprocessing/regional-population-zero-corrected/mesh_region_overlaps.csv', dtype={'mesh_code': 'string', 'region': 'string'}).set_index(['mesh_code', 'region']).land_overlap_m2
    assert set(grouped.index) == set(reference.index)
    delta = abs(grouped.reindex(reference.index) - reference)
    assert (delta <= np.maximum(.1, reference.abs() * 1e-6)).all()
    prior = pd.read_parquet(ROOT / 'data/processed/national/mesh_prefecture_national_preprocessed.parquet').set_index('Mesh Code')
    current = frame.set_index('mesh_code').loc[prior.index]
    assert np.array_equal(prior['Prefecture Code'], current.prefecture_code)
    for a, b in [('Cross Prefecture Mesh', 'cross_prefecture_mesh'), ('Prefecture Land Area', 'prefecture_land_area'),
                 ('Total Land Overlap', 'total_land_overlap'), ('Prefecture Land Share', 'prefecture_land_share')]:
        np.testing.assert_allclose(prior[a].to_numpy(dtype=float), current[b].to_numpy(dtype=float), rtol=1e-12, atol=1e-10)
    staged = OUT / 'mesh_prefecture_reviewed_confirmed_input.parquet'
    frame.to_parquet(staged, index=False)
    counts = frame.prefecture_code.value_counts().to_dict()
    pd.DataFrame([{'Prefecture Code': code, 'Prefecture': name, 'Meshes': counts[code], 'Observations': counts[code] * 4}
                  for code, name in PREFECTURE_NAMES.items()]).to_csv(OUT / 'prefecture_sample_counts.csv', index=False)
    mapping = {'mesh_code': 'Mesh Code', 'prefecture_code': 'Prefecture Code', 'prefecture': 'Prefecture',
               'cross_prefecture_mesh': 'Cross Prefecture Mesh', 'prefecture_land_area': 'Prefecture Land Area',
               'total_land_overlap': 'Total Land Overlap', 'prefecture_land_share': 'Prefecture Land Share',
               'assignment_status': 'Assignment Status', 'no_land_overlap': 'No Land Overlap',
               'prefecture_assignment_method': 'Prefecture Assignment Method', 'nearest_land_distance': 'Nearest Land Distance',
               'region_from_prefecture': 'Region From Prefecture', 'prior_region': 'Prior Region',
               'region_assignment_differs': 'Region Assignment Differs'}
    variables = [dict(original_name=a, readable_name=b, full_name=b, is_final_variable='yes' if a=='prefecture' else 'no', preprocessing=[])
                 for a, b in mapping.items()]
    contract = dict(confirmed=True, decision_id='MILI-D-20261009-040', allocation_decision_id=decision['decision_id'],
                    datasets={str(staged.relative_to(ROOT)): dict(output='data/processed/national/population_zero_corrected/mesh_prefecture_national_preprocessed.parquet',
                              script='src/preprocessing/preprocess_corrected_national_mesh_prefecture.py', variables=variables)},
                    construction='Largest positive prefecture land overlap; nineteen human-reviewed nearest-land exceptions with explicit flags.', substantive_panel_modified=False)
    (OUT / 'decisions.json').write_text(json.dumps(contract, indent=2)+'\n')
    pd.DataFrame(variables).to_csv(OUT / 'variable_list.csv', index=False)
    report = dict(status='passed', decision_id='MILI-D-20261009-040', classification_meshes=len(frame),
                  prefecture_counts=counts, prefecture_names=PREFECTURE_NAMES, cross_prefecture_meshes=int(frame.cross_prefecture_mesh.sum()),
                  region_assignment_differences=len(differences), retained_no_land_meshes=19, exception_decision_id=decision['decision_id'],
                  maximum_area_assignment_verified=True, old_prefecture_labels_and_areas_preserved=True, no_fictitious_land_area_or_share=True,
                  grouped_prefecture_region_area_max_difference_m2=float(delta.max()), staged_sha256=sha(staged), substantive_panel_modified=False)
    (OUT / 'classification_validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
