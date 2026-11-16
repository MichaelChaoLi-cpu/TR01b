"""Construct the approved 18 KSJ snapshot counts; separate GDAL and Arrow processes.

Run --stage prepare, --stage geometry, then --stage tables. The generated
per-source preprocessing scripts and link_ksj_eighteen_panel.py finish delivery.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/ksj-eighteen-facilities'
DEST = ROOT / 'data/processed/national/ksj_eighteen_facilities'
DECISION = 'MILI-D-20261010-021'
SPECS = [
    ('fuel_stations', 'Fuel Station Count', 'P07_002', ['P07_001']),
    ('roadside_stations', 'Roadside Station Count', 'P35_006', [f'P35_{i:03d}' for i in range(11, 29)]),
    ('expressway_nodes', 'Expressway Junction Count', 'N06_018', ['N06_019']),
    ('ports', 'Port Count', 'C02_005', ['C02_001', 'C02_002']),
    ('fishing_ports', 'Fishing Port Count', 'C09_002', ['C09_004']),
    ('scheduled_passenger_routes_nodes', 'Passenger Route Port Count', 'N09_004', []),
    ('heliports', 'Heliport Count', 'N11_001', ['N11_002', 'N11_003']),
    ('welfare', 'Welfare Facility Count', 'P14_008', ['P14_005', 'P14_006', 'P14_007']),
    ('culture', 'Cultural and Sports Facility Count', 'P27_005', ['P27_004']),
    ('municipal_offices_meeting_facilities', 'Municipal and Meeting Facility Count', 'P05_003', ['P05_002']),
    ('national_prefectural_offices', 'National and Prefectural Institution Count', 'P28_003', ['P28_002']),
    ('police', 'Police Facility Count', 'P18_001', ['P18_003']),
    ('fire_services', 'Fire Facility Count', 'P17_001', ['P17_003']),
    ('post_offices', 'Post Office Count', 'P30_005', ['P30_004']),
    ('research_institutions', 'Research Institution Count', 'P16_001', ['P16_002']),
    ('local_industry', 'Local Industry Facility Count', 'P24_005', ['P24_007', 'P24_008', 'P24_009', 'P24_010']),
    ('urban_parks_legacy', 'Urban Park Count', 'P13_003', ['P13_004']),
    ('tourism_resources', 'Tourism Resource Count', 'P12_002', ['P12_007']),
]


def dump(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def rows(path):
    with gzip.open(path, 'rt') as stream:
        for line in stream:
            yield json.loads(line)


def feature_key(row):
    return (row['source_archive'], row['source_member'], row['source_feature_id'])


def mesh_code(lon, lat):
    # Established repository boundary convention: south/west inclusive.
    r = math.floor(math.nextafter(lat * 120, math.inf))
    c = math.floor(math.nextafter((lon - 100) * 80, math.inf))
    return f'{r//80:02d}{c//80:02d}{r%80//10}{c%80//10}{r%10}{c%10}'


def prepare():
    import pandas as pd
    manifest = json.loads((ROOT / 'data/exp/data-augmentation-screening/ksj-eighteen-facilities/acquisition_manifest.json').read_text())
    assert manifest['status'] == 'passed'
    codes = pd.read_parquet(ROOT / 'data/exp/data-preprocessing/national/common_grid.parquet').mesh_code.astype(str).tolist()
    assert len(codes) == len(set(codes)) == 972800
    with gzip.open(OUT / 'mesh_codes.json.gz', 'wt') as stream:
        json.dump(codes, stream)
    baseline = OUT / 'AnaSOP_before_ksj.txt'
    if not baseline.exists():
        baseline.write_bytes((ROOT / 'docs/AnaSOP.md').read_bytes())
    old_delivery = OUT / 'inventory_delivery_validation.json'
    if not old_delivery.exists():
        old_delivery.write_bytes((OUT / 'delivery_validation.json').read_bytes())
    datasets = {}
    for kind, name, identity, classes in SPECS:
        base = name.removesuffix(' Count')
        mapping = {
            'mesh_code': 'Mesh Code', 'observed_count': name,
            'archive_year': base + ' Source Archive Year',
            'reference_year': base + ' Source Reference Year',
            'coverage_complete': base + ' Archive Coverage Complete',
            'declared_crs_used': base + ' Declared CRS Used',
            'duplicate_present': base + ' Exact Duplicate Present',
        }
        if kind == 'expressway_nodes':
            mapping['relation_inconsistency'] = base + ' Relation ID Inconsistent'
        if kind == 'tourism_resources':
            mapping['multi_location'] = base + ' Multiple Location Resource Present'
            mapping['point_only'] = base + ' Point Geometry Only'
        if kind == 'roadside_stations':
            mapping['reference_date'] = base + ' Source Reference Date'
        source = f'data/exp/data-preprocessing/ksj-eighteen-facilities/constructed-inputs/ksj_{kind}_mesh.parquet'
        datasets[source] = {
            'kind': kind, 'output': f'data/processed/national/ksj_eighteen_facilities/{kind}_mesh_preprocessed.parquet',
            'script': f'src/preprocessing/preprocess_ksj_{kind}_mesh.py',
            'identity_field': identity, 'classification_partition': classes,
            'variables': [{'original_name': k, 'readable_name': v, 'full_name': v,
                           'is_final_variable': 'yes' if k == 'observed_count' else 'no',
                           'role': 'TBD' if k == 'observed_count' else 'reference',
                           'preprocessing': []} for k, v in mapping.items()],
        }
    dump(OUT / 'decisions.json', {
        'confirmed': True, 'decision_id': DECISION, 'years': [2002, 2003, 2004, 2010, 2024],
        'target_epsg': 4612, 'datasets': datasets,
        'duplicate_rule': 'Within dataset, exact original nonmissing name/address + native coordinate geometry + class/function partition. Missing names retain individual identity. No normalization or fuzzy merge.',
        'tourism_rule': 'At most one count per deduplicated parent resource per mesh containing a native point; exclude reference lines/polygons.',
        'expressway_rule': 'End year 9999 and start year <=2025; retain categories 1-4 and conflicting relation IDs.',
        'zero_rule': 'No selected observed unit under completed archive coverage; does not establish real-world completeness.',
        'static_assumption': True, 'regression_roles': 'TBD; no model selected or refitted',
        'source_contract': 'CONSTRUCTION_PROPOSAL.md', 'imputation': False,
    })
    print('Confirmed contract and grid prepared.', flush=True)


def geometry():
    from osgeo import ogr, osr
    ogr.UseExceptions()
    osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
    target = osr.SpatialReference(); target.ImportFromEPSG(4612)
    target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    decisions = json.loads((OUT / 'decisions.json').read_text()); assert decisions['confirmed']
    with gzip.open(OUT / 'mesh_codes.json.gz', 'rt') as stream:
        grid = set(json.load(stream))
    schemas = json.loads((OUT / 'schemas.json').read_text())
    official = json.loads((OUT / 'official_crs_declarations.json').read_text())
    tourism = {feature_key(r): r for r in rows(OUT / 'tourism_native_geometry.jsonl.gz')}
    transformations = {}
    all_reports = []
    ledger_dir = OUT / 'construction-ledgers'; ledger_dir.mkdir(exist_ok=True)
    for kind, name, identity, classes in SPECS:
        counts = Counter(); fallback = set(); duplicates = set(); multiple = set(); inconsistent_meshes = set()
        units = {}; fingerprints = {}; source_records = 0; eligible_records = 0
        excluded = Counter(); unlocated = 0; declared_records = 0
        relation = defaultdict(set)
        # The current-node relation check is intentionally separate from deduplication.
        if kind == 'expressway_nodes':
            for key, schema in schemas.items():
                if schema['kind'] == kind and schema['geometry_type'] == 'Point':
                    for r in rows(OUT / 'source-inventory' / f'{key}.jsonl.gz'):
                        if r['N06_014'] == 9999 and r['N06_013'] is not None and r['N06_013'] <= 2025:
                            relation[r['N06_015']].add((r['N06_018'], r['N06_019'], r['source_longitude'], r['source_latitude']))
        conflict = {k for k, v in relation.items() if k is not None and len(v) > 1}
        with gzip.open(ledger_dir / f'{kind}_records.jsonl.gz', 'wt') as ledger:
            for schema_key, schema in schemas.items():
                if schema['kind'] != kind:
                    continue
                for r in rows(OUT / 'source-inventory' / f'{schema_key}.jsonl.gz'):
                    source_records += 1
                    parent = feature_key(r)
                    entry = {'source_schema': schema_key, 'source_archive': parent[0], 'source_member': parent[1],
                             'source_feature_id': parent[2], 'source_geometry_type': r['source_geometry_type'],
                             'unit_id': None, 'excluded_reason': None}
                    gt = r['source_geometry_type']
                    reason = None
                    if gt != 'POINT' and not (kind == 'tourism_resources' and gt == 'MULTIPOINT'):
                        reason = 'reference_nonpoint_geometry'
                    elif kind == 'expressway_nodes' and not (r['N06_014'] == 9999 and r['N06_013'] is not None and r['N06_013'] <= 2025):
                        reason = 'noncurrent_version'
                    if reason:
                        excluded[reason] += 1; entry['excluded_reason'] = reason
                        ledger.write(json.dumps(entry, ensure_ascii=False) + '\n'); continue
                    eligible_records += 1
                    missing_prj = r['source_crs_wkt'] is None
                    declared_records += int(missing_prj)
                    crs_key = r['source_crs_wkt'] or f"EPSG:{official[kind]['epsg']}"
                    if crs_key not in transformations:
                        native = osr.SpatialReference()
                        if missing_prj:
                            native.ImportFromEPSG(official[kind]['epsg'])
                        else:
                            native.ImportFromWkt(crs_key)
                        native.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
                        try:
                            native.AutoIdentifyEPSG()
                        except RuntimeError:
                            pass
                        crs_identity = native.GetAuthorityCode(None) or native.ExportToWkt()
                        transformations[crs_key] = (osr.CoordinateTransformation(native, target), crs_identity)
                    transform, crs_identity = transformations[crs_key]
                    native_points = ([(r['source_longitude'], r['source_latitude'])] if gt == 'POINT' else
                                     [tuple(p) for p in tourism[parent]['native_point_coordinates']])
                    if not native_points or any(x is None or y is None for x, y in native_points):
                        unlocated += 1; entry['excluded_reason'] = 'unlocated'
                        ledger.write(json.dumps(entry, ensure_ascii=False) + '\n'); continue
                    # Exact native geometry identity, with no coordinate rounding.
                    coords = tuple(sorted(native_points))
                    label = r[identity]
                    anonymous = label is None or label == ''
                    fingerprint = (label, crs_identity, coords, tuple(r[f] for f in classes), parent if anonymous else None)
                    is_duplicate = fingerprint in fingerprints
                    unit_id = fingerprints.get(fingerprint, f'{kind}:{len(units):07d}')
                    transformed = [transform.TransformPoint(x, y)[:2] for x, y in native_points]
                    assert all(math.isfinite(x) and math.isfinite(y) for x, y in transformed)
                    meshes = sorted({mesh_code(x, y) for x, y in transformed})
                    in_grid = [m for m in meshes if m in grid]
                    out_grid = [m for m in meshes if m not in grid]
                    flag = kind == 'expressway_nodes' and r['N06_015'] in conflict
                    if not is_duplicate:
                        fingerprints[fingerprint] = unit_id
                        units[unit_id] = {'unit_id': unit_id, 'representative': parent,
                            'original_name_or_address': label, 'classification_partition': [r[f] for f in classes],
                            'source_coordinate_crs': crs_identity, 'source_coordinate_geometry': coords,
                            'target_coordinates': transformed, 'meshes': meshes, 'in_grid_meshes': in_grid,
                            'out_of_grid_meshes': out_grid, 'member_records': 0,
                            'declared_crs_used': False, 'relation_id_inconsistent': flag,
                            'multiple_native_locations': len(set(native_points)) > 1}
                        counts.update(in_grid)
                    unit = units[unit_id]
                    assert unit['meshes'] == meshes
                    unit['member_records'] += 1
                    unit['declared_crs_used'] |= missing_prj
                    if missing_prj:
                        fallback.update(in_grid)
                    if is_duplicate:
                        duplicates.update(in_grid)
                    if len(set(native_points)) > 1:
                        multiple.update(in_grid)
                    if flag:
                        inconsistent_meshes.update(in_grid)
                    entry.update(unit_id=unit_id, declared_crs_used=missing_prj, exact_duplicate=is_duplicate,
                                 identity_missing=anonymous, relation_id_inconsistent=flag)
                    ledger.write(json.dumps(entry, ensure_ascii=False) + '\n')
        with gzip.open(ledger_dir / f'{kind}_units.jsonl.gz', 'wt') as stream:
            for unit in units.values():
                stream.write(json.dumps(unit, ensure_ascii=False) + '\n')
        assert sum(u['member_records'] for u in units.values()) + unlocated == eligible_records
        assert sum(counts.values()) == sum(len(u['in_grid_meshes']) for u in units.values())
        payload = {'counts': counts, 'declared_crs_used': sorted(fallback), 'duplicate_present': sorted(duplicates),
                   'multiple_location': sorted(multiple), 'relation_inconsistency': sorted(inconsistent_meshes)}
        dump(ledger_dir / f'{kind}_mesh_counts.json', payload)
        report = {'kind': kind, 'analytical_name': name, 'source_records': source_records,
            'eligible_records': eligible_records, 'unique_units': len(units),
            'exact_duplicate_records': eligible_records - unlocated - len(units),
            'unlocated_records': unlocated, 'excluded_records': dict(excluded),
            'declared_crs_records': declared_records, 'in_grid_unit_mesh_memberships': sum(counts.values()),
            'positive_meshes': len(counts), 'out_of_grid_units': sum(bool(u['out_of_grid_meshes']) for u in units.values()),
            'out_of_grid_memberships': sum(len(u['out_of_grid_meshes']) for u in units.values()),
            'multiple_location_units': sum(u['multiple_native_locations'] for u in units.values()),
            'inconsistent_relation_ids': sorted(conflict),
            'archive_year': next(s['archive_year'] for s in schemas.values() if s['kind'] == kind),
            'reference_year': next(s['reference_year'] for s in schemas.values() if s['kind'] == kind)}
        all_reports.append(report)
        print(kind, 'units', len(units), 'duplicates', report['exact_duplicate_records'],
              'mesh memberships', report['in_grid_unit_mesh_memberships'], 'outside', report['out_of_grid_units'], flush=True)
    dump(OUT / 'geometry_construction_report.json', {'status': 'passed', 'decision_id': DECISION,
         'target_epsg': 4612, 'grid_meshes': len(grid), 'datasets': all_reports})


def tables():
    import numpy as np
    import pandas as pd
    decisions = json.loads((OUT / 'decisions.json').read_text()); assert decisions['confirmed']
    report = json.loads((OUT / 'geometry_construction_report.json').read_text())
    reports = {d['kind']: d for d in report['datasets']}
    with gzip.open(OUT / 'mesh_codes.json.gz', 'rt') as stream:
        codes = json.load(stream)
    index = pd.Index(codes)
    for input_path, spec in decisions['datasets'].items():
        kind = spec['kind']; r = reports[kind]
        payload = json.loads((OUT / 'construction-ledgers' / f'{kind}_mesh_counts.json').read_text())
        values = np.zeros(len(codes), dtype=np.int32)
        for code, count in payload['counts'].items():
            pos = index.get_loc(code); values[pos] = count
        frame = pd.DataFrame({'mesh_code': pd.Series(codes, dtype='string'), 'observed_count': values,
                              'archive_year': np.int16(r['archive_year']), 'reference_year': np.int16(r['reference_year']),
                              'coverage_complete': True})
        for field in ['declared_crs_used', 'duplicate_present']:
            frame[field] = index.isin(payload[field])
        if kind == 'expressway_nodes':
            frame['relation_inconsistency'] = index.isin(payload['relation_inconsistency'])
        if kind == 'tourism_resources':
            frame['multi_location'] = index.isin(payload['multiple_location'])
            frame['point_only'] = True
        if kind == 'roadside_stations':
            frame['reference_date'] = '2019-01-01'
        dst = ROOT / input_path; dst.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(dst, index=False, compression='zstd')
        assert int(values.sum()) == r['in_grid_unit_mesh_memberships']
    print('Eighteen dense mesh inputs ready for confirmed readable-name scripts.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', required=True, choices=['prepare', 'geometry', 'tables'])
    stage = parser.parse_args().stage
    {'prepare': prepare, 'geometry': geometry, 'tables': tables}[stage]()
