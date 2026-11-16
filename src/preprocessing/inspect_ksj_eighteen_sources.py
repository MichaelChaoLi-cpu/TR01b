"""Inventory every original field in the eighteen selected KSJ GIS sources.

Raw ZIPs remain unchanged. Point coordinates are recorded in the original CRS;
nonpoint geometry remains referenced in its original archive, not converted to POI.
GDAL extraction and Arrow/pandas summaries run in separate processes.
"""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import re
import sys
import struct
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ACQUISITION = ROOT / 'data/exp/data-augmentation-screening/ksj-eighteen-facilities'
OUT = ROOT / 'data/exp/data-preprocessing/ksj-eighteen-facilities'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def verified_dbf_encoding(archive, member, siblings):
    """Use declarations where present; otherwise verify every character cell's bytes.

    A missing CPG is not evidence for CP932. Several modern bundled products
    contain UTF-8 DBFs without a CPG or an encoding suffix in their filenames.
    """
    dbf = archive.read(siblings[(member[:-4] + '.dbf').lower()])
    records = struct.unpack_from('<I', dbf, 4)[0]
    header, width = struct.unpack_from('<HH', dbf, 8)
    offset = 1; fields = []
    for pos in range(32, header - 1, 32):
        if dbf[pos] == 13:
            break
        length = dbf[pos + 16]
        if dbf[pos + 11] == ord('C'):
            fields.append((offset, length))
        offset += length
    assert offset == width, (member, offset, width)
    failures = {'UTF-8': 0, 'CP932': 0}; nonascii = 0
    cache = {}
    for i in range(records):
        start = header + i * width
        for offset, length in fields:
            value = dbf[start + offset:start + offset + length]
            if value.isascii():
                continue
            nonascii += 1
            if value not in cache:
                valid = {}
                for encoding in failures:
                    try:
                        value.decode(encoding, errors='strict'); valid[encoding] = True
                    except UnicodeDecodeError:
                        valid[encoding] = False
                cache[value] = valid
            for encoding, valid in cache[value].items():
                failures[encoding] += int(not valid)
    cpg = siblings.get((member[:-4] + '.cpg').lower())
    declared = archive.read(cpg).decode().strip() if cpg else None
    if declared:
        encoding = declared
        canonical = 'UTF-8' if declared.lower().replace('-', '') in {'utf8', '65001'} else 'CP932'
        assert failures[canonical] == 0, (member, declared, failures)
    elif re.search(r'utf[-_]?8', member, re.I):
        encoding = 'UTF-8'; assert failures[encoding] == 0
    elif failures['UTF-8'] == 0 and failures['CP932'] > 0:
        encoding = 'UTF-8'
    elif failures['CP932'] == 0:
        encoding = 'CP932'
    else:
        raise ValueError(f'Cannot decode DBF safely: {member}: {failures}')
    return encoding, dict(character_cells_nonascii=nonascii, strict_decode_failures=failures,
                          cpg_declaration=declared, selection='full DBF byte audit')


