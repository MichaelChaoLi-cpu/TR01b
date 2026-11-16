#!/usr/bin/env python3
"""Audit original missing road blocks; never recode or change processed data.

Run after acquire_road_coverage_reference.py. Current N03 polygons are a
diagnostic coastline/administrative-footprint reference, not historical truth.
"""
from pathlib import Path
import hashlib
import json
import math
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
from osgeo import ogr, osr

from audit_source_archives import dbf
from construct_road_pilot_trial import initialize_gdal, spatial_reference, polygon, mesh_code, WEST, SOUTH, DX, DY, SIZE

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / 'data/exp/data-preprocessing/pilot'
OUT = PILOT / 'coverage-investigation'
YEARS = [2002, 2003, 2004, 2010]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    initialize_gdal()
    processed_before = {str(p.relative_to(ROOT)): sha(p) for p in (ROOT / 'data/processed/pilot').glob('*.parquet')}
    grid = pd.read_csv(PILOT / 'common_grid_trial.csv', dtype={'mesh_code': 'string'})
    grid['second_mesh_code'] = grid.mesh_code.str[:6]
    assert len(grid) == 6400 and grid.mesh_code.is_unique
    blocks = grid.groupby('second_mesh_code').size()
    assert len(blocks) == 64 and (blocks == 100).all()
    checks = []
    histories = {}
    for year in YEARS:
        path = ROOT / f'data/raw/roads/n04_mesh/{year}/N04-{str(year)[2:]}_5030-jgd_GML.zip'
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
            dbf_name = next(n for n in archive.namelist() if n.endswith('.dbf'))
            rows, descriptors, deleted = dbf(archive.read(dbf_name))
            xml_name = next(n for n in archive.namelist() if n.endswith('.xml') and not n.startswith('KS-META'))
            tree = ET.fromstring(archive.read(xml_name))
            gml_rows = []
            tuple_sizes = []
            for element in tree.iter():
                if element.tag.endswith('}tupleList') and element.text:
                    tuples = [line.strip().split(',') for line in element.text.strip().splitlines()]
                    tuple_sizes.append(len(tuples))
                    gml_rows.extend(tuples)
            assert all(n == 100 for n in tuple_sizes)
        fields = [d[0] for d in descriptors]
        source = pd.DataFrame(rows)
        gml = pd.DataFrame(gml_rows, columns=fields)
        assert source.set_index('N04_001').sort_index().equals(gml.set_index('N04_001').sort_index())
        view = pd.read_csv(next((ROOT / 'data/exp/data-organization/source-tables').glob(f'n04_mesh_{year}_*.csv')),
                           dtype=str, keep_default_na=False)
        assert source.equals(view)
        counts = source.N04_001.str[:6].value_counts()
        assert (counts == 100).all() and source.N04_001.is_unique and deleted == 0
        assert set(source.N04_001) <= set(grid.mesh_code)
        shp_name = dbf_name[:-4] + '.shp'
        dataset = ogr.Open('/vsizip/' + str(path) + '/' + shp_name)
        assert dataset.GetLayer().GetFeatureCount() == len(source)
        actual = 'N04_055' if year == 2010 else 'N04_037'
        normalized = 'N04_056' if year == 2010 else 'N04_038'
        history = pd.DataFrame({'mesh_code': source.N04_001.astype('string'),
                                f'source_listed_{year}': True,
                                f'source_length_m_{year}': pd.to_numeric(source[actual], errors='coerce'),
                                f'source_normalized_length_{year}': pd.to_numeric(source[normalized], errors='coerce')})
        grid = grid.merge(history, on='mesh_code', how='left', validate='one_to_one')
        grid[f'source_listed_{year}'] = grid[f'source_listed_{year}'].eq(True)
        histories[year] = history
        checks.append(dict(road_year=year, raw_archive=str(path.relative_to(ROOT)), raw_sha256=sha(path),
                           dbf_rows=len(source), gml_rows=len(gml), shapefile_features=len(source),
                           listed_second_meshes=len(counts), absent_second_meshes=64-len(counts),
                           every_listed_block_has_100_records=True, every_gml_tuple_list_has_100_records=True,
                           deleted_dbf_rows=deleted, gml_dbf_view_agree=True))
    missing = grid[~grid.source_listed_2002].copy()
    assert len(missing) == 1200
    # Only auxiliary population diagnostics: no new final population variables.
    for year, field in [(2000, 'T000146001'), (2005, 'T000148001'), (2010, 'T000608001'), (2020, 'T001100001')]:
        source = pd.read_csv(next((ROOT / 'data/exp/data-organization/source-tables').glob(f'population_{year}_*.csv')),
                             dtype={'KEY_CODE': 'string'}, keep_default_na=False)
        pop = pd.DataFrame({'mesh_code': source.KEY_CODE, f'aux_population_{year}': pd.to_numeric(source[field], errors='coerce')})
        missing = missing.merge(pop, on='mesh_code', how='left', validate='one_to_one')
    recent = pd.read_csv(PILOT / '2024_road_grid_trial.csv', dtype={'mesh_code': 'string'})
    missing = missing.merge(recent[['mesh_code', 'road_length_km']], on='mesh_code', validate='one_to_one')
    missing = missing.rename(columns={'road_length_km': 'aux_ordinary_road_length_2024_km'})
    cells = {r.mesh_code: polygon(r.grid_row, r.grid_column) for r in missing.itertuples()}
    common = spatial_reference(4612)
    metric = spatial_reference(2444)
    to_metric = osr.CoordinateTransformation(common, metric)
    footprints = {}
    names = {code: set() for code in cells}
    reference_checks = []
    manifest = json.loads((OUT / 'reference/manifest.json').read_text())
    missing_by_index = {(r.grid_row, r.grid_column): r.mesh_code for r in missing.itertuples()}
    for record in manifest:
        path = ROOT / record['path']
        assert sha(path) == record['sha256']
        with zipfile.ZipFile(path) as archive:
            name = next(n for n in archive.namelist() if n.endswith('.shp'))
        dataset = ogr.Open('/vsizip/' + str(path) + '/' + name)
        layer = dataset.GetLayer()
        ref = layer.GetSpatialRef()
        assert ref.GetAuthorityCode(None) == '6668'
        ref.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
        transform = osr.CoordinateTransformation(ref, common)
        # Generous envelope contains all 12 absent blocks; geographic CRS shift
        # is smaller than the margin. Full geometries are transformed before clipping.
        layer.SetSpatialFilterRect(129.99, 33.65, 130.64, 34.01)
        scanned, repaired, intersected = 0, 0, 0
        for feature in layer:
            geometry = feature.GetGeometryRef().Clone()
            scanned += 1
            geometry.Transform(transform)
            if not geometry.IsValid():
                geometry = geometry.MakeValid()
                repaired += 1
            left, right, bottom, top = geometry.GetEnvelope()
            col_min = max(0, math.floor((left-WEST)/DX))
            col_max = min(SIZE-1, math.floor((right-WEST)/DX))
            row_min = max(0, math.floor((bottom-SOUTH)/DY))
            row_max = min(SIZE-1, math.floor((top-SOUTH)/DY))
            for row in range(row_min, row_max+1):
                for col in range(col_min, col_max+1):
                    code = missing_by_index.get((row, col))
                    if code is None:
                        continue
                    overlap = geometry.Intersection(cells[code])
                    if overlap.IsEmpty() or overlap.GetArea() == 0:
                        continue
                    footprints[code] = footprints[code].Union(overlap) if code in footprints else overlap
                    names[code].add('/'.join(str(feature.GetField(c) or '') for c in ['N03_001','N03_004','N03_005']))
                    intersected += 1
        reference_checks.append(dict(prefecture_code=record['prefecture_code'], candidate_features=scanned,
                                     invalid_geometries_repaired_for_diagnosis=repaired, positive_cell_intersections=intersected))
        print(f"Boundary reference {record['prefecture_code']}: {scanned} candidates; {intersected} intersections", flush=True)
    areas = {}
    for code, geometry in footprints.items():
        geometry.Transform(to_metric)
        areas[code] = geometry.GetArea()/1e6
    missing['aux_administrative_footprint_2024_km2'] = missing.mesh_code.map(areas).fillna(0.)
    missing['aux_land_footprint_present_2024'] = missing.aux_administrative_footprint_2024_km2 > 0
    missing['aux_administrative_names_2024'] = missing.mesh_code.map(lambda c: ';'.join(sorted(names[c])))
    missing['aux_land_fraction_2024'] = missing.aux_administrative_footprint_2024_km2 / missing.common_mesh_area_km2
    assert missing.aux_land_fraction_2024.between(0, 1+1e-6).all()
    missing['coverage_history'] = missing.apply(lambda r: ''.join('1' if r[f'source_listed_{y}'] else '0' for y in YEARS), axis=1)
    missing['diagnostic_classification'] = np.select(
        [missing.source_listed_2010, missing.aux_land_footprint_present_2024],
        ['whole block added in later source; cell may be land or sea', 'persistent omission with current administrative land footprint'],
        default='persistent omission; no current administrative land footprint')
    missing.to_csv(OUT / 'unlisted_mesh_diagnostics.csv', index=False)
    block_rows = []
    for block, group in missing.groupby('second_mesh_code'):
        block_rows.append(dict(second_mesh_code=block, meshes=len(group), coverage_history=group.coverage_history.iloc[0],
                               land_intersecting_meshes_2024=int(group.aux_land_footprint_present_2024.sum()),
                               administrative_footprint_2024_km2=float(group.aux_administrative_footprint_2024_km2.sum()),
                               any_population_meshes=int((group[[f'aux_population_{y}' for y in [2000,2005,2010,2020]]].fillna(0)>0).any(axis=1).sum()),
                               ordinary_road_meshes_2024=int((group.aux_ordinary_road_length_2024_km>0).sum())))
    pd.DataFrame(block_rows).to_csv(OUT / 'unlisted_second_mesh_blocks.csv', index=False)
    year_rows = []
    for year, population_year in [(2002,2000),(2003,2005),(2004,2005),(2010,2010)]:
        group = missing[~missing[f'source_listed_{year}']]
        year_rows.append(dict(road_year=year, absent_meshes=len(group), absent_second_meshes=len(group.second_mesh_code.unique()),
                              land_intersecting_meshes_2024=int(group.aux_land_footprint_present_2024.sum()),
                              no_land_intersection_meshes_2024=int((~group.aux_land_footprint_present_2024).sum()),
                              matched_population_year=population_year,
                              positive_matched_population_meshes=int((group[f'aux_population_{population_year}']>0).sum()),
                              positive_ordinary_road_meshes_2024=int((group.aux_ordinary_road_length_2024_km>0).sum())))
    pd.DataFrame(year_rows).to_csv(OUT / 'unlisted_mesh_summary.csv', index=False)
    pd.DataFrame(checks).to_csv(OUT / 'original_source_read_validation.csv', index=False)
    persistent = missing[~missing.source_listed_2010]
    land = missing[missing.aux_land_footprint_present_2024]
    land.to_csv(OUT / 'unlisted_land_intersecting_meshes.csv', index=False)
    preserved = all(sha(ROOT / path) == digest for path,digest in processed_before.items())
    assert preserved
    report = dict(status='passed', scope='primary mesh 5030; original unlisted rows only, not unknown rows',
                  original_source_checks=checks, current_boundary_reference_checks=reference_checks,
                  source_year_order=YEARS, earliest_absent_meshes=1200,
                  coverage_history_counts=missing.coverage_history.value_counts().to_dict(),
                  persistent_absent_meshes=len(persistent),
                  persistent_absent_with_current_land_footprint=int(persistent.aux_land_footprint_present_2024.sum()),
                  persistent_absent_with_population_in_any_checked_year=int((persistent[[f'aux_population_{y}' for y in [2000,2005,2010,2020]]].fillna(0)>0).any(axis=1).sum()),
                  persistent_absent_with_ordinary_roads_2024=int((persistent.aux_ordinary_road_length_2024_km>0).sum()),
                  year_summaries=year_rows, land_intersecting_meshes=land.mesh_code.tolist(),
                  processed_files_unchanged=preserved, processed_sha256_before_and_after=processed_before,
                  zero_recoding_performed=False, sample_selection_performed=False,
                  caveat='2024 administrative/coastline footprint is not a historical coastline or proof of zero roads; islands, source definition and coastline changes require separate interpretation')
    (OUT / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(year_summaries=year_rows, block_summaries=block_rows, processed_files_unchanged=preserved), indent=2))


if __name__ == '__main__':
    main()
