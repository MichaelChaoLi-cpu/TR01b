"""Inventory facility source attributes without selecting analytical variables.

Reads original ZIPs in place. Saves one traceable exploratory inventory per source
layer and the data-preprocessing skill's complete variable list in a scoped folder.
Run --stage extract followed by --stage summarize in separate processes.
GDAL and the local Arrow writer must not initialize in the same process.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import importlib.util
import json
import zipfile

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/static-facilities'
CATALOGUE = ROOT / 'data/exp/data-augmentation-screening/mlit-facilities'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def extract():
    from osgeo import gdal, ogr, osr
    ogr.UseExceptions()
    osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
    OUT.mkdir(parents=True, exist_ok=True)
    inventory = OUT / 'source-inventory'
    inventory.mkdir(exist_ok=True)
    manifest = json.loads((CATALOGUE / 'facility_download_manifest.json').read_text())
    sources = manifest['records']
    sources.append(dict(kind='railway', path='data/raw/railway/n02/2024/N02-24_GML.zip',
                        year=2024, sha256='504eefd4411cd0fd3ad9a50f35da2f5da07949d5144ded7630df0972f8deaac7'))
    grouped, audits = {}, []
    for item in sources:
        path = ROOT / item['path']
        assert digest(path) == item['sha256'], path
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None, path
            layers = [n for n in archive.namelist() if n.endswith('.shp')]
            if item['kind'] in ('railway', 'airports'):
                layers = [n for n in layers if n.startswith('UTF-8/')]
            assert layers, path
            for member in layers:
                # The CPG, where present, takes priority; older products use CP932.
                cpg = member[:-4] + '.cpg'
                encoding = archive.read(cpg).decode().strip() if cpg in archive.namelist() else (
                    'UTF-8' if item['kind'] in ('railway', 'airports') else 'CP932')
                gdal.SetConfigOption('SHAPE_ENCODING', encoding)
                # Some official ZIPs use literal backslashes in member names;
                # GDAL's virtual ZIP paths cannot read those directly. Stage
                # only the shapefile components in GDAL memory, preserving raw.
                staged = []
                for suffix in ('.shp', '.shx', '.dbf', '.prj', '.cpg'):
                    component = member[:-4] + suffix
                    if component in archive.namelist():
                        target = '/vsimem/static_facility_layer' + suffix
                        gdal.FileFromMemBuffer(target, archive.read(component))
                        staged.append(target)
                dataset = ogr.Open('/vsimem/static_facility_layer.shp')
                layer = dataset.GetLayer(0)
                reference = layer.GetSpatialRef()
                crs = reference.ExportToWkt() if reference else None
                rows = []
                for feature in layer:
                    attributes = feature.items()
                    for value in attributes.values():
                        if isinstance(value, str):
                            assert not any(0xD800 <= ord(c) <= 0xDFFF for c in value), (path, member)
                    geometry = feature.GetGeometryRef()
                    rows.append(dict(**attributes, source_archive=item['path'], source_member=member,
                                     source_feature_id=feature.GetFID(), source_edition=int(item['year']),
                                     source_geometry_wkt=geometry.ExportToWkt() if geometry else None,
                                     source_crs_wkt=crs,
                                     source_longitude=geometry.GetX() if geometry and geometry.GetGeometryName() == 'POINT' else None,
                                     source_latitude=geometry.GetY() if geometry and geometry.GetGeometryName() == 'POINT' else None))
                key = item['kind']
                if key in ('railway', 'airports'):
                    key += '_' + Path(member).stem.split('_')[-1]
                grouped.setdefault(key, []).append(pd.DataFrame(rows))
                audits.append(dict(category=key, source_archive=item['path'], source_member=member,
                                   records=len(rows), encoding=encoding, crs_present=crs is not None,
                                   sha256=item['sha256']))
                layer = None
                dataset = None
                for target in staged:
                    gdal.Unlink(target)
    for category, parts in grouped.items():
        frame = pd.concat(parts, ignore_index=True)
        assert not frame.duplicated(['source_archive', 'source_member', 'source_feature_id']).any()
        with gzip.open(inventory / (category + '.jsonl.gz'), 'wt', encoding='utf-8') as stream:
            for row in frame.to_dict('records'):
                # Pandas' nullable values are represented using its JSON encoder.
                stream.write(pd.Series(row).to_json(force_ascii=False) + '\n')
    pd.DataFrame(audits).to_csv(OUT / 'source_archive_audit.csv', index=False)
    print('Source extraction passed. Run --stage summarize in a separate process.', flush=True)


def summarize():
    inventory = OUT / 'source-inventory'
    audits = pd.read_csv(OUT / 'source_archive_audit.csv').to_dict('records')
    variables, datasets, summary = [], {}, []
    skill_path = ROOT / '.codex/skills/data-preprocessing/scripts/prepare_variable_list.py'
    spec = importlib.util.spec_from_file_location('variable_discovery', skill_path)
    discovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(discovery)
    for input_path in sorted(inventory.glob('*.jsonl.gz')):
        if input_path.name == 'bus_candidates.jsonl.gz':
            # This later geometry-stage input uses a temporary row index. The
            # authoritative original bus attributes remain in the separate
            # source/candidate inventories, not this shapefile inventory.
            continue
        category = input_path.name.removesuffix('.jsonl.gz')
        frame = pd.read_json(input_path, lines=True, compression='gzip', convert_dates=False, dtype=False)
        assert not frame.duplicated(['source_archive', 'source_member', 'source_feature_id']).any()
        path = inventory / (category + '.parquet')
        frame.to_parquet(path, index=False)
        relative = str(path.relative_to(ROOT))
        rows = []
        for name in frame:
            series = frame[name]
            row = dict(source_dataset=relative, original_name=name, dtype=str(series.dtype),
                       non_null_count=int(series.notna().sum()), null_pct=round(float(series.isna().mean() * 100), 4),
                       sample_values=', '.join(str(v)[:60] for v in series.dropna().head(3)),
                       feasibility_status='unknown', readable_name='', full_name='', is_final_variable='')
            rows.append(row)
        variables.extend(rows)
        datasets[relative] = rows
        summary.append(dict(category=category, records=len(frame), columns=len(frame.columns)))
    discovery.write_variable_list(OUT, variables)
    discovery.write_readme(OUT, datasets, [])
    with (OUT / 'README.md').open('a') as stream:
        stream.write('\n## Confirmed temporal assumption\n\n'
                     'MILI-D-20261010-016 attaches each constructed facility snapshot unchanged '
                     'to 2002, 2003, 2004, 2010 and 2024. Actual source editions remain explicit; '
                     'repeated values are assumption-based static context. See temporal_contract.json '
                     'and AnaSOP Section 4. Facility identity rules, airport eligibility and final '
                     'readable analytical columns remain pending construction confirmation. '
                     'This inventory does not write an augmented panel or refit a regression.\n\n'
                     'The separate bus-stop and terminal-candidate inventories retain original '
                     'attributes in data/exp/data-augmentation-screening/bus-terminal-candidates/. '
                     'The ten layers listed here are the four classified POI inventories, '
                     'two railway layers and four airport layers. Survey-content and railway-line '
                     'layers are reference inventories, not additional facility counts.\n')
    report = dict(status='passed', decision_id='MILI-D-20261010-016', archives=len({a['source_archive'] for a in audits}),
                  source_archives_unchanged=True, scientific_variables_constructed=False,
                  full_inventory_not_sampled=True, categories=summary,
                  missing_crs_layers=[a for a in audits if not a['crs_present']])
    (OUT / 'source_inventory_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'missing_crs_layers'}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['extract', 'summarize'], required=True)
    args = parser.parse_args()
    if args.stage == 'extract':
        extract()
    else:
        summarize()
