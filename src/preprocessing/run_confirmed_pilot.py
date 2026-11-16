#!/usr/bin/env python3
"""Run per-source skill-generated scripts and validate confirmed pilot outputs."""
from pathlib import Path
import argparse
import json
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / 'data/exp/data-preprocessing'
PILOT = EXP / 'pilot'
YEARS = [2002, 2003, 2004, 2010, 2024]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--validate-only', action='store_true', help='Validate existing outputs without rerunning writers')
    args = parser.parse_args()
    decisions = json.loads((EXP / 'decisions.json').read_text())
    if not args.validate_only:
        for dataset in decisions['datasets'].values():
            subprocess.run([sys.executable, str(ROOT / dataset['script'])], cwd=ROOT, check=True)
    checks = []
    frames = []
    historic = pd.read_csv(PILOT / 'historical_road_grid_trial.csv', dtype={'mesh_code': 'string'})
    for year in YEARS:
        road = pd.read_parquet(ROOT / f'data/processed/pilot/roads_{year}_preprocessed.parquet')
        light = pd.read_parquet(ROOT / f'data/processed/pilot/lights_{year}_preprocessed.parquet')
        for frame in [road, light]:
            assert len(frame) == 6400 and frame['Mesh Code'].is_unique
            assert frame['Mesh Code'].str.fullmatch(r'5030[0-7]{2}[0-9]{2}').all()
            assert all(name.isascii() and name == name.strip() for name in frame.columns)
        assert (road['Road Year'] == year).all()
        assert (light['Nighttime Light Year'] == year).all()
        assert light['Nighttime Radiance'].notna().all()
        assert light['Nighttime Light Coverage'].between(0, 1).all()
        if year != 2024:
            original = historic[historic.road_source_year == year].set_index('mesh_code')
            if year == 2010:
                repairs = pd.read_csv(PILOT / '2010_road_reconstruction.csv', dtype={'mesh_code': 'string'})
                for repair in repairs[repairs.applied_to_selected_road_length].itertuples():
                    assert original.loc[repair.mesh_code, 'road_length_km'] == repair.original_length_m / 1000
                    original.loc[repair.mesh_code, 'road_length_km'] = repair.reconstructed_length_m / 1000
            actual = road.set_index('Mesh Code').reindex(original.index)
            unknown = original['source_unknown'].eq(True)
            assert actual.loc[unknown, ['Road Length', 'Road Length Density', 'Mesh Area']].isna().all().all()
            for source, target in [('road_length_km', 'Road Length'), ('road_length_density', 'Road Length Density'),
                                   ('source_mesh_area_km2', 'Mesh Area')]:
                np.testing.assert_allclose(original[source], actual[target], rtol=0, atol=0, equal_nan=True)
            unlisted = ~road['Mesh Code'].isin(original.index)
            absent = road[unlisted]
            assert absent[['Road Length', 'Road Length Density', 'Mesh Area']].isna().all().all()
            assert int(unknown.sum() + unlisted.sum()) == int(road['Road Length Density'].isna().sum())
        else:
            np.testing.assert_allclose(road['Road Length'] / road['Mesh Area'], road['Road Length Density'])
        # Independently recompute valid weighted means for spatially dispersed cells.
        overlap_year = 2024 if year == 2024 else 2002
        weights = pd.read_csv(PILOT / f'{overlap_year}_pixel_mesh_overlaps.csv', dtype={'mesh_code': 'string'})
        pixels = pd.read_csv(ROOT / f'data/exp/data-organization/nighttime-pilot/{year}_native_pixels.csv')
        selected = light['Mesh Code'].iloc[np.linspace(0, 6399, 12, dtype=int)]
        portions = weights[weights.mesh_code.isin(selected)].merge(pixels, on=['raster_row', 'raster_column'], validate='many_to_one')
        source_tag = json.loads((ROOT / f'data/exp/data-organization/nighttime-pilot/{year}_tiff_index.json').read_text())['tags'].get('42113')
        valid = np.isfinite(portions.source_radiance)
        if source_tag is not None:
            valid &= portions.source_radiance != np.float32(float(source_tag.strip('\x00')))
        for code, chunk in portions[valid].groupby('mesh_code'):
            expected = np.average(chunk.source_radiance, weights=chunk.overlap_area_m2)
            actual = light.set_index('Mesh Code').loc[code, 'Nighttime Radiance']
            np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)
        pair = road.merge(light, on='Mesh Code', validate='one_to_one')
        frames.append(pair)
        checks.append(dict(road_year=year, meshes=len(pair), numeric_road_density=int(road['Road Length Density'].notna().sum()),
                           missing_road_density=int(road['Road Length Density'].isna().sum()),
                           zero_road_density=int((road['Road Length Density'] == 0).sum()),
                           numeric_nighttime_radiance=int(light['Nighttime Radiance'].notna().sum()),
                           zero_nighttime_radiance=int((light['Nighttime Radiance'] == 0).sum()),
                           unknown_road_meshes=int(unknown.sum()) if year != 2024 else 0,
                           unlisted_road_meshes=int(unlisted.sum()) if year != 2024 else 0,
                           unavailable_road_attributes_are_nan=True,
                           independent_light_mean_checks=len(selected)))
    panel = pd.concat(frames, ignore_index=True)
    assert len(panel) == 32000 and not panel.duplicated(['Mesh Code', 'Road Year']).any()
    anomaly = panel[(panel['Mesh Code'] == '50302281') & (panel['Road Year'] == 2010)].iloc[0]
    assert anomaly['Road Length'] == 12.143 and anomaly['Road Length Density'] == 11.325
    panel.to_parquet(ROOT / 'data/processed/pilot/road_light_pilot_preprocessed.parquet', index=False)
    pd.DataFrame(checks).to_csv(PILOT / 'processed_output_validation.csv', index=False)
    report = dict(status='passed', source_parquets=10, source_rows=64000, paired_rows=32000,
                  paired_columns=panel.columns.tolist(), selected_column_entries=45,
                  original_2010_anomaly_retained_in_quality_record=True, reconstructed_2010_total_length=True,
                  source_comparability_verified=False,
                  final_analysis_sample_selected=False, population_included=False,
                  coastal_mesh_classified=False, years=checks)
    (PILOT / 'processed_output_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    sample_contract = PILOT / 'island-exclusion/sample_decisions.json'
    if sample_contract.exists() and json.loads(sample_contract.read_text()).get('active', False):
        subprocess.run([sys.executable, str(ROOT / 'src/preprocessing/exclude_identified_offshore_meshes.py')], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
