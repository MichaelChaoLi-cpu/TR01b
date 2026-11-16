#!/usr/bin/env python3
"""Regional Fixed-Effects Baselines with Census Structural Zeros.

AnaSOP Sections 5-8; nine accepted geographic strata on the corrected national
sample; original-scale two-way FE and region-specific mesh-clustered inference.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from openpyxl import load_workbook
from table_regional_fixed_effects_baselines import main as estimate
from table_pilot_fixed_effects_baseline import sha

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'data/exp/estimation-framework-planning/regional-fixed-effects-population-zero-corrected/estimation_decisions.json'
QA = ROOT / 'data/exp/figure-table-generation/regional-fixed-effects-population-zero-corrected'


def main():
    contract = json.loads(CONTRACT.read_text())
    national_path = ROOT / 'data/exp/figure-table-generation/national-fixed-effects-population-zero-corrected/validation.json'
    national = json.loads(national_path.read_text())
    assert national['status'] == 'passed' and national['corrected_sample_membership_verified']
    assert national['meshes'] == 228988
    excluded = contract.get('excluded_mesh_codes', [])
    assert contract['expected_meshes'] == 228988-len(excluded)
    assert national['observations'] == 915952
    assert contract['expected_observations'] == 915952-4*len(excluded)
    assert contract['input'] == national['input']
    assert sha(ROOT / national['output']) == national['output_sha256']
    assert sha(ROOT / contract['national_sample_membership']) == national['sample_membership_sha256']
    estimate(contract_path=CONTRACT,qa_path=QA)
    report = json.loads((QA / 'validation.json').read_text())
    assert len(report['results']) == 9
    assert report['zero_population_observations'] == national['zero_population_observations']-4*len(excluded) == 274959-4*len(excluded)
    assert sum(r['zero_population_observations'] for r in report['results']) == 274959-4*len(excluded)
    prior = pd.read_parquet(ROOT / 'data/processed/national/mesh_region_national_preprocessed.parquet')
    mapping = pd.read_parquet(ROOT / contract['region_mapping']).set_index('Mesh Code')
    assert np.array_equal(prior.Region, mapping.loc[prior['Mesh Code'],'Region'])
    sheet = load_workbook(ROOT / report['output'],data_only=True)['Regional Baselines']
    headers = [sheet.cell(4,c).value for c in range(1,10)]
    rows = [[sheet.cell(r,c).value for c in range(1,10)] for r in range(5,23)]
    pd.DataFrame(rows,columns=headers).to_csv(QA / 'regression_table.csv',index=False)
    exceptions = mapping.loc[mapping['No Land Overlap']]
    assert len(exceptions) == 19
    assert exceptions.Region.value_counts().to_dict() == {'Kanto':10,'Kinki':7,'Kyushu':2}
    assert exceptions['Region Land Area'].isna().all() and exceptions['Region Land Share'].isna().all()
    preserved_six = False
    if (QA / 'partial_results.json').exists():
        partial = json.loads((QA / 'partial_results.json').read_text())
        results_by_region = {r['region']:r for r in report['results']}
        for earlier in partial['results']:
            for a,b in zip(earlier['coefficients'],results_by_region[earlier['region']]['coefficients']):
                for field in ['coefficient','clustered_standard_error','confidence_lower','confidence_upper']:
                    assert a[field] == b[field]
        preserved_six = True
    report.update(corrected_national_population_version_verified=True,
        old_mesh_region_labels_preserved=True,portable_table_csv_sha256=sha(QA / 'regression_table.csv'),
        retained_no_land_exceptions=19,exception_region_counts=exceptions.Region.value_counts().to_dict(),
        unaffected_six_model_results_exactly_preserved=preserved_six,
        allocation_decision_id=contract['allocation_decision_id'],protected_hashes_recorded_at_estimation_time=True)
    (QA / 'validation.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    main()
