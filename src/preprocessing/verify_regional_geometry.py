#!/usr/bin/env python3
"""Verify spatial allocation directly against source polygons on boundary cases.

Check one mesh for each observed cross-region combination plus one interior mesh
per region, without the construction's grid index or full-cell shortcuts.
"""
from collections import defaultdict
from pathlib import Path
import csv
import json
import zipfile
from osgeo import ogr, osr
from construct_regional_mesh_assignment import rectangle, reference, union_fragments, sha

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/regional'


def main(output_dir=OUT, unit='region', expected_strata=9, manifest_path=None):
    ogr.UseExceptions(); osr.UseExceptions(); osr.SetPROJSearchPaths(['/opt/homebrew/share/proj'])
    report = json.loads((output_dir / 'geometry_validation.json').read_text())
    stratum_column = 'region' if unit == 'region' else 'prefecture_code'
    with (output_dir / f'mesh_{unit}_confirmed_input.csv').open() as stream:
        mapping = {row['mesh_code']: row for row in csv.DictReader(stream)}
    with (output_dir / f'mesh_{unit}_overlaps.csv').open() as stream:
        overlap = defaultdict(dict)
        for row in csv.DictReader(stream):
            overlap[row['mesh_code']][row[stratum_column]] = float(row['land_overlap_m2'])
    cases = {}
    for mesh in sorted(mapping):
        regions = tuple(sorted(overlap[mesh]))
        if not regions:
            continue  # Unassigned meshes remain in the allocation audit, not this clipping check.
        key = regions if len(regions) > 1 else ('interior', regions[0])
        if key not in cases:
            cases[key] = mesh
    selected = list(cases.values())
    boxes = {}
    for mesh in selected:
        west = 100 + int(mesh[2:4]) + int(mesh[5])/8 + int(mesh[7])/80
        south = int(mesh[:2])*2/3 + int(mesh[4])/12 + int(mesh[6])/120
        boxes[mesh] = rectangle(west, south, west+1/80, south+1/120)
    fragments = defaultdict(lambda: defaultdict(list))
    prefecture_region = {f'{pref:02d}': region for region, prefs in report[unit+'s'].items() for pref in prefs}
    geo = reference(4612)
    manifest_path = manifest_path or OUT / 'reference/manifest.json'
    for record in json.loads(manifest_path.read_text()):
        path = ROOT / record['path']; assert sha(path) == record['sha256']
        with zipfile.ZipFile(path) as z:
            member = next(n for n in z.namelist() if n.endswith('.shp'))
        dataset = ogr.Open('/vsizip/' + str(path) + '/' + member)
        layer = dataset.GetLayer(); source = layer.GetSpatialRef().Clone()
        source.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(source, geo)
        region = prefecture_region[record['prefecture_code']]
        for feature in layer:
            geom = feature.GetGeometryRef().Clone(); geom.Transform(transform)
            a,b,c,d = geom.GetEnvelope()
            for mesh, box in boxes.items():
                x0,x1,y0,y1 = box.GetEnvelope()
                if b < x0 or a > x1 or d < y0 or c > y1:
                    continue
                clipped = geom.Intersection(box)
                if not clipped.IsEmpty() and clipped.GetArea() > 0:
                    fragments[mesh][region].append(clipped)
        dataset = None
    differences = []
    for mesh in selected:
        target = osr.SpatialReference(); target.ImportFromWkt(report['metric_projections'][mesh[:4]])
        target.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(geo, target)
        areas = {}
        for region, parts in fragments[mesh].items():
            union = union_fragments(parts); union.Transform(transform)
            if union.GetArea() > 1e-4:
                areas[region] = union.GetArea()
        assert set(areas) == set(overlap[mesh])
        for region in areas:
            delta = abs(areas[region] - overlap[mesh][region])
            assert delta < max(.01, areas[region] * 1e-8), (mesh, region, delta)
            differences.append(delta)
        assert max(areas, key=areas.get) == mapping[mesh][stratum_column]
    result = dict(status='passed', independently_clipped_meshes=len(selected),
                  unassigned_meshes_outside_positive_overlap_check=report['unassigned_meshes'],
                  observed_boundary_combinations_checked=sum(len(k)>1 and k[0]!='interior' for k in cases),
                  interior_strata_checked=expected_strata, maximum_area_difference_m2=max(differences),
                  method='Direct source polygon clipping, alternate mesh-coordinate reconstruction, no grid index and no full-cell containment shortcut')
    assert sum(k[0]=='interior' for k in cases)==expected_strata
    (output_dir / 'independent_geometry_validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
