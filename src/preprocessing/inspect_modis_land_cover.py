"""Inventory all source bands and reconstruct selected native pixels, without imputation."""
from pathlib import Path
import argparse
import gzip
import hashlib
import importlib.util
import json
import re
import numpy as np

from modis_mesh_overlap import CELL, RADIUS, WORLD_COLS, OUT, ROOT


def load(path):
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def pixel_ids(value):
    x, y = float(value['xllcorner']), float(value['yllcorner'])
    height, width = int(value['nrows']), int(value['ncols'])
    cf = (x + np.pi * RADIUS) / CELL
    rf = (np.pi * RADIUS / 2 - y) / CELL - height
    col, row = round(cf), round(rf)
    # TESViS serializes corner coordinates with limited precision. Snap only
    # demonstrably sub-decimetre metadata differences to the canonical grid.
    assert max(abs(cf - col), abs(rf - row)) * CELL < .1
    return ((row + np.arange(height, dtype=np.int64))[:, None] * WORLD_COLS +
            col + np.arange(width, dtype=np.int64)[None, :]).ravel().astype(np.uint32)


def inventory():
    import pandas as pd
    folder = ROOT / 'data/raw/land_cover/modis/mcd12q1_061/metadata'
    definitions = load(folder / 'bands.json.gz')['bands']
    frames = []
    for path in sorted(folder.glob('probe_*_2024_all_bands.json.gz')):
        value = load(path)
        frame = pd.DataFrame({s['band']: s['data'] for s in value['subset']})
        assert set(frame) == {d['band'] for d in definitions}
        for name in frame:
            frame[name] = frame[name].astype('uint8')
        frame['source_probe'] = str(path.relative_to(ROOT))
        frame['source_native_pixel_id'] = pixel_ids(value)
        frame['source_year'] = 2024
        frames.append(frame)
    frame = pd.concat(frames, ignore_index=True)
    path = OUT / 'source_band_inventory.parquet'
    frame.to_parquet(path, index=False)
    spec = importlib.util.spec_from_file_location('discovery',
        ROOT / '.codex/skills/data-preprocessing/scripts/prepare_variable_list.py')
    discovery = importlib.util.module_from_spec(spec); spec.loader.exec_module(discovery)
    rows = []
    for name in frame:
        series = frame[name]
        missing = (series == 255) if name in {d['band'] for d in definitions} else series.isna()
        rows.append(dict(source_dataset=str(path.relative_to(ROOT)), original_name=name,
                         dtype=str(series.dtype), non_null_count=int((~missing).sum()),
                         null_pct=100 * float(missing.mean()),
                         sample_values=', '.join(map(str, series[~missing].head(3))),
                         feasibility_status='unknown', readable_name='', full_name='', is_final_variable=''))
    discovery.write_variable_list(OUT, rows)
    discovery.write_readme(OUT, {str(path.relative_to(ROOT)): rows}, [])
    with (OUT / 'README.md').open('a') as stream:
        stream.write('\nThe complete source-band inventory uses four independent 2024 probes '
                     '(100 native pixels); null percentages denote published fill code 255 in '
                     'these probes, not national missingness. Every original band is preserved '
                     'in the raw probes. National acquisition retains LC_Type1 and QC only. '
                     'Reference identifiers are not classification variables.\n')
    print('Inventoried', len(definitions), 'original bands,', len(frame), 'probe pixels.', flush=True)


