#!/usr/bin/env python3
"""Validate revised regional geography after a documented boundary decision.

Require an explicit human decision file before resolving no-land meshes. Retain
the original geometric audit unchanged; do not invent land areas for exceptions.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from prepare_regional_confirmed_input import sha

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/regional-population-zero-corrected'


def main():
    geometry=json.loads((OUT / 'geometry_validation.json').read_text())
    decision=json.loads((OUT / 'allocation_decision.json').read_text())
    assert decision['confirmed'] and decision['mode'] in ['reviewed_nearest_land','exclude_from_regional_only']
    frame=pd.read_csv(OUT / 'mesh_region_confirmed_input.csv',dtype={'mesh_code':'string','region':'string','assignment_status':'string'})
    overlaps=pd.read_csv(OUT / 'mesh_region_overlaps.csv',dtype={'mesh_code':'string','region':'string'})
    assert len(frame)==228988 and frame.mesh_code.is_unique
    assert frame.mesh_code.str.fullmatch(r'\d{8}').all()
    unresolved=frame.assignment_status.eq('no_land_overlap')
    assert set(frame.loc[unresolved,'mesh_code'])==set(geometry['unassigned_meshes'])==set(decision['mesh_codes'])
    assert int(unresolved.sum())==19 and not frame.assignment_status.eq('area_tie').any()
    assert frame.loc[unresolved,'total_land_overlap'].eq(0).all()
    assert not overlaps.duplicated(['mesh_code','region']).any() and overlaps.land_overlap_m2.gt(0).all()
    normal=frame.loc[~unresolved].set_index('mesh_code')
    winner=overlaps.sort_values(['mesh_code','land_overlap_m2'],ascending=[True,False]).drop_duplicates('mesh_code').set_index('mesh_code')
    assert winner.region.reindex(normal.index).equals(normal.region)
    totals=overlaps.groupby('mesh_code').land_overlap_m2.sum().reindex(normal.index)
    assert np.allclose(totals/1e6,normal.total_land_overlap,rtol=1e-12,atol=1e-12)
    assert np.allclose(winner.land_overlap_m2.reindex(normal.index)/1e6,normal.region_land_area,rtol=1e-12,atol=1e-12)
    assert np.allclose(normal.region_land_area/normal.total_land_overlap,normal.region_land_share,rtol=1e-12,atol=1e-12)
    assert overlaps.groupby('mesh_code').size().gt(1).reindex(normal.index).equals(normal.cross_region_mesh)
    frame['no_land_overlap']=unresolved
    frame['region_assignment_method']='positive_land_area'
    frame['nearest_land_distance']=np.nan
    frame['nearest_prefecture_code']=pd.Series(pd.NA,index=frame.index,dtype='string')
    if decision['mode']=='reviewed_nearest_land':
        path=OUT / 'unassigned_mesh_region_proposals.csv'
        assert sha(path)==decision['proposal_sha256']
        proposals=pd.read_csv(path,dtype={'mesh_code':'string','nearest_prefecture_code':'string'}).set_index('mesh_code')
        assert set(proposals.index)==set(decision['mesh_codes'])
        assert proposals.minimum_land_distance_m.between(0,1500,inclusive='both').all()
        for index in frame.index[unresolved]:
            proposal=proposals.loc[frame.at[index,'mesh_code']]
            frame.at[index,'region']=proposal.proposed_region
            frame.at[index,'assignment_status']='reviewed_no_land_overlap'
            frame.at[index,'region_assignment_method']='reviewed_nearest_land'
            frame.at[index,'nearest_land_distance']=proposal.minimum_land_distance_m
            frame.at[index,'nearest_prefecture_code']=proposal.nearest_prefecture_code
        assert frame.loc[unresolved,'region_land_area'].isna().all()
        assert frame.loc[unresolved,'region_land_share'].isna().all()
    else:
        frame=frame.loc[~unresolved].copy()
    assert frame.region.notna().all()
    before=pd.read_parquet(ROOT / 'data/processed/national/mesh_region_national_preprocessed.parquet').set_index('Mesh Code')
    after=frame.set_index('mesh_code').loc[before.index]
    assert np.array_equal(before.Region,after.region)
    for a,b in [('Cross Region Mesh','cross_region_mesh'),('Region Land Area','region_land_area'),('Total Land Overlap','total_land_overlap'),('Region Land Share','region_land_share')]:
        np.testing.assert_allclose(before[a].to_numpy(dtype=float),after[b].to_numpy(dtype=float),rtol=1e-12,atol=1e-10)
    staged=OUT / 'mesh_region_reviewed_confirmed_input.parquet'
    frame.to_parquet(staged,index=False)
    counts=frame.region.value_counts().to_dict()
    pd.DataFrame([{'Region':r,'Meshes':counts[r],'Observations':counts[r]*4} for r in geometry['regions']]).to_csv(OUT / 'region_sample_counts.csv',index=False)
    mapping={'mesh_code':'Mesh Code','region':'Region','cross_region_mesh':'Cross Region Mesh',
        'region_land_area':'Region Land Area','total_land_overlap':'Total Land Overlap',
        'region_land_share':'Region Land Share','assignment_status':'Assignment Status',
        'no_land_overlap':'No Land Overlap','region_assignment_method':'Region Assignment Method',
        'nearest_land_distance':'Nearest Land Distance','nearest_prefecture_code':'Nearest Prefecture Code'}
    variables=[dict(original_name=a,readable_name=b,full_name=b,is_final_variable='yes' if a=='region' else 'no',
        role='geographic stratum' if a=='region' else 'reference',preprocessing=[]) for a,b in mapping.items()]
    spec=dict(output='data/processed/national/population_zero_corrected/mesh_region_national_preprocessed.parquet',
        script='src/preprocessing/preprocess_corrected_national_mesh_region.py',variables=variables)
    contract=dict(confirmed=True,decision_id='MILI-D-20261009-034',allocation_decision_id=decision['decision_id'],
        datasets={str(staged.relative_to(ROOT)):spec},source_rule='Largest positive regional land overlap; explicit no-land treatment in allocation_decision.json.',
        substantive_panel_modified=False)
    (OUT / 'decisions.json').write_text(json.dumps(contract,indent=2)+'\n')
    pd.DataFrame(variables).to_csv(OUT / 'variable_list.csv',index=False)
    validation=dict(status='passed',classification_meshes=len(frame),region_counts=counts,cross_region_meshes=int(frame.cross_region_mesh.sum()),
        no_land_cases=19,retained_no_land_cases=int(frame.no_land_overlap.sum()),excluded_mesh_codes=decision['mesh_codes'] if decision['mode']=='exclude_from_regional_only' else [],
        exception_decision_id=decision['decision_id'],exception_mode=decision['mode'],normal_maximum_area_assignments_verified=True,
        prior_mesh_region_labels_and_areas_preserved=True,no_fictitious_land_area_or_share=True,
        confirmed_input_sha256=sha(staged),substantive_panel_modified=False)
    (OUT / 'classification_validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    print(json.dumps(validation,indent=2))


if __name__=='__main__':main()
