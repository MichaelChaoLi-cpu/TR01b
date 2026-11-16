"""Construct the user-approved common geography for the four-layer baseline.

Original augmented panels remain unchanged. Region areas aggregate the existing
prefectural intersection audit; reviewed zero-overlap exceptions are reused.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/current-common-cohort'
DEST = ROOT / 'data/processed/national/current_common_cohort'
GEO = ROOT / 'data/exp/data-preprocessing/expanded-analysis-geography/prefecture-overlap'
YEARS = [2002, 2003, 2004, 2010, 2024]
CORE = ['Mesh Code', 'Road Year', 'Population Year', 'Nighttime Light Year',
        'Nighttime Radiance', 'Road Length Density', 'Population']


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + '\n')


def prepare():
    OUT.mkdir(parents=True, exist_ok=True); DEST.mkdir(parents=True, exist_ok=True)
    baseline = OUT / 'AnaSOP_before_common_cohort.txt'
    if not baseline.exists():
        baseline.write_bytes((ROOT / 'docs/AnaSOP.md').read_bytes())
    pointer = json.loads((ROOT / 'data/exp/data-preprocessing/active_panel.json').read_text())
    source = ROOT / pointer['core_balanced_panel']
    protected = {str(p.relative_to(ROOT)): sha(p) for p in [source,
        GEO / 'mesh_prefecture_confirmed_input.csv', GEO / 'mesh_prefecture_overlaps.csv',
        ROOT / 'data/processed/national/five_period/mesh_prefecture_national_preprocessed.parquet',
        ROOT / 'data/processed/national/five_period/mesh_region_national_preprocessed.parquet']}
    regions = json.loads((ROOT / 'data/exp/data-preprocessing/regional/geometry_validation.json').read_text())['regions']
    pref_region = {f'{p:02}': r for r, prefs in regions.items() for p in prefs}
    previous_pref = pd.read_parquet(ROOT / 'data/processed/national/five_period/mesh_prefecture_national_preprocessed.parquet')
    previous_region = pd.read_parquet(ROOT / 'data/processed/national/five_period/mesh_region_national_preprocessed.parquet')
    for frame in [previous_pref, previous_region]:
        frame['Mesh Code'] = frame['Mesh Code'].astype(str)
    names = previous_pref.groupby('Prefecture Code')['Prefecture'].first().to_dict()
    raw = pd.read_csv(GEO / 'mesh_prefecture_confirmed_input.csv', dtype={'mesh_code': str, 'prefecture_code': str})
    ordinary = raw.loc[raw.assignment_status.eq('assigned')].copy()
    assert len(ordinary) == 383371 and ordinary.prefecture_code.notna().all()
    # Largest total Region overlap, rather than assuming the largest Prefecture
    # must also belong to the largest Region.
    overlaps = pd.read_csv(GEO / 'mesh_prefecture_overlaps.csv', dtype={'mesh_code': str, 'prefecture_code': str})
    overlaps['Region'] = overlaps.prefecture_code.map(pref_region)
    area = overlaps.groupby(['mesh_code', 'Region'], as_index=False).land_overlap_m2.sum()
    ordered = area.sort_values(['mesh_code', 'land_overlap_m2', 'Region'], ascending=[True, False, True])
    selected = ordered.drop_duplicates('mesh_code').set_index('mesh_code')
    for code, group in ordered.groupby('mesh_code', sort=False):
        if len(group) > 1:
            assert abs(group.land_overlap_m2.iloc[0]-group.land_overlap_m2.iloc[1]) > 1e-6, code
    mapping = pd.DataFrame({'Mesh Code': ordinary.mesh_code.to_numpy(),
        'Prefecture Code': ordinary.prefecture_code.to_numpy(),
        'Prefecture': ordinary.prefecture_code.map(names).to_numpy(),
        'Region': ordinary.mesh_code.map(selected.Region).to_numpy(),
        'Total Land Overlap': ordinary.total_land_overlap.to_numpy(),
        'No Land Overlap': False, 'Assignment Status': 'assigned',
        'Prefecture Assignment Method': 'positive_land_area',
        'Region Assignment Method': 'positive_land_area',
        'Nearest Land Distance': np.nan})
    reviewed = previous_pref.loc[previous_pref['No Land Overlap']].copy()
    assert len(reviewed) == 19
    exception = reviewed[['Mesh Code', 'Prefecture Code', 'Prefecture', 'Total Land Overlap',
                          'No Land Overlap', 'Assignment Status', 'Prefecture Assignment Method', 'Nearest Land Distance']].copy()
    exception = exception.merge(previous_region[['Mesh Code', 'Region', 'Region Assignment Method']],
                                on='Mesh Code', validate='one_to_one')
    mapping = pd.concat([mapping, exception[mapping.columns]], ignore_index=True).sort_values('Mesh Code').reset_index(drop=True)
    assert len(mapping) == 383390 and mapping['Mesh Code'].is_unique
    assert mapping[['Region', 'Prefecture Code', 'Prefecture']].notna().all().all()
    for old, column in [(previous_pref, 'Prefecture Code'), (previous_region, 'Region')]:
        joined = old[['Mesh Code', column]].merge(mapping[['Mesh Code', column]], on='Mesh Code',
                                                how='left', suffixes=('_old', '_new'), validate='one_to_one')
        assert joined[column+'_old'].equals(joined[column+'_new']), column
    frame = pd.read_parquet(source, columns=CORE)
    selected_frame = frame.loc[frame['Mesh Code'].isin(mapping['Mesh Code'])].sort_values(['Mesh Code', 'Road Year']).reset_index(drop=True)
    assert len(selected_frame) == len(mapping)*5 and np.isfinite(selected_frame[CORE[-3:]].to_numpy()).all()
    assert np.array_equal(selected_frame['Road Year'].to_numpy().reshape(-1, 5), np.tile(YEARS, (len(mapping), 1)))
    merged = selected_frame.merge(mapping[['Mesh Code', 'Region', 'Prefecture Code', 'Prefecture', 'No Land Overlap']],
                                   on='Mesh Code', validate='many_to_one', sort=False)
    for c in CORE:
        assert np.array_equal(merged[c].to_numpy(), selected_frame[c].to_numpy()), c
    inputs = OUT / 'confirmed-inputs'; inputs.mkdir(exist_ok=True)
    panel_input = inputs / 'baseline_panel_input.parquet'
    mapping_input = inputs / 'mesh_geography_input.parquet'
    merged.to_parquet(panel_input, index=False, compression='zstd')
    mapping.to_parquet(mapping_input, index=False, compression='zstd')
    datasets = {}
    for path, name in [(panel_input, 'baseline_panel'), (mapping_input, 'mesh_geography')]:
        table = merged if path == panel_input else mapping
        datasets[str(path.relative_to(ROOT))] = dict(output=str((DEST / f'{name}_preprocessed.parquet').relative_to(ROOT)),
            script=f'src/preprocessing/preprocess_current_common_{name}.py',
            variables=[dict(original_name=c, readable_name=c, full_name=c,
                is_final_variable='yes' if c in CORE[-3:] else 'no', preprocessing=[]) for c in table])
    population = merged['Population'].to_numpy().reshape(-1, 5)
    dump(OUT / 'decisions.json', dict(confirmed=True, decision_id='MILI-D-20261010-026',
        model_decision_id='MILI-D-20261010-025', datasets=datasets, protected_inputs=protected,
        years=YEARS, population_years=[2000, 2005, 2005, 2010, 2020], regions=regions,
        meshes=len(mapping), observations=len(merged), reviewed_exceptions=19,
        candidate_meshes=966400, excluded_unattributable_meshes=966400-len(mapping),
        previous_meshes_retained=len(previous_pref), added_meshes=len(mapping)-len(previous_pref),
        zero_population_observations=int((population == 0).sum()),
        all_period_zero_population_meshes=int((population == 0).all(1).sum()),
        no_island_exclusion=True, additional_covariates_used=False,
        cohort_rule='Positive administrative overlap or an existing reviewed exception; complete five-period core data.',
        regional_rule='Largest summed positive prefectural overlap within each official Region.',
        original_core_values_preserved=True, previous_geographic_assignments_preserved=True))
    print('Common cohort prepared:', len(mapping), 'meshes;', len(merged), 'records.', flush=True)


def generate():
    subprocess.run([sys.executable, str(ROOT / '.codex/skills/data-preprocessing/scripts/generate_preprocessing_script.py'),
                    '--root', str(ROOT), '--decisions', str(OUT / 'decisions.json'), '--pretty'], check=True)
    d = json.loads((OUT / 'decisions.json').read_text())
    for source, spec in d['datasets'].items():
        subprocess.run([sys.executable, str(ROOT / spec['script'])], check=True)
        pd.testing.assert_frame_equal(pd.read_parquet(ROOT / source), pd.read_parquet(ROOT / spec['output']))
    for path, checksum in d['protected_inputs'].items():
        assert sha(ROOT / path) == checksum
    panel = DEST / 'baseline_panel_preprocessed.parquet'
    report = dict(d, status='passed', panel=str(panel.relative_to(ROOT)), panel_sha256=sha(panel),
                  mapping=str((DEST / 'mesh_geography_preprocessed.parquet').relative_to(ROOT)),
                  mapping_sha256=sha(DEST / 'mesh_geography_preprocessed.parquet'),
                  source_inputs_unchanged=True, generated_outputs_readback_verified=True)
    dump(OUT / 'panel_validation.json', report)
    (OUT / 'README.md').write_text(
        '# Approved common cohort for four baseline layers\n\n'
        f"{d['meshes']:,} meshes and {d['observations']:,} observations in 2002, 2003, 2004, 2010 and 2024. "
        'Retain every positive-overlap candidate, all eligible islands and nineteen reviewed exceptions. '
        'All previous 228,988 meshes and their Region/Prefecture assignments remain unchanged. '
        'The original 210-column augmented panels remain intact; the baseline projection contains only '
        'approved model variables, actual years and geographic keys. No land-cover complete-case rule is applied. '
        'Core values and the road-density zero coding are preserved exactly.\n\n'
        'Reproduce `python3 src/preprocessing/prepare_current_common_cohort.py --stage prepare`, then '
        '`python3 src/preprocessing/prepare_current_common_cohort.py --stage generate`.\n')
    print('Common panel validated:', report['panel'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['prepare', 'generate'], required=True)
    {'prepare': prepare, 'generate': generate}[parser.parse_args().stage]()
