"""Project existing approved variables onto the focused extension cohort."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/processed/national/land_cover_poi_extension'
PLAN = ROOT / 'data/exp/land-cover-poi-extension'
LAND = ['Urban Land Cover Share', 'Forest Land Cover Share', 'Cropland Land Cover Share',
        'Cropland Mosaic Land Cover Share', 'Water Land Cover Share']
POI = ['Distance to Railway Station', 'Distance to Passenger Airport', 'School Facility Count',
       'Medical Facility Count', 'Logistics Facility Count', 'Visitor and Event Facility Count']
EXPLANATORY = ['Road Length Density', 'Population'] + LAND + POI
YEARS = [2002, 2003, 2004, 2010, 2024]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    PLAN.mkdir(parents=True, exist_ok=True)
    pointer = json.loads((ROOT / 'data/exp/data-preprocessing/active_panel.json').read_text())
    source, baseline = ROOT / pointer['core_balanced_panel'], ROOT / pointer['active_baseline_panel']
    protected = {str(p.relative_to(ROOT)): sha(p) for p in [source, baseline, ROOT / 'data/exp/data-preprocessing/active_panel.json']}
    base = pd.read_parquet(baseline).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    codes = base['Mesh Code'].drop_duplicates().tolist()
    references = ['Other Land Cover Share', 'Land Cover Year', 'Land Cover Coverage', 'Land Cover Source Coverage',
        'Land Cover Unclassified Share', 'Land Cover Adjusted Share', 'Land Cover No Data Share',
        'Land Cover No Valid Pixels', 'Land Cover Incomplete Coverage', 'Land Cover Product',
        'School Facility Source Year', 'Medical Facility Source Year', 'Logistics Facility Source Year',
        'Visitor and Event Facility Source Year', 'Railway Source Year', 'Airport Source Year']
    extra = pd.read_parquet(source, columns=['Mesh Code', 'Road Year'] + LAND + POI + references,
                           filters=[('Mesh Code', 'in', codes)]).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    for key in ['Mesh Code', 'Road Year']:
        assert np.array_equal(base[key].to_numpy(), extra[key].to_numpy())
    augmented = pd.concat([base, extra.drop(columns=['Mesh Code', 'Road Year'])], axis=1)
    finite = np.isfinite(augmented[['Nighttime Radiance'] + EXPLANATORY].to_numpy(float)).all(axis=1)
    excluded = augmented.loc[~finite, 'Mesh Code'].unique().tolist()
    assert set(excluded) == {'36533738', '36533747', '36533748', '36533758'}
    keep = ~augmented['Mesh Code'].isin(excluded)
    augmented.loc[~keep, ['Mesh Code', 'Road Year']].to_csv(PLAN / 'unavailable_land_cover_membership.csv', index=False)
    panel = augmented.loc[keep].reset_index(drop=True)
    assert len(panel) == 1916930 and panel['Mesh Code'].nunique() == 383386
    assert not panel.duplicated(['Mesh Code', 'Road Year']).any()
    assert np.array_equal(panel['Road Year'].to_numpy().reshape(-1, 5), np.tile(YEARS, (383386, 1)))
    assert np.array_equal(panel[POI].to_numpy().reshape(-1, 5, 6), np.repeat(panel[POI].to_numpy().reshape(-1, 5, 6)[:, :1], 5, axis=1))
    assert np.array_equal(panel[base.columns].to_numpy(), base.loc[keep].to_numpy())
    output = OUT / 'focused_extension_panel_preprocessed.parquet'
    panel.to_parquet(output, index=False)
    pd.testing.assert_frame_equal(panel, pd.read_parquet(output))
    assert all(sha(ROOT / path) == value for path, value in protected.items())
    contract = dict(confirmed=True, decision_id='MILI-D-20261010-033', input=str(output.relative_to(ROOT)),
        source=str(source.relative_to(ROOT)), source_sha256=protected[str(source.relative_to(ROOT))],
        baseline=str(baseline.relative_to(ROOT)), panel_sha256=sha(output), outcome='Nighttime Radiance',
        explanatory=EXPLANATORY, land_cover_reference='Other Land Cover Share', poi_controls=POI,
        periods=YEARS, population_years=[2000, 2005, 2005, 2010, 2020], meshes=383386, observations=len(panel),
        excluded_missing_land_cover_meshes=excluded, excluded_observations=int((~keep).sum()),
        partial_land_cover_records=int(panel['Land Cover Incomplete Coverage'].sum()),
        zero_population_observations=int(panel['Population'].eq(0).sum()), effects=[], intercept=True,
        original_units=True, imputation=False, static_poi_replicated=True, candidate_radii_km=list(range(3, 51)),
        uncertainty='Mesh-clustered CR1; normal 95 percent confidence intervals',
        protected_inputs_unchanged=True, protected_sha256=protected,
        formal_baseline_outputs_preserved=True)
    (PLAN / 'execution_contract.json').write_text(json.dumps(contract, indent=2) + '\n')
    (PLAN / 'preprocessing_validation.json').write_text(json.dumps(dict(status='passed', **contract), indent=2) + '\n')
    print(json.dumps({key: contract[key] for key in ['meshes', 'observations', 'explanatory', 'partial_land_cover_records', 'zero_population_observations']}, indent=2))


if __name__ == '__main__':
    main()
