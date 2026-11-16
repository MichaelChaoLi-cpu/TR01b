#!/usr/bin/env python3
"""Apply pilot island exclusions only when the current contract is active.

The immutable exclusion contract defines exact cells, not whole mesh blocks
or a general national island policy. Complete source-derived Parquets remain.
"""
from pathlib import Path
import hashlib
import json

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/pilot/island-exclusion'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    contract = json.loads((OUT / 'sample_decisions.json').read_text())
    if not contract.get('active', False):
        print(json.dumps(dict(status='skipped', decision_id=contract['decision_id'],
                              reason='Offshore exclusion withdrawn; use the complete pilot table.')))
        return
    codes = contract['excluded_mesh_codes']
    years = contract['exclusion_years']
    assert len(codes) == len(set(codes)) == 17
    evidence = ROOT / contract['evidence']
    assert sha(evidence) == contract['evidence_sha256']
    reference = pd.read_csv(evidence, dtype={'mesh_code': 'string'})
    assert set(reference.mesh_code) == set(codes)
    source, target = ROOT / contract['input'], ROOT / contract['output']
    preserved = {str(p.relative_to(ROOT)): sha(p) for p in source.parent.glob('*.parquet') if p != target}
    full = pd.read_parquet(source)
    assert len(full) == 32000 and not full.duplicated(['Mesh Code', 'Road Year']).any()
    assert set(full['Road Year']) == set(years)
    mask = full['Mesh Code'].isin(codes)
    excluded, retained = full[mask].copy(), full[~mask].copy()
    assert len(excluded) == 85 and len(retained) == 31915
    expected_meshes = set(full['Mesh Code']) - set(codes)
    summaries = []
    for year in years:
        original = full[full['Road Year'] == year]
        removed = excluded[excluded['Road Year'] == year]
        remaining = retained[retained['Road Year'] == year]
        assert set(removed['Mesh Code']) == set(codes)
        assert set(remaining['Mesh Code']) == expected_meshes
        assert len(remaining) == 6383
        pd.testing.assert_frame_equal(remaining, original[~original['Mesh Code'].isin(codes)])
        summaries.append(dict(road_year=year, full_meshes=len(original), excluded_meshes=len(removed),
                              retained_meshes=len(remaining), numeric_road_density=int(remaining['Road Length Density'].notna().sum()),
                              missing_road_density=int(remaining['Road Length Density'].isna().sum()),
                              numeric_nighttime_radiance=int(remaining['Nighttime Radiance'].notna().sum())))
    retained.to_parquet(target, index=False)
    actual = pd.read_parquet(target)
    pd.testing.assert_frame_equal(actual, retained.reset_index(drop=True))
    reference.assign(decision_id=contract['decision_id'], applies_to_all_five_periods=True).to_csv(OUT / 'excluded_meshes.csv', index=False)
    excluded.to_csv(OUT / 'excluded_road_light_rows.csv', index=False)
    pd.DataFrame(summaries).to_csv(OUT / 'sample_counts.csv', index=False)
    assert all(sha(ROOT / path) == digest for path, digest in preserved.items())
    report = dict(status='passed', decision_id=contract['decision_id'], excluded_meshes=17,
                  excluded_mesh_year_rows=85, retained_meshes=6383, retained_mesh_year_rows=31915,
                  columns=actual.columns.tolist(), common_exclusion_set_all_periods=True,
                  retained_values_unchanged=True, complete_parquets_unchanged=True,
                  complete_parquet_sha256=preserved, output_sha256=sha(target),
                  zero_imputation_performed=False, full_estimation_sample_selected=False,
                  national_island_policy_selected=False, sample_counts=summaries)
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(status='passed', excluded_meshes=17, excluded_rows=85,
                          retained_meshes=6383, retained_rows=31915, sample_counts=summaries), indent=2))


if __name__ == '__main__':
    main()