def mosaic():
    weights = sorted((OUT / 'overlap-weights').glob('*.npz'))
    identifiers = []
    for path in weights:
        w = np.load(path)
        identifiers.append((w['row'].astype(np.int64) * WORLD_COLS + w['column']).astype(np.uint32))
    identifiers = np.unique(np.concatenate(identifiers))
    np.save(OUT / 'native_pixel_ids.npy', identifiers)
    manifest = json.loads((OUT / 'download_manifest.json').read_text())
    assert manifest['finished_requests'] == manifest['planned_requests']
    assert all(r['status'] == 'downloaded' for r in manifest['records']), 'Unresolved download requests'
    catalogue = {}
    for path in (ROOT / 'data/raw/land_cover/modis/mcd12q1_061/metadata').glob('lads_catalogue_*.html.gz'):
        year = int(path.name.split('_')[2][:4])
        catalogue[year] = set(re.findall(r'MCD12Q1\.A\d{7}\.h\d{2}v\d{2}\.061\.\d+\.hdf',
                                       gzip.decompress(path.read_bytes()).decode()))
    years = [2002, 2003, 2004, 2010, 2024]
    arrays = {band: np.full((5, len(identifiers)), 256, dtype=np.uint16) for band in ['LC_Type1', 'QC']}
    duplicates, version_checks = 0, 0
    for j, record in enumerate(manifest['records']):
        path = ROOT / record['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
        value = load(path); ids = pixel_ids(value)
        positions = np.searchsorted(identifiers, ids)
        use = positions < len(identifiers)
        use[use] &= identifiers[positions[use]] == ids[use]
        positions = positions[use]
        for subset in value['subset']:
            year = int(subset['calendar_date'][:4])
            granule = f"MCD12Q1.{subset['modis_date']}.{subset['tile']}.061.{subset['proc_date']}.hdf"
            assert granule in catalogue[year], granule
            version_checks += 1
            original = np.asarray(subset['data'], dtype=np.uint16)
            assert (original <= 255).all()
            data = original[use]
            target = arrays[subset['band']][years.index(year)]
            existing = target[positions]
            shared = existing != 256
            assert np.array_equal(existing[shared], data[shared]), (record['block'], subset['band'], year)
            duplicates += int(shared.sum())
            target[positions] = data
        if j % 100 == 0:
            print('Mosaic requests:', j + 1, '/', len(manifest['records']), flush=True)
    records = []
    for i, year in enumerate(years):
        source_present = (arrays['LC_Type1'][i] != 256) & (arrays['QC'][i] != 256)
        published_tiles = {n.split('.')[2] for n in catalogue[year]}
        published_ids = [int(tile[4:]) * 36 + int(tile[1:3]) for tile in published_tiles]
        native_columns, native_rows = identifiers % WORLD_COLS, identifiers // WORLD_COLS
        native_tile = native_rows // 2400 * 36 + native_columns // 2400
        published = np.isin(native_tile, published_ids)
        assert source_present[published].all(), (
            f'Unrequested pixels in published {year} tiles: {(published & ~source_present).sum()}')
        path = OUT / f'native_pixels_{year}.npz'
        np.savez_compressed(path, LC_Type1=arrays['LC_Type1'][i], QC=arrays['QC'][i],
                            published_tile=published, response_pixel_present=source_present)
        records.append(dict(year=year, unique_pixels=len(identifiers),
                            source_pixels_present=int(source_present.sum()),
                            pixels_in_unpublished_tiles=int((~published).sum()),
                            unpublished_tiles=sorted({f'h{int(t % 36):02}v{int(t // 36):02}'
                                                      for t in np.unique(native_tile[~published])}),
                            source_class_values=np.unique(arrays['LC_Type1'][i][source_present]).tolist(),
                            source_quality_values=np.unique(arrays['QC'][i][source_present]).tolist()))
    # Independent small requests verify array orientation and exact overlap pixel identity.
    checks = 0
    for path in sorted((ROOT / 'data/raw/land_cover/modis/mcd12q1_061/metadata').glob('probe_*.json.gz')):
        value = load(path); ids = pixel_ids(value)
        positions = np.searchsorted(identifiers, ids)
        use = positions < len(identifiers)
        use[use] &= identifiers[positions[use]] == ids[use]
        for subset in value['subset']:
            if subset['band'] not in arrays:
                continue
            assert np.array_equal(np.asarray(subset['data'])[use],
                                  arrays[subset['band']][4, positions[use]])
            checks += int(use.sum())
    report = dict(status='passed', unique_native_pixels=len(identifiers),
                  internal_source_absence_sentinel=256,
                  requests=len(manifest['records']), source_version_granule_checks=version_checks,
                  overlapping_pixel_values_verified=duplicates,
                  independent_small_request_pixel_checks=checks, years=records)
    source_absence_overlap = np.zeros(972800)
    for path in weights:
        w = np.load(path)
        ids = (w['row'].astype(np.int64) * WORLD_COLS + w['column']).astype(np.uint32)
        positions = np.searchsorted(identifiers, ids)
        source_absence_overlap += np.bincount(
            w['mesh'], weights=w['weight'] * ~published[positions], minlength=len(source_absence_overlap))
    report['source_availability_mesh_count_reference_year'] = years[-1]
    report['meshes_with_unpublished_source_overlap'] = int((source_absence_overlap > 1e-9).sum())
    report['meshes_entirely_in_unpublished_source_tile'] = int((source_absence_overlap > 1 - 1e-9).sum())
    (OUT / 'source_mosaic_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['inventory', 'mosaic'], required=True)
    args = parser.parse_args()
    inventory() if args.stage == 'inventory' else mosaic()
