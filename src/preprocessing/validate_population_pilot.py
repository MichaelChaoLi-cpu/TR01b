#!/usr/bin/env python3
"""Validate confirmed population Parquets against original pilot archives."""
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/exp'))
from audit_population_pilot import read_source, FIELDS, sha

PILOT = ROOT / 'data/exp/data-preprocessing/pilot'
OUT = PILOT / 'population'


def main():
    contract = json.loads((OUT / 'population_decisions.json').read_text())
    assert contract['confirmed']
    grid = pd.read_csv(PILOT / 'common_grid_trial.csv', dtype={'mesh_code': 'string'})
    quality = pd.read_csv(OUT / 'population_quality_flags.csv',
                          dtype={'mesh_code': 'string', 'population_literal': 'string'})
    assert len(quality) == 25600
    assert not quality.duplicated(['mesh_code', 'population_year']).any()
    summaries, hashes, input_hashes = [], {}, {}
    for year, field in FIELDS.items():
        source, archive, _ = read_source(year)
        assert sha(archive) == contract['raw_archive_sha256'][str(archive.relative_to(ROOT))]
        path = ROOT / f'data/processed/pilot/population_{year}_preprocessed.parquet'
        actual = pd.read_parquet(path)
        columns = ['Mesh Code', 'Population', 'Population Year']
        if year == 2020:
            columns += ['Disclosure Destination', 'Merged Mesh Codes', 'Disclosure Status']
        assert actual.columns.tolist() == columns
        assert all(c.isascii() and c == c.strip() for c in columns)
        assert len(actual) == 6400 and actual['Mesh Code'].is_unique
        assert set(actual['Mesh Code']) == set(grid.mesh_code)
        assert actual['Mesh Code'].str.fullmatch(r'5030[0-7]{2}[0-9]{2}').all()
        assert actual['Population Year'].eq(year).all()
        indexed = actual.set_index('Mesh Code')
        source_indexed = source.set_index('KEY_CODE')
        published = pd.to_numeric(source[field], errors='coerce').to_numpy(dtype=float)
        np.testing.assert_allclose(indexed.loc[source.KEY_CODE, 'Population'], published,
                                   rtol=0, atol=0, equal_nan=True)
        unlisted = ~actual['Mesh Code'].isin(source.KEY_CODE)
        assert actual.loc[unlisted, 'Population'].isna().all()
        numeric = actual.Population.dropna()
        assert numeric.ge(0).all() and numeric.mod(1).eq(0).all()
        assert int(numeric.sum()) == int(np.nansum(published))
        flags = quality[quality.population_year.eq(year)].set_index('mesh_code').loc[actual['Mesh Code']]
        assert flags.source_row_present.to_numpy().tolist() == (~unlisted).tolist()
        assert not flags.total_population_reaggregated.any()
        summary = dict(population_year=year, meshes=len(actual), columns=len(columns),
                       numeric_population=int(actual.Population.notna().sum()),
                       missing_population=int(actual.Population.isna().sum()),
                       unlisted_meshes=int(unlisted.sum()), numeric_zero=int(actual.Population.eq(0).sum()),
                       published_total_sum=int(numeric.sum()), source_values_unchanged=True)
        if year == 2020:
            expected_status = pd.to_numeric(source_indexed.HTKSYORI, errors='coerce')
            np.testing.assert_allclose(indexed.loc[source.KEY_CODE, 'Disclosure Status'], expected_status,
                                       rtol=0, atol=0, equal_nan=True)
            assert actual.loc[unlisted, ['Disclosure Status', 'Disclosure Destination', 'Merged Mesh Codes']].isna().all().all()
            for original, readable in [('HTKSAKI', 'Disclosure Destination'), ('GASSAN', 'Merged Mesh Codes')]:
                expected = source_indexed[original].replace('', pd.NA).astype('string')
                observed = indexed.loc[source.KEY_CODE, readable].astype('string')
                pd.testing.assert_series_equal(observed, expected, check_names=False)
            detail_suppressed = indexed['Disclosure Status'].eq(2)
            assert detail_suppressed.sum() == 282
            assert indexed.loc[detail_suppressed, 'Population'].notna().all()
            summary.update(detail_suppressed_meshes_with_published_totals=int(detail_suppressed.sum()),
                           detail_suppressed_mesh_published_total=int(indexed.loc[detail_suppressed, 'Population'].sum()))
        else:
            assert flags.detail_disclosure_status.isna().all()
            assert not flags.disclosure_metadata_available.any()
        hashes[str(path.relative_to(ROOT))] = sha(path)
        staged = PILOT / f'confirmed-inputs/population_{year}_confirmed_input.parquet'
        input_hashes[str(staged.relative_to(ROOT))] = sha(staged)
        summaries.append(summary)
    pd.DataFrame(summaries).to_csv(OUT / 'processed_summary.csv', index=False)
    report = dict(status='passed', decision_id=contract['decision_id'], source_parquets=4,
                  total_rows=25600, selected_column_entries=15, summaries=summaries,
                  raw_archives_unchanged=True, original_population_values_unchanged=True,
                  unlisted_population_is_nan=True, total_reaggregation_performed=False,
                  zero_imputation_performed=False, final_estimation_sample_selected=False,
                  output_sha256=hashes, prepared_input_sha256=input_hashes)
    (OUT / 'processed_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
