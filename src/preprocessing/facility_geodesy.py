"""GRS80 geodesic proximity with a batched ECEF bounding-box index.

Uses only NumPy. Chord length is a lower bound on surface distance, so tree
pruning does not approximate the nearest facility. Independently checked against
GDAL's geodesic implementation by validate_static_facility_panel.py.
"""
import numpy as np

A = 6378137.0
F = 1 / 298.257222101
B = A * (1 - F)


def geodesic_km(lon1, lat1, lon2, lat2):
    """Vectorized Vincenty inverse, in km; fail rather than hide nonconvergence."""
    u1 = np.arctan((1 - F) * np.tan(np.deg2rad(lat1)))
    u2 = np.arctan((1 - F) * np.tan(np.deg2rad(lat2)))
    su1, cu1, su2, cu2 = np.sin(u1), np.cos(u1), np.sin(u2), np.cos(u2)
    delta = np.deg2rad(np.asarray(lon2) - np.asarray(lon1))
    lam = delta.copy()
    for _ in range(100):
        sl, cl = np.sin(lam), np.cos(lam)
        ss = np.sqrt((cu2 * sl) ** 2 + (cu1 * su2 - su1 * cu2 * cl) ** 2)
        cs = su1 * su2 + cu1 * cu2 * cl
        sig = np.arctan2(ss, cs)
        sa = np.divide(cu1 * cu2 * sl, ss, out=np.zeros_like(ss), where=ss != 0)
        ca2 = 1 - sa ** 2
        c2m = cs - np.divide(2 * su1 * su2, ca2, out=np.zeros_like(ca2), where=ca2 > 1e-15)
        c = F / 16 * ca2 * (4 + F * (4 - 3 * ca2))
        updated = delta + (1 - c) * F * sa * (sig + c * ss * (c2m + c * cs * (-1 + 2 * c2m ** 2)))
        if np.max(np.abs(updated - lam), initial=0) < 1e-12:
            break
        lam = updated
    else:
        raise ValueError('Vincenty inverse did not converge')
    uu = ca2 * (A ** 2 - B ** 2) / B ** 2
    aa = 1 + uu / 16384 * (4096 + uu * (-768 + uu * (320 - 175 * uu)))
    bb = uu / 1024 * (256 + uu * (-128 + uu * (74 - 47 * uu)))
    ds = bb * ss * (c2m + bb / 4 * (cs * (-1 + 2 * c2m ** 2)
                    - bb / 6 * c2m * (-3 + 4 * ss ** 2) * (-3 + 4 * c2m ** 2)))
    return B * aa * (sig - ds) / 1000


def ecef(lon, lat):
    lon, lat = np.deg2rad(lon), np.deg2rad(lat)
    e2 = F * (2 - F)
    n = A / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    return np.column_stack([n * np.cos(lat) * np.cos(lon), n * np.cos(lat) * np.sin(lon),
                            n * (1 - e2) * np.sin(lat)])


def nearest(lon, lat, target_lon, target_lat, chunk=65536):
    points = ecef(target_lon, target_lat)
    queries = ecef(lon, lat)
    target_lon, target_lat = np.asarray(target_lon), np.asarray(target_lat)

    def build(indices):
        subset = points[indices]
        low, high = subset.min(0), subset.max(0)
        if len(indices) <= 12:
            return (low, high, indices, None)
        axis = int(np.argmax(high - low))
        order = indices[np.argsort(subset[:, axis], kind='stable')]
        middle = len(order) // 2
        return (low, high, None, (build(order[:middle]), build(order[middle:])))

    assert len(points) and np.isfinite(points).all() and np.isfinite(queries).all()
    root = build(np.arange(len(points)))
    distances = np.full(len(queries), np.inf)
    matched = np.full(len(queries), -1, dtype=np.int64)

    def lower(node, positions):
        lo, hi = node[:2]
        delta = np.maximum(np.maximum(lo - queries[positions], queries[positions] - hi), 0)
        return np.einsum('ij,ij->i', delta, delta)

    def visit(node, positions):
        positions = positions[lower(node, positions) <= (distances[positions] * 1000 + 1e-6) ** 2]
        if not len(positions):
            return
        if node[2] is not None:
            ids = node[2]
            values = geodesic_km(np.asarray(lon)[positions, None], np.asarray(lat)[positions, None],
                                 target_lon[ids][None, :], target_lat[ids][None, :])
            minimum = values.min(1)
            picked = np.where(values == minimum[:, None], ids[None, :], len(points)).min(1)
            update = (minimum < distances[positions]) | ((minimum == distances[positions]) & (picked < matched[positions]))
            hit = positions[update]
            distances[hit], matched[hit] = minimum[update], picked[update]
        else:
            left, right = node[3]
            first = lower(left, positions) <= lower(right, positions)
            for local, child1, child2 in ((positions[first], left, right), (positions[~first], right, left)):
                if len(local):
                    visit(child1, local)
                    visit(child2, local)

    for start in range(0, len(queries), chunk):
        visit(root, np.arange(start, min(start + chunk, len(queries))))
    assert (matched >= 0).all() and np.isfinite(distances).all()
    return distances, matched


def mesh_centres(codes):
    codes = np.asarray(codes).astype('U8')
    lon, lat = [], []
    for code in codes:
        lat.append(int(code[:2]) * 2 / 3 + int(code[4]) / 12 + int(code[6]) / 120 + 1 / 240)
        lon.append(int(code[2:4]) + 100 + int(code[5]) / 8 + int(code[7]) / 80 + 1 / 160)
    return np.asarray(lon), np.asarray(lat)


def mesh_codes(lon, lat):
    # Single-ULP protection at exactly representable standard-mesh boundaries.
    r = np.floor(np.nextafter(np.asarray(lat) * 120, np.inf)).astype(np.int64)
    c = np.floor(np.nextafter((np.asarray(lon) - 100) * 80, np.inf)).astype(np.int64)
    ids = r // 80 * 1000000 + c // 80 * 10000 + r % 80 // 10 * 1000 + c % 80 // 10 * 100 + r % 10 * 10 + c % 10
    return np.array([f'{i:08d}' for i in ids])
