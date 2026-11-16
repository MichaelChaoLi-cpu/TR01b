"""Attach approved static mesh characteristics to full and balanced panels.

Arrow batches preserve the original columns exactly and bound peak memory.
Run after the seven generated preprocess_static_*.py scripts.
"""
from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/static-facilities'
DEST = ROOT / 'data/processed/national/static_facilities'
BASE = ROOT / 'data/processed/national/five_period'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    contract=json.loads((OUT/'decisions.json').read_text())
    assert contract['confirmed'] and contract['decision_id']=='MILI-D-20261010-017'
    codes=pd.read_parquet(ROOT/'data/exp/data-preprocessing/national/common_grid.parquet').mesh_code
    index=pd.Index(codes)
    static=None
    analytical=[]
    for spec in contract['datasets'].values():
        table=pq.read_table(ROOT/spec['output'])
        assert table.column('Mesh Code').to_pylist()==codes.tolist()
        analytical.extend(v['readable_name'] for v in spec['variables'] if v['is_final_variable']=='yes')
        if static is None:static=table
        else:
            for name in table.column_names:
                if name=='Mesh Code':continue
                assert name not in static.column_names,name
                static=static.append_column(name,table.column(name))
    static=static.append_column('Facility Static Assumption',pa.array(np.ones(len(index),dtype=bool)))
    mesh_path=DEST/'static_facility_mesh_preprocessed.parquet'
    pq.write_table(static,mesh_path)
    static=pq.read_table(mesh_path)
    appended=[c for c in static.column_names if c!='Mesh Code']
    records=[]
    for source_name,output_name in [
        ('road_population_light_five_period_preprocessed.parquet','road_population_light_facilities_five_period_preprocessed.parquet'),
        ('balanced_five_period_panel_preprocessed.parquet','balanced_five_period_facilities_panel_preprocessed.parquet')]:
        source=BASE/source_name;dest=DEST/output_name;temporary=dest.with_suffix('.pending.parquet')
        before=sha(source);reader=pq.ParquetFile(source)
        writer=None;count=0
        try:
            for batch in reader.iter_batches(batch_size=65536):
                table=pa.Table.from_batches([batch]);positions=index.get_indexer(table.column('Mesh Code').to_pylist())
                assert (positions>=0).all()
                matched=static.take(pa.array(positions))
                assert matched.column('Mesh Code').equals(table.column('Mesh Code'))
                for col in appended:table=table.append_column(col,matched.column(col))
                if writer is None:writer=pq.ParquetWriter(temporary,table.schema,compression='zstd')
                writer.write_table(table);count+=len(batch)
        finally:
            if writer:writer.close()
        assert count==reader.metadata.num_rows
        dest_reader=pq.ParquetFile(temporary)
        verified_rows=0
        for original,result in zip(reader.iter_batches(batch_size=65536),dest_reader.iter_batches(batch_size=65536),strict=True):
            original=pa.Table.from_batches([original]);result=pa.Table.from_batches([result])
            assert original.equals(result.select(original.column_names),check_metadata=False)
            positions=index.get_indexer(original.column('Mesh Code').to_pylist())
            assert static.take(pa.array(positions)).select(appended).equals(result.select(appended),check_metadata=False)
            verified_rows+=len(result)
        assert verified_rows==count and sha(source)==before
        temporary.replace(dest)
        record=dict(source=str(source.relative_to(ROOT)),source_sha256=before,output=str(dest.relative_to(ROOT)),
                    output_sha256=sha(dest),rows=count,columns=len(dest_reader.schema_arrow.names),
                    all_original_columns_preserved_exactly=True,all_static_values_match_mesh_table=True,
                    no_row_dropping=True,no_key_duplication_introduced=True)
        records.append(record);print('Linked and verified:',output_name,count,record['columns'],flush=True)
    summary=pd.DataFrame({'Variable':analytical})
    for name in analytical:
        values=static.column(name).to_numpy()
        selected=summary.Variable.eq(name)
        summary.loc[selected,'Missing Meshes']=int(pd.isna(values).sum())
        summary.loc[selected,'Zero Meshes']=int((values==0).sum())
        summary.loc[selected,'Minimum']=np.nanmin(values)
        summary.loc[selected,'Maximum']=np.nanmax(values)
    summary.to_csv(OUT/'static_variable_summary.csv',index=False)
    report=dict(status='passed',decision_id=contract['decision_id'],temporal_decision=contract['temporal_decision'],
                periods=[2002,2003,2004,2010,2024],complete_meshes=len(index),analytical_facility_variables=len(analytical),
                static_columns_added=len(appended),mesh_table=str(mesh_path.relative_to(ROOT)),
                static_source_editions={'railway':2024,'regular_bus':2022,'highway_bus':2023,'airports':2021,
                                       'schools':2023,'medical':2020,'logistics':2013,'visitor_facilities':2014},
                static_assumption_flag_present=True,panel_outputs=records,regressions_refitted=False,
                land_cover='Not acquired; not silently filled or represented by a proxy')
    (OUT/'panel_linkage_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='panel_outputs'},indent=2),flush=True)


if __name__=='__main__':main()
