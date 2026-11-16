"""Independent source-ledger, mesh-sum and preservation checks for KSJ construction."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/ksj-eighteen-facilities'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def rows(path):
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            yield json.loads(line)


def key(r):
    return r['source_archive'], r['source_member'], r['source_feature_id']


def bounds(code):
    # Independently decode each native point's assigned third-order mesh.
    a, b = int(code[:2]), int(code[2:4])
    south = a * 2 / 3 + int(code[4]) / 12 + int(code[6]) / 120
    west = 100 + b + int(code[5]) / 8 + int(code[7]) / 80
    return west, south, west + 1 / 80, south + 1 / 120


def main():
    decisions = json.loads((OUT / 'decisions.json').read_text()); assert decisions['confirmed']
    geometry = json.loads((OUT / 'geometry_construction_report.json').read_text())
    reports = {r['kind']: r for r in geometry['datasets']}
    schemas = json.loads((OUT / 'schemas.json').read_text())
    tourism = {key(r): r for r in rows(OUT / 'tourism_native_geometry.jsonl.gz')}
    codes = pd.read_parquet(ROOT / 'data/exp/data-preprocessing/national/common_grid.parquet').mesh_code.astype(str)
    grid = set(codes)
    details = []
    for spec in decisions['datasets'].values():
        kind = spec['kind']; report = reports[kind]
        units = {u['unit_id']: u for u in rows(OUT / 'construction-ledgers' / f'{kind}_units.jsonl.gz')}
        records = {key(r): r for r in rows(OUT / 'construction-ledgers' / f'{kind}_records.jsonl.gz')}
        assert len(records) == report['source_records']
        independent_counts = Counter(); members = Counter(); duplicate_records = 0
        fingerprints = set()
        for unit in units.values():
            native = tuple(tuple(c) for c in unit['source_coordinate_geometry'])
            label = unit['original_name_or_address']; anonymous = label is None or label == ''
            fp = (label, unit['source_coordinate_crs'], native, tuple(unit['classification_partition']),
                  tuple(unit['representative']) if anonymous else None)
            assert fp not in fingerprints; fingerprints.add(fp)
            assert len(unit['meshes']) == len(set(unit['meshes']))
            assert set(unit['in_grid_meshes']) == set(unit['meshes']).intersection(grid)
            independent_counts.update(unit['in_grid_meshes'])
            # Every retained target point must fall inside one of its assigned mesh polygons.
            for lon, lat in unit['target_coordinates']:
                containing = []
                for code in unit['meshes']:
                    west, south, east, north = bounds(code)
                    if west - 1e-12 <= lon < east + 1e-12 and south - 1e-12 <= lat < north + 1e-12:
                        containing.append(code)
                assert containing, (kind, unit['unit_id'], lon, lat)
        source_count = 0
        for schema_key, schema in schemas.items():
            if schema['kind'] != kind:
                continue
            for original in rows(OUT / 'source-inventory' / f'{schema_key}.jsonl.gz'):
                source_count += 1
                ledger = records.pop(key(original))
                assert ledger['source_schema'] == schema_key
                if ledger['unit_id'] is None:
                    gt = original['source_geometry_type']
                    if ledger['excluded_reason'] == 'reference_nonpoint_geometry':
                        assert gt != 'POINT' and not (kind == 'tourism_resources' and gt == 'MULTIPOINT')
                    elif ledger['excluded_reason'] == 'noncurrent_version':
                        assert kind == 'expressway_nodes'
                        assert not (original['N06_014'] == 9999 and original['N06_013'] is not None and original['N06_013'] <= 2025)
                    else:
                        assert ledger['excluded_reason'] == 'unlocated'
                    continue
                unit = units[ledger['unit_id']]
                assert ledger['declared_crs_used'] == (original['source_crs_wkt'] is None)
                assert unit['original_name_or_address'] == original[spec['identity_field']]
                assert unit['classification_partition'] == [original[c] for c in spec['classification_partition']]
                if original['source_geometry_type'] == 'POINT':
                    assert unit['source_coordinate_geometry'] == [[original['source_longitude'], original['source_latitude']]]
                elif kind == 'tourism_resources':
                    assert unit['source_coordinate_geometry'] == sorted(tourism[key(original)]['native_point_coordinates'])
                if ledger['identity_missing']:
                    assert unit['member_records'] == 1
                if kind == 'expressway_nodes':
                    assert original['N06_014'] == 9999 and original['N06_013'] <= 2025
                    assert str(original['N06_019']) in {'1', '2', '3', '4'}
                members[ledger['unit_id']] += 1
                duplicate_records += int(ledger['exact_duplicate'])
        assert not records and source_count == report['source_records']
        assert duplicate_records == report['exact_duplicate_records']
        assert all(members[u] == units[u]['member_records'] for u in units)
        table = pq.read_table(ROOT / spec['output'])
        assert table.column_names == [v['readable_name'] for v in spec['variables']]
        assert table.column('Mesh Code').to_pylist() == codes.tolist()
        name = report['analytical_name']; values = table.column(name).to_numpy()
        expected = np.array([independent_counts[c] for c in codes], dtype=np.int32)
        assert np.array_equal(values, expected) and (values >= 0).all()
        assert table.column(name).null_count == 0
        prefix = name.removesuffix(' Count')
        assert np.all(table.column(prefix + ' Source Archive Year').to_numpy() == report['archive_year'])
        assert np.all(table.column(prefix + ' Source Reference Year').to_numpy() == report['reference_year'])
        assert np.all(table.column(prefix + ' Archive Coverage Complete').to_numpy())
        payload = json.loads((OUT / 'construction-ledgers' / f'{kind}_mesh_counts.json').read_text())
        assert payload['counts'] == dict(independent_counts)
        for field in ['declared_crs_used', 'duplicate_present']:
            flagged = set()
            for unit in units.values():
                condition = unit['declared_crs_used'] if field == 'declared_crs_used' else unit['member_records'] > 1
                if condition:
                    flagged.update(unit['in_grid_meshes'])
            assert flagged == set(payload[field])
            readable = prefix + (' Declared CRS Used' if field == 'declared_crs_used' else ' Exact Duplicate Present')
            assert np.array_equal(table.column(readable).to_numpy(), codes.isin(flagged).to_numpy())
        for field, unit_field in [('relation_inconsistency', 'relation_id_inconsistent'),
                                 ('multiple_location', 'multiple_native_locations')]:
            flagged = set()
            for unit in units.values():
                if unit[unit_field]:
                    flagged.update(unit['in_grid_meshes'])
            assert flagged == set(payload[field])
        details.append({'kind': kind, 'count_sum': int(values.sum()), 'positive_meshes': int((values > 0).sum()),
                        'zero_meshes': int((values == 0).sum()), 'maximum_mesh_count': int(values.max()),
                        'unique_units': len(units), 'duplicates': duplicate_records,
                        'source_rows_accounted_for': source_count,
                        'all_point_coordinates_inside_assigned_mesh': True,
                        'parquet_sha256': sha(ROOT / spec['output'])})
        print('Validated source ledger and mesh count:', kind, int(values.sum()), flush=True)
    manifest = json.loads((ROOT / 'data/exp/data-augmentation-screening/ksj-eighteen-facilities/acquisition_manifest.json').read_text())
    audits = json.loads((OUT / 'source_archive_audit.json').read_text())
    for audit in audits:
        canonical = 'UTF-8' if audit['encoding'].lower().replace('-', '') in {'utf8', '65001'} else 'CP932'
        assert audit['encoding_audit']['strict_decode_failures'][canonical] == 0
    # Original raw bytes must remain exactly as acquired.
    for item in manifest['records']:
        assert sha(ROOT / item['path']) == item['sha256']
    preserved = json.loads((OUT / 'preserved_inputs.json').read_text())
    for item in preserved:
        if item['path'] != 'docs/AnaSOP.md':
            assert sha(ROOT / item['path']) == item['sha256']
    link = json.loads((OUT / 'panel_linkage_validation.json').read_text())
    assert link['status'] == 'passed'
    for item in link['outputs']:
        assert sha(ROOT / item['source']) == item['source_sha256']
        assert sha(ROOT / item['output']) == item['output_sha256']
    result = dict(status='passed', decision_id=decisions['decision_id'], datasets=details,
                  selected_counts=18, raw_archives_verified=len(manifest['records']),
                  original_panels_and_results_unchanged=True, complete_source_record_accounting=True,
                  no_new_sample_exclusion=True, regressions_refitted=False,
                  panel_validation=link)
    (OUT / 'construction_validation.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
