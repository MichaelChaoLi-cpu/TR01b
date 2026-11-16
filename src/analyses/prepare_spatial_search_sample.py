#!/usr/bin/env python3
"""Prepare a reproducible spatial validation sample from the current panel.

This is model-independent preparation, not empirical local-model estimation.
Preserve the previous 1,286-center computational scale, resampling across the
current 151 primary tiles so recovered zero-population meshes are eligible.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from gwpr_twoways import mesh_centroids
from table_national_pooled_regression_with_census_structural_zeros import sha

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/spatial-search-inputs/population-zero-corrected'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source = ROOT / 'data/processed/national/population_zero_corrected/balanced_historical_panel_preprocessed.parquet'
    evidence = json.loads((ROOT / 'data/exp/data-preprocessing/population-zero-correction/panel_validation.json').read_text())
    digest = sha(source)
    assert digest == evidence['new_balanced_panel_sha256']
    sample = pd.read_parquet(source).sort_values(['Mesh Code', 'Road Year'])
    meshes = sample[['Mesh Code']].drop_duplicates().reset_index(drop=True)
    assert len(meshes) == 228988 and len(sample) == 915952
    meshes['Primary Tile'] = meshes['Mesh Code'].str[:4]
    coordinates = mesh_centroids(meshes['Mesh Code'].tolist())
    meshes['Latitude'], meshes['Longitude'] = coordinates.T
    population = sample['Population'].to_numpy().reshape(-1, 4)
    meshes['All Period Population Zero'] = (population == 0).all(axis=1)
    tiles = sorted(meshes['Primary Tile'].unique())
    counts = meshes.groupby('Primary Tile').size().reindex(tiles).to_numpy()
    target, seed = 1286, 20261010
    quota = np.minimum(4, counts)
    remaining = target - int(quota.sum())
    capacity = counts - quota
    fraction = remaining * capacity / capacity.sum()
    addition = np.floor(fraction).astype(int)
    leftover = remaining - int(addition.sum())
    for index in np.argsort(-(fraction - addition), kind='stable')[:leftover]:
        addition[index] += 1
    quota += addition
    assert quota.sum() == target and (quota <= counts).all()
    rng = np.random.default_rng(seed)
    parts = []
    for tile, count, selected_count in zip(tiles, counts, quota):
        eligible = meshes.loc[meshes['Primary Tile'].eq(tile)]
        selected = eligible.iloc[np.sort(rng.choice(len(eligible), size=int(selected_count), replace=False))].copy()
        selected['Validation Weight'] = float(count / selected_count)
        parts.append(selected)
    centers = pd.concat(parts, ignore_index=True).sort_values('Mesh Code').reset_index(drop=True)
    assert len(centers) == target and centers['Mesh Code'].is_unique
    assert centers['Primary Tile'].nunique() == 151
    assert np.isclose(centers['Validation Weight'].sum(), len(meshes))
    centers.to_csv(OUT / 'validation_centers.csv', index=False)
    pd.DataFrame({'Primary Tile': tiles, 'Eligible Meshes': counts, 'Validation Centers': quota}).to_csv(OUT / 'sampling_strata.csv', index=False)
    assert sha(source) == digest
    report = dict(status='passed', source=str(source.relative_to(ROOT)), source_sha256=digest,
                  national_meshes=len(meshes), observations=len(sample), primary_tiles=len(tiles), validation_centers=target,
                  seed=seed, sampling='Primary-tile strata, minimum four when available, proportional remaining allocation; no replacement.',
                  validation_weights='Tile mesh count divided by selected tile center count',
                  sampled_all_period_population_zero_meshes=int(centers['All Period Population Zero'].sum()),
                  all_zero_population_meshes=int(meshes['All Period Population Zero'].sum()),
                  validation_centers_sha256=sha(OUT / 'validation_centers.csv'),
                  local_model_estimated=False, bandwidth_selected=False, substantive_source_unchanged=True)
    (OUT / 'preparation_validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
