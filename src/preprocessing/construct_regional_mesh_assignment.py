#!/usr/bin/env python3
"""Assign the national baseline meshes to confirmed MLIT transportation regions.

This geometry-only process uses GDAL/GEOS and writes CSV, separately from Arrow.
The frozen 2024 administrative polygons classify meshes; they are not a land mask
for the historical variables. Every national baseline mesh is retained for audit.
"""
from collections import defaultdict
from pathlib import Path
import csv
import hashlib
import json
import math
import zipfile

import numpy as np
from osgeo import ogr, osr

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/regional'
REGIONS = {
    'Hokkaido': [1],
    'Tohoku': [2, 3, 4, 5, 6, 7],
    'Kanto': [8, 9, 10, 11, 12, 13, 14, 19],
    'Hokuriku-Shinetsu': [15, 16, 17, 20],
    'Chubu': [18, 21, 22, 23, 24],
    'Kinki': [25, 26, 27, 28, 29, 30],
    'Chugoku': [31, 32, 33, 34, 35],
    'Shikoku': [36, 37, 38, 39],
    'Kyushu': [40, 41, 42, 43, 44, 45, 46, 47],
}
REGION_PAGE = 'https://www.mlit.go.jp/k-toukei/jidousya_yougo.html'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(epsg):
    result = osr.SpatialReference()
    result.ImportFromEPSG(epsg)
    result.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return result


def rectangle(left, bottom, right, top):
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for x, y in [(left, bottom), (right, bottom), (right, top), (left, top), (left, bottom)]:
        ring.AddPoint_2D(x, y)
    result = ogr.Geometry(ogr.wkbPolygon)
    result.AddGeometry(ring)
    return result


def union_fragments(fragments):
    if len(fragments) == 1:
        return fragments[0].Clone()
    collection = ogr.Geometry(ogr.wkbGeometryCollection)
    for part in fragments:
        collection.AddGeometry(part)
    return collection.UnaryUnion()


