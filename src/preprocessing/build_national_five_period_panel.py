"""Append approved 2024 inputs and select the complete five-period cohort."""
from pathlib import Path
import json
import hashlib

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from prepare_national_2024_extension import ROOT, OUT, DEST, DECISION

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            digest.update(block)
    return digest.hexdigest()


def main():
    dest=ROOT/DEST;dest.mkdir(parents=True,exist_ok=True)
    historical=ROOT/'data/processed/national/population_zero_corrected/road_population_light_national_preprocessed.parquet'
    old_balanced=historical.parent/'balanced_historical_panel_preprocessed.parquet'
    inputs=[historical,old_balanced]+[dest/f'{k}_{y}_preprocessed.parquet' for k,y in [('roads',2024),('lights',2024),('population',2020)]]
    before={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    source=pq.ParquetFile(historical);assert source.num_row_groups==4
    grid=pd.read_parquet(ROOT/'data/exp/data-preprocessing/national/common_grid.parquet');codes=grid.mesh_code.tolist()
    periods=[2002,2003,2004,2010,2024];pop_years=[2000,2005,2005,2010,2020]
    last=None
    for k,y in [('roads',2024),('lights',2024),('population',2020)]:
        d=pd.read_parquet(dest/f'{k}_{y}_preprocessed.parquet')
        assert d['Mesh Code'].tolist()==codes and d['Mesh Code'].is_unique
        last=d if last is None else last.merge(d,on='Mesh Code',validate='one_to_one')
    metadata=pd.read_parquet(OUT/'population_metadata_2020.parquet')
    last=last.merge(metadata,on='Mesh Code',validate='one_to_one')
    frames=[];numeric=[];coverage=[];writer=None
    output=dest/'road_population_light_five_period_preprocessed.parquet'
    try:
        for i,(year,pop_year) in enumerate(zip(periods,pop_years)):
            frame=source.read_row_group(i).to_pandas() if i<4 else last.copy()
            if i==0: columns=frame.columns.tolist()
            frame=frame[columns]
            assert frame['Mesh Code'].tolist()==codes
            for c in ['Mesh Code','Disclosure Status','Disclosure Destination','Merged Mesh Codes']:frame[c]=frame[c].astype('string')
            assert frame['Road Year'].eq(year).all() and frame['Nighttime Light Year'].eq(year).all() and frame['Population Year'].eq(pop_year).all()
            good=np.isfinite(frame[['Road Length Density','Nighttime Radiance','Population']].to_numpy(dtype=float)).all(1)
            numeric.append(good);frames.append(frame)
            coverage.append(dict(road_year=year,population_year=pop_year,light_year=year,common_meshes=len(frame),
                                 numeric_roads=int(frame['Road Length Density'].notna().sum()),numeric_lights=int(frame['Nighttime Radiance'].notna().sum()),
                                 numeric_population=int(frame['Population'].notna().sum()),joint_numeric_meshes=int(good.sum())))
            table=pa.Table.from_pandas(frame,preserve_index=False)
            if writer is None:writer=pq.ParquetWriter(output,table.schema)
            writer.write_table(table)
    finally:
        if writer:writer.close()
    count=np.column_stack(numeric).sum(1);balanced=count==5
    old=pd.read_parquet(old_balanced);old_codes=set(old['Mesh Code']);selected=set(grid.loc[balanced,'mesh_code'])
    assert selected<=old_codes
    sample=pd.concat([f.loc[balanced] for f in frames],ignore_index=True).sort_values(['Mesh Code','Road Year']).reset_index(drop=True)
    g=len(selected);assert len(sample)==g*5
    assert np.array_equal(sample['Road Year'].to_numpy().reshape(g,5),np.tile(periods,(g,1)))
    assert np.isfinite(sample[['Road Length Density','Population','Nighttime Radiance']].to_numpy()).all()
    preserved=old[old['Mesh Code'].isin(selected)].reset_index(drop=True)
    pd.testing.assert_frame_equal(sample[sample['Road Year']!=2024].reset_index(drop=True),preserved)
    sample_path=dest/'balanced_five_period_panel_preprocessed.parquet';sample.to_parquet(sample_path,index=False)
    for stem,column in [('region','Region'),('prefecture','Prefecture Code')]:
        m=pd.read_parquet(historical.parent/f'mesh_{stem}_national_preprocessed.parquet')
        m=m[m['Mesh Code'].isin(selected)].reset_index(drop=True)
        assert m['Mesh Code'].is_unique and set(m['Mesh Code'])==selected and m[column].notna().all()
        m.to_parquet(dest/f'mesh_{stem}_national_preprocessed.parquet',index=False)
    availability=pd.DataFrame({'Mesh Code':codes,'Joint Numeric Periods':count,'Complete Five Periods':balanced})
    availability.to_parquet(OUT/'mesh_availability.parquet',index=False)
    pd.DataFrame(coverage).to_csv(OUT/'coverage_by_period.csv',index=False)
    assert all(sha(ROOT/p)==h for p,h in before.items())
    assert pq.read_metadata(output).num_rows==len(grid)*5
    report=dict(status='passed',decision_id=DECISION,periods=periods,population_years=pop_years,
                meshes=g,observations=len(sample),complete_grid_meshes=len(grid),complete_panel_rows=len(grid)*5,
                zero_population_observations=int(sample.Population.eq(0).sum()),
                all_period_zero_population_meshes=int(sample.groupby('Mesh Code').Population.max().eq(0).sum()),
                previous_four_period_meshes=len(old_codes),removed_meshes=sorted(old_codes-selected),
                historical_values_preserved_exactly=True,source_calibration=False,source_comparability_established=False,
                period_2024_population_offset_years=-4,protected_input_sha256=before,
                output=str(output.relative_to(ROOT)),output_sha256=sha(output),
                balanced_panel=str(sample_path.relative_to(ROOT)),balanced_panel_sha256=sha(sample_path))
    (OUT/'panel_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['protected_input_sha256','removed_meshes']},indent=2),flush=True)


if __name__=='__main__':main()
