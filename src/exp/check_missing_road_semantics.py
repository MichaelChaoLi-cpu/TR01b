#!/usr/bin/env python3
"""Check whether missing road cells can all be assumed to be empty sea.

Population overlap is diagnostic only; it does not prove road presence or
authorize population selection, zero imputation, or analysis-sample changes.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/pilot'
SOURCES = ROOT / 'data/exp/data-organization/source-tables'


def main():
    flags = pd.read_csv(OUT / 'road_quality_flags.csv', dtype={'mesh_code': 'string'})
    counts, examples = [], []
    for road_year, population_year, field in [
        (2002, 2000, 'T000146001'), (2003, 2005, 'T000148001'),
        (2004, 2005, 'T000148001'), (2010, 2010, 'T000608001')]:
        source = next(SOURCES.glob(f'population_{population_year}_*.csv'))
        population = pd.read_csv(source, dtype={'KEY_CODE': 'string'}, keep_default_na=False)
        population['source_population'] = pd.to_numeric(population[field], errors='coerce')
        joined = flags[flags.road_year == road_year].merge(
            population[['KEY_CODE', 'source_population']], left_on='mesh_code', right_on='KEY_CODE',
            how='left', validate='one_to_one')
        for label, mask in [('unknown', joined.source_unknown == True),
                            ('unlisted', joined.source_row_present == False)]:
            positive = joined[mask & (joined.source_population > 0)].copy()
            counts.append(dict(road_year=road_year, population_year=population_year,
                               missing_type=label, missing_meshes=int(mask.sum()),
                               meshes_with_reported_positive_population=len(positive)))
            positive['missing_type'] = label
            positive['population_year'] = population_year
            examples.append(positive[['mesh_code', 'road_year', 'population_year',
                                      'missing_type', 'source_population']])
    pd.DataFrame(counts).to_csv(OUT / 'missing_road_population_overlap.csv', index=False)
    pd.concat(examples).to_csv(OUT / 'missing_road_populated_meshes.csv', index=False)
    print(pd.DataFrame(counts).to_string(index=False))


if __name__ == '__main__':
    main()
