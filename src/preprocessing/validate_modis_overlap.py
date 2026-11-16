"""Independent OGR polygon intersections and denser meridian verification.

Run separately from Arrow writers because this host's GDAL/Arrow registries conflict.
"""
from pathlib import Path
import json
import numpy as np
from osgeo import ogr

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/modis-land-cover'
RADIUS = 6371007.181
CELL = 2 * np.pi * RADIUS / 36 / 2400
ogr.UseExceptions()


def polygon(points):
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for x, y in points:
        ring.AddPoint_2D(float(x), float(y))
    ring.AddPoint_2D(float(points[0][0]), float(points[0][1]))
    geometry = ogr.Geometry(ogr.wkbPolygon); geometry.AddGeometry(ring)
    return geometry


def main():
    coordinates = np.load(OUT / 'mesh_coordinates.npz')
    lon, lat = coordinates['lon'], coordinates['lat']
    selected = sorted(set(np.random.default_rng(20261010).choice(len(lon), 32, replace=False).tolist() +
                          [int(lon.argmin()), int(lon.argmax()), int(lat.argmin()), int(lat.argmax())]))
    stored = {}
    for path in sorted((OUT / 'overlap-weights').glob('*.npz')):
        start, end = map(int, path.stem.split('-'))
        targets = [i for i in selected if start <= i < end]
        if not targets:
            continue
        w = np.load(path)
        for mesh in targets:
            use = w['mesh'] == mesh
            stored[mesh] = {(int(c), int(r)): float(v)
                            for c, r, v in zip(w['column'][use], w['row'][use], w['weight'][use])}
    records = []
    for mesh in selected:
        # Decode the source mesh independently; do not use the weight generator's polygons.
        code = str(coordinates['codes'][mesh])
        south = int(code[:2]) * 2 / 3 + int(code[4]) / 12 + int(code[6]) / 120
        west = int(code[2:4]) + 100 + int(code[5]) / 8 + int(code[7]) / 80
        latitude = np.concatenate((np.linspace(south, south + 1 / 120, 65),
                                   np.linspace(south + 1 / 120, south, 65)))
        longitude = np.concatenate((np.repeat(west, 65), np.repeat(west + 1 / 80, 65)))
        c = (RADIUS * np.radians(longitude) * np.cos(np.radians(latitude)) + np.pi * RADIUS) / CELL
        r = (np.pi * RADIUS / 2 - RADIUS * np.radians(latitude)) / CELL
        origin = np.array([np.floor(c.min()), np.floor(r.min())])
        shape = polygon(np.stack((c, r), axis=1) - origin)
        area = shape.GetArea()
        errors = []; partition = 0.
        for col in range(int(np.floor(c.min())), int(np.floor(c.max())) + 1):
            for row in range(int(np.floor(r.min())), int(np.floor(r.max())) + 1):
                rectangle = polygon(np.array([[col, row], [col + 1, row], [col + 1, row + 1],
                                              [col, row + 1]]) - origin)
                fraction = shape.Intersection(rectangle).GetArea() / area
                errors.append(abs(fraction - stored[mesh].get((col, row), 0.)))
                partition += fraction
        records.append(dict(mesh_code=code, pixel_checks=len(errors),
                            maximum_pixel_share_difference=max(errors),
                            independent_partition_error=abs(partition - 1)))
    maximum = max(r['maximum_pixel_share_difference'] for r in records)
    assert maximum < 5e-6, maximum
    assert max(r['independent_partition_error'] for r in records) < 1e-9
    report = dict(status='passed', independent_engine='GDAL/OGR rectangle intersections',
                  independent_meridian_segments=64, production_meridian_segments=8,
                  selected_meshes=len(records), pixel_share_tolerance=5e-6,
                  maximum_pixel_share_difference=maximum, records=records)
    (OUT / 'independent_geometry_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Independent geometry:', len(records), 'meshes; maximum share difference', maximum, flush=True)


if __name__ == '__main__':
    main()
