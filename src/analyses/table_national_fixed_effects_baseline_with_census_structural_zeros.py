#!/usr/bin/env python3
"""National Fixed-Effects Baseline with Census Structural Zeros.

AnaSOP Sections 5-8; corrected 228,988-mesh historical sample, original-scale
mesh and period fixed effects, mesh-clustered CR1 inference. No data changes.
Reuse the independently checked estimator that generated the original baseline.
"""
from pathlib import Path
import json

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from table_pilot_fixed_effects_baseline import main as estimate, sha

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'data/exp/estimation-framework-planning/national-fixed-effects-population-zero-corrected/estimation_decisions.json'
QA = ROOT / 'data/exp/figure-table-generation/national-fixed-effects-population-zero-corrected'


def main():
    contract = json.loads(CONTRACT.read_text())
    validation = json.loads((ROOT / 'data/exp/data-preprocessing/population-zero-correction/panel_validation.json').read_text())
    assert validation['status'] == 'passed' and validation['decision_id'] == 'MILI-D-20261009-032'
    assert contract['input'] == validation['new_panel']
    assert sha(ROOT / contract['input']) == validation['new_panel_sha256']
    previous = [ROOT / 'data/results/tables/Table_national_fixed_effects_baseline.xlsx',
        ROOT / 'data/exp/figure-table-generation/national-fixed-effects/validation.json',
        ROOT / 'data/exp/figure-table-generation/national-fixed-effects/sample_membership.csv',
        ROOT / 'data/exp/estimation-framework-planning/national-fixed-effects/estimation_decisions.json']
    before = {str(p.relative_to(ROOT)):sha(p) for p in previous}
    estimate(contract_path=CONTRACT,qa_path=QA)
    result = json.loads((QA / 'validation.json').read_text())
    assert result['meshes'] == validation['sample']['revised_meshes'] == 228988
    assert result['observations'] == validation['sample']['revised_observations'] == 915952
    assert result['zero_population_observations'] == 274959
    expected = pd.read_parquet(ROOT / 'data/processed/national/population_zero_corrected/balanced_historical_panel_preprocessed.parquet',
                              columns=['Mesh Code','Road Year','Population Year','Nighttime Light Year'])
    actual = pd.read_csv(QA / 'sample_membership.csv',dtype={'Mesh Code':'string'})
    for column in expected:
        np.testing.assert_array_equal(expected[column].to_numpy(),actual[column].to_numpy())
    assert all(sha(ROOT / p) == h for p,h in before.items())
    result.update(corrected_sample_membership_verified=True,previous_national_outputs_preserved=True,
                  previous_national_sha256=before,preprocessing_validation_reference='data/exp/data-preprocessing/population-zero-correction/panel_validation.json')
    sheet = load_workbook(ROOT / result['output'],data_only=True)['Baseline']
    headers = [sheet.cell(4,c).value for c in range(1,6)]
    rows = [[sheet.cell(r,c).value for c in range(1,6)] for r in range(5,16)]
    pd.DataFrame(rows,columns=headers).to_csv(QA / 'regression_table.csv',index=False)
    result['portable_table_csv_sha256'] = sha(QA / 'regression_table.csv')
    (QA / 'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Corrected sample membership agrees exactly with preprocessing; previous national outputs preserved.')


if __name__ == '__main__':
    main()
