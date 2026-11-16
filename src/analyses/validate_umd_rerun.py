"""Independent readback and full-design checks for the UMD rerun delivery."""
from pathlib import Path
import json
import re
import numpy as np
import pandas as pd
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/exp/umd-four-layer'


def main():
    workbook = load_workbook(OUT/'pooled_umd_results.xlsx', data_only=True)
    sheet_checks = []
    for sheet in ['national', 'regional', 'prefecture', 'road comparison']:
        file = 'pooled_road_comparison.csv' if sheet == 'road comparison' else sheet+'_coefficients.csv'
        frame = pd.read_csv(OUT/file, keep_default_na=False)
        saved = list(workbook[sheet].iter_rows(min_row=2, values_only=True))
        assert len(frame) == len(saved)
        for expected, actual in zip(frame.itertuples(index=False, name=None), saved, strict=True):
            for a, b in zip(expected, actual, strict=True):
                if b is None:
                    assert a == ''
                elif isinstance(b, (int, float)):
                    assert np.isclose(float(a), b, rtol=1e-12, atol=1e-12)
                else:
                    assert str(a) == b
        sheet_checks.append(dict(sheet=sheet, rows=len(frame), all_cells_checked=True))
    contract = json.loads((OUT/'execution_contract.json').read_text())
    panel = pd.read_parquet(OUT/'inputs/model_panel.parquet')
    results = json.loads((OUT/'prefecture_validation.json').read_text())['results']
    full_design_checks = []
    names = contract['explanatory']
    for code in ['13', '29']:
        sample = panel.loc[panel['Prefecture Code'].astype(str).eq(code)].sort_values(['Mesh Code', 'Road Year'])
        result = next(r['extended'] for r in results if r['group'].startswith(code+' /'))
        raw = sample[names].to_numpy(float)
        scales = raw.std(0); scales[scales == 0] = 1
        x = np.column_stack([np.ones(len(sample)), (raw-raw.mean(0))/scales])
        beta, _, rank, _ = np.linalg.lstsq(x, sample['Nighttime Radiance'].to_numpy(float), rcond=None)
        expected = np.asarray([next(v['coefficient'] for v in result['coefficients'] if v['variable'] == n) for n in names[:2]])
        actual = beta[1:3]/scales[:2]
        np.testing.assert_allclose(expected, actual, rtol=1e-8, atol=1e-9)
        full_design_checks.append(dict(prefecture=code, full_design_rank=int(rank),
            retained_parameters=result['parameters'], maximum_core_difference=float(abs(expected-actual).max())))
    directory = OUT/'bandwidth-search-3-50km'
    table = pd.read_csv(directory/'bandwidth_search.csv')
    centers = pd.read_csv(directory/'validation_centers.csv', dtype={'Mesh Code': str})
    loss = np.load(directory/'validation_mse.npy')
    common = np.isfinite(loss).all(1); weights = centers['Validation Weight'].to_numpy(float)
    assert np.array_equal(common, centers['Common Estimable Support'].to_numpy())
    assert np.array_equal(table['Bandwidth km'], np.arange(3., 51.))
    for j in range(48):
        value = np.average(loss[common, j], weights=weights[common])
        assert np.isclose(value, table.iloc[j]['Common Weighted Level MSE'], rtol=1e-13)
    local_pointer = json.loads((OUT/'active_local_result.json').read_text())
    local = pd.read_parquet(ROOT/local_pointer['output'])
    good = local['Fit Status'].eq('ok')
    assert local['Mesh Code'].is_unique and len(local) == contract['meshes']
    assert set(local['Mesh Code']) == set(panel['Mesh Code'])
    assert local.loc[good, ['Road Density Coefficient', 'Population Coefficient']].notna().all().all()
    assert local.loc[~good, ['Road Density Coefficient', 'Population Coefficient']].isna().all().all()
    assert np.array_equal(local['Local Observations'], local['Positive Weight Meshes']*5)
    assert np.array_equal(local['Below 30 Observations'], local['Local Observations'] < 30)
    before = (OUT/'AnaSOP_before_umd_analysis.txt').read_text()
    after = (ROOT/'docs/AnaSOP.md').read_text()
    old_parts = re.split(r'(?=^## [1-8]\. )', before, flags=re.M)
    new_parts = re.split(r'(?=^## [1-8]\. )', after, flags=re.M)
    assert old_parts[:4] == new_parts[:4]
    foundation = lambda text: next(line for line in text.splitlines() if line.startswith('| Spatial Distribution of Key Variables |') and line.endswith('| done |'))
    assert foundation(before) == foundation(after)
    report = dict(status='passed', workbook_all_cell_checks=sheet_checks,
        full_design_core_checks=full_design_checks, all_48_cv_scores_independently_reaggregated=True,
        identical_cv_center_support_verified=True, all_local_ids_and_support_flags_verified=True,
        research_objective_and_data_overview_unchanged=True, accepted_foundation_map_plan_unchanged=True)
    (OUT/'independent_delivery_validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Independent UMD readback, full-design core, CV, local support and documentation checks passed.')


if __name__ == '__main__':
    main()
