"""Native MODIS sinusoidal pixel / JGD2000 standard-mesh overlap geometry.

No raster interpolation or centre-pixel assignment is used. Mesh meridians are
densified before clipping against native rectangular pixels. Area is measured in
the product's spherical equal-area sinusoidal projection, consistently in both
the numerator and denominator; it is not an ellipsoidal road-area measurement.
"""
from pathlib import Path
import argparse
import json
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/modis-land-cover'
RADIUS = 6371007.181
CELL = 2 * np.pi * RADIUS / 36 / 2400
WORLD_COLS = 86400
WORLD_ROWS = 43200


def mesh_polygon(lon, lat, segments=8):
    lon, lat = np.asarray(lon), np.asarray(lat)
    fraction = np.linspace(0, 1, segments + 1)
    # West edge south->north; east edge north->south, horizontal parallels.
    latitude = lat[:, None] - 1 / 240 + fraction[None, :] / 120
    latitude = np.concatenate((latitude, latitude[:, ::-1]), axis=1)
    longitude = np.concatenate((np.repeat((lon - 1 / 160)[:, None], segments + 1, axis=1),
                                np.repeat((lon + 1 / 160)[:, None], segments + 1, axis=1)), axis=1)
    phi = np.radians(latitude)
    col = (RADIUS * np.radians(longitude) * np.cos(phi) + np.pi * RADIUS) / CELL
    row = (np.pi * RADIUS / 2 - RADIUS * phi) / CELL
    return np.stack((col, row), axis=-1)


def polygon_area(poly, counts=None):
    n, width, _ = poly.shape
    if counts is None:
        counts = np.full(n, width)
    j = np.arange(width)[None, :]
    next_index = np.where(j + 1 < counts[:, None], j + 1, 0)
    nxt = poly[np.arange(n)[:, None], next_index]
    terms = poly[:, :, 0] * nxt[:, :, 1] - poly[:, :, 1] * nxt[:, :, 0]
    terms = np.where(j < counts[:, None], terms, 0)
    return np.abs(terms.sum(axis=1)) / 2


def clipped_area(poly):
    """Vectorized Sutherland-Hodgman clipping to [0,1] x [0,1]."""
    n, initial, _ = poly.shape
    width = initial + 4
    current = np.zeros((n, width, 2))
    current[:, :initial] = poly
    counts = np.full(n, initial, dtype=np.int16)
    row_index = np.arange(n)[:, None]
    vertex_index = np.arange(width)[None, :]
    for dimension, boundary, sign in ((0, 0., 1), (0, 1., -1), (1, 0., 1), (1, 1., -1)):
        live = vertex_index < counts[:, None]
        previous_index = np.where(vertex_index == 0, np.maximum(counts[:, None] - 1, 0),
                                  vertex_index - 1)
        previous = current[row_index, previous_index]
        inside = ((current[:, :, dimension] - boundary) * sign >= 0) & live
        previous_inside = ((previous[:, :, dimension] - boundary) * sign >= 0) & live
        crosses = (inside != previous_inside) & live
        emitted = crosses.astype(np.int16) + inside.astype(np.int16)
        starts = np.cumsum(emitted, axis=1) - emitted
        updated = np.zeros_like(current)
        denominator = current[:, :, dimension] - previous[:, :, dimension]
        fraction = np.divide(boundary - previous[:, :, dimension], denominator,
                             out=np.zeros_like(denominator), where=crosses)
        intersection = previous + fraction[:, :, None] * (current - previous)
        a, b = np.nonzero(crosses)
        updated[a, starts[a, b]] = intersection[a, b]
        a, b = np.nonzero(inside)
        updated[a, starts[a, b] + crosses[a, b]] = current[a, b]
        counts = emitted.sum(axis=1).astype(np.int16)
        assert counts.max(initial=0) <= width
        current = updated
    return polygon_area(current, counts)


