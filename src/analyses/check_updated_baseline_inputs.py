"""Check current core-complete inputs before the four-layer baseline rerun.

Read-only: confirms model variables and years without selecting geography or
estimating coefficients. Run locally with python3 from the project root.
"""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/four-layer-baseline-input-audit'
PERIODS = [2002, 2003, 2004, 2010, 2024]
POPULATION_YEARS = [2000, 2005, 2005, 2010, 2020]


def main():
    pointer = json.loads((ROOT / 'data/exp/data-preprocessing/active_panel.json').read_text())
    source = ROOT / pointer['core_balanced_panel']
    columns = ['Mesh Code', 'Road Year', 'Population Year', 'Nighttime Light Year',
               'Nighttime Radiance', 'Road Length Density', 'Population']
    frame = pd.read_parquet(source, columns=columns).sort_values(['Mesh Code', 'Road Year'])
    n = frame['Mesh Code'].nunique()
    assert len(frame) == n*5 and not frame.duplicated(['Mesh Code', 'Road Year']).any()
    assert np.array_equal(frame['Road Year'].to_numpy().reshape(n, 5), np.tile(PERIODS, (n, 1)))
    assert np.array_equal(frame['Population Year'].to_numpy().reshape(n, 5), np.tile(POPULATION_YEARS, (n, 1)))
    assert frame['Nighttime Light Year'].equals(frame['Road Year'])
    assert np.isfinite(frame[columns[-3:]].to_numpy()).all()
    population = frame['Population'].to_numpy().reshape(n, 5)
    assert np.array_equal(population[:, 1], population[:, 2])
    with source.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    geography = json.loads((ROOT / 'data/exp/data-preprocessing/expanded-analysis-geography/geography_audit_summary.json').read_text())
    candidate = json.loads((ROOT / 'data/exp/data-preprocessing/expanded-analysis-geography/candidate_contract.json').read_text())
    assert candidate['source_sha256'] == checksum and candidate['meshes'] == n
    report = dict(status='passed', model_decision_id='MILI-D-20261010-025',
        source=pointer['core_balanced_panel'], source_sha256=checksum,
        candidate_meshes=n, candidate_observations=len(frame), periods=PERIODS,
        population_years=POPULATION_YEARS, outcome='Nighttime Radiance',
        explanatory=['Road Length Density', 'Population'], effects=[], intercept=True,
        candidate_zero_population_observations=int((population == 0).sum()),
        candidate_all_period_zero_population_meshes=int((population == 0).all(axis=1).sum()),
        candidate_common_administrative_meshes=geography['potential_common_meshes'],
        geographic_cohort_decision='pending', regressions_fitted=False,
        core_values_finite=True, unique_five_period_keys=True, input_data_modified=False,
        gwpr_bandwidth_km=3, gwpr_bandwidth_reoptimized=False)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'input_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    (OUT / 'README.md').write_text(
        '# Four-layer baseline: input readiness\n\n'
        'Confirmed baseline: Nighttime Radiance on intercept, Road Length Density and Population, '
        'pooled without fixed effects. National and administrative inference retains mesh-clustered CR1; '
        'the exploratory local model retains 3 km bisquare weighting. No added facility or land-cover controls.\n\n'
        f'All {n:,} candidate meshes have unique five-period keys and finite core values. '
        'Original road/light years and matched population years are verified, including the reused 2005 population. '
        f"The potential shared administrative cohort contains {geography['potential_common_meshes']:,} meshes. "
        'Geographic cohort selection is pending; no model is fitted and no data or AnaSOP is modified.\n\n'
        'Reproduce: `python3 src/analyses/check_updated_baseline_inputs.py`.\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
