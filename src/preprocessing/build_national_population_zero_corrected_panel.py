#!/usr/bin/env python3
"""Replace only Population in a separately versioned historical panel; audit changes."""
from pathlib import Path
import json

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from prepare_national_population_zero_correction import ROOT, OUT, DEST, POP, TOTALS, DECISION, sha

MATCH = {2002:2000, 2003:2005, 2004:2005, 2010:2010}


def main():
    contract = json.loads((OUT / 'decisions.json').read_text())
    assert contract['confirmed'] and contract['decision_id'] == DECISION
    old_path = ROOT / 'data/processed/national/road_population_light_national_preprocessed.parquet'
    protected = list((ROOT / 'data/processed/national').glob('*.parquet'))
    protected += list((ROOT / 'data/processed/pilot').glob('*.parquet'))
    before = {str(p.relative_to(ROOT)):sha(p) for p in protected}
    old_file = pq.ParquetFile(old_path)
    assert old_file.num_row_groups == len(MATCH)
    grid = pd.read_parquet(ROOT / 'data/exp/data-preprocessing/national/common_grid.parquet')
    codes = grid.mesh_code.tolist()
    new_path = ROOT / DEST / old_path.name
    balanced_path = ROOT / DEST / 'balanced_historical_panel_preprocessed.parquet'
    writer, period_frames = None, []
    old_numeric, new_numeric, coverage = [], [], []
    try:
        for index, (year,pop_year) in enumerate(MATCH.items()):
            old = old_file.read_row_group(index).to_pandas()
            assert old['Road Year'].eq(year).all() and old['Population Year'].eq(pop_year).all()
            assert old['Mesh Code'].tolist() == codes
            pop = pd.read_parquet(ROOT / DEST / f'population_{pop_year}_preprocessed.parquet')
            assert pop['Mesh Code'].tolist() == codes and pop['Population Year'].eq(pop_year).all()
            frame = old.copy()
            frame['Population'] = pop['Population'].to_numpy()
            for column in old.columns:
                if column != 'Population':
                    pd.testing.assert_series_equal(frame[column],old[column])
            published = old['Population'].notna()
            np.testing.assert_array_equal(frame.loc[published,'Population'], old.loc[published,'Population'])
            changed = ~published & frame['Population'].notna()
            assert frame.loc[changed,'Population'].eq(0).all()
            variables = ['Road Length Density','Population','Nighttime Radiance']
            previous = np.isfinite(old[variables].to_numpy()).all(axis=1)
            current = np.isfinite(frame[variables].to_numpy()).all(axis=1)
            assert (~previous | current).all()
            old_numeric.append(previous);new_numeric.append(current)
            coverage.append(dict(road_year=year,population_year=pop_year,light_year=year,
                common_meshes=len(frame),numeric_roads=int(frame['Road Length Density'].notna().sum()),
                previous_numeric_population=int(published.sum()),
                revised_numeric_population=int(frame.Population.notna().sum()),
                population_structural_zeros_restored=int(changed.sum()),
                remaining_missing_population=int(frame.Population.isna().sum()),
                numeric_lights=int(frame['Nighttime Radiance'].notna().sum()),
                previous_joint_numeric_meshes=int(previous.sum()),revised_joint_numeric_meshes=int(current.sum())))
            table = pa.Table.from_pandas(frame,preserve_index=False)
            if writer is None: writer=pq.ParquetWriter(new_path,table.schema)
            writer.write_table(table)
            period_frames.append(frame)
            print(f'panel {year}: {previous.sum():,} -> {current.sum():,} jointly numeric meshes',flush=True)
    finally:
        if writer: writer.close()
    previous_count = np.column_stack(old_numeric).sum(axis=1)
    revised_count = np.column_stack(new_numeric).sum(axis=1)
    previous_balanced, balanced = previous_count == 4, revised_count == 4
    added = balanced & ~previous_balanced
    assert np.all(~previous_balanced | balanced)
    membership = pd.DataFrame({'Mesh Code':codes,'Previous Joint Numeric Periods':previous_count,
        'Revised Joint Numeric Periods':revised_count,'Previous Complete Four Periods':previous_balanced,
        'Complete Four Periods':balanced,'Added By Population Zero Correction':added})
    membership.to_parquet(OUT / 'mesh_availability.parquet',index=False)
    membership.loc[balanced].to_parquet(OUT / 'balanced_sample_membership.parquet',index=False)
    pd.DataFrame(coverage).to_csv(OUT / 'coverage_by_period.csv',index=False)
    estimation = pd.concat([f.loc[balanced] for f in period_frames],ignore_index=True)
    estimation = estimation.sort_values(['Mesh Code','Road Year'],kind='stable').reset_index(drop=True)
    assert estimation.groupby('Mesh Code',sort=False)['Road Year'].agg(list).map(lambda x:x==list(MATCH)).all()
    assert np.isfinite(estimation[['Road Length Density','Population','Nighttime Radiance']]).all().all()
    estimation.to_parquet(balanced_path,index=False)
    zeros = estimation.assign(zero=estimation.Population.eq(0)).groupby('Mesh Code').zero.sum()
    added_codes = membership.loc[added,'Mesh Code']
    population_summary = dict(
        meshes_zero_population_in_all_four_periods=int(zeros.eq(4).sum()),
        meshes_zero_population_in_at_least_one_period=int(zeros.gt(0).sum()),
        new_meshes_zero_population_in_all_four_periods=int(zeros.loc[added_codes].eq(4).sum()),
        zero_population_observations_in_balanced_panel=int(estimation.Population.eq(0).sum()),
        population_missing_meshes_in_balanced_panel=int(estimation.Population.isna().sum()))
    (OUT / 'balanced_population_summary.json').write_text(json.dumps(population_summary,indent=2)+'\n')
    for year in POP:
        pop = pd.read_parquet(ROOT / DEST / f'population_{year}_preprocessed.parquet')
        assert pop.Population.sum() == TOTALS[year]
    assert all(sha(ROOT / p) == h for p,h in before.items())
    assert all(sha(ROOT / p) == h for p,h in contract['raw_sha256'].items())
    meta = pq.read_metadata(new_path)
    assert meta.num_rows == len(grid)*4 and meta.num_columns == 13
    balanced_meta = pq.read_metadata(balanced_path)
    assert balanced_meta.num_rows == int(balanced.sum())*4 and balanced_meta.num_columns == 13
    sample_summary = dict(previous_meshes=int(previous_balanced.sum()),revised_meshes=int(balanced.sum()),
        added_meshes=int(added.sum()),removed_meshes=int((previous_balanced & ~balanced).sum()),
        previous_observations=int(previous_balanced.sum())*4,revised_observations=int(balanced.sum())*4,
        revised_primary_tiles=int(grid.loc[balanced,'mesh_code'].str[:4].nunique()))
    report = dict(status='passed',decision_id=DECISION,historical_periods=list(MATCH),population_matching=MATCH,
        complete_panel_rows=meta.num_rows,columns=13,sample=sample_summary,
        official_census_totals_preserved=TOTALS,source_published_population_preserved=True,
        roads_lights_years_metadata_exactly_unchanged=True,raw_files_unchanged=True,
        previous_processed_files_unchanged=True,protected_input_sha256=before,
        changed_value_rule='Only previously absent population records in verified covered tiles become zero.',
        population_missing_primary_tiles=['4529'],coastal_or_island_mask_applied=False,
        new_panel=str(new_path.relative_to(ROOT)),new_balanced_panel=str(balanced_path.relative_to(ROOT)),
        new_panel_sha256=sha(new_path),new_balanced_panel_sha256=sha(balanced_path),
        dependent_analysis_status='Previous FE, regional, prefecture, Moran, bandwidth CV, GWPR and map outputs use the old population version. Corrected-sample estimates have not been computed.')
    (OUT / 'panel_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(sample_summary,indent=2),flush=True)


if __name__ == '__main__':
    main()
