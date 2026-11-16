#!/usr/bin/env python3
"""Link confirmed pilot data and report numerical coverage without selecting rows."""
from pathlib import Path
import hashlib
import json
import shutil

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / 'data/exp/data-preprocessing/pilot'
OUT = PILOT / 'panel'
TARGET = ROOT / 'data/processed/pilot/road_population_light_pilot_preprocessed.parquet'
YEARS = [2002, 2003, 2004, 2010, 2024]
MATCHING = {2002: 2000, 2003: 2005, 2004: 2005, 2010: 2010, 2024: 2020}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flag(values):
    return values.astype('string').str.lower().eq('true').fillna(False)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = TARGET.parent / 'road_light_pilot_preprocessed.parquet'
    matching_path = ROOT / 'data/exp/data-organization/tables/period_matching.csv'
    matching = pd.read_csv(matching_path)
    assert matching.road_year.tolist() == YEARS
    assert dict(zip(matching.road_year, matching.population_year)) == MATCHING
    assert matching.ntl_year.tolist() == YEARS
    assert matching.panel_period.equals(matching.road_year)
    assert (matching.population_offset_years == matching.population_year - matching.road_year).all()
    assert (matching.population_gap_years == matching.population_offset_years.abs()).all()
    assert matching.population_year_reused.eq(matching.population_year.duplicated(keep=False).astype(int)).all()
    # Existing metadata names and meanings are preserved in an explicit sidecar.
    preserved = {str(p.relative_to(ROOT)): sha(p) for p in TARGET.parent.glob('*.parquet') if p != TARGET}
    inputs = {str(source.relative_to(ROOT)): sha(source), str(matching_path.relative_to(ROOT)): sha(matching_path)}
    road_light = pd.read_parquet(source)
    assert len(road_light) == 32000
    assert not road_light.duplicated(['Mesh Code', 'Road Year']).any()
    road_quality = pd.read_csv(PILOT / 'road_quality_flags.csv', dtype={'mesh_code': 'string'}, keep_default_na=False)
    pop_quality = pd.read_csv(PILOT / 'population/population_quality_flags.csv', dtype={'mesh_code': 'string'}, keep_default_na=False)
    frames, quality, counts = [], [], []
    reference_codes = set(road_light['Mesh Code'])
    assert len(reference_codes) == 6400
    for year, pop_year in MATCHING.items():
        original = road_light[road_light['Road Year'].eq(year)].reset_index(drop=True)
        pop_path = TARGET.parent / f'population_{pop_year}_preprocessed.parquet'
        population = pd.read_parquet(pop_path)
        assert len(population) == 6400 and population['Mesh Code'].is_unique
        assert set(population['Mesh Code']) == reference_codes
        assert population['Population Year'].eq(pop_year).all()
        inputs[str(pop_path.relative_to(ROOT))] = sha(pop_path)
        frame = original.merge(population, on='Mesh Code', how='left', validate='one_to_one', indicator=True)
        assert frame['_merge'].eq('both').all()
        frame = frame.drop(columns='_merge')
        for name in ['Disclosure Status', 'Disclosure Destination', 'Merged Mesh Codes']:
            if name not in frame:
                frame[name] = np.nan if name == 'Disclosure Status' else pd.Series(pd.NA, index=frame.index, dtype='string')
        # Same columns and order in all waves; only previously confirmed readable names.
        frame = frame[list(road_light.columns) + ['Population', 'Population Year',
                                                  'Disclosure Status', 'Disclosure Destination', 'Merged Mesh Codes']]
        assert len(frame) == 6400 and set(frame['Mesh Code']) == reference_codes
        pd.testing.assert_frame_equal(frame[list(original.columns)], original)
        for name in population.columns:
            if name != 'Mesh Code':
                observed = frame.set_index('Mesh Code').loc[population['Mesh Code'], name]
                expected = population.set_index('Mesh Code')[name]
                pd.testing.assert_series_equal(observed, expected, check_names=False)
        rq = road_quality[road_quality.road_year.eq(year)].set_index('mesh_code').loc[frame['Mesh Code']]
        pq = pop_quality[pop_quality.population_year.eq(pop_year)].set_index('mesh_code').loc[frame['Mesh Code']]
        road_present, road_unknown = flag(rq.source_row_present).to_numpy(), flag(rq.source_unknown).to_numpy()
        pop_present = flag(pq.source_row_present).to_numpy()
        assert not (road_unknown & ~road_present).any()
        assert frame.loc[road_unknown | ~road_present, ['Road Length', 'Road Length Density', 'Mesh Area']].isna().all().all()
        assert frame.loc[~pop_present, 'Population'].isna().all()
        road_valid = np.isfinite(frame['Road Length Density'])
        pop_valid = np.isfinite(frame['Population'])
        light_valid = np.isfinite(frame['Nighttime Radiance'])
        joint = road_valid & pop_valid & light_valid
        q = pd.DataFrame({'mesh_code': frame['Mesh Code'], 'road_year': year, 'population_year': pop_year,
                          'road_source_row_present': road_present, 'road_source_unknown': road_unknown,
                          'population_source_row_present': pop_present,
                          'population_total_nonnumeric': flag(pq.source_total_nonnumeric).to_numpy(),
                          'detail_disclosure_metadata_available': pop_year == 2020,
                          'road_density_numeric': road_valid, 'population_numeric': pop_valid,
                          'nighttime_radiance_numeric': light_valid, 'joint_numeric': joint,
                          'road_comparability_verified': False})
        quality.append(q)
        metadata = matching[matching.road_year.eq(year)].iloc[0]
        counts.append(dict(road_year=year, population_year=pop_year, nighttime_light_year=year,
                           meshes=len(frame), numeric_road_density=int(road_valid.sum()),
                           numeric_population=int(pop_valid.sum()), numeric_nighttime_radiance=int(light_valid.sum()),
                           joint_numeric=int(joint.sum()), joint_numeric_pct=float(joint.mean()*100),
                           road_unknown=int(road_unknown.sum()), road_unlisted=int((~road_present).sum()),
                           population_unlisted=int((~pop_present).sum()),
                           population_offset_years=int(metadata.population_offset_years),
                           population_gap_years=int(metadata.population_gap_years),
                           population_year_reused=bool(metadata.population_year_reused)))
        frames.append(frame)
    panel = pd.concat(frames, ignore_index=True)
    assert len(panel) == 32000 and len(panel.columns) == 13
    assert not panel.duplicated(['Mesh Code', 'Road Year']).any()
    assert all(name.isascii() for name in panel.columns)
    # Reused 2005 snapshot must remain identical in both road-anchored periods.
    a = panel[panel['Road Year'].eq(2003)].set_index('Mesh Code')['Population']
    b = panel[panel['Road Year'].eq(2004)].set_index('Mesh Code')['Population']
    pd.testing.assert_series_equal(a, b)
    panel.to_parquet(TARGET, index=False)
    pd.testing.assert_frame_equal(pd.read_parquet(TARGET), panel)
    flags = pd.concat(quality, ignore_index=True)
    availability = flags.pivot(index='mesh_code', columns='road_year', values='joint_numeric').reindex(columns=YEARS)
    assert availability.shape == (6400, 5) and availability.notna().all().all()
    availability.columns = [f'joint_numeric_{year}' for year in YEARS]
    availability['joint_numeric_periods'] = availability.sum(axis=1).astype(int)
    availability['all_five_joint_numeric'] = availability.joint_numeric_periods.eq(5)
    common = int(availability.all_five_joint_numeric.sum())
    historical_common = int(availability[[f'joint_numeric_{year}' for year in YEARS[:-1]]].all(axis=1).sum())
    distribution = availability.joint_numeric_periods.value_counts().reindex(range(6), fill_value=0).rename_axis('joint_numeric_periods').rename('meshes')
    flags.to_csv(OUT / 'panel_quality_flags.csv', index=False)
    pd.DataFrame(counts).to_csv(OUT / 'coverage_by_period.csv', index=False)
    availability.reset_index().to_csv(OUT / 'mesh_availability.csv', index=False)
    distribution.reset_index().to_csv(OUT / 'coverage_period_count.csv', index=False)
    shutil.copyfile(matching_path, OUT / 'period_matching.csv')
    assert all(sha(ROOT / path) == digest for path, digest in preserved.items())
    report = dict(status='passed', decision_id='MILI-D-20261009-011', paired_rows=len(panel),
                  meshes=6400, candidate_periods=YEARS, columns=panel.columns.tolist(),
                  per_period=counts, all_five_joint_numeric_meshes=common,
                  all_five_joint_numeric_rows=common * 5,
                  historical_four_joint_numeric_meshes=historical_common,
                  joint_numeric_period_distribution={str(k): int(v) for k, v in distribution.items()},
                  input_sha256=inputs, complete_source_parquets_unchanged=True,
                  preserved_output_sha256=preserved, output_sha256=sha(TARGET),
                  source_values_unchanged=True, missing_values_unchanged=True,
                  population_reuse_verified=True, period_matching_sha256=sha(matching_path),
                  imputation_performed=False, rows_dropped=0, geographic_exclusions_applied=False,
                  road_comparability_verified=False, final_estimation_sample_selected=False)
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    contract = dict(decision_id=report['decision_id'], output=str(TARGET.relative_to(ROOT)),
                    script='src/preprocessing/build_pilot_panel.py',
                    period_matching='data/exp/data-organization/tables/period_matching.csv',
                    preserved_matching_metadata='data/exp/data-preprocessing/pilot/panel/period_matching.csv',
                    years=MATCHING, linkage_keys=['Mesh Code', 'Road Year'],
                    complete_rows=32000, rows_dropped=0, imputation=False,
                    joint_numeric_definition='Finite Road Length Density, Population and Nighttime Radiance; zero is valid.',
                    road_comparability_verified=False, final_estimation_sample_selected=False)
    (OUT / 'panel_decisions.json').write_text(json.dumps(contract, indent=2) + '\n')
    central_path = PILOT.parent / 'decisions.json'
    decisions = json.loads(central_path.read_text())
    decisions['pilot_panel'] = contract
    decisions['confirmed_decisions'] = list(dict.fromkeys(decisions['confirmed_decisions'] + [report['decision_id']]))
    central_path.write_text(json.dumps(decisions, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['status', 'paired_rows', 'meshes', 'per_period',
                     'all_five_joint_numeric_meshes', 'historical_four_joint_numeric_meshes',
                     'joint_numeric_period_distribution']}, indent=2))


if __name__ == '__main__':
    main()
