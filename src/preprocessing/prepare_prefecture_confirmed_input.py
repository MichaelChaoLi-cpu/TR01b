#!/usr/bin/env python3
"""Validate prefecture allocation and stage typed input separately from GDAL.

Prefecture is the same largest-land-overlap concept, applied directly to the
forty-seven administrative units rather than constrained to the earlier Region.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'data/exp/data-preprocessing/prefecture'
NAMES = ['Hokkaido', 'Aomori', 'Iwate', 'Miyagi', 'Akita', 'Yamagata', 'Fukushima',
         'Ibaraki', 'Tochigi', 'Gunma', 'Saitama', 'Chiba', 'Tokyo', 'Kanagawa',
         'Niigata', 'Toyama', 'Ishikawa', 'Fukui', 'Yamanashi', 'Nagano', 'Gifu',
         'Shizuoka', 'Aichi', 'Mie', 'Shiga', 'Kyoto', 'Osaka', 'Hyogo', 'Nara',
         'Wakayama', 'Tottori', 'Shimane', 'Okayama', 'Hiroshima', 'Yamaguchi',
         'Tokushima', 'Kagawa', 'Ehime', 'Kochi', 'Fukuoka', 'Saga', 'Nagasaki',
         'Kumamoto', 'Oita', 'Miyazaki', 'Kagoshima', 'Okinawa']
PREFECTURE_NAMES = {f'{i:02d}': name for i, name in enumerate(NAMES, 1)}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = OUT / 'mesh_prefecture_confirmed_input.csv'
    geometry = json.loads((OUT / 'geometry_validation.json').read_text())
    assert geometry['status'] == 'passed' and not geometry['unassigned_meshes']
    frame = pd.read_csv(source, dtype={'mesh_code':'string', 'prefecture_code':'string', 'assignment_status':'string'})
    overlap = pd.read_csv(OUT / 'mesh_prefecture_overlaps.csv', dtype={'mesh_code':'string', 'prefecture_code':'string'})
    assert len(frame) == 134830 and frame.mesh_code.is_unique and frame.notna().all().all()
    assert frame.mesh_code.str.fullmatch(r'[0-9]{8}').all()
    assert frame.prefecture_code.str.fullmatch(r'[0-9]{2}').all()
    assert frame.assignment_status.eq('assigned').all()
    assert not overlap.duplicated(['mesh_code','prefecture_code']).any() and overlap.land_overlap_m2.gt(0).all()
    indexed = frame.set_index('mesh_code')
    winner = overlap.sort_values(['mesh_code','land_overlap_m2'], ascending=[True,False]).drop_duplicates('mesh_code').set_index('mesh_code')
    assert winner.prefecture_code.reindex(indexed.index).equals(indexed.prefecture_code)
    totals = overlap.groupby('mesh_code').land_overlap_m2.sum().reindex(indexed.index)
    assert np.allclose(totals/1e6, indexed.total_land_overlap, rtol=1e-12, atol=1e-12)
    assert np.allclose(winner.land_overlap_m2.reindex(indexed.index)/1e6, indexed.prefecture_land_area, rtol=1e-12, atol=1e-12)
    assert np.allclose(indexed.prefecture_land_area/indexed.total_land_overlap, indexed.prefecture_land_share, rtol=1e-12, atol=1e-12)
    assert overlap.groupby('mesh_code').size().gt(1).reindex(indexed.index).equals(indexed.cross_prefecture_mesh)
    assert frame.prefecture_code.value_counts().to_dict() == geometry['prefecture_mesh_counts']
    assert set(frame.prefecture_code) == set(PREFECTURE_NAMES)
    frame['prefecture'] = frame.prefecture_code.map(PREFECTURE_NAMES).astype('string')
    regional_geometry = json.loads((ROOT / 'data/exp/data-preprocessing/regional/geometry_validation.json').read_text())
    region_lookup = {f'{pref:02d}':region for region,prefs in regional_geometry['regions'].items() for pref in prefs}
    prior = pd.read_parquet(ROOT / 'data/processed/national/mesh_region_national_preprocessed.parquet')
    prior_region = prior.set_index('Mesh Code').Region
    frame['region_from_prefecture'] = frame.prefecture_code.map(region_lookup).astype('string')
    frame['prior_region'] = frame.mesh_code.map(prior_region).astype('string')
    frame['region_assignment_differs'] = frame.region_from_prefecture.ne(frame.prior_region)
    assert not frame.prior_region.isna().any()
    mismatches = frame.loc[frame.region_assignment_differs]
    assert set(mismatches.mesh_code).issubset(set(prior.loc[prior['Cross Region Mesh'],'Mesh Code']))
    mismatches.to_csv(OUT / 'prefecture_region_boundary_differences.csv', index=False)
    # Grouped prefecture intersections independently reproduce the regional ledger.
    grouped = overlap.assign(region=overlap.prefecture_code.map(region_lookup)).groupby(['mesh_code','region']).land_overlap_m2.sum()
    previous = pd.read_csv(ROOT / 'data/exp/data-preprocessing/regional/mesh_region_overlaps.csv', dtype={'mesh_code':'string','region':'string'}).set_index(['mesh_code','region']).land_overlap_m2
    assert set(grouped.index) == set(previous.index)
    area_difference = abs(grouped.reindex(previous.index)-previous)
    assert (area_difference <= np.maximum(.1, previous.abs()*1e-6)).all()
    staged = OUT / 'mesh_prefecture_confirmed_input.parquet'
    frame.to_parquet(staged,index=False)
    pd.DataFrame([{'Prefecture Code':code,'Prefecture':PREFECTURE_NAMES[code],'Meshes':count,'Observations':count*4} for code,count in geometry['prefecture_mesh_counts'].items()]).to_csv(OUT / 'prefecture_sample_counts.csv',index=False)
    result = dict(status='passed', decision_id='MILI-D-20261009-020', unique_meshes=len(frame),
                  prefecture_codes_preserved_as_text=True, maximum_area_assignment_verified=True,
                  exhaustive_national_partition_verified=True, cross_prefecture_meshes=int(frame.cross_prefecture_mesh.sum()),
                  prior_region_assignment_differences=len(mismatches),
                  grouped_prefecture_to_region_area_max_difference_m2=float(area_difference.max()),
                  prefecture_names=PREFECTURE_NAMES, prefecture_mesh_counts=geometry['prefecture_mesh_counts'],
                  source_sha256=sha(source), staged_sha256=sha(staged), substantive_panel_modified=False)
    (OUT / 'classification_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__ == '__main__':
    main()
