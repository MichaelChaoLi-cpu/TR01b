"""Construct the confirmed UMD dominant land context for the 2024 screen.

Uses already validated shares and the approved regression cohort. Does not recode
IGBP, normalize shares, fill missing data, or change the original panel.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/exp/umd-four-layer/inputs/model_panel.parquet'
OUT = ROOT / 'data/processed/national/modis_umd/mismatch_context_2024_preprocessed.parquet'
AUDIT = ROOT / 'data/exp/data-preprocessing/umd-mismatch-context'
SHARES = {
    'Urban': 'Urban Land Cover Share',
    'Forest': 'Forest Land Cover Share',
    'Cropland': 'Cropland Land Cover Share',
    'Water': 'Water Land Cover Share',
    'Shrublands and Grasslands': 'Shrublands and Grasslands',
    'Barren': 'Barren',
}

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def main():
    source_hash = sha(SOURCE)
    columns = ['Mesh Code', 'Road Year', 'Land Cover Year', *SHARES.values(),
               'Land Cover Coverage', 'Land Cover Incomplete Coverage', 'Land Cover Product']
    d = pd.read_parquet(SOURCE, columns=columns, filters=[('Road Year', '==', 2024)])
    assert len(d) == 383386 and d['Mesh Code'].is_unique
    assert d['Land Cover Year'].eq(2024).all()
    a = d[list(SHARES.values())].to_numpy()
    assert np.isfinite(a).all() and (a >= 0).all()
    np.testing.assert_allclose(a.sum(1), d['Land Cover Coverage'], atol=1e-10)
    maxima = a.max(1)
    tied = np.isclose(a, maxima[:, None], rtol=0, atol=1e-12).sum(1) > 1
    d['Land Context'] = np.array(list(SHARES), dtype=object)[a.argmax(1)]
    d.loc[tied, 'Land Context'] = 'Tied dominant classes'
    incomplete = d['Land Cover Incomplete Coverage'].astype(bool)
    d.loc[incomplete, 'Land Context'] = 'Incomplete coverage'
    assert d['Land Context'].notna().all()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    d.to_parquet(OUT, index=False)
    pd.testing.assert_frame_equal(d, pd.read_parquet(OUT))
    assert sha(SOURCE) == source_hash
    decisions = {
        'decision_id': 'MILI-D-20261011-027', 'classification': 'UMD',
        'source': str(SOURCE.relative_to(ROOT)), 'source_sha256': source_hash,
        'output': str(OUT.relative_to(ROOT)), 'script': str(Path(__file__).relative_to(ROOT)),
        'shares': SHARES, 'derived_variable': 'Land Context', 'is_final_variable': 'yes',
        'rule': 'Largest full-mesh share; ties within absolute 1e-12; incomplete coverage overrides dominance',
        'fill_or_normalize': False, 'cohort': 'Approved 383386-mesh extended model cohort',
    }
    (AUDIT / 'decisions.json').write_text(json.dumps(decisions, indent=2) + '\n')
    report = {'status': 'passed', **decisions, 'rows': len(d), 'columns': len(d.columns),
              'counts': {str(k): int(v) for k, v in d['Land Context'].value_counts().items()},
              'incomplete_meshes': int(incomplete.sum()), 'tied_meshes_before_coverage_override': int(tied.sum()),
              'output_sha256': sha(OUT), 'source_unchanged': True, 'parquet_roundtrip_passed': True}
    (AUDIT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    (AUDIT / 'README.md').write_text(
        '# UMD mismatch land context\n\nDecision MILI-D-20261011-027 uses the six already confirmed UMD '
        'shares to construct dominant Land Context for the approved 2024 mesh cohort. '
        'Ties within absolute 1e-12 are retained as Tied dominant classes; incomplete coverage takes '
        'priority. No filling, normalization or source-panel changes. Only context is constructed here; '
        'screening is performed separately by run_umd_mismatch_screen.py.\n')
    print(json.dumps({'status': 'passed', 'rows': len(d), 'counts': report['counts']}), flush=True)

if __name__ == '__main__':
    main()
