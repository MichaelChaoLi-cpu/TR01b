"""Cross-check the four requested five-period model families and saved outputs."""
from pathlib import Path
import hashlib
import json
import re

import numpy as np
import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/regression-reprocessing/five-period-2024'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(2**20), b''): h.update(chunk)
    return h.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    panel_audit = json.loads((ROOT / 'data/exp/data-preprocessing/five-period-2024/panel_validation.json').read_text())
    source = ROOT / panel_audit['balanced_panel']
    sample = pd.read_parquet(source)
    codes = set(sample['Mesh Code'])
    periods = [2002, 2003, 2004, 2010, 2024]
    assert panel_audit['status'] == 'passed' and len(sample) == len(codes)*5 == 1144940
    assert sha(source) == panel_audit['balanced_panel_sha256']
    reports, summary, files = {}, [], {}
    qa = ROOT / 'data/exp/figure-table-generation/five-period-2024'
    for family in ['national', 'regional', 'prefecture']:
        report = json.loads((qa / family / 'validation.json').read_text())
        assert report['status'] == 'passed' and report['effects'] == [] and report['periods'] == periods
        assert report['input_sha256'] == sha(source) and report['meshes'] == len(codes) and report['observations'] == len(sample)
        workbook = ROOT / report['output']; assert sha(workbook) == report['output_sha256']
        table = pd.read_csv(qa / family / 'table.csv')
        ws = load_workbook(workbook, data_only=True)['Pooled results']
        assert list(table.columns) == list(next(ws.iter_rows(min_row=2, max_row=2, values_only=True)))
        assert table.shape == tuple(report['table_shape']) and ws.max_row == len(table)+2
        membership = pd.read_csv(qa / family / 'sample_membership.csv', dtype={'Mesh Code':str})
        keys = ['Mesh Code', 'Road Year', 'Population Year', 'Nighttime Light Year']
        pd.testing.assert_frame_equal(membership[keys], sample[keys].astype({'Mesh Code':str}), check_dtype=False)
        for path, digest in report['protected_sha256'].items():
            if path.startswith('data/processed/'): assert sha(ROOT / path) == digest
        roads = [r['coefficients'][1] for r in report['results']]
        summary.append(dict(model=family, meshes=report['meshes'], observations=report['observations'],
                            fitted_groups=len(roads), significantly_positive_road_groups=sum(e['confidence_lower']>0 for e in roads),
                            significantly_negative_road_groups=sum(e['confidence_upper']<0 for e in roads),
                            confidence_interval_crossing_zero_groups=sum(e['confidence_lower']<=0<=e['confidence_upper'] for e in roads),
                            r_squared_min=min(r['ordinary_pooled_r_squared'] for r in report['results']),
                            r_squared_max=max(r['ordinary_pooled_r_squared'] for r in report['results'])))
        files[report['output']] = report['output_sha256'];reports[family]=report
    local_dir = ROOT / 'data/exp/gwpr-pooled-five-period-2024/mesh-map-3km'
    local = json.loads((local_dir / 'local_fit_validation.json').read_text())
    data = pd.read_parquet(local_dir / 'local_coefficients.parquet')
    assert local['status'] == 'passed' and local['periods'] == periods and local['effects'] == []
    assert not local['bandwidth_reoptimized'] and local['bandwidth_km'] == 3
    assert sha(local_dir / 'local_coefficients.parquet') == local['output_sha256']
    assert set(data['Mesh Code']) == codes and data['Mesh Code'].is_unique
    assert np.array_equal(data['Local Observations'], data['Positive Weight Meshes']*5)
    good = data['Fit Status'].eq('ok');beta = data.loc[good, 'Road Density Coefficient']
    assert good.sum() == local['estimable_meshes']
    assert (beta<0).sum() == local['road_coefficient_negative_meshes']
    assert data.loc[~good, ['Intercept','Road Density Coefficient','Population Coefficient']].isna().all().all()
    assert np.array_equal(data['Below 30 Observations'], data['Local Observations']<30)
    map_report = json.loads((local_dir / 'map_validation.json').read_text())
    assert map_report['polygons_shown'] == len(codes) and map_report['source_sha256'] == local['output_sha256']
    for path, digest in map_report['outputs'].items(): assert sha(local_dir / path)==digest
    anasop = (ROOT / 'docs/AnaSOP.md').read_text()
    assert all(f'## {i}.' in anasop for i in range(1,9)) and not re.search(r'[\u4e00-\u9fff]',anasop)
    previous = (ROOT / 'data/exp/data-preprocessing/five-period-2024/AnaSOP_before.md').read_text()
    assert anasop[anasop.index('## 8.'):] == previous[previous.index('## 8.'):]
    pd.DataFrame(summary).to_csv(OUT / 'model_summary.csv', index=False)
    report = dict(status='passed', decision_id='MILI-D-20261010-012', scope='All four requested model families include 2024',
                  meshes=len(codes), observations=len(sample), periods=periods, population_years=panel_audit['population_years'],
                  models=summary, gwpr=dict(estimable_meshes=int(good.sum()),failed_meshes=int((~good).sum()),
                  negative_share=float((beta<0).mean()),negative_meshes=int((beta<0).sum()),
                  exact_zero_meshes=int((beta==0).sum()),bandwidth_km=3,bandwidth_reoptimized=False,local_inference=False),
                  same_panel_membership_verified=True, five_records_per_positive_weight_mesh_verified=True,
                  historical_values_and_population_zeros_preserved=True, effects=[], source_calibration=False,
                  source_comparability_established=False, formal_table_outputs=files, anasop_sha256=sha(ROOT/'docs/AnaSOP.md'),
                  formal_human_output_review='pending', no_skipped_model_family=True)
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__': main()
