"""Link approved static KSJ counts without changing any existing panel value."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/ksj-eighteen-facilities'
DEST = ROOT / 'data/processed/national/ksj_eighteen_facilities'
SOURCE = ROOT / 'data/processed/national/modis_land_cover'
YEARS = [2002, 2003, 2004, 2010, 2024]


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    decisions = json.loads((OUT / 'decisions.json').read_text()); assert decisions['confirmed']
    codes = pd.read_parquet(ROOT / 'data/exp/data-preprocessing/national/common_grid.parquet').mesh_code.astype(str)
    index = pd.Index(codes); assert index.is_unique
    mesh = pa.table({'Mesh Code': codes.tolist()})
    for spec in decisions['datasets'].values():
        table = pq.read_table(ROOT / spec['output'])
        assert table.column('Mesh Code').to_pylist() == codes.tolist()
        for name in table.column_names:
            if name != 'Mesh Code':
                assert name not in mesh.column_names
                mesh = mesh.append_column(name, table.column(name))
    mesh = mesh.append_column('KSJ Static Assumption', pa.array(np.ones(len(codes), dtype=bool)))
    mesh_path = DEST / 'ksj_eighteen_facility_mesh_preprocessed.parquet'
    pq.write_table(mesh, mesh_path, compression='zstd')
    appended = [c for c in mesh.column_names if c != 'Mesh Code']
    outputs = []
    for source_name, dest_name in [
        ('road_population_light_facilities_land_cover_five_period_preprocessed.parquet',
         'road_population_light_facilities_land_cover_ksj_five_period_preprocessed.parquet'),
        ('balanced_five_period_facilities_land_cover_panel_preprocessed.parquet',
         'balanced_five_period_facilities_land_cover_ksj_panel_preprocessed.parquet')]:
        source = SOURCE / source_name; dest = DEST / dest_name
        before = sha(source); reader = pq.ParquetFile(source)
        assert len(reader.schema_arrow.names) == 95
        assert not set(appended).intersection(reader.schema_arrow.names)
        pending = dest.with_suffix('.pending.parquet')
        writer = None; count = 0; seen = np.zeros((5, len(codes)), dtype=np.uint8)
        def positions(table):
            positions = index.get_indexer(table.column('Mesh Code').to_pylist())
            assert (positions >= 0).all()
            return positions
        try:
            for batch in reader.iter_batches(batch_size=65536):
                original = pa.Table.from_batches([batch]); pos = positions(original)
                years = original.column('Road Year').to_numpy()
                assert np.isin(years, YEARS).all()
                for j, year in enumerate(YEARS):
                    selected = pos[years == year]
                    assert len(np.unique(selected)) == len(selected)
                    assert np.all(seen[j, selected] == 0)
                    seen[j, selected] = 1
                matched = mesh.take(pa.array(pos)); result = original
                for name in appended:
                    result = result.append_column(name, matched.column(name))
                if writer is None:
                    writer = pq.ParquetWriter(pending, result.schema, compression='zstd')
                writer.write_table(result); count += len(result)
        finally:
            if writer:
                writer.close()
        exported = pq.ParquetFile(pending)
        assert count == reader.metadata.num_rows == exported.metadata.num_rows
        assert np.all(seen == seen[0])  # five periods per retained mesh
        verified = 0; population_zeros = 0
        for a, b in zip(reader.iter_batches(batch_size=65536), exported.iter_batches(batch_size=65536), strict=True):
            original, result = pa.Table.from_batches([a]), pa.Table.from_batches([b])
            assert original.equals(result.select(original.column_names), check_metadata=False)
            assert mesh.take(pa.array(positions(original))).select(appended).equals(result.select(appended), check_metadata=False)
            population_zeros += int(np.sum(result.column('Population').to_numpy() == 0))
            verified += len(result)
        assert verified == count and sha(source) == before
        pending.replace(dest)
        outputs.append(dict(source=str(source.relative_to(ROOT)), source_sha256=before,
            output=str(dest.relative_to(ROOT)), output_sha256=sha(dest), rows=count,
            columns=len(exported.schema_arrow.names), meshes=int(seen[0].sum()),
            original_columns_preserved_exactly=95, all_previous_values_preserved_exactly=True,
            all_static_values_match_mesh_source=True, population_zero_rows=population_zeros,
            five_periods_per_mesh=True, no_key_duplication=True, no_row_deletion=True))
        print('Linked and verified:', dest_name, count, len(exported.schema_arrow.names), flush=True)
    (OUT / 'panel_linkage_validation.json').write_text(json.dumps(dict(status='passed',
        decision_id=decisions['decision_id'], years=YEARS, mesh_rows=len(mesh), mesh_columns=len(mesh.column_names),
        analytical_columns_added=18, columns_added=len(appended), outputs=outputs,
        regressions_refitted=False), indent=2) + '\n')


if __name__ == '__main__':
    main()
