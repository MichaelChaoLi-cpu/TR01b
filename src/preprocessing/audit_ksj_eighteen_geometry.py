"""Inspect source geometries and product-declared CRS before mesh construction."""
import gzip
import hashlib
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/ksj-eighteen-facilities'
sys.path.insert(0, str(ROOT / 'src/exp'))
from inventory_ksj_poi_catalogue import Page


def main():
    from osgeo import gdal, ogr, osr
    ogr.UseExceptions()
    osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
    records = json.loads((ROOT / 'data/exp/data-augmentation-screening/ksj-eighteen-facilities/acquisition_manifest.json').read_text())['records']
    schemas = json.loads((OUT / 'schemas.json').read_text())
    declarations = {}
    for kind in {s['kind'] for s in schemas.values()}:
        page = Page()
        page.feed((ROOT / 'data/exp/data-augmentation-screening/ksj-poi-catalogue-20261010/source-pages' / (kind + '.html')).read_text(encoding='utf-8-sig'))
        rows = [row for row in page.rows if row and row[0] == '座標系']
        assert len(rows) == 1
        text = rows[0][1]
        assert 'JGD2011' in text or 'JGD2000' in text
        declarations[kind] = dict(declaration=text, epsg=6668 if 'JGD2011' in text else 4612,
                                  provenance='Official KSJ product page; use only when file CRS is missing; target common-grid datum is JGD2000 EPSG:4612')
    (OUT / 'official_crs_declarations.json').write_text(json.dumps(declarations, ensure_ascii=False, indent=2) + '\n')
    tourism = next(r for r in records if r['kind'] == 'tourism_resources')
    histogram, geometric_types = Counter(), Counter()
    with zipfile.ZipFile(ROOT / tourism['path']) as archive, gzip.open(OUT / 'tourism_native_geometry.jsonl.gz', 'wt', encoding='utf-8') as stream:
        members = archive.namelist()
        for member in members:
            if not member.lower().endswith('.shp'):
                continue
            cpg = member[:-4] + '.cpg'
            encoding = archive.read(cpg).decode().strip() if cpg in members else 'CP932'
            gdal.SetConfigOption('SHAPE_ENCODING', encoding)
            staged = []
            for suffix in ('.shp', '.shx', '.dbf', '.prj', '.cpg'):
                name = member[:-4] + suffix
                if name in members:
                    target = '/vsimem/ksj_tourism_audit' + suffix
                    gdal.FileFromMemBuffer(target, archive.read(name))
                    staged.append(target)
            dataset = ogr.Open('/vsimem/ksj_tourism_audit.shp')
            layer = dataset.GetLayer(0)
            for feature in layer:
                geometry = feature.GetGeometryRef()
                name = geometry.GetGeometryName()
                geometric_types[name] += 1
                n = geometry.GetGeometryCount() if name == 'MULTIPOINT' else (1 if name == 'POINT' else 0)
                if name == 'MULTIPOINT':
                    histogram[n] += 1
                native_points = ([geometry.GetPoint(0)[:2]] if name == 'POINT' else
                                 [geometry.GetGeometryRef(i).GetPoint(0)[:2] for i in range(n)]
                                 if name == 'MULTIPOINT' else [])
                stream.write(json.dumps(dict(source_archive=tourism['path'], source_member=member,
                                             source_feature_id=feature.GetFID(), source_geometry_type=name,
                                             source_geometry_wkt=geometry.ExportToWkt(), native_point_count=n,
                                             native_point_coordinates=native_points), ensure_ascii=False) + '\n')
            layer = None
            dataset = None
            for target in staged:
                gdal.Unlink(target)
    validation = dict(status='passed', official_crs_declarations=len(declarations), tourism_source_geometry_counts=dict(geometric_types),
                      tourism_multipoint_child_counts=dict(histogram), no_native_geometry_conversion=True,
                      no_analytical_variables_constructed=True)
    (OUT / 'geometry_source_audit.json').write_text(json.dumps(validation, indent=2) + '\n')
    print(json.dumps(validation, indent=2))


if __name__ == '__main__':
    main()
