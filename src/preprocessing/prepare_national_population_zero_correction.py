#!/usr/bin/env python3
"""Decode documented absent census records as zero inside verified source tiles.

Read-only raw inputs; separate revised outputs preserve the earlier data version.
Run this script, the three generated preprocessing scripts, then the panel builder.
"""
from pathlib import Path
import csv
import hashlib
import io
import json
import zipfile

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/population-zero-correction'
DEST = 'data/processed/national/population_zero_corrected'
POP = {2000: 'T000146', 2005: 'T000148', 2010: 'T000608'}
TOTALS = {2000: 126925843, 2005: 127767994, 2010: 128057352}
DECISION = 'MILI-D-20261009-032'
REFERENCE = 'https://www.stat.go.jp/data/mesh/pdf/ryuijikou.pdf'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    staging = OUT / 'confirmed-inputs'
    staging.mkdir(parents=True, exist_ok=True)
    grid = pd.read_parquet(ROOT / 'data/exp/data-preprocessing/national/common_grid.parquet')
    assert grid.mesh_code.is_unique and len(grid) == 972800
    tiles = set(grid.mesh_code.str[:4])
    manifest = pd.read_csv(ROOT / 'data/exp/data-organization/tables/download_manifest.csv').set_index('local_path')
    datasets, audits, coverage, hashes, previous_hashes = {}, [], [], {}, {}
    for year, stats in POP.items():
        archives = sorted((ROOT / f'data/raw/population/estat_1km/{year}').glob('*.zip'))
        assert len(archives) == 151
        covered_tiles, parts = set(), []
        for path in archives:
            relative = str(path.relative_to(ROOT))
            expected = manifest.loc[relative]
            assert expected['status'] == 'downloaded_verified', relative
            digest = sha(path)
            assert digest == expected['sha256'], relative
            hashes[relative] = digest
            tile = path.stem.split('_')[1]
            assert tile in tiles and tile not in covered_tiles
            covered_tiles.add(tile)
            with zipfile.ZipFile(path) as archive:
                names = [n for n in archive.namelist() if n.lower().endswith('.txt')]
                assert len(names) == 1
                rows = list(csv.reader(io.StringIO(archive.read(names[0]).decode('cp932'))))
            raw = pd.DataFrame(rows[2:], columns=rows[0])
            assert raw.KEY_CODE.str.fullmatch(r'\d{8}').all()
            assert raw.KEY_CODE.str.startswith(tile).all() and raw.KEY_CODE.is_unique
            population = pd.to_numeric(raw[stats + '001'], errors='coerce')
            numeric = np.isfinite(population)
            population = population.mask(~numeric)
            assert (population[numeric] >= 0).all()
            male = pd.to_numeric(raw[stats + '002'], errors='coerce')
            female = pd.to_numeric(raw[stats + '003'], errors='coerce')
            comparable = numeric & np.isfinite(male) & np.isfinite(female)
            assert (male[comparable] + female[comparable]).eq(population[comparable]).all()
            parts.append(pd.DataFrame({'mesh_code': raw.KEY_CODE, 'population': population,
                                       'source_row_present': True}))
            audits.append(dict(population_year=year,primary_tile=tile,source=relative,
                rows=len(raw),numeric_totals=int(numeric.sum()),invalid_totals=int((~numeric).sum()),
                literal_zero_totals=int(population.eq(0).sum()),population_sum=int(population.sum()),sha256=digest))
        source = pd.concat(parts, ignore_index=True)
        assert source.mesh_code.is_unique and source.mesh_code.isin(grid.mesh_code).all()
        assert source.population.sum() == TOTALS[year]
        frame = grid.merge(source, on='mesh_code', how='left', validate='one_to_one')
        present = frame.source_row_present.eq(True)
        covered = frame.mesh_code.str[:4].isin(covered_tiles)
        zero = covered & ~present
        frame.loc[zero, 'population'] = 0.0
        frame['population_year'] = year
        quality = pd.DataFrame({'Mesh Code': frame.mesh_code, 'Population Year': year,
            'Source Row Present': present, 'Source Tile Covered': covered,
            'Population Structural Zero': zero,
            'Population Coverage Gap': ~covered,
            'Invalid Published Total': present & ~np.isfinite(frame.population)})
        quality.to_parquet(OUT / f'population_quality_{year}.parquet', index=False)
        old_path = ROOT / f'data/processed/national/population_{year}_preprocessed.parquet'
        previous_hashes[str(old_path.relative_to(ROOT))] = sha(old_path)
        old = pd.read_parquet(old_path)
        assert old['Mesh Code'].tolist() == frame.mesh_code.tolist()
        np.testing.assert_array_equal(old.loc[present, 'Population'], frame.loc[present, 'population'])
        assert old.loc[zero, 'Population'].isna().all()
        assert frame.loc[~covered, 'population'].isna().all()
        assert frame.population.sum() == old.Population.sum() == TOTALS[year]
        staged = staging / f'population_{year}_confirmed_input.parquet'
        frame[['mesh_code', 'population', 'population_year']].to_parquet(staged, index=False)
        mapping = {'mesh_code': 'Mesh Code', 'population': 'Population', 'population_year': 'Population Year'}
        datasets[str(staged.relative_to(ROOT))] = dict(
            output=f'{DEST}/population_{year}_preprocessed.parquet',
            script=f'src/preprocessing/preprocess_national_population_zero_{year}.py',
            variables=[dict(original_name=a,readable_name=b,full_name=b,
                is_final_variable='yes' if a == 'population' else 'no',preprocessing=[],
                role='control' if a == 'population' else 'reference') for a,b in mapping.items()],
            spatial_preparation='src/preprocessing/prepare_national_population_zero_correction.py',
            source_details=dict(total_field=stats+'001',documented_absent_records_in_covered_tiles=0,
                uncovered_tiles_and_invalid_recorded_totals='NaN',reference=REFERENCE,
                statistical_imputation=False,reaggregation=False))
        coverage.append(dict(population_year=year,common_meshes=len(frame),downloaded_tiles=len(covered_tiles),
            published_meshes=int(present.sum()),structural_zero_meshes=int(zero.sum()),
            numeric_population_meshes=int(frame.population.notna().sum()),
            missing_population_meshes=int(frame.population.isna().sum()),
            coverage_gap_tiles=','.join(sorted(tiles-covered_tiles)),population_sum=int(frame.population.sum())))
        print(f'population {year}: {present.sum():,} source records, {zero.sum():,} documented zeros, '
              f'{frame.population.isna().sum():,} missing; total {frame.population.sum():,.0f}',flush=True)
    pd.DataFrame(audits).to_csv(OUT / 'raw_archive_audit.csv',index=False)
    pd.DataFrame(coverage).to_csv(OUT / 'population_coverage.csv',index=False)
    assert all(sha(ROOT / p) == h for p,h in hashes.items())
    assert all(sha(ROOT / p) == h for p,h in previous_hashes.items())
    contract = dict(confirmed=True,decision_id=DECISION,supersedes='MILI-D-20261009-010',
        datasets=datasets,common_meshes=len(grid),raw_sha256=hashes,previous_population_sha256=previous_hashes,
        raw_modified=False,source_numeric_values_preserved=True,official_census_totals_preserved=True,
        zero_rule='Absent third-order census record inside a verified complete first-order archive is zero.',
        gap_rule='No first-order archive or invalid published total remains NaN; never blanket fillna(0).',
        road_rule='Unknown and unlisted road observations remain NaN.',
        source_reference=REFERENCE)
    (OUT / 'decisions.json').write_text(json.dumps(contract,indent=2)+'\n')
    (OUT / 'source_evidence.json').write_text(json.dumps(dict(reference=REFERENCE,
        verified_date='2026-10-09',document='Statistics Bureau mesh download data notes',
        evidence=[dict(page=1,meaning='Census meshes with no population have no records.'),
            dict(page=2,meaning='Total population is exempt from disclosure suppression.'),
            dict(page=2,meaning='First-order downloads contain all records in the tile regardless of prefecture.')],
        archive_audit='raw_archive_audit.csv',literal_zero_records=0,
        source_archives=453,coverage_gap_primary_tiles=['4529']),indent=2)+'\n')


if __name__ == '__main__':
    main()
