"""Read-only trace of Tokyo IGBP class 14 from native pixels to model inputs."""
from pathlib import Path
import hashlib
import json
import zipfile
import numpy as np
import pandas as pd
from shapely import make_valid, union_all, intersects_xy
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'data/exp/data-preprocessing/modis-land-cover'
PANEL = ROOT / 'data/processed/national/association_spatial_heterogeneity/panel_preprocessed.parquet'
OUT = ROOT / 'data/exp/modis-tokyo-mosaic-audit'
YEARS = [2002, 2003, 2004, 2010, 2024]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    manifest = json.loads((ROOT / 'data/exp/data-preprocessing/regional/reference/manifest.json').read_text())
    entry = next(r for r in manifest if r['prefecture_code'] == '13')
    boundary_path = ROOT / entry['path']
    protected = [PANEL, boundary_path, SOURCE / 'native_pixel_ids.npy', SOURCE / 'mesh_coordinates.npz']
    protected += [SOURCE / f'native_pixels_{year}.npz' for year in YEARS]
    protected += [ROOT / f'data/processed/national/modis_water_retained/modis_land_cover_{year}_preprocessed.parquet' for year in YEARS]
    hashes = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    assert hashes[entry['path']] == entry['sha256']
    panel = pd.read_parquet(PANEL, filters=[('Prefecture Code', '==', '13')],
                            columns=['Mesh Code', 'Road Year', 'Cropland Mosaic Land Cover Share',
                                     'Cropland Land Cover Share', 'Forest Land Cover Share'])
    codes = panel['Mesh Code'].unique()
    coordinates = np.load(SOURCE / 'mesh_coordinates.npz')
    selected = np.isin(coordinates['codes'], codes)
    ids = np.load(SOURCE / 'native_pixel_ids.npy')
    touched = np.zeros(len(ids), dtype=bool)
    edges = []
    for path in sorted((SOURCE / 'overlap-weights').glob('*.npz')):
        with np.load(path) as w:
            start, end = int(w['start']), int(w['end'])
            if not selected[start:end].any():
                continue
            use = selected[w['mesh']] & (w['weight'] > 0)
            native = (w['row'][use].astype(np.int64) * 86400 + w['column'][use]).astype(np.uint32)
            pos = np.searchsorted(ids, native)
            assert np.array_equal(ids[pos], native)
            touched[pos] = True
            edges.append((w['mesh'][use], pos, w['weight'][use]))
    with zipfile.ZipFile(boundary_path) as archive:
        member = next(s for s in archive.namelist() if s.endswith('.geojson') and 'subprefecture' not in s)
        features = json.loads(archive.read(member))['features']
    geometry = union_all([make_valid(shape(f['geometry'])) for f in features if f['geometry']])
    # Native pixel centers, not boundary-clipped pixel areas: a separate descriptive check.
    latitude = 90 - (ids // 86400 + .5) / 240
    longitude = ((ids % 86400 + .5) / 240 - 180) / np.cos(np.deg2rad(latitude))
    xmin, ymin, xmax, ymax = geometry.bounds
    bbox = (longitude >= xmin) & (longitude <= xmax) & (latitude >= ymin) & (latitude <= ymax)
    inside = np.zeros(len(ids), dtype=bool)
    inside[bbox] = intersects_xy(geometry, longitude[bbox], latitude[bbox])
    records = []
    for year in YEARS:
        pixels = np.load(SOURCE / f'native_pixels_{year}.npz')
        present = pixels['published_tile'] & pixels['response_pixel_present']
        lc, qc = pixels['LC_Type1'], pixels['QC']
        accepted = present & np.isin(qc, [0, 2, 3, 4, 5, 6, 7, 8, 9])
        annual = pd.read_parquet(ROOT / f'data/processed/national/modis_water_retained/modis_land_cover_{year}_preprocessed.parquet',
                                  columns=['Mesh Code', 'Cropland Mosaic Land Cover Share', 'Cropland Land Cover Share'])
        annual = annual.set_index('Mesh Code').loc[codes]
        fitted = panel[panel['Road Year'].eq(year)].set_index('Mesh Code').loc[codes]
        reconstructed = np.zeros(len(selected))
        for mesh, pos, weight in edges:
            np.add.at(reconstructed, mesh, weight * (present[pos] & (lc[pos] == 14) & accepted[pos]))
        reference = pd.Series(reconstructed[selected], index=coordinates['codes'][selected]).loc[codes]
        np.testing.assert_allclose(reference, annual['Cropland Mosaic Land Cover Share'], atol=1e-12, rtol=0)
        np.testing.assert_array_equal(annual['Cropland Mosaic Land Cover Share'], fitted['Cropland Mosaic Land Cover Share'])
        classes, counts = np.unique(lc[touched & present], return_counts=True)
        records.append({'year': year, 'model_meshes': len(codes),
                        'positive_mosaic_meshes': int((annual['Cropland Mosaic Land Cover Share'] > 0).sum()),
                        'positive_cropland_meshes': int((annual['Cropland Land Cover Share'] > 0).sum()),
                        'positive_forest_meshes': int((fitted['Forest Land Cover Share'] > 0).sum()),
                        'raw_class14_pixels_touching_model_meshes_before_qc': int((touched & present & (lc == 14)).sum()),
                        'raw_class14_pixel_centers_in_official_tokyo_boundary_before_qc': int((inside & present & (lc == 14)).sum()),
                        'raw_class12_pixel_centers_in_official_tokyo_boundary_before_qc': int((inside & present & (lc == 12)).sum()),
                        'native_classes_touching_model_meshes': dict(zip(classes.astype(str), counts.tolist())),
                        'native_overlap_reconstruction_matches_annual': True,
                        'annual_to_model_values_unchanged': True})
    assert hashes == {str(p.relative_to(ROOT)): sha(p) for p in protected}
    report = {'status': 'passed', 'scope': 'Existing 2,418 Tokyo model meshes and saved native pixels',
              'classification': 'MCD12Q1 Collection 6.1 LC_Type1 IGBP class 14',
              'boundary_center_check_limitation': 'Pixel-center counts do not measure clipped administrative land-cover area or pixels beyond the acquired mesh universe.',
              'source_files_unchanged': True, 'source_hashes': hashes, 'records': records}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    for r in records:
        print(json.dumps({k: v for k, v in r.items() if k != 'native_classes_touching_model_meshes'}), flush=True)


if __name__ == '__main__':
    main()
