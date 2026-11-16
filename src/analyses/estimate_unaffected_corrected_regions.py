#!/usr/bin/env python3
"""Compute the six corrected regional models independent of no-land treatment.

This is a progress checkpoint for the requested regional comparison, not a
different model or sample rule. The remaining three regions require a decision.
"""
from pathlib import Path
import json
import pandas as pd
from table_regional_fixed_effects_baselines import fit_region
from table_pilot_fixed_effects_baseline import sha

ROOT=Path(__file__).resolve().parents[2]


def main():
    contract=json.loads((ROOT / 'data/exp/estimation-framework-planning/regional-fixed-effects/estimation_decisions.json').read_text())
    contract['decision_id']='MILI-D-20261009-034'
    path=ROOT / 'data/processed/national/population_zero_corrected/balanced_historical_panel_preprocessed.parquet'
    source=pd.read_parquet(path)
    assert len(source)==915952
    geography=ROOT / 'data/exp/data-preprocessing/regional-population-zero-corrected'
    mapping=pd.read_csv(geography / 'mesh_region_confirmed_input.csv',dtype={'mesh_code':'string','region':'string'})
    proposals=pd.read_csv(geography / 'unassigned_mesh_region_proposals.csv')
    assert set(proposals.proposed_region)=={'Kanto','Kinki','Kyushu'}
    results=[]
    for region in ['Hokkaido','Tohoku','Hokuriku-Shinetsu','Chubu','Chugoku','Shikoku']:
        codes=mapping.loc[mapping.region.eq(region),'mesh_code']
        sample=source.loc[source['Mesh Code'].isin(codes)].sort_values(['Mesh Code','Road Year'])
        result=fit_region(sample,contract);result['region']=region;results.append(result)
        print(f"{region}: {result['meshes']:,} meshes; road coefficient {result['coefficients'][0]['coefficient']:.8f}",flush=True)
    output=ROOT / 'data/exp/figure-table-generation/regional-fixed-effects-population-zero-corrected'
    output.mkdir(parents=True,exist_ok=True)
    report=dict(status='six_unaffected_regions_numerically_validated',decision_id='MILI-D-20261009-034',
        results=results,remaining_regions=['Kanto','Kinki','Kyushu'],
        pending_decision='Nineteen no-land-intersection meshes: reviewed regional exceptions or regional-only exclusion.',
        input=str(path.relative_to(ROOT)),input_sha256=sha(path),
        geometric_mapping_sha256=sha(geography / 'mesh_region_confirmed_input.csv'),formal_comparison_table_generated=False)
    (output / 'partial_results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