def prepare():
    import pandas as pd
    from facility_geodesy import mesh_centres
    codes = pd.read_parquet(ROOT / 'data/exp/data-preprocessing/national/common_grid.parquet').mesh_code
    lon, lat = mesh_centres(codes.to_numpy())
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / 'mesh_coordinates.npz', codes=codes.to_numpy().astype('U8'), lon=lon, lat=lat)
    poly = mesh_polygon(lon, lat)
    stride = 360
    cmin = np.floor(poly[:, :, 0].min(axis=1) / stride).astype(int)
    cmax = np.floor(poly[:, :, 0].max(axis=1) / stride).astype(int)
    rmin = np.floor(poly[:, :, 1].min(axis=1) / stride).astype(int)
    rmax = np.floor(poly[:, :, 1].max(axis=1) / stride).astype(int)
    blocks = set()
    for dc in (0, 1):
        for dr in (0, 1):
            blocks.update(zip(np.minimum(cmin + dc, cmax).tolist(),
                              np.minimum(rmin + dr, rmax).tolist()))
    requests = []
    for bc, br in sorted(blocks):
        centre_col, centre_row = bc * stride + 180.5, br * stride + 180.5
        adjustment = None
        if (bc, br) == (193, 33):
            # The original buffered window touched unpublished ocean h29v04.
            # All positive study overlaps in this block lie south of row 12000.
            # Keep a 401-pixel window wholly south of that missing tile edge.
            centre_col, centre_row = 69600.5, 12200.5
            adjustment = 'Avoid unpublished h29v04; preserve all positive study overlaps in this block.'
        if (bc, br) == (213, 43):
            # h32v06 is absent from all five Collection 6.1 catalogues. Acquire
            # the adjacent published h31v06 pixels; unavailable h32v06 pixels
            # retain source-absence flags rather than an inferred water label.
            centre_col = 76599.5
            adjustment = 'Acquire published h31v06 only; h32v06 is absent from every source catalogue.'
        x = centre_col * CELL - np.pi * RADIUS
        y = np.pi * RADIUS / 2 - centre_row * CELL
        phi = y / RADIUS
        requests.append(dict(block=f'c{bc:03}r{br:03}', latitude=float(np.degrees(phi)),
                             longitude=float(np.degrees(x / (RADIUS * np.cos(phi)))),
                             block_column=bc, block_row=br, window_adjustment=adjustment))
    (OUT / 'subset_plan.json').write_text(json.dumps(dict(
        radius=RADIUS, cellsize=CELL, block_stride_pixels=stride, request_radius_km=100,
        years=[2002, 2003, 2004, 2010, 2024], bands=['LC_Type1', 'QC'], requests=requests),
        indent=2) + '\n')
    print('Prepared complete mesh coordinates and', len(requests), 'subset locations.', flush=True)


def weights(limit=None):
    coordinates = np.load(OUT / 'mesh_coordinates.npz')
    lon, lat = coordinates['lon'], coordinates['lat']
    stop = len(lon) if limit is None else min(limit, len(lon))
    folder = OUT / ('overlap-weights' if limit is None else 'overlap-pilot')
    folder.mkdir(exist_ok=True)
    audits = []
    for start in range(0, stop, 8192):
        end = min(start + 8192, stop)
        dest = folder / f'{start:07}-{end:07}.npz'
        poly = mesh_polygon(lon[start:end], lat[start:end])
        area = polygon_area(poly - poly[:, :1])
        cmin = np.floor(poly[:, :, 0].min(axis=1)).astype(np.int32)
        cmax = np.floor(poly[:, :, 0].max(axis=1)).astype(np.int32)
        rmin = np.floor(poly[:, :, 1].min(axis=1)).astype(np.int32)
        rmax = np.floor(poly[:, :, 1].max(axis=1)).astype(np.int32)
        meshes, columns, rows = [], [], []
        for dc in range(int((cmax - cmin).max()) + 1):
            for dr in range(int((rmax - rmin).max()) + 1):
                use = np.flatnonzero((cmin + dc <= cmax) & (rmin + dr <= rmax))
                meshes.append(use); columns.append(cmin[use] + dc); rows.append(rmin[use] + dr)
        local_mesh = np.concatenate(meshes)
        col, row = np.concatenate(columns), np.concatenate(rows)
        candidate = poly[local_mesh] - np.stack((col, row), axis=1)[:, None, :]
        overlap = clipped_area(candidate)
        use = overlap > 1e-12
        local_mesh, col, row, overlap = local_mesh[use], col[use], row[use], overlap[use]
        share = overlap / area[local_mesh]
        sums = np.bincount(local_mesh, weights=share, minlength=end - start)
        error = np.max(np.abs(sums - 1))
        assert error < 1e-9, error
        assert (share > 0).all() and (share <= 1 + 1e-10).all()
        assert ((col >= 0) & (col < WORLD_COLS) & (row >= 0) & (row < WORLD_ROWS)).all()
        np.savez_compressed(dest, mesh=(local_mesh + start).astype(np.int32),
                            column=col, row=row, weight=share,
                            start=np.array(start), end=np.array(end), mesh_area_km2=area * CELL**2 / 1e6)
        audits.append(dict(start=start, end=end, positive_intersections=len(share),
                           maximum_partition_error=float(error)))
        if start % (8192 * 8) == 0:
            print('Overlap weights:', end, '/', stop, flush=True)
    (folder / 'validation.json').write_text(json.dumps(dict(
        status='passed', meshes=stop, meridian_segments=8,
        area_projection='Native MODIS spherical equal-area sinusoidal',
        positive_intersections=sum(a['positive_intersections'] for a in audits),
        maximum_partition_error=max(a['maximum_partition_error'] for a in audits),
        batches=audits), indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['plan', 'weights'], required=True)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    prepare() if args.stage == 'plan' else weights(args.limit)
