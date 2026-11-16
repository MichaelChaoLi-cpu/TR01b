"""Link confirmed annual MODIS mesh outputs to facility-augmented five-period panels."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/modis-land-cover'
DEST = ROOT / 'data/processed/national/modis_land_cover'
SOURCE = ROOT / 'data/processed/national/static_facilities'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    decisions = json.loads((OUT / 'decisions.json').read_text())
    assert decisions['confirmed']
    contract = json.loads((OUT / 'proposed_construction.json').read_text())
    assert contract['confirmed']
    years = contract['years']
    codes = pd.read_parquet(ROOT / 'data/exp/data-preprocessing/national/common_grid.parquet').mesh_code
    index = pd.Index(codes)
    assert index.is_unique
    parts = []
    for year, spec in zip(years, decisions['datasets'].values(), strict=True):
        table = pq.read_table(ROOT / spec['output'])
        assert table.column('Mesh Code').to_pylist() == codes.tolist()
        assert np.all(table.column('Land Cover Year').to_numpy() == year)
        parts.append(table)
    modis = pa.concat_tables(parts)
    mesh_path = DEST / 'modis_land_cover_mesh_preprocessed.parquet'
    pq.write_table(modis, mesh_path, compression='zstd')
    appended = [c for c in modis.column_names if c != 'Mesh Code']
    outputs = []
    for source_name, destination_name in [
        ('road_population_light_facilities_five_period_preprocessed.parquet',
         'road_population_light_facilities_land_cover_five_period_preprocessed.parquet'),
        ('balanced_five_period_facilities_panel_preprocessed.parquet',
         'balanced_five_period_facilities_land_cover_panel_preprocessed.parquet')]:
        source = SOURCE / source_name; dest = DEST / destination_name
        temporary = dest.with_suffix('.pending.parquet')
        before = sha(source); reader = pq.ParquetFile(source)
        assert not set(appended).intersection(reader.schema_arrow.names)
        writer = None; count = 0
        def positions(table):
            mesh_positions = index.get_indexer(table.column('Mesh Code').to_pylist())
            assert (mesh_positions >= 0).all()
            observed = table.column('Road Year').to_numpy()
            year_positions = np.array([years.index(int(v)) for v in observed])
            return mesh_positions + len(index) * year_positions
        try:
            for batch in reader.iter_batches(batch_size=65536):
                original = pa.Table.from_batches([batch])
                matched = modis.take(pa.array(positions(original)))
                assert matched.column('Mesh Code').to_pylist() == original.column('Mesh Code').to_pylist()
                assert np.array_equal(matched.column('Land Cover Year').to_numpy(),
                                      original.column('Road Year').to_numpy())
                result = original
                for name in appended:
                    result = result.append_column(name, matched.column(name))
                if writer is None:
                    writer = pq.ParquetWriter(temporary, result.schema, compression='zstd')
                writer.write_table(result); count += len(result)
        finally:
            if writer:
                writer.close()
        exported = pq.ParquetFile(temporary)
        assert count == reader.metadata.num_rows == exported.metadata.num_rows
        verified = 0
        for a, b in zip(reader.iter_batches(batch_size=65536),
                        exported.iter_batches(batch_size=65536), strict=True):
            original, result = pa.Table.from_batches([a]), pa.Table.from_batches([b])
            assert original.equals(result.select(original.column_names), check_metadata=False)
            assert modis.take(pa.array(positions(original))).select(appended).equals(
                result.select(appended), check_metadata=False)
            verified += len(result)
        assert verified == count and sha(source) == before
        temporary.replace(dest)
        outputs.append(dict(source=str(source.relative_to(ROOT)), source_sha256=before,
                            output=str(dest.relative_to(ROOT)), output_sha256=sha(dest),
                            rows=count, columns=len(exported.schema_arrow.names),
                            all_previous_columns_preserved_exactly=True,
                            annual_modis_values_match_source_table=True,
                            no_row_deletion=True, no_key_duplication=True))
        print('Linked and verified:', destination_name, count, len(exported.schema_arrow.names), flush=True)
    (OUT / 'panel_linkage_validation.json').write_text(json.dumps(dict(
        status='passed', decision_id=decisions['decision_id'], years=years,
        mesh_year_rows=len(modis), mesh_columns=len(modis.column_names), columns_added=len(appended),
        outputs=outputs, static_facilities_preserved=True, regressions_refitted=False), indent=2) + '\n')


if __name__ == '__main__':
    main()
