#!/usr/bin/env python3
"""Prepare confirmed road/light variables from validated spatial pilot caches.

Rebuild caches from original archives with the documented upstream scripts first.
This stage never changes raw data, imputes values, or selects an analysis sample.
"""
from pathlib import Path
import hashlib
import json
import platform

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / 'data/exp/data-preprocessing/pilot'
STAGING = PILOT / 'confirmed-inputs'
YEARS = [2002, 2003, 2004, 2010, 2024]


def read_csv(path):
    return pd.read_csv(path, dtype={'mesh_code': 'string'}, keep_default_na=True)


def variable(original, readable, final=False):
    return dict(original_name=original, readable_name=readable,
                full_name=readable, is_final_variable='yes' if final else 'no',
                preprocessing=[])


def main():
    STAGING.mkdir(parents=True, exist_ok=True)
    grid = read_csv(PILOT / 'common_grid_trial.csv')
    assert len(grid) == 6400 and grid.mesh_code.is_unique
    historic = read_csv(PILOT / 'historical_road_grid_trial.csv')
    recent = read_csv(PILOT / '2024_road_grid_trial.csv')
    mapping = pd.read_csv(PILOT / 'nighttime_overlap_file_mapping.csv').set_index('year')
    geo_validation = json.loads((PILOT / 'spatial_alignment_validation.json').read_text())
    assert geo_validation['maximum_clipping_difference_m'] < .01
    datasets = {}
    light_quality = []
    road_quality = []
    coverage_checks = []
    consumed = set()
    reconstruction_path = PILOT / '2010_road_reconstruction.csv'
    reconstruction = read_csv(reconstruction_path)

    def register(kind, year, frame, specs, source_details):
        source = STAGING / f'{kind}_{year}_confirmed_input.parquet'
        frame.to_parquet(source, index=False)
        datasets[str(source.relative_to(ROOT))] = dict(
            output=f'data/processed/pilot/{kind}_{year}_preprocessed.parquet',
            script=f'src/preprocessing/preprocess_pilot_{kind}_{year}.py',
            variables=specs, spatial_preparation='src/preprocessing/prepare_confirmed_pilot.py',
            source_details=source_details)

    for year in YEARS:
        if year == 2024:
            road = recent.copy()
            road['mesh_area_km2'] = road['common_mesh_area_km2']
            road['road_year'] = year
            road['source_row_present'] = True
            road['source_unknown'] = False
            road['normalization_anomaly'] = False
            road['zero_meaning'] = 'no selected ordinary centerline in published tile'
            details = {'raw_fields': ['N13_002', 'N13_004'],
                       'construction': 'ordinary centerlines; states 1-4; intersect common mesh; projected length / projected full mesh area'}
        else:
            subset = historic[historic.road_source_year == year].copy()
            assert subset.mesh_code.is_unique
            road = grid.merge(subset, on='mesh_code', how='left', validate='one_to_one')
            road['mesh_area_km2'] = road['source_mesh_area_km2']
            road['road_year'] = year
            road['source_row_present'] = road['source_row_present'].fillna(False).astype(bool)
            missing_road = ~road['source_row_present'] | road['source_unknown'].eq(True)
            road.loc[missing_road, ['road_length_km', 'road_length_density', 'mesh_area_km2']] = np.nan
            road['zero_meaning'] = 'reported numeric zero only; absent or unknown stays missing'
            details = {'raw_fields': ['N04_001', 'N04_002', 'N04_055' if year == 2010 else 'N04_037',
                                     'N04_056' if year == 2010 else 'N04_038'],
                       'construction': 'length m / 1000; supplied normalized length m/km2 / 1000; source area km2 (earlier m2 / 1e6)'}
        road['normalization_anomaly_resolved'] = False
        road['source_category_anomaly'] = False
        road['source_category_anomaly_resolved_in_reference'] = False
        road['road_length_before_correction_km'] = road['road_length_km']
        if year == 2010:
            for repair in reconstruction.itertuples():
                match = road.mesh_code == repair.mesh_code
                assert match.sum() == 1
                if repair.applied_to_selected_road_length:
                    assert road.loc[match, 'road_length_km'].item() == repair.original_length_m / 1000
                    road.loc[match, 'road_length_km'] = repair.reconstructed_length_m / 1000
                    road.loc[match, 'normalization_anomaly_resolved'] = True
                else:
                    road.loc[match, 'source_category_anomaly'] = True
                    road.loc[match, 'source_category_anomaly_resolved_in_reference'] = True
            details['evidence_supported_reconstruction'] = str(reconstruction_path.relative_to(ROOT))
        register('roads', year, road[['mesh_code', 'road_length_km', 'road_length_density', 'mesh_area_km2', 'road_year']],
                 [variable('mesh_code', 'Mesh Code'), variable('road_length_km', 'Road Length'),
                  variable('road_length_density', 'Road Length Density', True),
                  variable('mesh_area_km2', 'Mesh Area'), variable('road_year', 'Road Year')], details)
        quality_cols = ['mesh_code', 'road_year', 'source_row_present', 'source_unknown',
                        'normalization_anomaly', 'normalization_anomaly_resolved', 'source_category_anomaly',
                        'source_category_anomaly_resolved_in_reference', 'road_length_before_correction_km',
                        'source_comparability_verified', 'zero_meaning']
        quality_cols += [c for c in ['road_length_literal', 'road_density_literal', 'source_area_literal',
                                   'unknown_width_length_km', 'common_mesh_area_km2'] if c in road]
        road_quality.append(road[quality_cols])

        pixel_path = ROOT / f'data/exp/data-organization/nighttime-pilot/{year}_native_pixels.csv'
        index_path = pixel_path.with_name(f'{year}_tiff_index.json')
        overlap_path = PILOT / mapping.loc[year, 'overlap_file']
        pixels = pd.read_csv(pixel_path)
        assert not pixels.duplicated(['raster_row', 'raster_column']).any()
        nodata_literal = json.loads(index_path.read_text())['tags'].get('42113')
        nodata = float(str(nodata_literal).strip('\x00')) if nodata_literal is not None else None
        pixels['valid'] = np.isfinite(pixels.source_radiance)
        if nodata is not None:
            pixels['valid'] &= pixels.source_radiance != np.float32(nodata)
        weights = read_csv(overlap_path)
        assert (weights.overlap_area_m2 > 0).all()
        joined = weights.merge(pixels, on=['raster_row', 'raster_column'], how='left',
                               validate='many_to_one', indicator=True)
        assert (joined['_merge'] == 'both').all(), 'Window lacks intersecting native pixels'
        joined['valid_area'] = joined.overlap_area_m2.where(joined.valid, 0.)
        joined['weighted_radiance'] = joined.source_radiance.where(joined.valid, 0.) * joined.valid_area
        totals = joined.groupby('mesh_code')[['valid_area', 'weighted_radiance']].sum()
        lights = grid[['mesh_code', 'common_mesh_area_km2']].merge(totals, on='mesh_code', how='left', validate='one_to_one')
        assert lights.valid_area.notna().all()
        lights['nighttime_radiance'] = lights.weighted_radiance / lights.valid_area.where(lights.valid_area > 0)
        raw_coverage = lights.valid_area / (lights.common_mesh_area_km2 * 1e6)
        assert (raw_coverage <= 1 + 1e-7).all(), 'Geometric overlap exceeds numerical tolerance'
        # Bound only numerical roundoff in a proportion; preserve raw ratios in QA.
        lights['nighttime_light_coverage'] = raw_coverage.clip(upper=1.)
        lights['nighttime_light_year'] = year
        lights['coastal_mesh'] = pd.Series(pd.NA, index=lights.index, dtype='boolean')
        lights['coastal_classification_status'] = 'not classified: no verified coastline mask'
        lights['raw_coverage_fraction'] = raw_coverage
        lights['no_valid_pixels'] = lights.valid_area == 0
        register('lights', year, lights[['mesh_code', 'nighttime_radiance', 'nighttime_light_year', 'nighttime_light_coverage']],
                 [variable('mesh_code', 'Mesh Code'), variable('nighttime_radiance', 'Nighttime Radiance', True),
                  variable('nighttime_light_year', 'Nighttime Light Year'), variable('nighttime_light_coverage', 'Nighttime Light Coverage')],
                 {'raw_input': 'source_radiance', 'overlap_file': str(overlap_path.relative_to(ROOT)),
                  'construction': 'valid native-pixel intersection-area-weighted mean; full mesh area; no land mask',
                  'declared_nodata': nodata_literal})
        light_quality.append(lights[['mesh_code', 'nighttime_light_year', 'raw_coverage_fraction', 'no_valid_pixels',
                                     'coastal_mesh', 'coastal_classification_status']])
        coverage_checks.append(dict(year=year, meshes=len(lights), numeric_meshes=int(lights.nighttime_radiance.notna().sum()),
                                    zero_meshes=int((lights.nighttime_radiance == 0).sum()),
                                    minimum_raw_coverage=float(raw_coverage.min()), maximum_raw_coverage=float(raw_coverage.max()),
                                    valid_native_pixels=int(pixels.valid.sum())))
        consumed.update([pixel_path, index_path, overlap_path])
    pd.concat(road_quality).to_csv(PILOT / 'road_quality_flags.csv', index=False)
    pd.concat(light_quality).to_csv(PILOT / 'nighttime_quality_flags.csv', index=False)
    pd.DataFrame(coverage_checks).to_csv(PILOT / 'nighttime_aggregation_validation.csv', index=False)
    consumed.update(PILOT / name for name in ['common_grid_trial.csv', 'historical_road_grid_trial.csv',
                                               '2024_road_grid_trial.csv', 'road_trial_validation.json',
                                               'spatial_alignment_validation.json', 'nighttime_overlap_file_mapping.csv',
                                               '2010_road_reconstruction.csv', '2010_road_reconstruction_validation.json'])
    decisions = dict(datasets=datasets, confirmed_decisions=['MILI-D-20261009-003', 'MILI-D-20261009-004', 'MILI-D-20261009-005'],
                     population_status='pending user variable confirmation', final_analysis_sample_selected=False,
                     runtime=dict(python=platform.python_version(), pandas=pd.__version__, numpy=np.__version__),
                     quality_flags='data/exp/data-preprocessing/pilot/*_quality_flags.csv',
                     prepared_input_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(consumed)})
    sample_contract = PILOT / 'island-exclusion/sample_decisions.json'
    missing_contract = PILOT / 'road_missing_data_decisions.json'
    if missing_contract.exists():
        decisions['road_missing_data'] = json.loads(missing_contract.read_text())
        decisions['confirmed_decisions'].append(decisions['road_missing_data']['decision_id'])
    if sample_contract.exists():
        decisions['sample_exclusion'] = json.loads(sample_contract.read_text())
        decisions['confirmed_decisions'].append(decisions['sample_exclusion']['decision_id'])
        if decisions['sample_exclusion'].get('supersedes'):
            decisions['superseded_decisions'] = [decisions['sample_exclusion']['supersedes']]
    population_contract = PILOT / 'population/population_decisions.json'
    if population_contract.exists():
        population = json.loads(population_contract.read_text())
        if population.get('confirmed', False):
            decisions['population_decisions'] = population
            decisions['datasets'].update(population.get('datasets', {}))
            decisions['population_status'] = 'confirmed pilot total population; no final estimation sample selected'
            decisions['confirmed_decisions'].append(population['decision_id'])
    panel_contract = PILOT / 'panel/panel_decisions.json'
    if panel_contract.exists():
        decisions['pilot_panel'] = json.loads(panel_contract.read_text())
        decisions['confirmed_decisions'].append(decisions['pilot_panel']['decision_id'])
    roles_contract = PILOT / 'model_roles_decisions.json'
    if roles_contract.exists():
        roles = json.loads(roles_contract.read_text())
        if roles.get('confirmed', False):
            decisions['initial_model_roles'] = roles
            for record_id in [roles['method_direction_decision_id'], roles['decision_id']]:
                if record_id not in decisions['confirmed_decisions']:
                    decisions['confirmed_decisions'].append(record_id)
            for dataset in decisions['datasets'].values():
                for variable in dataset['variables']:
                    role = roles['roles'].get(variable['readable_name'])
                    if role:
                        variable['role'] = role
    national_contract = PILOT.parent / 'national/decisions.json'
    if national_contract.exists():
        national = json.loads(national_contract.read_text())
        if national.get('confirmed', False):
            decisions['datasets'].update(national.get('datasets', {}))
            decisions['national_preprocessing'] = {
                'decision_id': 'MILI-D-20261009-015',
                'contract': str(national_contract.relative_to(ROOT)),
                'panel': 'data/processed/national/road_population_light_national_preprocessed.parquet',
            }
            if 'MILI-D-20261009-015' not in decisions['confirmed_decisions']:
                decisions['confirmed_decisions'].append('MILI-D-20261009-015')
    regional_contract = PILOT.parent / 'regional/decisions.json'
    if regional_contract.exists():
        regional = json.loads(regional_contract.read_text())
        if regional.get('confirmed', False):
            decisions['datasets'].update(regional.get('datasets', {}))
            decisions['regional_preprocessing'] = {
                'decision_id': regional['decision_id'],
                'contract': str(regional_contract.relative_to(ROOT)),
            }
            if regional['decision_id'] not in decisions['confirmed_decisions']:
                decisions['confirmed_decisions'].append(regional['decision_id'])
    prefecture_contract = PILOT.parent / 'prefecture/decisions.json'
    if prefecture_contract.exists():
        prefecture = json.loads(prefecture_contract.read_text())
        if prefecture.get('confirmed', False):
            decisions['datasets'].update(prefecture.get('datasets', {}))
            decisions['prefecture_preprocessing'] = {
                'decision_id': prefecture['decision_id'],
                'contract': str(prefecture_contract.relative_to(ROOT)),
            }
            if prefecture['decision_id'] not in decisions['confirmed_decisions']:
                decisions['confirmed_decisions'].append(prefecture['decision_id'])
    (PILOT.parent / 'decisions.json').write_text(json.dumps(decisions, indent=2) + '\n')
    # Annotate the original full-field inventory; keep unconfirmed population entries untouched.
    inventory_path = PILOT.parent / 'variable_list.csv'
    inventory = pd.read_csv(inventory_path, keep_default_na=False)
    for index, row in inventory.iterrows():
        source, name = row['source_dataset'], row['original_name']
        readable = None
        if 'nighttime-pilot/' in source and name == 'source_radiance':
            readable = 'Nighttime Radiance'
        elif '/n04_mesh_' in source:
            readable = {'N04_001': 'Mesh Code', 'N04_002': 'Mesh Area',
                        'N04_055' if '_2010_' in source else 'N04_037': 'Road Length',
                        'N04_056' if '_2010_' in source else 'N04_038': 'Road Length Density'}.get(name)
        if readable:
            inventory.loc[index, ['readable_name', 'full_name', 'is_final_variable']] = [
                readable, readable, 'yes' if readable in ['Road Length Density', 'Nighttime Radiance'] else 'no']
    inventory.to_csv(inventory_path, index=False)
    print(json.dumps(coverage_checks, indent=2))


if __name__ == '__main__':
    main()