def main(output_dir=OUT, grouping=REGIONS, decision_id='MILI-D-20261009-018',
         manifest_path=None, unit='region', grouping_source=REGION_PAGE,
         sample_path=None, expected_meshes=134830, compact_console=False):
    ogr.UseExceptions()
    osr.UseExceptions()
    osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_path = sample_path or ROOT / 'data/exp/figure-table-generation/national-fixed-effects/sample_membership.csv'
    source_hash = sha(sample_path)
    with sample_path.open() as stream:
        codes = sorted({row['Mesh Code'] for row in csv.DictReader(stream)})
    assert len(codes) == expected_meshes
    prefecture_region = {f'{pref:02d}': region for region, prefs in grouping.items() for pref in prefs}
    assert sorted(prefecture_region) == [f'{i:02d}' for i in range(1, 48)]
    by_row = defaultdict(list)
    positions = {}
    for code in codes:
        r = int(code[:2]) * 80 + int(code[4]) * 10 + int(code[6])
        c = (int(code[2:4]) + 100) * 80 + int(code[5]) * 10 + int(code[7])
        positions[(r, c)] = code
        by_row[r].append(c)
    by_row = {r: np.array(sorted(cols)) for r, cols in by_row.items()}
    rows = np.array(sorted(by_row))
    boxes = {}
    full = defaultdict(set)
    partial = defaultdict(lambda: defaultdict(list))
    manifest_path = manifest_path or OUT / 'reference/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    audits = []
    geo = reference(4612)
    for record in manifest:
        path = ROOT / record['path']
        assert sha(path) == record['sha256']
        with zipfile.ZipFile(path) as archive:
            member = next(n for n in archive.namelist() if n.endswith('.shp'))
        dataset = ogr.Open('/vsizip/' + str(path) + '/' + member)
        layer = dataset.GetLayer()
        source_ref = layer.GetSpatialRef().Clone()
        source_ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(source_ref, geo)
        code = record['prefecture_code']
        region = prefecture_region[code]
        features, candidates, intersections, repaired = 0, 0, 0, 0
        for feature in layer:
            features += 1
            geom = feature.GetGeometryRef().Clone()
            geom.Transform(transform)
            xmin, xmax, ymin, ymax = geom.GetEnvelope()
            rlo, rhi = math.floor(ymin * 120 + 1e-9), math.ceil(ymax * 120 - 1e-9)
            clo, chi = math.floor(xmin * 80 + 1e-9), math.ceil(xmax * 80 - 1e-9)
            selected_rows = rows[np.searchsorted(rows, rlo):np.searchsorted(rows, rhi)]
            if not len(selected_rows):
                continue
            if not geom.IsValid():
                geom = geom.MakeValid()
                repaired += 1
            prepared = geom.CreatePreparedGeometry()
            for r in selected_rows:
                cols = by_row[r]
                for c in cols[np.searchsorted(cols, clo):np.searchsorted(cols, chi)]:
                    mesh = positions[(r, c)]
                    if region in full[mesh]:
                        continue
                    candidates += 1
                    if mesh not in boxes:
                        boxes[mesh] = rectangle(c / 80, r / 120, (c + 1) / 80, (r + 1) / 120)
                    box = boxes[mesh]
                    if prepared.Contains(box):
                        full[mesh].add(region)
                        partial[mesh].pop(region, None)
                    elif prepared.Intersects(box):
                        intersection = geom.Intersection(box)
                        if not intersection.IsEmpty() and intersection.GetArea() > 0:
                            partial[mesh][region].append(intersection)
                            intersections += 1
        audits.append(dict(prefecture_code=code, **{'region' if unit == 'region' else 'stratum': region}, source_features=features,
                           candidate_mesh_tests=candidates, positive_partial_intersections=intersections,
                           invalid_geometries_made_valid=repaired, source_crs=source_ref.ExportToWkt()))
        print(f'Prefecture {code} ({region}): {features:,} features, {intersections:,} partial intersections', flush=True)
        dataset = None

    transforms = {}
    metric_definitions = {}
    def metric(mesh):
        tile = mesh[:4]
        if tile not in transforms:
            south = int(tile[:2]) * 2 / 3
            west = int(tile[2:]) + 100
            target = reference(4612)
            target.SetProjCS('Local mesh-tile transverse Mercator')
            target.SetTM(south + 1/3, west + .5, 1, 0, 0)
            transforms[tile] = osr.CoordinateTransformation(geo, target)
            metric_definitions[tile] = target.ExportToWkt()
        return transforms[tile]

    result = []
    overlap_rows = []
    for i, mesh in enumerate(codes):
        regions = set(full[mesh]) | set(partial[mesh])
        areas = {}
        for region in sorted(regions):
            geom = boxes[mesh].Clone() if region in full[mesh] else union_fragments(partial[mesh][region])
            geom.Transform(metric(mesh))
            area = geom.GetArea()
            if area > 1e-4:
                areas[region] = area
                overlap_rows.append({'mesh_code': mesh, 'region' if unit == 'region' else 'prefecture_code': region,
                                     'land_overlap_m2': area})
        ordered = sorted(areas, key=lambda region: (-areas[region], region))
        tied = len(ordered) > 1 and abs(areas[ordered[0]] - areas[ordered[1]]) <= 1e-6
        selected = ordered[0] if ordered and not tied else None
        result.append({'mesh_code': mesh, 'region' if unit == 'region' else 'prefecture_code': selected,
                       f'cross_{unit}_mesh': len(ordered) > 1,
                       f'{unit}_land_area': areas[selected]/1e6 if selected else None,
                       'total_land_overlap': sum(areas.values())/1e6,
                       f'{unit}_land_share': areas[selected]/sum(areas.values()) if selected else None,
                       'assignment_status': 'assigned' if selected else ('area_tie' if tied else 'no_land_overlap')})
        if (i + 1) % 25000 == 0:
            print(f'Metric-area classifications: {i+1:,}/{len(codes):,}', flush=True)

    for name, data in [(f'mesh_{unit}_confirmed_input.csv', result), (f'mesh_{unit}_overlaps.csv', overlap_rows), ('source_geometry_audit.csv', audits)]:
        with (output_dir / name).open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    stratum_column = 'region' if unit == 'region' else 'prefecture_code'
    counts = {region: sum(row[stratum_column] == region for row in result) for region in grouping}
    unassigned = [row['mesh_code'] for row in result if row[stratum_column] is None]
    report = dict(status='passed' if not unassigned else 'requires_geographic_review',
                  decision_id=decision_id,
                  administrative_boundary_date='2024-01-01',
                  mesh_reference_crs='EPSG:4612', metric_projections=metric_definitions,
                  national_baseline_meshes=len(codes),
                  unassigned_meshes=unassigned, reference_archives_unchanged=True,
                  national_sample_membership_sha256=source_hash,
                  source_sample_unchanged=sha(sample_path)==source_hash,
                  assignment_rule=f'Largest positive {unit} administrative land-intersection area, held fixed across periods; no nearest-stratum fallback')
    report[unit + 's'] = grouping
    report[f'{unit}_source'] = grouping_source
    report[f'{unit}_mesh_counts'] = counts
    report[f'cross_{unit}_meshes'] = sum(row[f'cross_{unit}_mesh'] for row in result)
    report['boundary_reference_manifest'] = str(manifest_path.relative_to(ROOT))
    assert report['source_sample_unchanged']
    (output_dir / 'geometry_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    console = {k: v for k, v in report.items() if k != 'metric_projections'
               and not (compact_console and k == 'unassigned_meshes')}
    if compact_console:
        console['unassigned_mesh_count'] = len(unassigned)
    print(json.dumps(console, indent=2), flush=True)


if __name__ == '__main__':
    main()