def extract():
    sys.path.insert(0, str(ROOT / 'src/exp'))
    from acquire_ksj_eighteen_facilities import archive_parts
    from osgeo import gdal, ogr, osr
    ogr.UseExceptions()
    osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
    manifest = json.loads((ACQUISITION / 'acquisition_manifest.json').read_text())
    assert manifest['status'] == 'passed' and len(manifest['categories']) == 18
    inventory = OUT / 'source-inventory'
    inventory.mkdir(parents=True, exist_ok=True)
    handles, audits, schemas, alternatives = {}, [], {}, []
    try:
        for number, item in enumerate(manifest['records'], 1):
            path = ROOT / item['path']
            assert digest(path) == item['sha256'], path
            with zipfile.ZipFile(path) as outer:
                for archive, prefix in archive_parts(outer):
                    members = archive.namelist()
                    layers = [name for name in members if name.lower().endswith('.shp')]
                    utf8 = [name for name in layers if re.search(r'utf[-_]?8', name, re.I)]
                    if utf8:
                        alternatives.extend(dict(source_archive=item['path'], member=prefix + name, reason='Alternative encoding; UTF-8 representation selected')
                                            for name in layers if name not in utf8)
                        layers = utf8
                    assert layers, path
                    for member in layers:
                        siblings = {name.lower(): name for name in members}
                        encoding, encoding_audit = verified_dbf_encoding(archive, member, siblings)
                        gdal.SetConfigOption('SHAPE_ENCODING', encoding)
                        staged = []
                        for suffix in ('.shp', '.shx', '.dbf', '.prj', '.cpg'):
                            component = siblings.get((member[:-4] + suffix).lower())
                            if component:
                                target = '/vsimem/ksj_eighteen_layer' + suffix
                                gdal.FileFromMemBuffer(target, archive.read(component))
                                staged.append(target)
                        dataset = ogr.Open('/vsimem/ksj_eighteen_layer.shp')
                        assert dataset is not None, (path, member)
                        layer = dataset.GetLayer(0)
                        reference = layer.GetSpatialRef()
                        crs = reference.ExportToWkt() if reference else None
                        definition = layer.GetLayerDefn()
                        fields = [dict(name=definition.GetFieldDefn(i).GetName(),
                                       type=definition.GetFieldDefn(i).GetTypeName()) for i in range(definition.GetFieldCount())]
                        geometry_type = ogr.GeometryTypeToName(layer.GetGeomType())
                        fingerprint = hashlib.sha256(json.dumps([geometry_type, fields], sort_keys=True).encode()).hexdigest()[:8]
                        key = item['kind'] + '_' + re.sub(r'[^a-z0-9]+', '_', geometry_type.lower()).strip('_') + '_' + fingerprint
                        if key not in handles:
                            handles[key] = gzip.open(inventory / (key + '.jsonl.gz'), 'wt', encoding='utf-8')
                            schemas[key] = dict(kind=item['kind'], geometry_type=geometry_type, fields=fields, crs=crs,
                                                archive_year=item['year'], reference_year=item['reference_year'])
                        count, missing_geometry = 0, 0
                        for feature in layer:
                            attributes = feature.items()
                            for value in attributes.values():
                                if isinstance(value, str):
                                    assert not any(0xD800 <= ord(char) <= 0xDFFF for char in value), (path, member)
                                    assert '\ufffd' not in value, (path, member)
                            geometry = feature.GetGeometryRef()
                            geometry_name = geometry.GetGeometryName() if geometry else None
                            is_point = geometry_name == 'POINT' and not geometry.IsEmpty()
                            missing_geometry += int(geometry is None or geometry.IsEmpty())
                            row = dict(**attributes, source_archive=item['path'], source_member=prefix + member, source_feature_id=feature.GetFID(),
                                       source_archive_year=item['year'], source_reference_year=item['reference_year'],
                                       source_geometry_type=geometry_name, source_geometry_missing=geometry is None or geometry.IsEmpty(),
                                       source_crs_wkt=crs,
                                       source_longitude=geometry.GetX() if is_point else None,
                                       source_latitude=geometry.GetY() if is_point else None,
                                       source_point_wkt=geometry.ExportToWkt() if is_point else None)
                            handles[key].write(json.dumps(row, ensure_ascii=False, allow_nan=False, default=str) + '\n')
                            count += 1
                        assert count == layer.GetFeatureCount(), (path, member, count)
                        audits.append(dict(category=key, kind=item['kind'], source_archive=item['path'], source_member=prefix + member,
                                           records=count, geometry_type=geometry_type, missing_geometry=missing_geometry,
                                           encoding=encoding, encoding_audit=encoding_audit,
                                           crs_present=crs is not None, sha256=item['sha256']))
                        layer = None
                        dataset = None
                        for target in staged:
                            gdal.Unlink(target)
            if number % 20 == 0 or number == len(manifest['records']):
                print(f'Inventoried {number}/{len(manifest["records"])} archives', flush=True)
    finally:
        for handle in handles.values():
            handle.close()
    (OUT / 'schemas.json').write_text(json.dumps(schemas, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'source_archive_audit.json').write_text(json.dumps(audits, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'alternative_encodings.json').write_text(json.dumps(alternatives, ensure_ascii=False, indent=2) + '\n')
    print('Extraction completed; run summarize separately.', flush=True)


def summarize():
    import pandas as pd
    schema = json.loads((OUT / 'schemas.json').read_text())
    audits = json.loads((OUT / 'source_archive_audit.json').read_text())
    manifest = json.loads((ACQUISITION / 'acquisition_manifest.json').read_text())
    spec = importlib.util.spec_from_file_location('ksj_variable_discovery', ROOT / '.codex/skills/data-preprocessing/scripts/prepare_variable_list.py')
    discovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(discovery)
    variables, datasets, summaries, classifications = [], {}, [], []
    for key, info in schema.items():
        path = OUT / 'source-inventory' / (key + '.jsonl.gz')
        frame = pd.read_json(path, lines=True, compression='gzip', dtype=False, convert_dates=False)
        expected = sum(a['records'] for a in audits if a['category'] == key)
        assert len(frame) == expected
        assert not frame.duplicated(['source_archive', 'source_member', 'source_feature_id']).any()
        parquet = path.with_name(key + '.parquet')
        frame.to_parquet(parquet, index=False)
        relative = str(parquet.relative_to(ROOT))
        rows = []
        for name in frame:
            series = frame[name]
            row = dict(source_dataset=relative, original_name=name, dtype=str(series.dtype),
                       non_null_count=int(series.notna().sum()), null_pct=round(float(series.isna().mean() * 100), 4),
                       sample_values=', '.join(str(value)[:60] for value in series.dropna().head(3)),
                       feasibility_status='unknown', readable_name='', full_name='', is_final_variable='')
            rows.append(row)
            if not name.startswith('source_') and series.nunique(dropna=True) <= 150 and series.nunique(dropna=True) > 0:
                for value, count in series.value_counts(dropna=False).items():
                    classifications.append(dict(category=key, field=name, value=str(value), records=int(count)))
        variables.extend(rows)
        datasets[relative] = rows
        point = frame['source_geometry_type'].eq('POINT')
        summaries.append(dict(category=key, kind=info['kind'], geometry_type=info['geometry_type'], records=len(frame),
                              columns=len(frame.columns), original_fields=len(info['fields']),
                              point_records=int(point.sum()), missing_geometry=int(frame['source_geometry_missing'].sum()),
                              missing_point_coordinates=int((point & (frame['source_longitude'].isna() | frame['source_latitude'].isna())).sum()),
                              source_archive_year=info['archive_year'], source_reference_year=info['reference_year']))
        print(key, len(frame), 'records;', info['geometry_type'], flush=True)
    discovery.write_variable_list(OUT, variables)
    discovery.write_readme(OUT, datasets, [])
    pd.DataFrame(summaries).to_csv(OUT / 'source_layer_summary.csv', index=False)
    pd.DataFrame(classifications).to_csv(OUT / 'source_value_frequencies.csv', index=False)
    summary = pd.DataFrame(summaries).groupby('kind', sort=False).agg(records=('records', 'sum'), point_records=('point_records', 'sum'),
                                                                 reference_year=('source_reference_year', 'first'), layers=('category', 'size'))
    summary.to_csv(OUT / 'category_summary.csv')
    assert len(summary) == 18
    for record in manifest['records']:
        assert digest(ROOT / record['path']) == record['sha256']
    assert {a['source_archive'] for a in audits} == {r['path'] for r in manifest['records']}
    validation = dict(status='passed', decision_id='MILI-D-20261010-020', categories=len(summary), source_layers=len(schema),
                      validated_archives=len(manifest['records']), all_raw_archive_sha256_unchanged=True,
                      full_inventory_not_sampled=True, source_field_rows=len(variables),
                      point_records=int(summary['point_records'].sum()), nonpoint_records=int(summary['records'].sum()-summary['point_records'].sum()),
                      missing_crs_layers=[a for a in audits if not a['crs_present']],
                      analytical_variables_constructed=False, five_period_panel_updated=False, regression_refitted=False)
    (OUT / 'source_inventory_validation.json').write_text(json.dumps(validation, indent=2) + '\n')
    with (OUT / 'README.md').open('a') as stream:
        stream.write('\n## Scope and status\n\nAll eighteen selected products have been acquired under MILI-D-20261010-020. '
                     'This is a complete source-attribute inventory, not an analytical selection. '
                     'Point and nonpoint source layers remain separate; alternative encodings are recorded separately. '
                     'No polygons or route lines were converted into facility points. Counts include raw feature records '
                     'and, where present, historical versions; they are not deduplicated operating facilities. '
                     'The proposed readable analytical variables and source filters are in CONSTRUCTION_PROPOSAL.md. '
                     'No mesh variable or augmented panel has been written and no regression has been refitted.\n')
    print(json.dumps({k: v for k, v in validation.items() if k != 'missing_crs_layers'}, indent=2), flush=True)
    print('Layers without PRJ:', len(validation['missing_crs_layers']), '; official declarations are audited separately.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['extract', 'summarize'], required=True)
    args = parser.parse_args()
    extract() if args.stage == 'extract' else summarize()
