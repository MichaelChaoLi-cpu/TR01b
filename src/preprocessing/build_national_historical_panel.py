#!/usr/bin/env python3
"""Link nationwide confirmed inputs and audit the same balanced baseline rule."""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/exp/data-preprocessing/national'
PROCESSED=ROOT/'data/processed/national'
MATCH={2002:2000,2003:2005,2004:2005,2010:2010}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    contract=json.loads((OUT/'decisions.json').read_text())
    assert contract['confirmed'] and len(contract['datasets'])==11
    inputs=[ROOT/d['output'] for d in contract['datasets'].values()]
    protected=inputs+list((ROOT/'data/processed/pilot').glob('*.parquet'))
    before={str(p.relative_to(ROOT)):sha(p) for p in protected}
    grid=pd.read_parquet(OUT/'common_grid.parquet');n=len(grid)
    expected=grid.mesh_code.tolist()
    coverage=[];patterns=[];pilot_comparisons=[]
    panel_path=PROCESSED/'road_population_light_national_preprocessed.parquet'
    writer=None
    try:
        for year,pop_year in MATCH.items():
            roads=pd.read_parquet(PROCESSED/f'roads_{year}_preprocessed.parquet')
            lights=pd.read_parquet(PROCESSED/f'lights_{year}_preprocessed.parquet')
            population=pd.read_parquet(PROCESSED/f'population_{pop_year}_preprocessed.parquet')
            for data in [roads,lights,population]:
                assert len(data)==n and data['Mesh Code'].is_unique
                assert data['Mesh Code'].tolist()==expected
            frame=roads.merge(lights,on='Mesh Code',validate='one_to_one').merge(population,on='Mesh Code',validate='one_to_one')
            for data in [roads,lights,population]:
                for col in data:
                    pd.testing.assert_series_equal(frame[col],data[col],check_names=True,check_dtype=col!='Mesh Code')
            frame['Mesh Code']=pd.array(frame['Mesh Code'],dtype='string')
            for col in ['Disclosure Status','Disclosure Destination','Merged Mesh Codes']:
                frame[col]=pd.Series(pd.NA,index=frame.index,dtype='string')
            table=pa.Table.from_pandas(frame,preserve_index=False)
            if writer is None:writer=pq.ParquetWriter(panel_path,table.schema)
            writer.write_table(table)
            numeric=np.isfinite(frame[['Road Length Density','Population','Nighttime Radiance']].to_numpy()).all(axis=1)
            patterns.append(numeric)
            coverage.append(dict(road_year=year,population_year=pop_year,light_year=year,complete_meshes=n,
                numeric_roads=int(frame['Road Length Density'].notna().sum()),numeric_population=int(frame['Population'].notna().sum()),
                numeric_lights=int(frame['Nighttime Radiance'].notna().sum()),joint_numeric_meshes=int(numeric.sum())))
            pilot=pd.read_parquet(ROOT/'data/processed/pilot/road_population_light_pilot_preprocessed.parquet')
            pilot=pilot[pilot['Road Year'].eq(year)].set_index('Mesh Code')
            overlap=frame.set_index('Mesh Code').loc[pilot.index]
            for col in ['Road Length','Road Length Density','Mesh Area','Population','Population Year','Road Year','Nighttime Light Year']:
                assert np.allclose(pd.to_numeric(overlap[col]),pd.to_numeric(pilot[col]),atol=0,rtol=0,equal_nan=True),col
            difference=abs(overlap['Nighttime Radiance']-pilot['Nighttime Radiance']).max()
            assert difference<1e-7
            pilot_comparisons.append(dict(year=year,pilot_meshes=len(pilot),nonlight_values_exact=True,max_radiance_difference=float(difference)))
            print(f'panel {year}: {numeric.sum():,} jointly numeric meshes',flush=True)
    finally:
        if writer:writer.close()
    counts=np.column_stack(patterns).sum(axis=1)
    pd.DataFrame(coverage).to_csv(OUT/'coverage_by_period.csv',index=False)
    pd.DataFrame({'Mesh Code':expected,'Joint Numeric Periods':counts,'Complete Four Periods':counts==4}).to_parquet(OUT/'mesh_availability.parquet',index=False)
    pd.Series(counts).value_counts().reindex(range(5),fill_value=0).rename_axis('joint_numeric_periods').rename('meshes').to_csv(OUT/'coverage_period_count.csv')
    census={2000:126925843,2005:127767994,2010:128057352}
    for y,total in census.items():
        observed=pd.read_parquet(PROCESSED/f'population_{y}_preprocessed.parquet')['Population'].sum()
        assert observed==total,(y,observed,total)
    assert all(sha(ROOT/p)==h for p,h in before.items())
    meta=pq.read_metadata(panel_path)
    assert meta.num_rows==n*4 and meta.num_columns==13
    balanced=int((counts==4).sum())
    report=dict(status='passed',decision_id='MILI-D-20261009-015',national_primary_tiles=len(contract['national_primary_tiles']),
        complete_meshes=n,complete_panel_rows=n*4,columns=13,historical_years=list(MATCH),population_matching=MATCH,
        jointly_numeric_records=int(counts.sum()),balanced_estimation_meshes=balanced,balanced_estimation_records=balanced*4,
        balanced_primary_tiles=int(grid.loc[counts==4,'mesh_code'].str[:4].nunique()),
        census_totals_match_official=True,census_totals=census,
        census_reference='https://www.stat.go.jp/data/kokusei/2020/kekka/pdf/all.pdf',
        pilot_overlap_checks=pilot_comparisons,values_preserved_during_linkage=True,imputation=False,source_rescaling=False,
        historical_source_equivalence_established=False,coastal_or_island_mask_applied=False,
        protected_input_sha256=before,output_sha256=sha(panel_path),output=str(panel_path.relative_to(ROOT)))
    (OUT/'panel_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='protected_input_sha256'},indent=2))


if __name__=='__main__':main()
