"""Read-only preflight for requested national, regional, prefecture and GWPR reruns.

Run locally: python3 src/analyses/check_regression_reprocessing_inputs.py
Only writes its exploratory readiness report; it does not estimate models.
"""
from pathlib import Path
import ast
import hashlib
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/regression-reprocessing/preflight'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    names = ['national', 'regional', 'prefecture']
    contracts = {
        name: json.loads((ROOT / f'data/exp/estimation-framework-planning/{name}-pooled-population-zero-corrected/estimation_decisions.json').read_text())
        for name in names
    }
    national = contracts['national']
    path = ROOT / national['input']
    fingerprint = sha(path)
    sample = pd.read_parquet(path).sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    periods = national['periods']
    meshes = sample['Mesh Code'].nunique()
    assert len(sample) == national['expected_observations'] == meshes * len(periods)
    assert meshes == national['expected_meshes']
    assert not sample.duplicated(['Mesh Code', 'Road Year']).any()
    assert np.isfinite(sample[[national['outcome']] + national['explanatory']].to_numpy()).all()
    assert np.array_equal(sample['Road Year'].to_numpy().reshape(meshes, len(periods)), np.tile(periods, (meshes, 1)))
    assert np.array_equal(sample['Population Year'].to_numpy().reshape(meshes, len(periods)), np.tile(national['population_years'], (meshes, 1)))
    assert sample['Nighttime Light Year'].equals(sample['Road Year'])
    report = {'status': 'input_checks_passed_scope_confirmation_pending',
              'scope_question': 'Rerun four model families on existing periods or add 2024?',
              'historical_panel': {'path': national['input'], 'sha256': fingerprint,
                                   'meshes': int(meshes), 'observations': len(sample),
                                   'road_year_counts': {str(k): int(v) for k, v in sample['Road Year'].value_counts().sort_index().items()},
                                   'population_year_counts': {str(k): int(v) for k, v in sample['Population Year'].value_counts().sort_index().items()},
                                   'zero_population_observations': int(sample['Population'].eq(0).sum())},
              'models': {}, 'raw_candidate_inventory': {}, 'models_executed': False}
    for name, contract in contracts.items():
        assert contract['input'] == national['input'] and contract['periods'] == periods
        assert contract['effects'] == [] and contract['intercept']
        ast.parse((ROOT / contract['analysis_script']).read_text())
        previous_path = ROOT / f'data/exp/figure-table-generation/{name}-pooled-population-zero-corrected/validation.json'
        previous = json.loads(previous_path.read_text())
        previous_input_sha = previous.get('input_sha256', previous.get('protected_sha256', {}).get(national['input']))
        assert previous['status'] == 'passed' and previous_input_sha == fingerprint
        entry = {'script': contract['analysis_script'], 'input_sha256_verified': True,
                 'effects': [], 'intercept': True, 'existing_output': contract['output_workbook']}
        if name != 'national':
            mapping_key = 'region_mapping' if name == 'regional' else 'prefecture_mapping'
            mapping = pd.read_parquet(ROOT / contract[mapping_key])
            assert mapping['Mesh Code'].is_unique and set(mapping['Mesh Code']) == set(sample['Mesh Code'])
            group = 'Region' if name == 'regional' else 'Prefecture Code'
            assert mapping[group].notna().all()
            entry['groups'] = int(mapping[group].nunique())
            assert entry['groups'] == (9 if name == 'regional' else 47)
        report['models'][name] = entry
    gwpr_contract = json.loads((ROOT / 'data/exp/gwpr-pooled-population-zero-corrected/mesh-map-3km/execution_contract.json').read_text())
    assert gwpr_contract['source'] == national['input'] and gwpr_contract['source_sha256'] == fingerprint
    assert gwpr_contract['periods'] == periods and gwpr_contract['effects'] == []
    report['models']['gwpr'] = {'script': 'src/analyses/run_gwpr_pooled_candidate_mesh_map.py',
                               'input_sha256_verified': True, 'bandwidth_km': gwpr_contract['bandwidth_km'],
                               'bandwidth_status': gwpr_contract['bandwidth_status'], 'effects': []}
    for label, relative in {
        'roads_2024': 'data/raw/roads/n13_lines/2024',
        'population_2020': 'data/raw/population/estat_1km/2020',
        'lights_2024': 'data/raw/nighttime_lights/viirs_like_v2/dataset_10.1/2024'
    }.items():
        files = sorted((ROOT / relative).glob('*.zip'))
        report['raw_candidate_inventory'][label] = {
            'directory': relative, 'zip_files': len(files), 'total_bytes': sum(p.stat().st_size for p in files),
            'inventory_only_not_completeness_validation': True}
    report['national_2024_processed_files'] = [str(p.relative_to(ROOT)) for p in (ROOT / 'data/processed/national').rglob('*2024*.parquet')]
    report['national_2020_processed_files'] = [str(p.relative_to(ROOT)) for p in (ROOT / 'data/processed/national').rglob('*2020*.parquet')]
    report['five_period_readiness'] = 'Not ready: national 2024 preprocessing/linkage and source comparability unresolved; scope unconfirmed.'
    assert sha(path) == fingerprint
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'readiness.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'models'}, indent=2))


if __name__ == '__main__':
    main()
